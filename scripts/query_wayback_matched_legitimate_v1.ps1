param(
    [Parameter(Mandatory = $true)]
    [string]$QueuePath,

    [Parameter(Mandatory = $true)]
    [string]$ReportPath,

    [int]$TimeoutSec = 30,

    [int]$ExpectedCandidateCount = 11
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $QueuePath -PathType Leaf)) {
    throw "Missing queue: $QueuePath"
}
if (Test-Path -LiteralPath $ReportPath) {
    throw "Refusing to overwrite report: $ReportPath"
}
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    throw 'curl.exe is required for the Wayback availability API'
}

$selected = @(
    Get-Content -LiteralPath $QueuePath |
        Where-Object { $_.Trim() } |
        ForEach-Object { $_ | ConvertFrom-Json } |
        Where-Object { $_.archive_acquisition_state -eq 'NEEDS_ARCHIVE_QUERY' }
)
if ($selected.Count -ne $ExpectedCandidateCount) {
    throw "Expected $ExpectedCandidateCount archive-query candidates, found $($selected.Count)"
}

$archiveIp = Resolve-DnsName -Name archive.org -Type A -DnsOnly -ErrorAction Stop |
    Where-Object Type -eq 'A' |
    Select-Object -First 1 -ExpandProperty IPAddress
if (-not $archiveIp) {
    throw 'archive.org did not resolve to an IPv4 address'
}

$results = @()
$networkRequestCount = 0
foreach ($candidate in $selected) {
    $candidateHost = ([string]$candidate.candidate_host).ToLowerInvariant().TrimEnd('.')
    $targetTimestamp = [string]$candidate.target_timestamp
    if ($targetTimestamp -notmatch '^\d{8}$') {
        throw "Invalid target timestamp: $($candidate.candidate_id)"
    }
    $encodedHost = [uri]::EscapeDataString($candidateHost)
    $requestUrl = "https://archive.org/wayback/available?url=$encodedHost&timestamp=$targetTimestamp"
    try {
        $networkRequestCount += 1
        $responseText = & curl.exe `
            --silent `
            --show-error `
            --connect-timeout $TimeoutSec `
            --max-time $TimeoutSec `
            --proto '=https' `
            --resolve "archive.org`:443:$archiveIp" `
            $requestUrl
        if ($LASTEXITCODE -ne 0) {
            throw "curl exit $LASTEXITCODE"
        }
        $response = (($responseText -join [Environment]::NewLine) | ConvertFrom-Json)
        $closest = $response.archived_snapshots.closest
        $available = $null -ne $closest -and $closest.available -eq $true -and [string]$closest.status -eq '200'
        $snapshotTimestamp = if ($available) { [string]$closest.timestamp } else { $null }
        $results += [pscustomobject]@{
            candidate_id = [string]$candidate.candidate_id
            candidate_host = $candidateHost
            source_case_id = [string]$candidate.source_case_id
            query_timestamp = $targetTimestamp
            available = $available
            snapshot_timestamp = $snapshotTimestamp
            snapshot_url = if ($available) { ([string]$closest.url -replace '^http://', 'https://') } else { $null }
            error = $null
        }
    }
    catch {
        $results += [pscustomobject]@{
            candidate_id = [string]$candidate.candidate_id
            candidate_host = $candidateHost
            source_case_id = [string]$candidate.source_case_id
            query_timestamp = $targetTimestamp
            available = $false
            snapshot_timestamp = $null
            snapshot_url = $null
            error = $_.Exception.Message
        }
    }
}

$report = [ordered]@{
    report_id = 'WAYBACK_MATCHED_LEGITIMATE_AVAILABILITY_V1'
    created_at = [DateTimeOffset]::Now.ToString('o')
    queue_path = (Resolve-Path -LiteralPath $QueuePath).Path
    queue_sha256 = (Get-FileHash -LiteralPath $QueuePath -Algorithm SHA256).Hash.ToLowerInvariant()
    requested_candidate_count = $selected.Count
    network_request_count = $networkRequestCount
    available_snapshot_count = @($results | Where-Object available -eq $true).Count
    results = $results
    safety_contract = [ordered]@{
        candidate_live_domain_access_operations = 0
        only_archive_availability_api_accessed = $true
        archived_page_download_operations = 0
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
