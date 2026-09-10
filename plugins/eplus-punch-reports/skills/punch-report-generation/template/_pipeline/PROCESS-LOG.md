# Process log, <PROJECT> v0.1

The run record. What went in, what was decided, what was changed and why, and how
the result was verified.

**Two kinds of content live here.** The block under "Run record (generated)" is
written by `scripts/run_record.py` at the end of every `run_pipeline.sh` and is
never edited by hand: inputs, scope rules, counts, drafting tally, verifier
output, script versions. A scope change is a re-run and those numbers follow.
Everything else on this page is a decision or an observation a person or the
main thread made, written as the run happens, not reconstructed afterwards.

**This is a record of what the code does, not a description of what it should
do.** A previous generation of this pipeline documented four features its shipped
code did not have, and every one of them cost real time later. If you write a
behaviour here, run it first.

---

## Run record (generated)

<!-- run-record:start -->
(written by scripts/run_record.py on the first pipeline run)
<!-- run-record:end -->

## Scope decision

<What was included, what was excluded, on whose direction, and what is still open
in PlanGrid. The numbers are in the run record; this is the reasoning.>

## Inputs the record cannot see

| Input | Path | Notes |
|---|---|---|
| Walk notes | `<path or "none">` | <if two near-identical files arrived, which was used> |
| Prior report | `<path or "none">` | <what was reused> |

## Scripts changed this run

| Script | Change | Why |
|---|---|---|

(Any change here is also a `LESSONS-LEARNED.md` entry and an error report, so
the plugin gets the fix; a workspace-only fix is lost on the next project.)

## Precedent pass

- Tools used and roughly how many calls
- Which items carry a verified citation versus a documented gap (the record's
  "precedent note present" count folds both together)
- Any theme the corpus could not cover

## Review rounds

### Round 1, <date>

**Feedback.** <verbatim where possible>

**Root cause.** <the actual cause, not the symptom>

**Fix.** <what changed, and whether it was enforced in code or just corrected>

## Limitations carried into v0.2

<What is known to be imperfect and was accepted for this revision.>
