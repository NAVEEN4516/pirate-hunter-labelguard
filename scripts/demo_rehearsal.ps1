param([string]$BaseUrl = 'http://localhost:8000')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$outputFolder = Join-Path $projectRoot 'output/demo'
New-Item -ItemType Directory -Path $outputFolder -Force | Out-Null
$records = @()
Invoke-RestMethod "$BaseUrl/ready" | ConvertTo-Json -Depth 5 | Write-Host

foreach ($item in @(
    @{ Name = 'valid-protein'; Route = 'clear-for-print' },
    @{ Name = 'insufficient-protein'; Route = 'revise-and-recheck' },
    @{ Name = 'out-of-scope'; Route = 'regulatory-review' },
    @{ Name = 'small-pack'; Route = 'regulatory-review' }
)) {
    $payload = Get-Content (Join-Path $projectRoot "examples/$($item.Name).json") -Raw | ConvertFrom-Json
    # A unique batch forces fresh agent work rather than a warmed-cache answer.
    $payload.declarations.batch_number += '-DEMO-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
    $accepted = Invoke-RestMethod "$BaseUrl/v1/runs" -Method Post -ContentType 'application/json' -Body ($payload | ConvertTo-Json -Depth 30)
    $deadline = (Get-Date).AddSeconds(65)
    do {
        Start-Sleep -Milliseconds 300
        $run = Invoke-RestMethod "$BaseUrl/v1/runs/$($accepted.run_id)"
        if ((Get-Date) -gt $deadline) { throw "Run timed out: $($accepted.run_id)" }
    } while ($run.status -notin @('completed', 'failed'))
    if ($run.status -ne 'completed' -or $run.result.route -ne $item.Route -or
        $run.result.print_authorized -ne $false -or $run.result.verified -ne $true) {
        throw "Unexpected result for $($item.Name): $($run | ConvertTo-Json -Depth 8)"
    }
    $trace = Invoke-RestMethod "$BaseUrl/v1/runs/$($accepted.run_id)/trace"
    $trace | ConvertTo-Json -Depth 50 | Set-Content (Join-Path $outputFolder "$($item.Name)-trace.json") -Encoding utf8
    $records += [pscustomobject]@{ example = $item.Name; run_id = $run.run_id; route = $run.result.route; latency_s = $run.latency_s; verified = $run.result.verified; print_authorized = $run.result.print_authorized }
    Write-Host "$($item.Name): $($run.result.route), run $($run.run_id)"
}
foreach ($name in @('malformed', 'prompt-injection')) {
    $payload = Get-Content (Join-Path $projectRoot "examples/$name.json") -Raw
    $before = (Invoke-RestMethod "$BaseUrl/v1/dashboard").counts | ConvertTo-Json -Compress
    $rejection = $null
    try {
        Invoke-RestMethod "$BaseUrl/v1/runs" -Method Post -ContentType 'application/json' -Body $payload | Out-Null
        throw "Expected HTTP 422 for $name"
    } catch {
        if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 422) { throw }
        $rejection = $_.ErrorDetails.Message | ConvertFrom-Json
        if ($rejection.agent_started -ne $false -or -not $rejection.quarantine_id) { throw 'Missing safe rejection evidence' }
    }
    $after = (Invoke-RestMethod "$BaseUrl/v1/dashboard").counts | ConvertTo-Json -Compress
    if ($before -ne $after) { throw "Rejected $name changed run counts" }
    $records += [pscustomobject]@{ example = $name; http_status = 422; agent_started = $rejection.agent_started; quarantine_id = $rejection.quarantine_id; run_counts_unchanged = $true }
    Write-Host "$name`: HTTP 422, quarantine recorded, no agent started"
}
$report = [pscustomobject]@{ checked_at = (Get-Date).ToUniversalTime().ToString('o'); base_url = $BaseUrl; cases_passed = $records.Count; records = $records }
$report | ConvertTo-Json -Depth 20 | Set-Content (Join-Path $outputFolder 'rehearsal.json') -Encoding utf8
Write-Host 'All six demo cases passed. Evidence saved in output/demo/.'
