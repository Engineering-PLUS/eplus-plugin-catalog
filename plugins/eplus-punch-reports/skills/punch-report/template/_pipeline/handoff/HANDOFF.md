# Session handoff, <PROJECT> v0.1

Everything a future run needs in order to be better than this one. Start here.

---

## What to read, in order

| # | File | Why |
|---|---|---|
| 1 | `../CLAUDE.md` | How the pipeline works and the rules it enforces. Read before touching any script. |
| 2 | `../LESSONS-LEARNED.md` | What broke, why, and the recommended skill updates. **This is the learning data.** |
| 3 | `../PROCESS-LOG.md` | The run record: inputs, decisions, review rounds, verification. |
| 4 | `../ISSUES-LIST.md` | What is still missing (generated block at the top, each with its `update_report.py` command), then the open questions for the reviewer. |
| 5 | `../../client-profile.json` | Client-level facts (name, address, EP number, inspector, reviewer), delivered to the project folder for the next report. |

Nothing in this package comes from, or is written to, agent memory. Everything
the next run needs is in these files, where the next engineer can also read it.

## Picking this report up again

In a new session, rebuild the workspace from this package and apply the change:

```bash
bash <plugin skill>/scripts/init_workspace.sh <new workspace> --from-package <this package>.zip
cd <new workspace>/_pipeline && bash scripts/install_deps.sh
python3 scripts/update_report.py <changes> --deliver
```

---

## The changes most worth carrying into the skill

Condensed from `LESSONS-LEARNED.md`. Keep this to the ones that cost real time.

1.
2.
3.

---

## State of the deliverables

| File | Status |
|---|---|
| `<report>.docx` | |
| `<report>-Review.xlsx` | |

## Reproducing this report

```bash
cd _pipeline
bash scripts/smoke_test.sh     # tooling check
bash scripts/run_pipeline.sh   # five steps + verify
```

Outputs the .docx, the file of record (a convenience PDF only on request, via
`scripts/export_pdf.py`). Deps: `bash scripts/install_deps.sh`, then
`bash scripts/smoke_test.sh`.

Scope lives in exactly one place, `SCOPE` in `run_pipeline.sh`. Cover and footer
strings live in `build/report.config.json`, not in the renderer.

## Not carried forward, and why

<Walk notes, excluded items, anything deliberately left out and the reason. If
excluded items relate to included ones, say which.>
