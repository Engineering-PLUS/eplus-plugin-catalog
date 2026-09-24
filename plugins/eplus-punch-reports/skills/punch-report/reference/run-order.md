# Run order: building a punch report

The order of a run, from finding the inputs to applying the answers. SKILL.md
and the other `reference/` files are the authority on each step; read only the
reference a step names. "What the user typed" is the text after `/punch-report`,
or the folder or project the user named when asking for the report: a folder
name, a PlanGrid project name, or nothing.

## The rule: build first, ask last

Users start this and walk away. Field results 2026-09-09 to 2026-09-23: runs
that asked before building sat on an unanswered question for 12 to 47 minutes
and some never produced a draft; one opened the folder picker with no
explanation and the user cancelled it. So:

- **No question, folder picker or confirmation before the draft exists.** Not
  `AskUserQuestion`, not `request_cowork_directory`, not a question in prose
  that waits for a reply. Every decision below has a default; take it. The
  one exception is **No match** in section 1.
- **Anything unknown goes on the draft, visibly.** A missing cover fact
  renders as a red `[MISSING: ...]` marker; everything else the draft still
  needs lands in the finish list with the one command that supplies it.
- **Questions come once, at the end**, after the draft is delivered, together
  with the finish list (section 7). A user who never answers still has a
  complete draft.
- **Facts come from records, never from memory.** Client, address, EP number,
  inspector, scope decisions and the version come from the project folder's
  `client-profile.json`, PlanGrid, the user, or the project folder's own
  deliveries. Do not open memory files for any of them, and never label a
  memory fact as "the earlier report record". Field result 2026-09-23: a run
  filled the whole cover from a memory note, so the test could not tell the
  plugin's behaviour from the note's.

## 1. Find the inputs: one command

```bash
S=/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-punch-reports/skills/punch-report
python3 "$S/scripts/locate_inputs.py" "<what the user typed>"
```

