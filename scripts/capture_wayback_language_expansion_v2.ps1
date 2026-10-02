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

    [ValidateRange(5, 120)]
    [int]$TimeoutSec = 30,

    [ValidateRange(1, 60)]
    [int]$MinimumAvailablePerBranch = 18,

    [string]$TargetSubdirectory = 'matched_wayback_language_v2'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $AvailabilityReport -PathType Leaf)) {
    throw "Missing availability report: $AvailabilityReport"
}
if (Test-Path -LiteralPath $ReportPath) {
    throw "Refusing to overwrite report: $ReportPath"
}
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    throw 'curl.exe is required for byte-preserving archived-page capture'
}
$availability = Get-Content -LiteralPath $AvailabilityReport -Raw | ConvertFrom-Json
$unresolvedErrors = @($availability.results | Where-Object { $_.error }).Count
if ($unresolvedErrors -ne 0) {
    throw "Availability report has $unresolvedErrors unresolved errors; retry before capture"
}
$selected = @($availability.results | Where-Object available -eq $true)
foreach ($branch in @('CONFIRMED_CANDIDATE', 'LEGITIMATE_CANDIDATE')) {
    $count = @($selected | Where-Object reference_branch -eq $branch).Count
    if ($count -lt $MinimumAvailablePerBranch) {
        throw "At least $MinimumAvailablePerBranch available $branch snapshots are required, found $count"
    }
}

$targetDirectory = Join-Path $RawRoot "external_text_captures\$CaptureDate\$TargetSubdirectory"
New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
$resolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$resolvedTargetDirectory = (Resolve-Path -LiteralPath $targetDirectory).Path
if (-not $resolvedTargetDirectory.StartsWith($resolvedRawRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Capture target escaped raw root: $resolvedTargetDirectory"
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
    $safeCandidateId = $candidateId -replace '[^A-Za-z0-9_.-]', '_'
    $targetPath = Join-Path $targetDirectory "$safeCandidateId`__$candidateHost.html"
    if (Test-Path -LiteralPath $targetPath) {
        throw "Refusing to reuse an unregistered existing target: $targetPath"
    }

    $temporaryPath = Join-Path ([System.IO.Path]::GetTempPath()) ("isi_wayback_v2_" + [guid]::NewGuid().ToString('N') + '.html')
    $curlErrorPath = Join-Path ([System.IO.Path]::GetTempPath()) ("isi_wayback_v2_" + [guid]::NewGuid().ToString('N') + '.stderr.txt')
    try {
        $currentUrl = $rawReplayUrl
        $redirectCount = 0
        while ($true) {
            $currentUri = [uri]$currentUrl
            if ($currentUri.Scheme -ne 'https' -or $currentUri.Host.ToLowerInvariant().TrimEnd('.') -ne 'web.archive.org') {
                throw "Archive redirect guard rejected URL: $currentUrl"
            }
            $networkRequestCount += 1
            $metadataText = & curl.exe `
                --silent `
                --show-error `
                --request GET `
                --output $temporaryPath `
                --connect-timeout $TimeoutSec `
                --max-time $TimeoutSec `
                --proto '=https' `
                --header 'User-Agent: ISI-Research/1.0 (academic benchmark acquisition)' `
                --write-out '%{json}' `
                $currentUrl 2> $curlErrorPath
            if ($LASTEXITCODE -ne 0) {
                $curlError = if (Test-Path -LiteralPath $curlErrorPath) { (Get-Content -LiteralPath $curlErrorPath -Raw).Trim() } else { 'no curl diagnostic' }
                throw "curl exit $LASTEXITCODE`: $curlError"
            }
            $metadata = (($metadataText -join [Environment]::NewLine) | ConvertFrom-Json)
            $statusCode = [int]$metadata.http_code
            if ($statusCode -ge 300 -and $statusCode -lt 400) {
                if ($redirectCount -ge 5) { throw 'Maximum archive redirect count exceeded' }
                $redirectUrl = [string]$metadata.redirect_url
                if (-not $redirectUrl) { throw "HTTP $statusCode without a usable redirect URL" }
                $redirectUri = [uri]$redirectUrl
                if ($redirectUri.Scheme -ne 'https' -or $redirectUri.Host.ToLowerInvariant().TrimEnd('.') -ne 'web.archive.org') {
                    throw "Archive redirect guard rejected URL: $redirectUrl"
                }
                $redirectCount += 1
                $currentUrl = $redirectUri.AbsoluteUri
                continue
            }
            if ($statusCode -ne 200) { throw "Unexpected HTTP status: $statusCode" }
            $contentType = [string]$metadata.content_type
            if (-not $contentType.StartsWith('text/html', [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Unexpected content type: $contentType"
            }
            $length = (Get-Item -LiteralPath $temporaryPath).Length
            if ($length -lt 1024) { throw "Archived HTML capture is unexpectedly small: $length bytes" }
            Move-Item -LiteralPath $temporaryPath -Destination $targetPath
            $results += [pscustomobject]@{
                candidate_id = $candidateId
                candidate_host = $candidateHost
                source_case_id = [string]$item.source_case_id
                reference_branch = [string]$item.reference_branch
                snapshot_timestamp = $timestamp
                requested_archive_url = $rawReplayUrl
                final_archive_url = $currentUrl
                redirect_count = $redirectCount
                http_status = $statusCode
                content_type = $contentType
                outcome = 'CAPTURED'
                error = $null
                path = $targetPath
                bytes = $length
                sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetPath).Hash.ToLowerInvariant()
            }
            break
        }
    }
    catch {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) { Remove-Item -LiteralPath $temporaryPath -Force }
        $results += [pscustomobject]@{
            candidate_id = $candidateId
            candidate_host = $candidateHost
            source_case_id = [string]$item.source_case_id
            reference_branch = [string]$item.reference_branch
            snapshot_timestamp = $timestamp
            requested_archive_url = $rawReplayUrl
            final_archive_url = $null
            redirect_count = $null
            http_status = $null
            content_type = $null
            outcome = 'FAILED'
            error = $_.Exception.Message
            path = $null
            bytes = $null
            sha256 = $null
        }
    }
    finally {
        if (Test-Path -LiteralPath $curlErrorPath -PathType Leaf) { Remove-Item -LiteralPath $curlErrorPath -Force }
    }
}

$capturedByBranch = [ordered]@{}
foreach ($branch in @('CONFIRMED_CANDIDATE', 'LEGITIMATE_CANDIDATE')) {
    $capturedByBranch[$branch] = @($results | Where-Object { $_.reference_branch -eq $branch -and $_.outcome -eq 'CAPTURED' }).Count
}
$report = [ordered]@{
    report_id = 'WAYBACK_LANGUAGE_EXPANSION_CAPTURE_V2'
    created_at = [DateTimeOffset]::Now.ToString('o')
    availability_report = (Resolve-Path -LiteralPath $AvailabilityReport).Path
    availability_report_sha256 = (Get-FileHash -LiteralPath $AvailabilityReport -Algorithm SHA256).Hash.ToLowerInvariant()
    raw_root = $resolvedRawRoot
    capture_date = $CaptureDate
    requested_snapshot_count = $selected.Count
    network_request_count = $networkRequestCount
    captured_count = @($results | Where-Object outcome -eq 'CAPTURED').Count
    captured_by_reference_branch = $capturedByBranch
    failed_count = @($results | Where-Object outcome -eq 'FAILED').Count
    results = $results
    safety_contract = [ordered]@{
        candidate_live_domain_access_operations = 0
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
