---
description: TEMPORARY test aid for eplus-model-routing. Reports which model this session runs on and whether the routing hook fired. One line, no tools.
argument-hint: (no arguments)
---

Reply with exactly two lines and nothing else. Do not use any tool, do not
load any skill.

Line 1: `Model: ` followed by the value on the `Model:` line of your env block,
verbatim.

Line 2: `Routing note: ` followed by `received` if a `[model-routing]` note
appeared in your context for this prompt, otherwise `not received`.
