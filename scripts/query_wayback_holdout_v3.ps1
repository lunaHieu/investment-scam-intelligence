param(
    [Parameter(Mandatory = $true)]
    [string]$QueuePath,

    [Parameter(Mandatory = $true)]
    [string]$ReportPath,

    [int]$TimeoutSec = 30,

    [int]$ExpectedPerBranch = 100,

    [ValidateRange(1, 4)]
    [int]$ThrottleLimit = 2
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $QueuePath -PathType Leaf)) {
    throw "Missing queue: $QueuePath"
}
if (Test-Path -LiteralPath $ReportPath) {
    throw "Refusing to overwrite report: $ReportPath"
}

$selected = @(
    Get-Content -LiteralPath $QueuePath |
        Where-Object { $_.Trim() } |
        ForEach-Object { $_ | ConvertFrom-Json } |
        Where-Object { $_.archive_acquisition_state -eq 'NEEDS_ARCHIVE_QUERY' }
)
$branchCounts = @{}
foreach ($branch in @('CONFIRMED_CANDIDATE', 'LEGITIMATE_CANDIDATE')) {
    $branchCounts[$branch] = @($selected | Where-Object reference_branch -eq $branch).Count
    if ($branchCounts[$branch] -ne $ExpectedPerBranch) {
        throw "Expected $ExpectedPerBranch $branch candidates, found $($branchCounts[$branch])"
    }
}
if (@($selected.candidate_host | Sort-Object -Unique).Count -ne $selected.Count) {
    throw 'Queue contains duplicate candidate hosts'
}
if (@($selected | Where-Object { $_.label_created -ne $false -or $_.training_eligible -ne 'NO' }).Count -ne 0) {
    throw 'Queue contains a label or training-eligible candidate'
}

$results = @(
    $selected | ForEach-Object -ThrottleLimit $ThrottleLimit -Parallel {
        $candidate = $_
        $candidateHost = ([string]$candidate.candidate_host).ToLowerInvariant().TrimEnd('.')
        $targetTimestamp = [string]$candidate.target_timestamp
        if ($targetTimestamp -notmatch '^\d{8}$') {
            throw "Invalid target timestamp: $($candidate.candidate_id)"
        }
        $encodedHost = [uri]::EscapeDataString($candidateHost)
        $requestUrl = "https://archive.org/wayback/available?url=$encodedHost&timestamp=$targetTimestamp"
        try {
            $httpResponse = Invoke-WebRequest `
                -Uri $requestUrl `
                -Headers @{'User-Agent' = 'ISI-Research/1.0 (academic benchmark acquisition)'} `
                -TimeoutSec $using:TimeoutSec `
                -MaximumRedirection 0
            if ([int]$httpResponse.StatusCode -ne 200) {
                throw "Unexpected HTTP status: $($httpResponse.StatusCode)"
            }
            $response = $httpResponse.Content | ConvertFrom-Json
            $closest = $response.archived_snapshots.closest
            $available = $null -ne $closest -and $closest.available -eq $true -and [string]$closest.status -eq '200'
            [pscustomobject]@{
                candidate_id = [string]$candidate.candidate_id
                candidate_host = $candidateHost
                source_case_id = [string]$candidate.source_case_id
                reference_branch = [string]$candidate.reference_branch
                query_timestamp = $targetTimestamp
                available = $available
                snapshot_timestamp = if ($available) { [string]$closest.timestamp } else { $null }
                snapshot_url = if ($available) { ([string]$closest.url -replace '^http://', 'https://') } else { $null }
                error = $null
            }
        }
        catch {
            [pscustomobject]@{
                candidate_id = [string]$candidate.candidate_id
                candidate_host = $candidateHost
                source_case_id = [string]$candidate.source_case_id
                reference_branch = [string]$candidate.reference_branch
                query_timestamp = $targetTimestamp
                available = $false
                snapshot_timestamp = $null
                snapshot_url = $null
                error = $_.Exception.Message
            }
        }
    }
)
$results = @($results | Sort-Object candidate_id)
$availabilityByBranch = [ordered]@{}
foreach ($branch in @('CONFIRMED_CANDIDATE', 'LEGITIMATE_CANDIDATE')) {
    $availabilityByBranch[$branch] = @(
        $results | Where-Object { $_.reference_branch -eq $branch -and $_.available -eq $true }
    ).Count
}
$unresolved = @($results | Where-Object { $_.error }).Count
$report = [ordered]@{
    report_id = 'WAYBACK_HOLDOUT_AVAILABILITY_V3'
    created_at = [DateTimeOffset]::Now.ToString('o')
    queue_path = (Resolve-Path -LiteralPath $QueuePath).Path
    queue_sha256 = (Get-FileHash -LiteralPath $QueuePath -Algorithm SHA256).Hash.ToLowerInvariant()
    requested_candidate_count = $selected.Count
    requested_by_reference_branch = $branchCounts
    network_request_count = $results.Count
    available_snapshot_count = @($results | Where-Object available -eq $true).Count
    available_by_reference_branch = $availabilityByBranch
    unresolved_error_count = $unresolved
    acquisition_ready = ($unresolved -eq 0)
    results = $results
    safety_contract = [ordered]@{
        candidate_live_domain_access_operations = 0
        only_archive_availability_api_accessed = $true
        archived_page_download_operations = 0
        labels_created = 0
        model_scoring_operations = 0
        training_allowed = $false
        errors_are_not_interpreted_as_no_snapshot = $true
        https_certificate_validation_enabled = $true
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
