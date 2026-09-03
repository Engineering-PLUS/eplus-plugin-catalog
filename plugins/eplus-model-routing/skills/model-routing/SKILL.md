---
name: model-routing
description: Use whenever the "Model:" line in your env block names Opus or Fable, whenever a [model-routing] note appears in context, before any multi-step task, and whenever the user asks about models, speed, or cost. Teaches an expensive main thread to keep itself to decisions and hand the work to the sonnet-standard and haiku-fast workers, with the real cost order and the EPLUS rule that routing is by difficulty AND stakes.
---

# Model routing: keep the expensive thread thin

Every message on this deployment is billed, and the main thread often runs on
Opus or Fable, the two most expensive tiers. This skill moves work off that
thread. Two workers are available as subagents; each runs on a cheaper model
in its own context and returns a compact result.

## Step 1: read your own env block

Find the `Model:` line in the env block of your instructions.
- **Opus or Fable**: you are the expensive thread. Everything below applies.
  Your job is to decide, to talk to the user, to review, and to hand work
  down. You do not read documents, run loops, or draft prose yourself.
- **Sonnet or Haiku**: delegation is about context hygiene, not price. Use
  the workers for verbose work; otherwise do the task.

## The cost order (cheapest first)

| Runs as | Model | Approximate cost per 1M tokens (in / out) | Role |
|---|---|---|---|
| `haiku-fast` worker | Haiku 4.5 | $1 / $5 | mechanical tasks; 128K context, keep inputs small |
| `sonnet-standard` worker | Sonnet 5 | $2 / $10 | the bulk of real work |
| main thread | Opus 5 | $5 / $25 | decisions, review, the final answer |
| main thread | Fable 5 | $10 / $50 | the most expensive; decisions only |

Fable is roughly twice Opus and five times Sonnet. There is no Opus or Fable
worker on purpose: an expensive main thread pushes work down, never sideways.
Prices are approximate list rates; the ratios are what matter.

## The two things that actually cost money

1. **Every tool call from the main thread re-reads the whole context.** A
   measured Cowork session carried about 43k tokens of fixed context before
   the task added anything and paid it again on every call. A run with 150
   tool calls on Opus pays that block 150 times at the Opus rate. So: batch
   shell commands into one call, never read large files in this thread, never
   loop over files here. Hand the loop to a worker.
2. **Context that grows never shrinks.** Every file read, tool dump, and
   research sweep that lands in this thread is re-sent on every later turn,
   and past about 200K tokens the input is billed at a premium tier. Workers
   discard their context when they return; this thread keeps everything.

## What to delegate, and to whom

Route on **difficulty and stakes**, never on difficulty alone.

| Work | Route |
|---|---|
| Reformatting, extraction of fields, classification, tagging, list cleanup, renames, simple transforms, checking whether files or strings exist, reading a small file for specific values | `haiku-fast` |
| Reading or summarizing documents, research sweeps, corpus lookups | `sonnet-standard` |
| Drafting emails, memos, summaries, report text | `sonnet-standard` |
| Coding, scripts, data transforms with logic, structured data | `sonnet-standard` |
| Any loop over many files or many tool calls | `sonnet-standard` (which may push mechanical parts to `haiku-fast`) |
| Genuinely hard, ambiguous, or novel reasoning | yourself, but only after a worker has gathered the material |
| Anything client-facing, any technical determination, any number or code section that must be right, anything that commits the firm | draft on `sonnet-standard`, then **you review it** before it goes out |
| A quick, low-stakes answer you can give in a sentence | answer it yourself |
| Talking to the user, choosing between options, the final answer | yourself |

A task can be easy and high-stakes at once. "Rewrite this email" is a Sonnet
job; if the email states a technical position to a client, you still read the
draft with a reviewer's eye before it goes out: technical accuracy, every
number and code section, anything that overcommits the firm, tone. The stakes
decide, not the word "email".

## How to hand work down

- Give the worker everything it needs in the prompt: the material or the file
  paths, the format you want back, and the constraints. It cannot ask you
  anything.
- Ask for a result, not a plan. Both workers return a fixed shape. Read the
  `Stakes` line from `sonnet-standard` and the `Escalate` line from
  `haiku-fast` and act on them.
- Resume rather than respawn. A follow-up on work a worker already did goes
  back to that worker, whose context already holds the material.
- Run independent workers in parallel, at most three at a time.
- Never spawn a worker on Opus or Fable. The spawn gate will stop and ask if
  you try; that prompt is correct behavior.
- If a spawn fails because the model alias is blocked on this fleet, tell the
  user in one line. Do not fall back silently to doing the work yourself.

## When the user asks about models

Explain in plain language: Haiku is the fastest and cheapest, good for
mechanical work; Sonnet is the balanced, low-cost default for real work; Opus
is more capable and more expensive; Fable is the most capable and by far the
most expensive, so a session running on it should hand nearly all of its work
down. Costs are real per message here; the goal is the cheapest model that
meets the task's difficulty and its stakes.
