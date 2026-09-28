param(
    [Parameter(Mandatory = $true)]
    [string]$QueuePath,

    [Parameter(Mandatory = $true)]
    [string]$RawRoot,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$CaptureDate,

    [Parameter(Mandatory = $true)]
    [string[]]$CandidateId,

    [Parameter(Mandatory = $true)]
    [string]$ReportPath,

    [int]$TimeoutSec = 25
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $QueuePath -PathType Leaf)) {
    throw "Missing queue: $QueuePath"
}
if (Test-Path -LiteralPath $ReportPath) {
    throw "Refusing to overwrite report: $ReportPath"
}
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    throw 'curl.exe is required for resolver-pinned capture'
}

$queue = @(
    Get-Content -LiteralPath $QueuePath |
        Where-Object { $_.Trim() } |
        ForEach-Object { $_ | ConvertFrom-Json }
)
$byId = @{}
foreach ($candidate in $queue) {
    $byId[$candidate.candidate_id] = $candidate
}

$targetDirectory = Join-Path $RawRoot "external_warning_evidence\$CaptureDate\official_notices"
New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
$resolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$resolvedTargetDirectory = (Resolve-Path -LiteralPath $targetDirectory).Path
if (-not $resolvedTargetDirectory.StartsWith($resolvedRawRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Capture target escaped raw root: $resolvedTargetDirectory"
}

$results = @()
$networkRequestCount = 0
$dnsResolutionCount = 0
foreach ($id in $CandidateId) {
    if (-not $byId.ContainsKey($id)) {
        throw "Unknown candidate ID: $id"
    }
    $candidate = $byId[$id]
    if (
        $candidate.target_outcome -notin @('CONFIRMED_CANDIDATE', 'CONFIRMED_RESERVE_CANDIDATE') -or
        $candidate.source_id -ne 'iosco_i_scan'
    ) {
        throw "Candidate is not an IOSCO confirmed-branch candidate: $id"
    }

    $requestedUrl = [string]$candidate.official_reference.url
    $requestedUri = [uri]$requestedUrl
    if ($requestedUri.Scheme -ne 'https') {
        throw "Official warning URL is not HTTPS: $requestedUrl"
    }
    $requestedHost = $requestedUri.Host.ToLowerInvariant().TrimEnd('.')
    $baseHost = if ($requestedHost.StartsWith('www.')) { $requestedHost.Substring(4) } else { $requestedHost }
    $allowedHosts = @($baseHost, "www.$baseHost")
    $targetPath = Join-Path $targetDirectory "$id`__$baseHost.html"
    if (Test-Path -LiteralPath $targetPath) {
        $results += [pscustomobject]@{
            candidate_id = $id
            regulator_host = $requestedHost
            requested_url = $requestedUrl
            outcome = 'SKIPPED_EXISTING'
            error_class = $null
            error = $null
            path = $targetPath
            bytes = (Get-Item -LiteralPath $targetPath).Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetPath).Hash.ToLowerInvariant()
        }
        continue
    }

    $temporaryPath = Join-Path ([System.IO.Path]::GetTempPath()) ("isi_notice_" + [guid]::NewGuid().ToString('N') + '.html')
    $curlErrorPath = Join-Path ([System.IO.Path]::GetTempPath()) ("isi_notice_" + [guid]::NewGuid().ToString('N') + '.stderr.txt')
    try {
        $currentUrl = $requestedUrl
        $redirectCount = 0
        $resolvedAddresses = @{}
        while ($true) {
            $currentUri = [uri]$currentUrl
            $currentHost = $currentUri.Host.ToLowerInvariant().TrimEnd('.')
            if ($currentUri.Scheme -ne 'https' -or $currentHost -notin $allowedHosts) {
                throw "Redirect guard rejected URL: $currentUrl"
            }
            if (-not $resolvedAddresses.ContainsKey($currentHost)) {
                $dnsResolutionCount += 1
                $addresses = @(
                    Resolve-DnsName -Name $currentHost -Type A -DnsOnly -ErrorAction Stop |
                        Where-Object Type -eq 'A' |
                        Select-Object -ExpandProperty IPAddress
                )
                if ($addresses.Count -lt 1) {
                    throw "No IPv4 address resolved for $currentHost"
                }
                $resolvedAddresses[$currentHost] = [string]$addresses[0]
            }

            $networkRequestCount += 1
            $curlArguments = @(
                '--silent',
                '--show-error',
                '--request', 'GET',
                '--output', $temporaryPath,
                '--connect-timeout', [string]$TimeoutSec,
                '--max-time', [string]$TimeoutSec,
                '--proto', '=https',
                '--resolve', "$currentHost`:443:$($resolvedAddresses[$currentHost])",
                '--header', 'User-Agent: ISI-Research/1.0',
                '--write-out', '%{json}',
                $currentUrl
            )
            $metadataText = & curl.exe @curlArguments 2> $curlErrorPath
            $curlExitCode = $LASTEXITCODE
            if ($curlExitCode -ne 0) {
                $curlError = if (Test-Path -LiteralPath $curlErrorPath) {
                    (Get-Content -LiteralPath $curlErrorPath -Raw).Trim()
                } else {
                    'no curl diagnostic'
                }
                throw "curl exit $curlExitCode`: $curlError"
            }
            $metadata = (($metadataText -join [Environment]::NewLine) | ConvertFrom-Json)
            $statusCode = [int]$metadata.http_code
            if ($statusCode -ge 300 -and $statusCode -lt 400) {
                if ($redirectCount -ge 5) {
                    throw 'Maximum redirect count exceeded'
                }
                $redirectUrl = [string]$metadata.redirect_url
                if (-not $redirectUrl) {
                    throw "HTTP $statusCode without a usable redirect URL"
                }
                $redirectUri = [uri]$redirectUrl
                $redirectHost = $redirectUri.Host.ToLowerInvariant().TrimEnd('.')
                if ($redirectUri.Scheme -ne 'https' -or $redirectHost -notin $allowedHosts) {
                    throw "Redirect guard rejected URL: $redirectUrl"
                }
                $redirectCount += 1
                $currentUrl = $redirectUri.AbsoluteUri
                continue
            }
            if ($statusCode -ne 200) {
                throw "Unexpected HTTP status: $statusCode"
            }
            $contentType = [string]$metadata.content_type
            if (-not $contentType.StartsWith('text/html', [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Unexpected content type: $contentType"
            }
            $length = (Get-Item -LiteralPath $temporaryPath).Length
            if ($length -lt 1024) {
                throw "HTML capture is unexpectedly small: $length bytes"
            }
            Move-Item -LiteralPath $temporaryPath -Destination $targetPath
            $results += [pscustomobject]@{
                candidate_id = $id
                candidate_host = [string]$candidate.candidate_host
                regulator_host = $requestedHost
                requested_url = $requestedUrl
                final_url = $currentUrl
                redirect_count = $redirectCount
                http_status = $statusCode
                content_type = $contentType
                outcome = 'CAPTURED'
                error_class = $null
                error = $null
                path = $targetPath
                bytes = $length
                sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetPath).Hash.ToLowerInvariant()
            }
            break
        }
    }
    catch {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
        $message = $_.Exception.Message
        $errorClass = if ($message -match 'Resolve-DnsName|No IPv4|No such host|Could not resolve') {
            'DNS_RESOLUTION_FAILURE'
        } elseif ($message -match 'timed out|Timeout|curl exit 28') {
            'NETWORK_TIMEOUT'
        } elseif ($message -match 'Redirect guard') {
            'REDIRECT_GUARD_REJECTION'
        } elseif ($message -match 'HTTP status') {
            'HTTP_STATUS_REJECTION'
        } else {
            'NETWORK_OR_ARTIFACT_FAILURE'
        }
        $results += [pscustomobject]@{
            candidate_id = $id
            candidate_host = [string]$candidate.candidate_host
            regulator_host = $requestedHost
            requested_url = $requestedUrl
            outcome = 'FAILED'
            error_class = $errorClass
            error = $message
            path = $null
            bytes = $null
            sha256 = $null
        }
    }
    finally {
        if (Test-Path -LiteralPath $curlErrorPath -PathType Leaf) {
            Remove-Item -LiteralPath $curlErrorPath -Force
        }
    }
}

$report = [ordered]@{
    report_id = 'OFFICIAL_WARNING_PAGE_CAPTURE_RUN_V1'
    created_at = [DateTimeOffset]::Now.ToString('o')
    method = 'Resolve-DnsName A record plus curl --resolve; manual same-regulator-host HTTPS redirect loop'
    queue_path = $QueuePath
    raw_root = $resolvedRawRoot
    capture_date = $CaptureDate
    requested_candidate_count = $CandidateId.Count
    dns_resolution_count = $dnsResolutionCount
    network_request_count = $networkRequestCount
    captured_count = @($results | Where-Object outcome -eq 'CAPTURED').Count
    failed_count = @($results | Where-Object outcome -eq 'FAILED').Count
    skipped_existing_count = @($results | Where-Object outcome -eq 'SKIPPED_EXISTING').Count
    results = $results
    safety_contract = [ordered]@{
        candidate_domain_access_operations = 0
        only_official_warning_urls_allowed = $true
        warning_page_as_model_input_allowed = $false
        https_only = $true
        automatic_cross_host_redirect_following = $false
        labels_created = 0
        model_scoring_operations = 0
        training_allowed = $false
    }
}
$reportParent = Split-Path -Parent $ReportPath
New-Item -ItemType Directory -Path $reportParent -Force | Out-Null
[System.IO.File]::WriteAllText(
    $ReportPath,
    (($report | ConvertTo-Json -Depth 10) + [Environment]::NewLine),
    [System.Text.UTF8Encoding]::new($false)
)
$report | ConvertTo-Json -Depth 10
