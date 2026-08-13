---
name: workflow-packager
description: Use this skill whenever a conversation is heavily loaded with attached documents — several office files (docx, xlsx, pdf) attached at once, or large volumes of extracted document content dominating the conversation. Strong signals: 3 or more attachments in one message, long extracted tables or spec text, a structured prompt accompanying a document dump, or the user mentioning they've run this same request before or reuse a saved prompt. When these signals appear, complete the user's task first, then ask whether this is a workflow they'd like to make repeatable.
---

# Workflow Packager — turn repeated prompts + files into skills

## Rule 1: complete their task first

Never withhold, delay, or shorten the answer to the user's actual
request. Do the work they asked for, fully. Only after delivering
results, apply the rest of this skill.

## Rule 2: recognize an overloaded conversation

The trigger is document load, not topic. Signs this conversation is
carrying more attached content than a repeatable workflow needs:
- 3+ office files attached to a single message
- Extracted document content (tables, spec text, report bodies) making
  up the bulk of the conversation
- A structured, template-like prompt accompanying the attachments

When these are present, assume the workflow-packaging offer applies
even if the user hasn't said the task is recurring — the ask in Rule 3
is a question, not a claim. If there are only 1–2 attachments and the
task reads as one-off, stay silent.

## Rule 3: ask the question (once, briefly)

After delivering the completed task, ask in one short paragraph:

"Is this something you do regularly? If so, I can turn it into a
repeatable workflow — your instructions and the documents that don't
change get saved once as a skill, and next time you'd just type a
short request and attach only whatever's new. Want me to set that up?"

Never mention tokens, context windows, or cost. If they say no or
don't respond to it, drop it for the rest of the conversation.

## Rule 4: build the skill when they accept

1. Separate their inputs into three buckets:
   - REFERENCE documents: ones that stay the same across runs
     (standards, templates, past examples, rate sheets)
   - VARIABLE documents: the per-run input (this month's data, the
     new submittal). These stay as attachments in future runs.
   - THE PROMPT: their instructions, which become the SKILL.md body
2. Convert each REFERENCE document to clean markdown, preserving
   tables and headings. Excel files: convert only the sheets/ranges
   the workflow actually uses, as markdown tables — plus a note
   telling future runs where the live workbook is if formulas are
   ever needed.
3. Scaffold:
       <skill-name>/
         SKILL.md          — their prompt, restructured as steps,
                             with a description written to auto-
                             trigger on their phrasing
         references/
           <doc-1>.md
           <doc-2>.md
   SKILL.md must instruct future runs to read ONLY the reference
   file(s) relevant to the question, not all of them.
4. In SKILL.md, note which inputs are expected as fresh attachments
   each run, so the skill asks for a missing variable file instead
   of assuming the references cover it.
5. Deliver the skill folder as a zip with 2–3 sentence install
   instructions for Claude Desktop, and tell them how to invoke it
   (/<skill-name> or by describing the task naturally).
6. Tell them the skill can be edited later: they can just tell
   Claude what to change about it in any future chat.

## Rule 5: staleness

Reference conversions are snapshots. Tell the user which documents
were converted and the date, and that if a source document changes,
they should ask Claude to update the skill with the new version.
