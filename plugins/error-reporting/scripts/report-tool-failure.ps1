# PostToolUseFailure hook. Runs on the Windows host under PowerShell. Classifies every
# tool failure, counts it for the session, and nudges the model in proportion:
#
#   eplus  : a tool on an EPLUS MCP server failed (rfi-knowledge-hub, punch-knowledge-hub,
#            plangrid, any mcp__plugin_eplus-* server). Full file-it nudge every time.
#   egress : the payload carries the network-allowlist signature (any tool). Full egress
#            procedure the first time in the session, a one-line reminder after that.
#   other  : bash exits, Read/Write errors, browser tool misuse, failed spawns. These
#            are mostly the model's own exploratory misses (field result 2026-09-22:
#            three of four nudges in one session, none worth a report). One short
#            counted line for the first five per session, then silence. Still counted.
#
# The count lives in CLAUDE_PLUGIN_DATA\<session_id>\failures.json (TEMP fallback) and
# every failure appends one line to <transcript dir>\<session_id>\error-reporting-failures.log,
# the folder the session exporter zips, so an export shows how often hooks fired and why.
#
# Every nudge ends with the reporter identity (DOMAIN\user@MACHINE, read via .NET) so
# requested_by is always filled in. PowerShell 5.1-compatible, ASCII only, no BOM.
#
# Self-skip: silent when the failed tool is the error-reporting server itself, decided
# on tool_name (raw text match only when the payload does not parse), so a failing
# reporter can't drive a report -> fail -> report loop.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable everything with EPLUS_NO_ERROR_NUDGE=1; disable only the egress branch with
# EPLUS_NO_EGRESS_NUDGE=1 (egress blocks are then treated as "other").

$ErrorActionPreference = 'SilentlyContinue'

$script:EplusToolPattern = '^mcp__(plugin_[A-Za-z0-9-]+_)?(rfi-knowledge-hub|punch-knowledge-hub|plangrid|eplus-[A-Za-z0-9-]+)__'
$script:OtherNudgeCap = 5

function Get-CounterPath([string] $sid) {
    $root = $env:CLAUDE_PLUGIN_DATA
    if (-not $root) { $root = Join-Path $env:TEMP 'error-reporting' }
    $dir = Join-Path $root $sid
    try { if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null } } catch { return $null }
    return (Join-Path $dir 'failures.json')
}

