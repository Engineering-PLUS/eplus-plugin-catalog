# PreToolUse gate for commit_approved_rfi -- PowerShell, runs on the Windows
# host (NO python, NO sh). The marketplace promises that nothing reaches the
# EPLUS knowledge base without the user's sign-off. The skill enforces that
# with an AskUserQuestion gate, which is instruction-only; this hook makes
# the harness itself prompt before ANY call to commit_approved_rfi, whatever
# the model decided. It never denies and never allows: the decision is
# always "ask", so the user sees the write and confirms or refuses it.
#
# Matched on both tool-name forms (managed connector and bundled plugin), so
# the hook does not inspect tool_name; it only reads stdin to stay
# well-formed and to surface the rfi_id in the prompt text.
# Never blocks on its own; always exit 0 with the decision in JSON.
# Escape hatch: EPLUS_NO_RFI_COMMIT_GATE=1 emits nothing (normal permission
# flow applies).

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_RFI_COMMIT_GATE) { exit 0 }
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    $rfiId = ''
    $project = ''
    try {
        $data = $raw | ConvertFrom-Json -ErrorAction Stop
        if ($null -ne $data -and $data.PSObject.Properties['tool_input'] -and $null -ne $data.tool_input) {
            $ti = $data.tool_input
            if ($ti.PSObject.Properties['rfi_id'] -and $ti.rfi_id) { $rfiId = [string]$ti.rfi_id }
            if ($ti.PSObject.Properties['project_id'] -and $ti.project_id) { $project = [string]$ti.project_id }
        }
    } catch { }

    $what = 'this RFI response'
    if ($rfiId) { $what = "response $rfiId" }
    if ($project) { $what = "$what (project $project)" }
    $reason = "Write to the EPLUS knowledge base: $what will be logged permanently and become citable by future lookups. Confirm only if you approved this exact final text."
    if ($reason.Length -gt 400) { $reason = $reason.Substring(0, 400) }

    $out = @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'ask'; permissionDecisionReason = $reason } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 5))
} catch {
    # A broken gate must not break the tool call; the skill's own gate still applies.
}

exit 0
