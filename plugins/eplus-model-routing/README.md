# eplus-model-routing

Cost control for the Cowork fleet. On this paid 3P deployment the main thread
usually runs on Opus or Fable, the two most expensive tiers, and a single day
has cost hundreds of dollars with no delegation at all. This plugin detects
when a session is on an expensive tier, puts the routing rule in context at
that moment, and ships two cheap workers, Sonnet and Haiku, to hand work to.
There is no Opus or Fable worker on purpose: an expensive thread pushes work
down, never sideways. Hard reasoning and review of client-facing output stay
on the main thread, which is already the capable model.

## How detection works

**Field result (2026-09-03, two Cowork exports):** the SessionStart payload
carries no `model` field, so step 1 below never fires on Cowork today. The
first prompt of every session gets the env-check note; from the second prompt
on, the transcript names the model and detection is exact. The model was
observed reading its own `Model:` line correctly, so the first-prompt note
is reliable. Cost of that fallback on a Sonnet or Haiku session: about 80
tokens once.


The desktop app tells the model which model it is in the env block of its
instructions (`Model: claude-opus-5[1m]` and similar). Hooks cannot see that
text; they see only their JSON payload. Two payloads carry the model:

1. **SessionStart** includes a `model` field. `note-model.ps1` records it to a
   per-session file and emits nothing, so this costs zero context tokens.
2. **UserPromptSubmit** does not, so `route-check.ps1` reads the recorded
   value, falls back to the last assistant message's model in the transcript
   tail, and otherwise treats the tier as unknown.

| Detected tier | What route-check injects on the prompt |
|---|---|
| Opus or Fable | first prompt: the full digest, about 110 tokens; later prompts: a one-line reminder, about 25 tokens. Both tell the model to confirm against its own env `Model:` line. Subagent hand-backs and task notifications get nothing (see below). |
| Sonnet or Haiku | nothing |
| Unknown | a one-line instruction to check the env `Model:` line and, if it names Opus or Fable, read the skill |

## Contents

| Component | Path | Purpose |
|---|---|---|
| Skill | `skills/model-routing/SKILL.md` | The policy: read your env Model line, the cost order, the two real cost drivers (tool calls re-read context; context never shrinks), what to delegate to which worker, how to hand work down, how to talk about models. The cost table lives here only. |
| Worker | `agents/sonnet-standard.md` | Sonnet 5. Research, reading, drafting, coding, loops. Finishes the task, returns `Result / Assumptions / Gaps / Stakes`, never asks questions. May push mechanical sub-steps to haiku-fast. |
| Worker | `agents/haiku-fast.md` | Haiku 4.5, 128K context. Reformatting, extraction, classification, list work, small file checks. Returns `Result / Assumptions / Gaps / Escalate`. |
| Hook | `scripts/note-model.ps1` | SessionStart: records the payload model to `%TEMP%\eplus-model-routing\<session>\model.txt` (and plugin data when set), plus the payload's key names as a diagnostic; emits nothing. |
| Hook | `scripts/route-check.ps1` | UserPromptSubmit: tier detection and the injection above. |
| Hook | `scripts/spawn-gate.ps1` | PreToolUse on Agent: logs every spawn to `routing.log`; returns `ask` when a spawn requests Opus or Fable. |
| Command | `commands/model-check.md` | Temporary test aid: prints the env model line and whether the routing note arrived. Remove before wide rollout. |
| Command | `commands/routing-test.md` | Temporary scripted test: detection, one haiku-fast spawn, one sonnet-standard spawn, one gated Opus spawn attempt, five-row results table. Remove before wide rollout. |

Switches: `EPLUS_NO_MODEL_ROUTING=1` disables recording and injection;
`EPLUS_ALLOW_EXPENSIVE_SPAWN=1` disables the gate but keeps the spawn log.

### Hook wiring notes

The prose that used to sit in a top-level `description` field of
`hooks/hooks.json` lives here: the plugins reference documents no such field,
so it is kept out of the file the app parses.

