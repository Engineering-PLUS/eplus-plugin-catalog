# PreToolUse hook. Runs on the Windows host under PowerShell.
#
# Denies a LibreOffice PDF conversion of a punch report. The pipeline outputs
# .docx only: the reviewer generates the PDF from Word, which is the only
# renderer that recalculates the TOC PAGEREF fields. A LibreOffice conversion
# produces a PDF whose page numbers are blank or wrong, and that mistake has
# already shipped once.
#
# DELIBERATELY NARROW. It fires only when the command both converts to PDF and
# names the pipeline folder (_pipeline) or a report by its naming convention
# (-DRAFT-v), so the docx skill's own soffice validation and every unrelated
# conversion are untouched, even inside a folder whose name contains "punch".
#
# Always exits 0; the decision travels in the JSON, not the exit code.
# Disable with EPLUS_NO_PUNCH_PDF_GUARD=1.

$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ($env:EPLUS_NO_PUNCH_PDF_GUARD) { exit 0 }

    $payload = $raw | ConvertFrom-Json
    $cmd = $payload.tool_input.command
    if (-not $cmd) { exit 0 }

    # scripts/render_preview.py converts to PDF in a scratch directory it deletes
    # before exiting, purely to rasterise pages for a layout spot check; no PDF
    # survives to be mistaken for a deliverable. Exempt it by name.
    if ($cmd -match 'render_preview\.py') { exit 0 }

    $isConvert = ($cmd -match 'soffice|libreoffice') -and ($cmd -match 'convert-to\s+pdf|--convert-to\s+pdf')
    if (-not $isConvert) { exit 0 }

    # Only guard punch report material: the pipeline folder or the report naming
    # convention (<report>-DRAFT-v0.1.docx). NOT the word "punch": most project
    # folders carry it, and matching it denied every unrelated conversion in them,
    # including the docx skill's own validation (field result 2026-09-02).
    if ($cmd -notmatch '_pipeline|-DRAFT-v') { exit 0 }

    $reason = 'The punch report pipeline outputs .docx only, by design. Word recalculates the ' +
              'TOC PAGEREF fields on open and on PDF export; LibreOffice does not, and it paginates ' +
              'differently, so a PDF made this way carries blank or wrong page numbers. That exact ' +
              'bug already shipped once. The reviewer generates the PDF from Word when their markup ' +
              'is done. If you need to verify the document, use scripts/verify_report.py, which ' +
              'reads the OOXML directly and needs no LibreOffice.'

    $out = @{ hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = 'deny'
        permissionDecisionReason = $reason
    } }
    [Console]::Out.Write((ConvertTo-Json -InputObject $out -Compress -Depth 8))
} catch {
    # Never let the guard itself block a tool call.
}

exit 0
