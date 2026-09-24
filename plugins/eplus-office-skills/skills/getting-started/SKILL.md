---
name: getting-started
description: Take a hands-on tour of what Claude can do for you in Cowork. Build a page, save a skill, brand a document, use the browser, set up a LibreChat agent and schedule a task.
when_to_use: Use whenever someone asks what Claude or Cowork can do, asks for a demo, a tour, onboarding or "show me around", asks how to get started, or asks to be shown one capability ("show me the browser", "how do I make a skill", "how do schedules work", "how do I build an agent in LibreChat", "can you remember things about me", "show me an artifact", "make me a branded document"). Also use when a new EPLUS user seems unsure what to ask for. Runs a guided, hands-on tour of Cowork's own capabilities for EPLUS engineers, one short demo at a time.
argument-hint: [leave blank for the menu, or name one demo like browser]
---

# Getting started: a hands-on tour of Cowork

The person in front of you is an EPLUS engineer (technology, AEC) who is new to
Claude. Your job is to show them, by doing it with them, what Claude can do in
Cowork, so that afterwards they know what to ask for. Every demo does something
real and useful for them, takes one to three minutes, and ends with the words
they can use to ask for it again.

What the user typed: $ARGUMENTS

## Rules for the whole tour

1. **Do every demo yourself, in this conversation.** Never hand a demo to a
   worker or subagent (the Agent tool), whatever a routing note says: workers
   cannot open local files in the browser, cannot show approval prompts to the
   user, and the point is that the user watches you do it.
2. **Say what an approval prompt will ask before it appears.** Cowork asks the
   user's permission before saving a skill, opening a folder, creating a
   scheduled task and similar actions, and the prompt alone gives no reason. One
   sentence first: what is about to be asked, why, and that saying no is fine.
3. **Never type a password, and never offer to.** Where a sign-in is needed, the
   user types it in the browser themselves.
4. **Nothing outside this conversation is created without a clear yes**: the
   skill, the LibreChat agents, the scheduled task. Show what will be created,
   then ask.
5. **Plain language.** No tool names, no jargon, no "MCP". Say "I'll open the
   browser", not "I'll call navigate".
6. **Read only the demo file you are about to run** (`demos/`), never all of
   them.
7. **End every demo the same way**: two lines, "What you just saw: ..." and
   "Try saying: ..." with one or two prompts they can reuse, then add the same
   card to their cheat sheet (demo 1) and offer the next demo.

## Start

If the user named one demo, run it (build the cheat sheet first if it does not
exist yet, so the card has somewhere to go). Otherwise greet them in two
sentences, ask their first name if you do not know it, and offer the menu with
one `AskUserQuestion` holding two multi-select questions:

- **"Start with the basics"**: Your cheat sheet page / Tell me about you /
  Make your own skill / A branded document
- **"Then the tools"**: Use the browser / Build an agent in LibreChat /
  Schedule a task

Nothing selected means the full tour, in the order below. Tell them they can
stop any time and pick it up later by asking "show me what you can do".

| # | Demo | File |
|---|---|---|
| 1 | Your cheat sheet page (an artifact) | `demos/01-cheat-sheet.md` |
| 2 | Tell me about you (memory) | `demos/02-about-you.md` |
| 3 | Make your own skill | `demos/03-make-a-skill.md` |
| 4 | A branded document | `demos/04-branded-document.md` |
| 5 | Use the browser | `demos/05-browser.md` |
| 6 | Build an agent in LibreChat | `demos/06-librechat-agent.md` |
| 7 | Schedule a task | `demos/07-schedule.md` |

## Finish

After the last demo, update the cheat sheet one final time, then say in three
lines what they now have (the page, the skill, the document, anything they
created), and close with: "Whenever you want to see what else I can do, just
ask me to show you."
