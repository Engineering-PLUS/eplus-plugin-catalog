# Exporting the Task Report PDF from PlanGrid in the browser

The Task Report PDF is the only source of the per-pin sheet clips, and it is
not part of the `plangrid` connector pull. When the user attached none and
`locate_inputs.py` found none, the main thread exports one from PlanGrid in
the built-in browser, **filtered to this report's pins**, while the rest of
the run carries on, and fetches it into the workspace before the render.
Walked end to end on 2026-10-01 (CTX2, 36 tasks: about 100 seconds, 3 MB) and
2026-10-06 (Project Miner Building A, a 36-item report: unfiltered, all 94
tasks, about 6.5 minutes and 12.4 MB; filtered to the walk date, exactly the 36
tasks #59 to #94, under 4 minutes and 6.2 MB).

**Main thread only.** A worker never opens the browser: the sign-in notice is
for the user, and workers have no contact with the user.

**The clips are always wanted unless the user says so in those words** ("no
drawing clips", "skip the Task Report", "don't use PlanGrid in the browser").
A request that names the sources to draft from ("only pics and description
notes", "from the photos") is about the wording, not the clips. Field result
2026-10-06: "only pics and description notes for visit 6" was read as "no
clips", the export was recorded as skipped, and the user had to stop the run.

**When it does not apply:** a Task Report PDF is already on disk or uploaded;
a revision whose package already carries pin clips; the **No match** path
(empty template); the user said in so many words not to export the clips.

## The shape: sign in early, export after the data pass, collect before the render

| When | What |
|---|---|
| Right after `list_projects` gives the project uid (run order, section 1) | load the browser tools, open the task list, check the sign-in (steps 1 and 2) |
| Right after the data pass (`bash scripts/run_pipeline.sh`, so `data/items.json` holds the scope) | start the export, filtered to the scope (steps 3 and 4); then hand drafting to the worker |
| After drafting, before `RENDER_ONLY=1 bash scripts/run_pipeline.sh` | collect (step 5), up to 5 minutes of polling |
| Still nothing | record the skip (step 7) and render without clips |

The export starts after the data pass because the filter comes from the
scoped items; it generates while the items are drafted (two to five minutes).
Collect **before** the render, not after it: on 2026-10-01 the model rendered
first, then started the export, and had to render a second time for the
clips. The draft never waits on the export. A render-only pass cuts the clips
of a PDF beside `_pipeline/` when the report has none yet.

## 1. Load the browser tools

They are deferred in the desktop app. One call:

```
ToolSearch  query: "select:mcp__Claude_Browser__preview_start,mcp__Claude_Browser__navigate,mcp__Claude_Browser__get_page_text,mcp__Claude_Browser__find,mcp__Claude_Browser__computer,mcp__Claude_Browser__javascript_tool"
```

If they do not come back, the seat has no browser: record the skip (step 7,
reason `browser tools not available`) and carry on.

## 2. Open the project's task list and check the sign-in

```
mcp__Claude_Browser__preview_start   url: "https://app.plangrid.com/projects/<project uid>/issues/"
mcp__Claude_Browser__get_page_text
```

The url needs the `https://`; a bare host is rejected ("not a valid file path
or URL", field result 2026-09-22). `<project uid>` is the uid
`list_projects` returned.

**Signed out:** the page URL ends in `/login`, or the text reads "Log in to
your account". Claude cannot sign in for the user, and a sign-in does not last
forever (a pane signed in on 2026-10-01 was signed out again by 2026-10-06).
Tell the user, without waiting for a reply, in two places that show:

1. A task in the task list, created right away:
   `TaskCreate  subject: "Sign in to PlanGrid in the browser pane"`,
   description: "Needed for the drawing clip on each pin. Claude can't sign in
   for you; the draft carries on meanwhile." Mark it completed once the task
   list loads signed in.
2. The **first sentence of your next status line**, for example: "PlanGrid
   needs you to sign in in the browser pane (I can't do that for you) so I can
   export the drawing clips; I'm carrying on with the draft meanwhile."

Never only in your thinking: on 2026-10-01, 2026-10-02 and 2026-10-06 the
model composed the notice in its thinking, a separate message was never
written, and the users found the login page in the pane on their own.

At step 3 and at the collect point, `navigate` to the task list again and
check. Still signed out at the collect point: record the skip, reason
`not signed in to PlanGrid`, and say it again in the final message.

**Signed in:** the page lists the project's tasks ("Export (All)" is on it).
A PlanGrid error page instead (no access to the project): skip, reason
`no access to the project in PlanGrid`.

## 3. Start the export, filtered to this report's pins

From `_pipeline/`, after the data pass:

```bash
python3 scripts/task_report_filter.py --project-uid <project uid>
```

It prints a `filter url` (the task list with `created_after` and
`created_before` set to the scope's first and last pin date, as PlanGrid dates them)
and the number of in-scope items. Then:

```
mcp__Claude_Browser__navigate   url: "<filter url>"
mcp__Claude_Browser__find       query: "Export (Filtered)"   -> click its ref with mcp__Claude_Browser__computer left_click
mcp__Claude_Browser__computer   action: wait, duration: 2
mcp__Claude_Browser__find       query: "filtered tasks"      -> "<N> filtered tasks"; N must be at least the in-scope count
mcp__Claude_Browser__find       query: "Generate"            -> click its ref
```

The button reads **Export (Filtered)** only when the filter took; "Export
(All)" means it did not (signed out, or the page reloaded): navigate to the
filter url again. If "filtered tasks" is not found after the click, the panel
did not open (the list was still loading): wait 3 seconds, `find` the button
again and click it once more (field result 2026-10-06). N can exceed the scope (another walk on the same day); the
clip extractor takes only the report's items. N below the scope count means
the window is wrong: export with "Export (All)" instead. A scope with no pin
dates (`task_report_filter.py` exits nonzero) also exports all.

**Leave every option in the panel at its default and click by `ref` only.**
The defaults (PDF, sorted by ID, photos included, every task detail) are what
the pipeline reads. Page size starts blank and comes out US Letter;
`extract_sheet_clips.py` reads A4 as well, so never touch it. **Never fill
"Email to"**: it emails the report to whoever is named. Never click inside the
panel by coordinate: it is a scrolling panel, and on 2026-10-01 a coordinate
click meant for the page size unticked a task-detail box instead. Never type
into the Filters panel either: the filter url sets it.

One export per run. If this run already started one, reuse its staple link.

## 4. Note the staple link

The panel switches to "Generating report" with a **Shareable Link** to the
report's own page, `https://app.plangrid.com/projects/<uid>/staple/<report id>`.
Read it and the report's name with `mcp__Claude_Browser__javascript_tool`
(action `javascript_exec`), pasted as is:

```js
await (async () => {
  for (let i = 0; i < 50; i++) {
    const link = [...document.querySelectorAll('input')].map(e => e.value).find(v => /\/staple\//.test(v));
    if (link) {
      const m = document.body.innerText.match(/['‘"]([^'’"\n]+)['’"] will be available/);
      return {staple: link, name: m ? m[1] : ''};
    }
    await new Promise(r => setTimeout(r, 200));
  }
  return {staple: null, page: document.body.innerText.slice(0, 300)};
})()
```

Then `navigate` the tab to the staple link. Leaving the panel does not stop
the export. Carry on with the run.

If the panel closed before the link was read: `navigate` to
`https://app.plangrid.com/projects/<uid>/issues/reports`. The newest row is
the export ("PlanGrid Task Report - <today>"). Its **Share** button shows the
same staple link. **Never click Save there**: it downloads to the user's own
machine behind a Save dialog they have to answer, and the sandbox cannot see
the file.

## 5. Collect: poll the staple page, then catch the download link

On the staple tab, run this with `javascript_tool`, pasted as is:

```js
await (async () => {
  const text = document.body.innerText;
  const title = (text.match(/PlanGrid Task Report[^\n]*|[^\n]*Report - [A-Z][a-z]{2} \d{1,2}, \d{4}/) || [''])[0].trim();
  const btn = [...document.querySelectorAll('button')].find(b => /^\s*Download\s*$/.test(b.innerText));
  if (!btn) return {state: /Generating/i.test(text) ? 'generating' : 'unexpected', title, page: text.slice(0, 300)};
  let link = null;
  const realOpen = window.open;
  window.open = (u) => { link = String(u); return null; };
  btn.click();
  for (let i = 0; i < 50 && !link; i++) await new Promise(r => setTimeout(r, 100));
  window.open = realOpen;
  return link ? {state: 'ready', title, link} : {state: 'no-link', title, page: text.slice(0, 300)};
})()
```

- `generating`: `mcp__Claude_Browser__computer` `wait` 10 seconds (the
  longest one wait allows), three waits per round, then run it again. The
  page updates itself; no reload. Stop at the budget in the table above.
  (Tasks > Reports shows the same export as "Generating: N%" if you want a
  progress figure for the status line.)
- `ready`: `link` is a signed download link to
  `plangrid-reports-prod-reportsresults-19fdmf8y8pfpb.s3.amazonaws.com`, good
  for 30 days. Go to step 6.
- `unexpected` or `no-link`: `navigate` to the staple link once and run it
  again; the same answer twice is a skip with the page text as the reason.

Why the snippet, not a click: the Download button opens the file in a new
tab, which the browser pane blocks when the model clicks, and a `navigate` to
the link saves it to the user's Downloads folder behind a Save dialog. The
snippet reads the link the button was about to open and opens nothing.

**The link is a credential for that one PDF.** Pass it to the script and
nowhere else: never in a message to the user, a file, `PROCESS-LOG.md`, or a
worker prompt.

## 6. Fetch it into the workspace

From `_pipeline/`, the link exactly as the snippet returned it, in single
quotes:

```bash
bash scripts/fetch_task_report.sh '<link>' --staple '<staple link>' --report-name '<title>'
```

It saves `../<report name>.pdf` beside `_pipeline/`, checks it is a complete
PDF, prints one line, and writes `../task_report_route.json`, which
`run_record.py` turns into the **Task Report route** row of `PROCESS-LOG.md`.
Exit 0: done, the next `run_pipeline.sh` pass uses it.

Exit nonzero: the run carries on without clips. The script has recorded the
fallback and prints the reason:

- **could not connect / refused before S3**: the sandbox's egress allowlist
  does not include the host. File it with `request_egress_allow`
  (error-reporting skill) naming the host it prints; do not retry.
- **expired**: run the step 5 snippet again for a fresh link, fetch once more.
- **cut or retyped**: the link was not passed exactly; fetch once more with
  the snippet's value.

## 7. Record a skip

Whenever the export did not happen or did not finish in budget:

```bash
bash scripts/fetch_task_report.sh --skipped "<reason>" [--staple '<staple link>'] [--report-name '<title>']
```

The finish list then says where the report is waiting in PlanGrid (Tasks >
Reports, by name) and how to add it later (`update_report.py --task-report`).
The final message says it in one line, with the reason.

Next: back to `reference/run-order.md`, where you left it.
