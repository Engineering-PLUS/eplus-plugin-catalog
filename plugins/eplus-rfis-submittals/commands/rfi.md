---
description: Review an RFI or submittal and draft a formal EPLUS response grounded in the Hermes knowledge engine
argument-hint: <RFI text, attached document reference, or instructions — e.g. "review this request and draft a response">
---

Process the following RFI/submittal request using the EPLUS 4-step RFI
workflow defined in the `rfi-workflow` skill (load it first if not
already loaded):

$ARGUMENTS

1. **Deconstruct** — parse the request/attached document; extract Project
   ID, CSI division/section, equipment/materials, and the core technical
   question. Ask the user if critical attributes are missing.
2. **Query Hermes** — do NOT answer from pre-training memory. Formulate a
   detailed, intent-rich query and call `query_hermes_rfi(query=...,
   project_id=..., csi_section=...)`. Refine and re-query if gaps remain.
3. **Draft** — synthesize the Hermes context report into a formal EPLUS
   engineering RFI response with explicit citations to the spec clauses
   and codebook sections Hermes returned.
4. **HITL gate** — present the draft and ask: "Does this response meet
   your approval? Reply 'Approve' to commit this RFI response to the team
   knowledge base." Only on explicit approval call
   `commit_approved_rfi(...)` with the finalized markdown, RFI ID,
   project ID, and metadata. Never commit without approval.