- **Three single-PowerShell wirings.** (1) `note-model.ps1` on `SessionStart`
  records the payload's `model` field to `%TEMP%\eplus-model-routing\<session_id>\model.txt`
  (and plugin data when set). Field result 2026-09-03: Cowork's SessionStart
  payload has no `model` field (`session_id`, `transcript_path`, `cwd`,
  `hook_event_name`, `source` only), so on Cowork the first prompt of a
  session always gets the env-check note and every later prompt is detected
  from the transcript; the script emits nothing (zero context tokens; one
  short launch per session open, resume, or compaction). (2) `route-check.ps1`
  on `UserPromptSubmit` reads that file (falling back to the transcript tail,
  then to unknown) and injects a short `additionalContext` only when the
  session is on Opus or Fable or the tier is unknown; the note always tells the
  model to confirm against the `Model:` line in its own env block. First
  injection per session is the full digest (~110 tokens), later ones a
  one-line reminder (~25 tokens); on Sonnet or Haiku nothing is injected.
  Machine-generated prompts are skipped: on Cowork each subagent's
  `SubagentHandback` reaches `UserPromptSubmit` as a queued prompt starting
  with `<agent-message from="...">` (export of 2026-09-23: three parallel
  workers produced three reminders in two seconds, mid-turn), so a prompt
  starting with `<agent-message` or `<task-notification` gets no note.
  (3) `spawn-gate.ps1` on `PreToolUse:Agent` logs every spawn's
  `subagent_type` and `model` to `routing.log` under `%TEMP%\eplus-model-routing`
  (and plugin data when set) and returns `permissionDecision: "ask"` when a
  spawn requests Opus or Fable (field-verified 2026-09-03: the approval prompt
  appears in Cowork under auto mode), since the only workers here run on
  Sonnet and Haiku.
- **Form.** Every entry uses `"shell": "powershell"` with a direct
  `& "${CLAUDE_PLUGIN_ROOT}\scripts\<name>.ps1"` call, adopted 2026-09-03 after
  a field A/B in the same export: the app's own PowerShell runs the script in
  one process (540 ms measured) instead of launching a second `powershell.exe`
  (907 ms). The single-launch form is the standard for this catalog. All
  scripts always exit 0; decisions travel in the JSON body.

Surfaces: through the exports of 2026-09-09 plugin hooks loaded only in
Cowork sessions, never in the Chat tab. The desktop app release of 2026-09-11
runs organization-plugin hooks in Chat too, matching Cowork and Code, so
expect the same per-prompt route-check spawn and the spawn gate in Chat
sessions from that build on. Not yet confirmed from a Chat export.

## Worker output shapes

Both workers are written for models that drift: numbered rules first, no
questions allowed, a fixed reply shape, and an explicit escalation line
instead of "trying harder". `sonnet-standard` flags stakes (`review before it
goes out`) rather than judging them, so the main thread always knows what to
read before it leaves the firm. `haiku-fast` escalates to `sonnet-standard`
when a task turns out to need writing or judgment.

## Testing

Fastest path: run `/eplus-model-routing:routing-test` once on an Opus or
Fable session. **Step 4 raises an approval prompt in the Cowork UI; that prompt
is the test, so read it and decline it.** Then export. The
five-row table plus the export's hook attachments and `routing.log` cover
every mechanism. The manual steps below do the same thing piecewise.

1. Run `/eplus-model-routing:model-check` as the first prompt of a session.
   Line 1 shows the env model. Line 2 should say `received` on an Opus or
   Fable session and `not received` on a Sonnet session, which proves the
   SessionStart recording worked. If it says `received` on Sonnet, the
   SessionStart payload did not carry `model` and the hook fell back to the
   unknown variant.
2. Run it again as a second prompt; on Opus or Fable the note is the short
   reminder.
3. Give a real multi-step task on an Opus or Fable session and export. The
   export's `routing.log` should show `sonnet-standard` and `haiku-fast`
   spawns; the hook attachments show the injected notes.
4. Ask a worker to run on Opus by name. Expect the gate's approval prompt in
   the UI (field-verified 2026-09-03). The model cannot see that prompt, so
   only the person at the keyboard can report it.

Models are referenced by alias (`sonnet`, `haiku`). If the fleet's allowed
models policy blocks an alias, the spawn fails at Agent-tool time; the skill
tells the model to say so rather than doing the work itself silently.

## Versioning

Bump `version` in `.claude-plugin/plugin.json` in every release; the fleet
only syncs on a bump.
