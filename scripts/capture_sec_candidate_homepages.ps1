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

    [int]$TimeoutSec = 20
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $QueuePath -PathType Leaf)) {
    throw "Missing queue: $QueuePath"
}
if (Test-Path -LiteralPath $ReportPath) {
    throw "Refusing to overwrite report: $ReportPath"
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

$targetDirectory = Join-Path $RawRoot "external_text_captures\$CaptureDate\legitimate"
New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
$resolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$resolvedTargetDirectory = (Resolve-Path -LiteralPath $targetDirectory).Path
if (-not $resolvedTargetDirectory.StartsWith($resolvedRawRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Capture target escaped raw root: $resolvedTargetDirectory"
}

$results = @()
$networkRequestCount = 0
foreach ($id in $CandidateId) {
    if (-not $byId.ContainsKey($id)) {
        throw "Unknown candidate ID: $id"
    }
    $candidate = $byId[$id]
    if ($candidate.target_outcome -ne 'LEGITIMATE_CANDIDATE' -or $candidate.source_id -ne 'sec_iapd') {
        throw "Candidate is not an SEC/IAPD legitimate candidate: $id"
    }
    $hostName = ([string]$candidate.candidate_host).ToLowerInvariant().TrimEnd('.')
    $requestedUrl = "https://$hostName/"
    $targetPath = Join-Path $targetDirectory "$id`__$hostName.html"
    if (Test-Path -LiteralPath $targetPath) {
        $results += [pscustomobject]@{
            candidate_id = $id
            candidate_host = $hostName
            requested_url = $requestedUrl
            outcome = 'SKIPPED_EXISTING'
            error = $null
            path = $targetPath
            bytes = (Get-Item -LiteralPath $targetPath).Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetPath).Hash.ToLowerInvariant()
        }
        continue
    }

    $temporaryPath = Join-Path ([System.IO.Path]::GetTempPath()) ("isi_capture_" + [guid]::NewGuid().ToString('N') + '.html')
    try {
        $networkRequestCount += 1
        $response = Invoke-WebRequest `
            -Uri $requestedUrl `
            -Headers @{'User-Agent' = 'ISI-Research/1.0'} `
            -UseBasicParsing `
            -TimeoutSec $TimeoutSec `
            -MaximumRedirection 5 `
            -OutFile $temporaryPath `
            -PassThru
        $finalUrl = $response.BaseResponse.RequestMessage.RequestUri.AbsoluteUri
        $finalHost = $response.BaseResponse.RequestMessage.RequestUri.Host.ToLowerInvariant().TrimEnd('.')
        $allowedHosts = @($hostName, "www.$hostName")
        if ($finalHost -notin $allowedHosts) {
            throw "Unexpected redirect host: $finalHost"
        }
        $contentType = $response.Headers.ContentType.ToString()
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
            candidate_host = $hostName
            requested_url = $requestedUrl
            final_url = $finalUrl
            http_status = [int]$response.StatusCode
            content_type = $contentType
            outcome = 'CAPTURED'
            error = $null
            path = $targetPath
            bytes = $length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetPath).Hash.ToLowerInvariant()
        }
    }
    catch {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
        $results += [pscustomobject]@{
            candidate_id = $id
            candidate_host = $hostName
            requested_url = $requestedUrl
            outcome = 'FAILED'
            error = $_.Exception.Message
            path = $null
            bytes = $null
            sha256 = $null
        }
    }
}

$report = [ordered]@{
    report_id = 'SEC_REGISTERED_HOMEPAGE_CAPTURE_RUN_V1'
    created_at = [DateTimeOffset]::Now.ToString('o')
    queue_path = $QueuePath
    raw_root = $resolvedRawRoot
    capture_date = $CaptureDate
    requested_candidate_count = $CandidateId.Count
    network_request_count = $networkRequestCount
    captured_count = @($results | Where-Object outcome -eq 'CAPTURED').Count
    failed_count = @($results | Where-Object outcome -eq 'FAILED').Count
    skipped_existing_count = @($results | Where-Object outcome -eq 'SKIPPED_EXISTING').Count
    results = $results
    safety_contract = [ordered]@{
        live_suspicious_domain_access_operations = 0
        only_sec_iapd_candidate_hosts_allowed = $true
        cross_host_redirect_allowed = $false
        labels_created = 0
        model_scoring_operations = 0
        training_allowed = $false
    }
}
$reportParent = Split-Path -Parent $ReportPath
New-Item -ItemType Directory -Path $reportParent -Force | Out-Null
[System.IO.File]::WriteAllText(
    $ReportPath,
    (($report | ConvertTo-Json -Depth 8) + [Environment]::NewLine),
    [System.Text.UTF8Encoding]::new($false)
)
$report | ConvertTo-Json -Depth 8
