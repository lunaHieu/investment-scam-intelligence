param(
    [Parameter(Mandatory = $true)]
    [string]$InputReport,

    [Parameter(Mandatory = $true)]
    [string]$OutputReport,

    [ValidateRange(1, 300)]
    [int]$DelaySec = 5,

    [ValidateRange(5, 120)]
    [int]$TimeoutSec = 30,

    [ValidateRange(1, 5)]
    [int]$MaxAttemptsPerCandidate = 2
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $InputReport -PathType Leaf)) {
    throw "Missing input report: $InputReport"
}
if (Test-Path -LiteralPath $OutputReport) {
    throw "Refusing to overwrite report: $OutputReport"
}
$input = Get-Content -LiteralPath $InputReport -Raw | ConvertFrom-Json
if ($input.report_id -notmatch '^WAYBACK_LANGUAGE_EXPANSION_AVAILABILITY_V2') {
    throw "Unexpected input report id: $($input.report_id)"
}
$results = @($input.results)
if ($results.Count -ne [int]$input.requested_candidate_count) {
    throw 'Input report result coverage is incomplete'
}
$retryTargets = @($results | Where-Object { $_.error })
$retryRequestCount = 0

foreach ($target in $retryTargets) {
    $finalError = [string]$target.error
    for ($attempt = 1; $attempt -le $MaxAttemptsPerCandidate; $attempt += 1) {
        Start-Sleep -Seconds $DelaySec
        $candidateHost = ([string]$target.candidate_host).ToLowerInvariant().TrimEnd('.')
        $targetTimestamp = [string]$target.query_timestamp
        $requestUrl = "https://archive.org/wayback/available?url=$([uri]::EscapeDataString($candidateHost))&timestamp=$targetTimestamp"
        try {
            $retryRequestCount += 1
            $httpResponse = Invoke-WebRequest `
                -Uri $requestUrl `
                -Headers @{'User-Agent' = 'ISI-Research/1.0 (academic benchmark acquisition)'} `
                -TimeoutSec $TimeoutSec `
                -MaximumRedirection 0
            if ([int]$httpResponse.StatusCode -ne 200) {
                throw "Unexpected HTTP status: $($httpResponse.StatusCode)"
            }
            $response = $httpResponse.Content | ConvertFrom-Json
            $closest = $response.archived_snapshots.closest
            $available = $null -ne $closest -and $closest.available -eq $true -and [string]$closest.status -eq '200'
            $target.available = $available
            $target.snapshot_timestamp = if ($available) { [string]$closest.timestamp } else { $null }
            $target.snapshot_url = if ($available) { ([string]$closest.url -replace '^http://', 'https://') } else { $null }
            $target.error = $null
            $finalError = $null
            break
        }
        catch {
            $finalError = $_.Exception.Message
        }
    }
    if ($finalError) {
        $target.available = $false
        $target.snapshot_timestamp = $null
        $target.snapshot_url = $null
        $target.error = $finalError
    }
}

$availabilityByBranch = [ordered]@{}
foreach ($branch in @('CONFIRMED_CANDIDATE', 'LEGITIMATE_CANDIDATE')) {
    $availabilityByBranch[$branch] = @($results | Where-Object { $_.reference_branch -eq $branch -and $_.available -eq $true }).Count
}
$unresolved = @($results | Where-Object { $_.error }).Count
$report = [ordered]@{
    report_id = 'WAYBACK_LANGUAGE_EXPANSION_AVAILABILITY_V2_RETRY'
    created_at = [DateTimeOffset]::Now.ToString('o')
    parent_report = (Resolve-Path -LiteralPath $InputReport).Path
    parent_report_sha256 = (Get-FileHash -LiteralPath $InputReport -Algorithm SHA256).Hash.ToLowerInvariant()
    queue_path = [string]$input.queue_path
    queue_sha256 = [string]$input.queue_sha256
    requested_candidate_count = [int]$input.requested_candidate_count
    requested_by_reference_branch = $input.requested_by_reference_branch
    original_network_request_count = [int]$input.network_request_count
    retry_target_count = $retryTargets.Count
    retry_request_count = $retryRequestCount
    available_snapshot_count = @($results | Where-Object available -eq $true).Count
    available_by_reference_branch = $availabilityByBranch
    unresolved_error_count = $unresolved
    acquisition_ready = ($unresolved -eq 0)
    results = @($results | Sort-Object candidate_id)
    safety_contract = [ordered]@{
        candidate_live_domain_access_operations = 0
        only_archive_availability_api_accessed = $true
        archived_page_download_operations = 0
        labels_created = 0
        model_scoring_operations = 0
        training_allowed = $false
        errors_are_not_interpreted_as_no_snapshot = $true
    }
}
$reportParent = Split-Path -Parent $OutputReport
New-Item -ItemType Directory -Path $reportParent -Force | Out-Null
[System.IO.File]::WriteAllText(
    $OutputReport,
    (($report | ConvertTo-Json -Depth 10) + [Environment]::NewLine),
    [System.Text.UTF8Encoding]::new($false)
)
$report | ConvertTo-Json -Depth 10
