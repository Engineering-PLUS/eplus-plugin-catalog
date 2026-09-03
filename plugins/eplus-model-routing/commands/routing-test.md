---
description: TEMPORARY scripted test of eplus-model-routing - detection, both workers, and the expensive-spawn gate. Minimal tokens. Remove before wide rollout.
argument-hint: (no arguments)
---

Run the model-routing smoke test. Follow the steps exactly, one tool call per
step, no clarifying questions, no task list, no prose between steps except
the step number. Do not load any skill and do not read any file.

**1. Detection.** Note two facts for the table: the value on the `Model:`
line of your env block, and whether a `[model-routing]` note appeared in
your context for this prompt.

**2. Haiku worker.** Spawn the `haiku-fast` agent (subagent type
`eplus-model-routing:haiku-fast`) with exactly this task:
"Return the word ok as the Result. Nothing else." Record PASS if the reply
contains `Result:` and `ok`, otherwise record the first line of the error.

**3. Sonnet worker.** Spawn the `sonnet-standard` agent (subagent type
`eplus-model-routing:sonnet-standard`) with exactly this task:
"Return the word ok as the Result and set Stakes to none." Record PASS if
the reply contains `Result:` and `Stakes: none`, otherwise the first line of
the error.

**4. Expensive spawn gate.** Attempt to spawn a `general-purpose` agent with
the model parameter set to `opus` and the task "Return the word ok." Expected:
an approval prompt appears before the spawn. If it does, decline it or, if
you cannot decline, record whatever happened. Record GATED if a prompt
appeared, NOT GATED if the agent ran without one, or the first line of the
error.

**5. Results.** Print exactly this table as your entire final message,
followed by one line: "Export this session now."

```
| # | Check | Result |
|---|---|---|
| 1a | env Model line | |
| 1b | routing note received | |
| 2 | haiku-fast spawn | |
| 3 | sonnet-standard spawn | |
| 4 | opus spawn gated | |
```
