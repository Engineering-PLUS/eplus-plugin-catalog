# Shared pieces for the error-reporting hooks. Dot-sourced by report-tool-failure.ps1
# (PostToolUseFailure), egress-request-nudge.ps1 (PostToolUse on web_fetch) and
# note-identity.ps1 (SessionStart). PowerShell 5.1-compatible, ASCII only, no BOM.
# Nothing here touches the network; the only side effect is a marker file under TEMP
# used to de-duplicate a nudge when both tool-event hooks fire for the same call.

# The three block shapes seen in exports (2026-08-14, 2026-09-09):
#   host-side web_fetch : Host "x" is not on the network allowlist (cowork-egress-blocked)
#   in-VM curl / pip    : curl: (56) Received HTTP code 403 from proxy after CONNECT
# A bare "HTTP 403: Forbidden" is deliberately NOT a signature: it is also what
# Cloudflare bot challenges and SAS permission errors return.
$script:EgressSignature = 'cowork-egress-blocked|not on the network allowlist|Received HTTP code 403 from proxy after CONNECT'

function Get-EplusIdentity {
    # Who is sitting at this seat. Hooks run on the Windows host under the signed-in
    # user's account, so the environment is authoritative; the model itself has no
    # real identity on the 3P deployment (the app's account is a placeholder
    # address, verified in the 2026-09-09 exports). Format: DOMAIN\user@MACHINE.
    $u = $env:USERNAME
    if (-not $u) { return 'unknown' }
    $d = $env:USERDOMAIN
    $m = $env:COMPUTERNAME
    $id = $u
    if ($d) { $id = $d + '\' + $u }
    if ($m) { $id = $id + '@' + $m }
    return $id
}

function Get-IdentityLine {
    # One sentence appended to every nudge so the identity is present at filing
    # time even after compaction dropped the SessionStart note.
    return (' Reporter identity for this seat: ' + (Get-EplusIdentity) +
            '. Put exactly that in requested_by on every report_issue and ' +
            'request_egress_allow call; never guess a different name.')
}

function Get-HookField {
    # Pulls a top-level string field out of the raw hook payload without parsing
    # the whole JSON (tool_response can be 70k+ characters).
    param([string]$Raw, [string]$Name)
    $m = [regex]::Match($Raw, '"' + $Name + '"\s*:\s*"([^"]*)"')
    if ($m.Success) { return $m.Groups[1].Value }
    return ''
}

function Test-EgressAlreadyNudged {
    # Returns $true when another hook already nudged for this tool_use_id in this
    # session. Creates the marker otherwise. Any failure to read or write the
    # marker returns $false so the nudge is never lost to a filesystem hiccup.
    param([string]$Raw)
    try {
        $sid = Get-HookField -Raw $Raw -Name 'session_id'
        $tid = Get-HookField -Raw $Raw -Name 'tool_use_id'
        if (-not $sid -or -not $tid) { return $false }
        $sid = ($sid -replace '[^A-Za-z0-9_.-]', '_')
        $tid = ($tid -replace '[^A-Za-z0-9_.-]', '_')
        $base = $env:TEMP
        if (-not $base) { return $false }
        $dir = Join-Path (Join-Path $base 'eplus-error-reporting') $sid
        $marker = Join-Path $dir $tid
        if (Test-Path -LiteralPath $marker) { return $true }
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        [IO.File]::WriteAllText($marker, (Get-Date).ToString('o'))
        return $false
    } catch {
        return $false
    }
}

function Get-EgressContext {
    # The additionalContext injected after an egress block. Kept as one string so
    # both hook events say exactly the same thing. Wording mirrors the
    # "Egress allow requests" section of skills/error-reporting/SKILL.md.
    return ('[error-reporting] That failure is a network egress block, not a site error. ' +
            'Per the error-reporting skill: (1) Name the blocked host. If the request was ' +
            'redirected, the blocked host is the redirect target (curl reports it as ' +
            'url_effective); record both hosts. (2) Call check_egress_host(host) on the ' +
            'error-reporting server (mcp__error-reporting__check_egress_host, or the ' +
            'mcp__plugin_error-reporting_error-reporting__ form). unknown: call ' +
            'request_egress_allow once with host, url (no query string), redirect_from, ' +
            'the user goal in their own words, why this site is needed for it, tool_name, ' +
            'the exact error text and requested_by; then tell the user the request_id and ' +
            'that an admin must approve it. pending: tell the user it is awaiting approval; ' +
            'file nothing. denied: relay the reason; file nothing. allowed: retry the fetch ' +
            'once; if it still fails the seat has not picked up the change, so tell the user ' +
            'to fully close the Claude app (quit it, not just the window) and relaunch, then ' +
            'continue. (3) Continue with everything that does not need that host. Never retry ' +
            'the fetch in a loop and never route around the block through bash. A Cloudflare ' +
            'bot challenge (cf-mitigated) or a site-side 403 is not an egress block: do not ' +
            'file. If the error-reporting tools are unavailable, append the same fields to ' +
            'EGRESS-ALLOWLIST-REQUEST.md in the session outputs folder and say so in one line.' +
            (Get-IdentityLine))
}
