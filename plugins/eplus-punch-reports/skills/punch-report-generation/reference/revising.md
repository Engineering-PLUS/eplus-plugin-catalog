# Revising an existing report

Covers a revision round on a report that has already been delivered. Assumes a delivered
package (`.zip`) exists in the project folder and/or the user has a reviewed `.docx`;
the work happens in a fresh workspace unzipped from that package.

## Revising an existing report — the common case

Almost all real work is a revision (r2…r5 in one week on one project), not a
clean run from a pull, and the revision path has its own rules:

- **Re-run in a fresh workspace, never in the delivered copy.** Unzip the prior
  delivery package into a new workspace, refresh `_pipeline/scripts/` from this
  skill's `scripts/` (the package carries the scripts it was built with, which
  may be behind), run `bash scripts/install_deps.sh && bash scripts/smoke_test.sh`,
  work there, and deliver again with `package.py` under a **new package name**.
  The project folder stays read-only until that delivery, exactly as on a first
  run.
- **The reviewer's Word edits are the senior source.** Rebuilding from scratch
  discards them. To recover approved wording from a reviewed .docx, use
  `scripts/import_reviewed_docx.py` — **a PROTOTYPE that has not yet been run
  end to end as one program**; it was assembled from ad hoc code that recovered
  16 write-ups once. It matches embedded photos to normalised thumbnails by
  **32×32 greyscale pixel signature** — exact, unlike caption timestamps, which
  collide the moment two photos share a minute — and emits drafted entries with
  `"origin": "reviewer_final"`. It also reveals photos the reviewer silently
  deleted. Check every entry it writes against the reviewed document before
  rendering from it.
- **`origin: reviewer_final` and `origin: user_reviewed` text is untouchable.**
  `build_master.py` refuses to sanitize-rewrite it and fails loudly if it would
  have to; the voice guard does not apply to it. Fix source text explicitly or
  not at all.
- **Reviewer pin merges live in the judgment layer.** Record them as a `merges`
  block in `drafted_items.json` — `{"items": [...], "merges": [{"into": 22,
  "from": 23, "drop_photos": ["…"]}]}` — which `build_master.py` applies
  in-memory (photos folded in chronological order, deduped by uid, titles
  matching a `drop_photos` substring dropped, absorbed pin auto-omitted).
  Never mutate `items.json` to represent a human decision; a re-run of
  consolidate would erase it.
- **New site visits need their own Task Report export** for sheet clips (see
  Step 6 in `reference/build-data.md`); do not salvage clips from the previous render.
- Re-run the wording review (Step 3.5, `reference/drafting.md`) **only for new or changed items** — a
  revision must never re-ask questions the user already answered. Their
  previous answers are in `drafted_items.json` with `origin: user_reviewed`.


Next: `reference/drafting.md` for new or changed items only, then `reference/render.md` and `reference/verify-and-deliver.md`.