try {
    . (Join-Path $PSScriptRoot 'egress-common.ps1')
    $raw = Read-HookInput
    if ($env:EPLUS_NO_ERROR_NUDGE) { exit 0 }

    $selfPattern = 'error-reporting__|_error-reporting_|report_issue$|request_egress_allow$|check_egress_host$|list_egress_requests$'
    $payload = $null
    try { $payload = ConvertFrom-Json -InputObject $raw -ErrorAction Stop } catch { $payload = $null }
    $tool = ''
    if ($null -ne $payload -and $payload.PSObject.Properties['tool_name']) { $tool = [string]$payload.tool_name }
    if ($tool) {
        if ($tool -match $selfPattern) { exit 0 }
    } elseif ($raw -match 'report_issue' -or $raw -match 'error-reporting__' -or $raw -match '_error-reporting_') { exit 0 }
    if (-not $tool) { $tool = 'unknown-tool' }

    # classify
    $class = 'other'
    if ((-not $env:EPLUS_NO_EGRESS_NUDGE) -and ($raw -match $script:EgressSignature)) { $class = 'egress' }
    elseif ($tool -match $script:EplusToolPattern) { $class = 'eplus' }

    # count (per session)
    $sid = 'unknown-session'
    if ($null -ne $payload -and $payload.PSObject.Properties['session_id'] -and $payload.session_id) { $sid = [string]$payload.session_id }
    $counts = @{ total = 0; eplus = 0; egress = 0; other = 0; by_tool = @{} }
    $cpath = Get-CounterPath $sid
    if ($cpath -and (Test-Path -LiteralPath $cpath)) {
        try {
            $saved = ConvertFrom-Json -InputObject ([IO.File]::ReadAllText($cpath, $script:HookUtf8)) -ErrorAction Stop
            foreach ($k in @('total', 'eplus', 'egress', 'other')) { if ($saved.PSObject.Properties[$k]) { $counts[$k] = [int]$saved.$k } }
            if ($saved.PSObject.Properties['by_tool'] -and $saved.by_tool) { foreach ($p in $saved.by_tool.PSObject.Properties) { $counts.by_tool[$p.Name] = [int]$p.Value } }
        } catch { }
    }
    $counts.total++; $counts[$class]++
    if ($counts.by_tool.ContainsKey($tool)) { $counts.by_tool[$tool]++ } else { $counts.by_tool[$tool] = 1 }
    if ($cpath) { try { [IO.File]::WriteAllText($cpath, (ConvertTo-Json -InputObject $counts -Compress -Depth 4), $script:HookUtf8) } catch { } }

    # tally line into the exported session folder
    if ($null -ne $payload -and $payload.PSObject.Properties['transcript_path'] -and $payload.transcript_path) {
        try {
            $tdir = Split-Path -Path ([string]$payload.transcript_path) -Parent
            if ($tdir) {
                $exportDir = Join-Path $tdir $sid
                if (-not (Test-Path -LiteralPath $exportDir)) { New-Item -ItemType Directory -Path $exportDir -Force | Out-Null }
                $agent = 'main'
                if ($payload.PSObject.Properties['agent_type'] -and $payload.agent_type) { $agent = [string]$payload.agent_type }
                $line = ('{0:yyyy-MM-ddTHH:mm:ssZ} #{1} {2} tool={3} tool_count={4} agent={5}' -f [DateTime]::UtcNow, $counts.total, $class, $tool, $counts.by_tool[$tool], $agent) + "`n"
                [IO.File]::AppendAllText((Join-Path $exportDir 'error-reporting-failures.log'), $line, $script:HookUtf8)
            }
        } catch { }
    }

    # nudge, in proportion
    $n = $counts.total
    $ctx = $null
    switch ($class) {
        'eplus' {
            $ctx = '[error-reporting] Tool failure #' + $n + ' this session, on an EPLUS server tool (' + $tool + ', failure ' + $counts.by_tool[$tool] + ' for this tool). ' +
                   'Per the error-reporting skill, decide first whether it is a real failure: an expected empty or ' +
                   '"not found" result is not one and gets no report. If it is real, file it once with the report_issue tool ' +
                   '(mcp__error-reporting__report_issue, or the mcp__plugin_error-reporting_error-reporting__report_issue form): ' +
                   'category tool_failure, the real tool_name and server_name, a one-line message, and the exact error text plus ' +
                   'the failing inputs in details. Fire-and-forget: on the {status: logged} response, tell the user in one short ' +
                   'sentence that it was logged (no log_id, no tool names, no error text) and continue the task. One report per ' +
                   'distinct issue, never a secret in the body. If report_issue itself is unavailable, refused, or fails, say so ' +
                   'in one sentence and move on.' + (Get-IdentityLine)
        }
        'egress' {
            if ($counts.egress -le 1) {
                $ctx = (Get-EgressContext)
            } else {
                $ctx = '[error-reporting] Another network egress block (#' + $counts.egress + ' this session, tool ' + $tool + '). ' +
                       'Same procedure as before: name the blocked host (the redirect target if redirected), check_egress_host, ' +
                       'request_egress_allow once only if unknown, one sentence to the user, then continue without that host. ' +
                       'Never retry in a loop or route around the block.' + (Get-IdentityLine)
            }
        }
        default {
            if ($counts.other -le $script:OtherNudgeCap) {
                $ctx = '[error-reporting] Tool failure #' + $n + ' this session (' + $tool + ', not an EPLUS server tool). ' +
                       'No report unless this is a genuine EPLUS-side defect; an expected nonzero exit or your own mistaken ' +
                       'call gets none.'
                if ($counts.other -eq $script:OtherNudgeCap) { $ctx += ' Further non-EPLUS failures this session are counted silently.' }
                $ctx += (Get-IdentityLine)
            }
        }
    }
    if (-not $ctx) { exit 0 }

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'PostToolUseFailure'
        additionalContext = $ctx
    } }
    Write-HookOutput (ConvertTo-Json -InputObject $out -Compress -Depth 8)
} catch {
    # Never let the reporter itself become a hook failure.
}

exit 0