`<session>` is the first path segment under `/sessions/` (`ls /sessions`).
It reports the **project folder** (the connected folder whose name matches
the argument, else the only one connected), where to **deliver**, the **next
version** (from that folder's own `-DRAFT-vN.N` files), and the inputs it
found: a pull folder (`tasks.json`), Task Report PDFs, `client-profile.json`,
an earlier package.

- **Project folder NONE:** carry on. Build and deliver into the session
  outputs folder it names. Section 7 asks for the folder; nothing before it.
- **An earlier package in the project folder** (`*-Punch-Report-*.zip`): this
  is a revision. Go to `reference/revising.md`; it starts from that package
  and changes only what changed.
- **The pull:** a pull folder on disk is copied into the workspace (section
  2). Otherwise use the `plangrid` MCP: `list_projects`, take the project
  whose name matches the argument or the project folder's name. When the user
  typed nothing and nothing matches, take the most recently updated project,
  and say which one you took in the finish list and the final message. Then
  one `get_tasks` and one `list_sheets`; `scripts/pull_mcp.sh` fetches their
  packets (`reference/build-data.md`, Step 0b). Never retype a result into a
  file.
- **No match: the one question before a draft.** The user named a project,
  `list_projects` finds nothing for it (search again with
  `active_only: false`), and there is no pull or Task Report PDF on disk.
  Never substitute an unrelated project: field result 2026-09-24, "htx2"
  matched nothing and the most recent project would have put a Project Miner
  report in the htx2 folder. Ask one `AskUserQuestion`: **an empty report**
  (the cover plus three blank item pages to fill in by hand, two Word files),
  up to two PlanGrid projects whose names come closest, or **I'll add the
  inputs** (a pull or a Task Report PDF in the folder, then tell you). A
  project picked from the options is a normal run. An empty report is built
  and delivered like this, and nothing else from sections 3 to 6 applies:

  ```bash
  bash "$S/scripts/init_workspace.sh" <workspace>
  cd <workspace>/_pipeline && bash scripts/install_deps.sh
  python3 scripts/blank_template.py --pages 3
  python3 scripts/prefill_config.py --project-name "<what the user typed>" --version <next version> \
      [--project-folder <project folder>]
  RENDER_ONLY=1 bash scripts/run_pipeline.sh
  python3 scripts/package.py <workspace> "<deliver to>" --template-only
  ```

  `--template-only` delivers the body and the cover and nothing else: no
  package, no review sheet, no client profile, no paperwork. The final
  message names the two files, says the item pages are blank for the
  engineer to fill in (more pages: `--pages N`), and lists the cover fields
  marked `[MISSING]`; no finish-list questions.
- **No Task Report PDF:** build without pin clips. It is a finish-list entry,
  not a question.

## 2. Build the workspace

```bash
bash "$S/scripts/init_workspace.sh" <workspace>
cd <workspace>/_pipeline && bash scripts/install_deps.sh && bash scripts/smoke_test.sh
```

`<workspace>` is in the session outputs folder, named after the report
(`/sessions/<session>/mnt/outputs/<project>-punch-<walkdate>/`). The stamper
lays out the template, copies the plugin's scripts, makes the tree writable,
and exits non-zero naming anything missing. **Do not write your own `cp`
lines for this, and do not let a worker.** Then copy the inputs in once,
beside `_pipeline/`: the pull folder (or the MCP route writes
`plangrid_mcp/` and `plangrid_pull/`), the Task Report PDF if there is one.
The project folder stays read-only until delivery.

`${CLAUDE_PLUGIN_ROOT}` is the host-side path of the same folder (Read and
Grep use it); it does not exist inside the sandbox, so do not `find /` for it.
Nobody edits the scripts during a run. If a step needs a code change, the main
thread makes the smallest edit in the workspace copy, records it in
`LESSONS-LEARNED.md`, and files it with `report_issue` before delivering.

## 3. Data, then the cover from records

```bash
bash scripts/run_pipeline.sh            # consolidate, photos, sheet clips; stops before drafting
python3 scripts/prefill_config.py --project-name "<PlanGrid project name>" --version <next version> \
    [--project-folder <project folder>] [--building "<only if a source on record states it>"]
```

`prefill_config.py` fills `report.config.json` from `client-profile.json`
(the project folder's copy), the PlanGrid project name, the pin dates and the
pin authors, sets the issuance date to TBD and the file name from the version,
and records each value's source in `fact_sources`. Whatever no record states
stays empty and shows as `[MISSING: ...]`. Do not fill those from memory or
from inference; the finish list asks for them.

## 4. The decisions, already made

These used to be intake questions. They are defaults now, each reversible
later with one command (section 8):

| Decision | Default in the draft | Changed later with `update_report.py` |
|---|---|---|
| Pins PlanGrid deleted or archived | left out, listed in the finish list | `--deleted-pins keep` |
| Near-miss record-only notes | kept, listed | `--drop N` |
| A pull spanning two walk dates | one list, every item carries its pin date | `--set visit_sections=by_date` |
| Issuance date | TBD | `--set issuance_date=YYYY-MM-DD` |
| Client, address, EP number, building, inspector | from the profile and PlanGrid, else `[MISSING]` | `--set <key>=...` |
| Cover | a separate `-Cover.docx`; body page 1 blank for it | `--set cover_mode=supplied\|blank\|none` |
| Wording | every item drafted in field-report voice; inferred items flagged with confidence and an Editor's Note | `--item N --description "..."` |
| No Task Report PDF | no pin clips | `--task-report "<pdf>"` |
| Items without photos | an empty paste grid | `--item N --photo-mode none` |
| Where it goes | the project folder, else the session outputs folder | `--deliver <folder>` |

## 5. Draft, check precedent, render

Draft every item (`reference/drafting.md`; hand it to a worker with
`reference/worker-brief.md` pasted verbatim), check precedent, then:

```bash
RENDER_ONLY=1 bash scripts/run_pipeline.sh
```

It builds the master, renders, verifies, writes the run record and the review
sheet, and prints the **finish list** (also in `build/finish.json` and at the
top of `ISSUES-LIST.md`). Then look at three preview pages: the cover, one item
with photos, one without (`scripts/render_preview.py`). Nothing more.

**A worker's Open questions do not go to the user mid-run.** The main thread
settles each one from house policy (SKILL.md) and the defaults above, writes
the question and the choice made into `ISSUES-LIST.md`, and carries on. Only a
question with no default and no safe choice stops that one item: it ships as
`undetermined` with an Editor's Note, and the question joins the finish list.

## 6. Paperwork, then deliver once

`run_record.py` fills the identity fields. Write what only a person can:
`ISSUES-LIST.md` (the reviewer's open questions, blocking first, below the
generated finish list), the scope paragraph and precedent pass in
`PROCESS-LOG.md`, `LESSONS-LEARNED.md` ("nothing broke" is fine),
`handoff/HANDOFF.md`, and the README scope paragraph. `package.py` refuses to
deliver while any still carries template text.

```bash
python3 scripts/package.py <workspace> "<deliver to, from locate_inputs.py>"
```

The one write to the project folder in the run. It never overwrites. **The
folder keeps only the current version and the inputs**: earlier versions of
the report already there (body, cover, review sheet, package) are written into
the new package under `previous-versions/` and then removed from the folder,
each only after the new zip is verified to hold an identical copy. If Cowork
has not allowed deletes in that folder yet, the packager prints `CLEANUP
PENDING` and three steps. **Step 1: post the message it prints, as written,
before asking for anything.** It names every file that will be deleted, says
they are the previous version, that identical copies are inside the new
package, that nothing else in the folder is touched, and that declining just
leaves them there. Cowork's permission prompt names one file and gives no
reason, so without this message people cannot tell what they are approving
(field result 2026-09-23: "I'll tidy them out of the folder" was all the user
got). Never shorten it to a summary and never ask before posting it. Step 2:
call `allow_cowork_file_delete` once with the path it names (one approval
covers the folder). Step 3: if allowed, run
`python3 scripts/package.py --prune "<folder>"`. Read the whole packager
output, never a `tail` of it, so the message is not cut. That is the only delete in a
run, and it removes nothing the new package does not hold. The Task Report
PDF and `client-profile.json` always stay.

## 7. The final message: what is done, what is missing, then the questions

In this order, short:

1. **What was built and where.** The body `.docx`, its `-Cover.docx`, the
   review `.xlsx` and the package, as links **in the folder they were
   delivered to**. If that is the session outputs folder, say so in the first
   sentence: the report is not in a project folder yet, and connecting one
   takes one command.
2. **The finish list**, from the pipeline's output, the blocking entries
   first: missing cover facts, issuance date, pin clips, delivery folder.
   Then the review points in one or two lines.
3. **One `AskUserQuestion`**, at most four questions, for the blocking gaps
   a person can answer on the spot (identity block, issuance date, the
   project folder to deliver to, deleted pins). Say the draft is complete
   either way and they can answer later in this session.

## 8. When the answers arrive: surgical edits, never a rebuild

Each answer is one `update_report.py` call, from `_pipeline/`; several can
ride in one call. It edits the config or the drafts, re-renders (seconds, no
worker, no reference reading), verifies, logs the change in
`PROCESS-LOG.md`, and with `--deliver` packages the next version (v0.1 to
v0.2) beside the earlier one:

```bash
python3 scripts/update_report.py --set client_display_name="ServerFarm CTX2" --set ep_project_no=27625 \
    --set issuance_date=2026-09-30 --deliver
python3 scripts/update_report.py --task-report "/sessions/<session>/mnt/<folder>/PlanGrid Task Report.pdf" --deliver
python3 scripts/update_report.py --item 12 --description "..." --deliver
python3 scripts/update_report.py --deliver "<newly connected folder>"
```

**Several answers go in ONE call**, so the folder gets one new version, not
one per answer (field result 2026-09-23: a date, then a folder, then a Task
Report gave three renders and two deliveries a minute apart). A delivery to a
folder that holds a Task Report PDF uses it automatically when the report has
no pin clips yet, in the same call. Every `--deliver` tidies the folder as in
section 6, including `CLEANUP PENDING`.

Do not start a worker, re-read references, re-run the data steps or re-draft
items for any of these. A scope change (`--scope`, `--created-after`) re-runs
the data steps inside the same command; new items it brings in are named in
its error and are the only ones to draft. In a new session the workspace is
gone: rebuild it from the delivered package (`reference/revising.md`, three
commands), then the same calls.

## 9. What the project folder holds when the run is done

| File | What it is |
|---|---|
| `<Project>-Punch-Report-DRAFT-vN.N.docx` | the report body, the file of record; page 1 is blank for the cover |
| `<Project>-Punch-Report-DRAFT-vN.N-Cover.docx` | the cover, a separate Word file (cover mode `template`) |
| `<Project>-Punch-Report[-DRAFT-vN.N]-Review.xlsx` | the review spreadsheet: bulk edits in the yellow columns, imported back |
| `<Project>-Punch-Report-DRAFT-vN.N.zip` | the package: the whole workspace (data, drafts, photos, clips, paperwork, scripts) to revise from, plus every earlier version under `previous-versions/` |
| `client-profile.json` | client-level facts for the next report for this client |
| `PlanGrid Task Report ... .pdf` | the user's own input, the source of the pin clips; never moved |

Nothing else. Files in the session outputs folder stay there; the session
discards them. The `.docx` is the file of record; a PDF is made only when
asked (`scripts/export_pdf.py`, then `package.py --pdf`, described as a
convenience copy).
