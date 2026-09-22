# PreToolUse hook on this plugin's reporting tools (report_issue and
# request_egress_allow, under both the managed-connector name
# mcp__error-reporting__* and the bundled name
# mcp__plugin_error-reporting_error-reporting__*). Runs on the Windows host under
# PowerShell. PowerShell 5.1-compatible, ASCII only, no BOM.
#
# Why (0.4.0): reports were reaching the backend with requested_by "unknown". The
# SessionStart note (note-identity.ps1) lands in the main thread only; a subagent
# that files a report never held it, and on Desktop build 1.52386.3 a blocked fetch
# came back as a successful result, so the PostToolUseFailure nudge that repeats the
# identity never fired either. Plugin hooks do run inside subagents (hooks
# reference: "Hooks from settings files, managed policy settings, and plugins also
# run inside subagents"), so a PreToolUse hook on the reporting call itself is the
# one place the identity is guaranteed to be present at filing time.
#
# What it does: reads the hook payload as UTF-8, and when tool_input.requested_by is
# empty or "unknown" rewrites it to the seat identity (DOMAIN\user@MACHINE from
# egress-common.ps1). It also appends one bracketed trace tag to details
# (report_issue) or error_text (request_egress_allow):
#   [seat session <session_id>; env session <CLAUDE_CODE_SESSION_ID or none>; agent <agent_type>/<agent_id> or main]
# so a report filed by a worker can be traced to its session and agent. The tag is
# appended after the existing text, which is otherwise left untouched. When anything
# changed it returns permissionDecision "allow" with updatedInput (the hooks
# reference: updatedInput "Replaces the entire input object, so include unchanged
# fields alongside modified ones" and is combined with "allow" to auto-approve).
# Deny and ask rules, and MCP tools marked requiresUserInteraction, still win over the
# allow. When nothing needed changing it emits the identity line as additionalContext
# only and leaves the permission decision to the harness. When the host identity
# cannot be read at all the hook never overwrites requested_by and says so.
#
# Always exits 0. Disable with EPLUS_NO_IDENTITY_STAMP=1 (EPLUS_NO_ERROR_NUDGE=1
# also silences it). Cost: one PowerShell spawn per reporting call.

$ErrorActionPreference = 'SilentlyContinue'

try {
    . (Join-Path $PSScriptRoot 'egress-common.ps1')
    $raw = Read-HookInput
    if ($env:EPLUS_NO_ERROR_NUDGE -or $env:EPLUS_NO_IDENTITY_STAMP) { exit 0 }

    $identity = Get-EplusIdentity

    $payload = $null
    try { $payload = ConvertFrom-Json -InputObject $raw } catch { $payload = $null }

    $stamped = $false
    $tagged  = $false
    $ti      = $null

    if ($payload -and $payload.tool_input) {
        $ti = $payload.tool_input

        # 1. requested_by: fill in only when the model sent nothing usable and the
        #    host identity is known.
        $rb = ''
        if ($ti.PSObject.Properties['requested_by']) { $rb = [string]$ti.requested_by }
        if ($null -eq $rb) { $rb = '' }
        if ($identity -ne 'unknown' -and $rb.Trim().ToLower() -in @('', 'unknown')) {
            Add-Member -InputObject $ti -NotePropertyName 'requested_by' -NotePropertyValue $identity -Force
            $stamped = $true
        }

        # 2. Trace tag on the free-text field of the two filing tools.
        $tool  = [string]$payload.tool_name
        $field = ''
        if ($tool -match 'report_issue$')               { $field = 'details' }
        elseif ($tool -match 'request_egress_allow$')   { $field = 'error_text' }
        if ($field) {
            $sid    = [string]$payload.session_id
            $envSid = [string]$env:CLAUDE_CODE_SESSION_ID
            $agent  = ''
            if ($payload.agent_type) { $agent = [string]$payload.agent_type }
            if ($payload.agent_id) {
                if ($agent) { $agent = $agent + '/' + [string]$payload.agent_id } else { $agent = 'subagent/' + [string]$payload.agent_id }
            }
            if (-not $agent)  { $agent = 'main' }
            if (-not $sid)    { $sid = 'unknown' }
            if (-not $envSid) { $envSid = 'none' }
            # components never carry brackets or line breaks, so the tag stays one token
            $sid = $sid -replace '[\[\]\r\n]', '_'; $envSid = $envSid -replace '[\[\]\r\n]', '_'; $agent = $agent -replace '[\[\]\r\n]', '_'
            $tag = '[seat session ' + $sid + '; env session ' + $envSid + '; agent ' + $agent + ']'

            $cur = ''
            if ($ti.PSObject.Properties[$field]) { $cur = [string]$ti.$field }
            if ($null -eq $cur) { $cur = '' }
            if ($cur -notmatch '\[seat session [^\]]*; env session [^\]]*; agent [^\]]*\]') {
                $new = $(if ($cur -eq '') { $tag } else { $cur + ' ' + $tag })
                Add-Member -InputObject $ti -NotePropertyName $field -NotePropertyValue $new -Force
                $tagged = $true
            }
        }
    }

    if ($identity -eq 'unknown') {
        $ctx = '[error-reporting] The seat hook could not read a user name on this machine, so it left ' +
               'requested_by as sent. Keep the identity you already have (the identity line in context, ' +
               'or the login from the working directory path); never invent a different name.'
    } else {
        $ctx = '[error-reporting] Reporter identity for this seat: ' + $identity + '.'
        if ($stamped) {
            $ctx += ' requested_by on this call was empty or unknown and has been set to that value by the seat hook.'
        }
        $ctx += ' Put exactly that in requested_by on every report_issue and request_egress_allow call; never guess a different name.'
    }

    $hso = @{
        hookEventName     = 'PreToolUse'
        additionalContext = $ctx
    }
    if ($stamped -or $tagged) {
        $what = @()
        if ($stamped) { $what += 'requested_by set to the seat identity' }
        if ($tagged)  { $what += 'trace tag appended' }
        $hso.permissionDecision       = 'allow'
        $hso.permissionDecisionReason = 'error-reporting: ' + ($what -join '; ')
        $hso.updatedInput             = $ti
    }
    $out = @{ hookSpecificOutput = $hso }
    Write-HookOutput (ConvertTo-Json -InputObject $out -Compress -Depth 20)
} catch {
    # Never let the stamp itself become a hook failure.
}

exit 0
