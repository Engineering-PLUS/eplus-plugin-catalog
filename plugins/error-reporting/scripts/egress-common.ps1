# Shared pieces for the error-reporting hooks. Dot-sourced by note-identity.ps1
# (SessionStart), stamp-identity.ps1 (PreToolUse on the reporting tools),
# egress-after-fetch.ps1 (PostToolUse on web_fetch) and report-tool-failure.ps1
# (PostToolUseFailure). PowerShell 5.1-compatible, ASCII only, no BOM. Nothing here
# touches the network or the filesystem.
#
# 0.3.1 removed a PostToolUse web_fetch wiring and its marker-file dedupe because
# PostToolUseFailure was field-proven on egress blocks (exports of 2026-09-09).
# 0.4.0 brings a PostToolUse web_fetch wiring back, without dedupe: on Desktop
# build 1.52386.3 (export of 2026-09-15) a refused fetch returned as a successful
# result, so the failure event never fired. Success and failure events are
# exclusive per call, so the two wirings cannot double up.

# The block shapes seen in exports (2026-08-14, 2026-09-09):
#   host-side web_fetch : Host "x" is not on the network allowlist (cowork-egress-blocked)
#   in-VM curl / pip    : curl: (56) Received HTTP code 403 from proxy after CONNECT
# A bare "HTTP 403: Forbidden" is deliberately NOT a signature: it is also what
# Cloudflare bot challenges and SAS permission errors return.
$script:EgressSignature = 'cowork-egress-blocked|not on the network allowlist|Received HTTP code 403 from proxy after CONNECT'

# Hook stdin/stdout as UTF-8 regardless of the console code page. A hook process
# starts with an IBM437 console (measured 2026-09-17), so [Console]::In.ReadToEnd()
# garbles any non-ASCII text in the payload and PS 5.1's ConvertTo-Json leaves
# non-ASCII unescaped on the way out. Every script reads and writes through these.
$script:HookUtf8 = New-Object System.Text.UTF8Encoding($false)

function Read-HookInput {
    try {
        $sr = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), $script:HookUtf8)
        $raw = $sr.ReadToEnd()
        if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }
        return $raw
    } catch { return '' }
}

function Write-HookOutput([string] $text) {
    try {
        $bytes = $script:HookUtf8.GetBytes($text)
        $o = [Console]::OpenStandardOutput()
        $o.Write($bytes, 0, $bytes.Length)
        $o.Flush()
    } catch { }
}

function Get-EplusIdentity {
    # Who is sitting at this seat. Hooks run on the Windows host under the signed-in
    # user's account. Read through the .NET API first: on one pilot seat (2026-09-09)
    # COMPUTERNAME was missing from the hook environment while USERNAME was present,
    # so environment variables are only the fallback. The model itself has no real
    # identity on the 3P deployment (the app account is a placeholder address).
    # Format: DOMAIN\user@MACHINE.
    $u = ''; $d = ''; $m = ''
    try { $u = [Environment]::UserName } catch { }
    try { $d = [Environment]::UserDomainName } catch { }
    try { $m = [Environment]::MachineName } catch { }
    if (-not $u) { $u = $env:USERNAME }
    if (-not $d) { $d = $env:USERDOMAIN }
    if (-not $m) { $m = $env:COMPUTERNAME }
    if (-not $u) { return 'unknown' }
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

function Get-EgressContext {
    # The additionalContext injected after an egress block. Wording mirrors the
    # "Egress allow requests" section of skills/error-reporting/SKILL.md.
    return ('[error-reporting] That failure is a network egress block, not a site error. ' +
            'Per the error-reporting skill: (1) Name the blocked host. If the request was ' +
            'redirected, the blocked host is the redirect target (curl reports it as ' +
            'url_effective); record both hosts. (2) Call check_egress_host(host) on the ' +
            'error-reporting server (mcp__error-reporting__check_egress_host, or the ' +
            'mcp__plugin_error-reporting_error-reporting__ form). unknown: call ' +
            'request_egress_allow once with host, url (no query string), redirect_from, ' +
            'the user goal in their own words, why this site is needed for it, tool_name, ' +
            'the exact error text and requested_by. pending: file nothing. denied: file ' +
            'nothing. allowed: retry the fetch once, then stop. (3) Tell the user in ONE ' +
            'sentence folded into your normal answer: could not reach the site, request filed ' +
            '(or: already requested / declined: reason / approved but this seat needs a full ' +
            'quit and relaunch of the app). No request id, no tool names, no error text, no ' +
            'explanation of the procedure. Then continue with everything that does not need ' +
            'that host. Never retry the fetch in a loop and never route around the block ' +
            'through bash. A Cloudflare bot challenge (cf-mitigated) or a site-side 403 is not ' +
            'an egress block: do not file. If a reporting tool is refused by the permission ' +
            'classifier, or the tools are unavailable, append the same fields to ' +
            'EGRESS-ALLOWLIST-REQUEST.md in the session outputs folder and do not retry that ' +
            'call this turn.' +
            (Get-IdentityLine))
}
