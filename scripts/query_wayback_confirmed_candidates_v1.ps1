param(
    [Parameter(Mandatory = $true)]
    [string]$QueuePath,

    [Parameter(Mandatory = $true)]
    [string[]]$CandidateId,

    [Parameter(Mandatory = $true)]
    [string]$ReportPath,

    [int]$TimeoutSec = 30
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

$queue = @(
    Get-Content -LiteralPath $QueuePath |
        Where-Object { $_.Trim() } |
        ForEach-Object { $_ | ConvertFrom-Json }
)
$byId = @{}
foreach ($candidate in $queue) {
    $byId[$candidate.candidate_id] = $candidate
}

$archiveIp = Resolve-DnsName -Name archive.org -Type A -DnsOnly -ErrorAction Stop |
    Where-Object Type -eq 'A' |
    Select-Object -First 1 -ExpandProperty IPAddress
if (-not $archiveIp) {
    throw 'archive.org did not resolve to an IPv4 address'
}

$results = @()
$networkRequestCount = 0
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
    $candidateHost = ([string]$candidate.candidate_host).ToLowerInvariant().TrimEnd('.')
    $validationDate = [string]$candidate.official_reference.evidence_dates.validation_date
    $targetTimestamp = if ($validationDate -match '^\d{4}-\d{2}-\d{2}$') {
        $validationDate.Replace('-', '')
    } else {
        '20260924'
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
        $snapshotYear = if ($snapshotTimestamp -match '^\d{4}') { [int]$snapshotTimestamp.Substring(0, 4) } else { $null }
        $results += [pscustomobject]@{
            candidate_id = $id
            candidate_host = $candidateHost
            validation_date = $validationDate
            query_timestamp = $targetTimestamp
            available = $available
            snapshot_timestamp = $snapshotTimestamp
            snapshot_year = $snapshotYear
            snapshot_url = if ($available) { ([string]$closest.url -replace '^http://', 'https://') } else { $null }
            recent_enough_for_follow_up = $available -and $snapshotYear -ge 2024
            error = $null
        }
    }
    catch {
        $results += [pscustomobject]@{
            candidate_id = $id
            candidate_host = $candidateHost
            validation_date = $validationDate
            query_timestamp = $targetTimestamp
            available = $false
            snapshot_timestamp = $null
            snapshot_year = $null
            snapshot_url = $null
            recent_enough_for_follow_up = $false
            error = $_.Exception.Message
        }
    }
}

$report = [ordered]@{
    report_id = 'WAYBACK_CONFIRMED_CANDIDATE_AVAILABILITY_V1'
    created_at = [DateTimeOffset]::Now.ToString('o')
    queue_path = $QueuePath
    requested_candidate_count = $CandidateId.Count
    network_request_count = $networkRequestCount
    available_snapshot_count = @($results | Where-Object available -eq $true).Count
    recent_follow_up_count = @($results | Where-Object recent_enough_for_follow_up -eq $true).Count
    results = $results
    safety_contract = [ordered]@{
        candidate_domain_access_operations = 0
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
