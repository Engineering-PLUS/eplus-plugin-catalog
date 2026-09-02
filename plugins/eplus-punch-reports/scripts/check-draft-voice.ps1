# PostToolUse hook. Runs on the Windows host under PowerShell.
#
# When drafted_items.json is written or edited, sweep it for the field-report
# voice rules and for em/en dashes, and report any hit back as context so it is
# fixed at authoring time rather than at build time.
#
# build_master.py is the authority: it fails the build on a voice hit, and it
# rewrites em/en dashes to commas (mechanically, so the wording suffers) and only
# fails if any survive. This hook exists because that feedback arrives minutes
# later, after photos and clips have been rebuilt. The banned list mirrors
# VOICE_BANNED in build_master.py; keep them in step.
#
# Context-only output (additionalContext); never decision fields; always exits 0.
# Disable with EPLUS_NO_PUNCH_VOICE_CHECK=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_PUNCH_VOICE_CHECK) { exit 0 }

    $payload = $raw | ConvertFrom-Json
    $file = $payload.tool_input.file_path
    if (-not $file) { exit 0 }
    if ($file -notmatch 'drafted_items\.json$') { exit 0 }
    if (-not (Test-Path -LiteralPath $file)) { exit 0 }

    $items = (Get-Content -LiteralPath $file -Raw -Encoding UTF8) | ConvertFrom-Json
    if (-not $items) { exit 0 }

    # Editor's Notes are internal, are deleted before issuing, and legitimately
    # discuss photographs and pins. Only descriptions are in scope.
    # Same eight patterns as build_master.py VOICE_BANNED.
    $banned = @(
        @{ p = 'photograph';                  why = 'narrates the evidence' },
        @{ p = 'photo shows';                 why = 'narrates the evidence' },
        @{ p = 'in the frame';                why = 'narrates the evidence' },
        @{ p = '\bimages?\b';                 why = 'narrates the evidence' },
        @{ p = 'this photo';                  why = 'narrates the evidence' },
        @{ p = 'field engineer';              why = 'third-person self-reference' },
        @{ p = 'no description was recorded'; why = 'narrates the record, not the site' },
        @{ p = 'not determinable from';       why = 'narrates the evidence' }
    )

    $dashPattern = '[' + [char]0x2013 + [char]0x2014 + ']'

    $hits = New-Object System.Collections.ArrayList
    foreach ($item in $items) {
        $desc = $item.description
        if (-not $desc) { continue }
        $ref = $item.number
        foreach ($b in $banned) {
            if ($desc -match $b.p) {
                [void]$hits.Add("item $ref : '$($Matches[0])' ($($b.why))")
            }
        }
        # Built from code points, not literal characters. PowerShell 5.1 reads a
        # BOM-less script as ANSI, which mangles a literal em dash in source and
        # makes the check silently never fire.
        if ($desc -match $dashPattern) {
            [void]$hits.Add("item $ref : em or en dash")
        }
    }

    if ($hits.Count -eq 0) { exit 0 }

    $list = ($hits -join '; ')
    $ctx = "[punch-report] Voice check on drafted_items.json found $($hits.Count) issue(s): $list. " +
           'Item descriptions are in field-report voice: state the condition directly rather than ' +
           'narrating the evidence ("Metal stud framing at this location carries a junction box with...", ' +
           'not "the photograph shows..."), and never refer to the field engineer in the third person ' +
           'since this report is theirs ("Work remained in progress at the time of the walk."). For ' +
           'genuinely unclear pins write "could not be established during the walk and requires field ' +
           'verification". No em or en dashes anywhere. Editor''s Notes are internal and exempt. ' +
           'build_master.py fails the build on a voice hit and mechanically rewrites dashes to commas, ' +
           'so fix both now while the wording is still yours.'

    $out = @{ hookSpecificOutput = @{
        hookEventName     = 'PostToolUse'
        additionalContext = $ctx
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # A malformed or partially-written draft file is not a hook failure.
}

exit 0
