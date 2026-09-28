param(
    [Parameter(Mandatory = $true)]
    [string]$AvailabilityReport,

    [Parameter(Mandatory = $true)]
    [string]$RawRoot,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$CaptureDate,

    [Parameter(Mandatory = $true)]
    [string]$ReportPath,

    [int]$TimeoutSec = 30
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $AvailabilityReport -PathType Leaf)) {
    throw "Missing availability report: $AvailabilityReport"
}
if (Test-Path -LiteralPath $ReportPath) {
    throw "Refusing to overwrite report: $ReportPath"
}
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    throw 'curl.exe is required for archived-page capture'
}

$availability = Get-Content -LiteralPath $AvailabilityReport -Raw | ConvertFrom-Json
$selected = @($availability.results | Where-Object recent_enough_for_follow_up -eq $true)
if ($selected.Count -lt 1) {
    throw 'No recent Wayback snapshots were selected for follow-up'
}

$targetDirectory = Join-Path $RawRoot "external_text_captures\$CaptureDate\confirmed_wayback"
New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
$resolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$resolvedTargetDirectory = (Resolve-Path -LiteralPath $targetDirectory).Path
if (-not $resolvedTargetDirectory.StartsWith($resolvedRawRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Capture target escaped raw root: $resolvedTargetDirectory"
}

$archiveIp = Resolve-DnsName -Name web.archive.org -Type A -DnsOnly -ErrorAction Stop |
    Where-Object Type -eq 'A' |
    Select-Object -First 1 -ExpandProperty IPAddress
if (-not $archiveIp) {
    throw 'web.archive.org did not resolve to an IPv4 address'
}

$results = @()
$networkRequestCount = 0
foreach ($item in $selected) {
    $candidateId = [string]$item.candidate_id
    $candidateHost = ([string]$item.candidate_host).ToLowerInvariant().TrimEnd('.')
    $snapshotUrl = [string]$item.snapshot_url
    if ($snapshotUrl -notmatch '^https://web\.archive\.org/web/(\d{14})/(.+)$') {
        throw "Unexpected snapshot URL: $snapshotUrl"
    }
    $timestamp = $Matches[1]
    $originalUrl = $Matches[2]
    $rawReplayUrl = "https://web.archive.org/web/$($timestamp)id_/$originalUrl"
    $targetPath = Join-Path $targetDirectory "$candidateId`__$candidateHost.html"
    if (Test-Path -LiteralPath $targetPath) {
        $results += [pscustomobject]@{
            candidate_id = $candidateId
            candidate_host = $candidateHost
            snapshot_timestamp = $timestamp
            requested_archive_url = $rawReplayUrl
            outcome = 'SKIPPED_EXISTING'
            error_class = $null
            error = $null
            path = $targetPath
            bytes = (Get-Item -LiteralPath $targetPath).Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetPath).Hash.ToLowerInvariant()
        }
        continue
    }

    $temporaryPath = Join-Path ([System.IO.Path]::GetTempPath()) ("isi_wayback_" + [guid]::NewGuid().ToString('N') + '.html')
    $curlErrorPath = Join-Path ([System.IO.Path]::GetTempPath()) ("isi_wayback_" + [guid]::NewGuid().ToString('N') + '.stderr.txt')
    try {
        $currentUrl = $rawReplayUrl
        $redirectCount = 0
        while ($true) {
            $currentUri = [uri]$currentUrl
            if (
                $currentUri.Scheme -ne 'https' -or
                $currentUri.Host.ToLowerInvariant().TrimEnd('.') -ne 'web.archive.org'
            ) {
                throw "Archive redirect guard rejected URL: $currentUrl"
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
                '--resolve', "web.archive.org`:443:$archiveIp",
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
                    throw 'Maximum archive redirect count exceeded'
                }
                $redirectUrl = [string]$metadata.redirect_url
                if (-not $redirectUrl) {
                    throw "HTTP $statusCode without a usable redirect URL"
                }
                $redirectUri = [uri]$redirectUrl
                if (
                    $redirectUri.Scheme -ne 'https' -or
                    $redirectUri.Host.ToLowerInvariant().TrimEnd('.') -ne 'web.archive.org'
                ) {
                    throw "Archive redirect guard rejected URL: $redirectUrl"
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
                throw "Archived HTML capture is unexpectedly small: $length bytes"
            }
            Move-Item -LiteralPath $temporaryPath -Destination $targetPath
            $results += [pscustomobject]@{
                candidate_id = $candidateId
                candidate_host = $candidateHost
                snapshot_timestamp = $timestamp
                requested_archive_url = $rawReplayUrl
                final_archive_url = $currentUrl
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
        $errorClass = if ($message -match 'timed out|Timeout|curl exit 28') {
            'NETWORK_TIMEOUT'
        } elseif ($message -match 'redirect guard') {
            'ARCHIVE_REDIRECT_GUARD_REJECTION'
        } elseif ($message -match 'HTTP status') {
            'HTTP_STATUS_REJECTION'
        } else {
            'NETWORK_OR_ARTIFACT_FAILURE'
        }
        $results += [pscustomobject]@{
            candidate_id = $candidateId
            candidate_host = $candidateHost
            snapshot_timestamp = $timestamp
            requested_archive_url = $rawReplayUrl
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
    report_id = 'WAYBACK_CONFIRMED_CANDIDATE_CAPTURE_V1'
    created_at = [DateTimeOffset]::Now.ToString('o')
    availability_report = $AvailabilityReport
    raw_root = $resolvedRawRoot
    capture_date = $CaptureDate
    requested_snapshot_count = $selected.Count
    network_request_count = $networkRequestCount
    captured_count = @($results | Where-Object outcome -eq 'CAPTURED').Count
    failed_count = @($results | Where-Object outcome -eq 'FAILED').Count
    skipped_existing_count = @($results | Where-Object outcome -eq 'SKIPPED_EXISTING').Count
    results = $results
    safety_contract = [ordered]@{
        candidate_domain_access_operations = 0
        only_web_archive_host_accessed = $true
        raw_replay_modifier_used = $true
        automatic_external_redirect_following = $false
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
