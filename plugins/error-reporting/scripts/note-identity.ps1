# SessionStart hook (startup, resume, compact). Runs on the Windows host under
# PowerShell. Tells the model who is sitting at this seat so every report_issue and
# request_egress_allow call can carry requested_by. PowerShell 5.1-compatible,
# ASCII only, no BOM.
#
# Why a hook: on the 3P deployment the app's account identity is a placeholder
# (metadata emailAddress "cowork-3p@localhost", exports of 2026-09-09), so the
# model's env block carries no real user name. The host environment does:
# USERDOMAIN\USERNAME@COMPUTERNAME. Compaction drops the note, which is why the
# "*" matcher covers SessionStart:compact too, and why every failure nudge repeats
# the identity line (see egress-common.ps1).
#
# Cost: one PowerShell spawn per session open, resume, or compaction; the script
# does no I/O beyond reading the environment. Context-only, always exits 0.
# Disable with EPLUS_NO_IDENTITY_NOTE=1 (EPLUS_NO_ERROR_NUDGE=1 also silences it).

$ErrorActionPreference = 'SilentlyContinue'

try {
    $null = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_ERROR_NUDGE -or $env:EPLUS_NO_IDENTITY_NOTE) { exit 0 }

    . (Join-Path $PSScriptRoot 'egress-common.ps1')

    $ctx = '[error-reporting] Reporter identity for this seat: ' + (Get-EplusIdentity) +
           '. Put exactly that in the requested_by field of every report_issue and ' +
           'request_egress_allow call. Never guess or infer a different name; if this ' +
           'note is missing when you file, use "unknown".'

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'SessionStart'
        additionalContext = $ctx
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the note itself become a hook failure.
}

exit 0
