---
name: eplus-getting-started
description: The EPLUS tour of Claude in the desktop app. A hands-on look at what Claude can do for you. Connect your accounts, get your getting-started page in the browser, save a skill, brand a document, use the browser, set up a LibreChat agent, schedule a task and watch the training video library.
when_to_use: Use whenever someone asks what Claude can do, asks for a demo, a tour, onboarding or "show me around", asks how to get started, or asks to be shown one capability ("show me the browser", "how do I make a skill", "how do schedules work", "how do I build an agent in LibreChat", "find me a training video", "can you remember things about me", "show me an artifact", "make me a branded document"). Also use when a new EPLUS user seems unsure what to ask for. Runs a guided, hands-on tour of Claude's own capabilities for EPLUS engineers, one short demo at a time.
argument-hint: [leave blank for the menu, or name one demo like browser]
---

# EPLUS getting started: a hands-on tour of Claude

The person in front of you is an EPLUS engineer (technology, AEC) who is new to
Claude. Your job is to show them, by doing it with them, what Claude can do in
the desktop app, so that afterwards they know what to ask for. Every demo does something
real and useful for them, takes one to three minutes, and ends with the words
they can use to ask for it again.

What the user typed: $ARGUMENTS

## Rules for the whole tour

1. **Do every demo yourself, in this conversation.** Never hand a demo to a
   worker or subagent (the Agent tool), whatever a routing note says: workers
   cannot open local files in the browser, cannot show approval prompts to the
   user, and the point is that the user watches you do it.
2. **Say what an approval prompt will ask before it appears.** The app asks the
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
7. **End every demo the same way, out loud.** Two lines in the chat, "What
   you just saw: ..." and "Try saying: ..." with one or two prompts they can
   reuse. They are never skipped, even when the next demo follows at once.
   Then append the demo's card to `cheatsheet-cards.json` (demo 1 explains)
   and start the next demo they picked in the same reply, with no question in
   between. Stop only when their list is done or they say stop. The user never
   has to type something just to keep the tour moving.
8. **Pace it for someone watching, not reading a log.** Before each thing they
   will see, one short sentence saying what is about to happen; then do it;
   then leave it on screen. In the browser that means a wait of about five
   seconds after every visible change, and never undoing a change they were
   meant to see sooner than eight seconds after making it. Between demos,
   the closing lines are the pause.
9. **Fix your own mistakes silently.** A tool error caused by a missing or
   wrong argument is yours: retry with it and say nothing about it. The user
   only hears about a problem when it changes what they get.

## Start

Greet them in two sentences, then run demo 0 (`demos/00-connect-accounts.md`)
before anything else, every time: it checks their Microsoft 365 account, gets
a first-time user signed in to the connectors, and gives you their name from
the Microsoft 365 profile (`get_me`). Never ask for their name: when Microsoft
365 is not signed in, demo 0 shows the sign-in card. The seat's login name is
a shorthand, never a first name: do not take it from there. If the profile
still cannot be read after the sign-in, carry on without a name (see demo 0,
step 5). Then run demo 1 (`demos/01-getting-started-page.md`), also every
time: it builds their getting-started page and opens it in the browser, so
they have it in front of them while they choose. Then, if the user named one
demo, run it. Otherwise offer the menu with one `AskUserQuestion` holding two
multi-select questions:

- **"Start with the basics"**: Tell me about you / Make your own skill /
  A branded document
- **"Then the tools"**: Use the browser / Build an agent in LibreChat /
  Schedule a task / Training videos

Nothing selected means the full tour, in the order below. Tell them they can
stop any time and pick it up later by asking "show me what you can do".

| # | Demo | File |
|---|---|---|
| 0 | Connect your accounts (always, first) | `demos/00-connect-accounts.md` |
| 1 | Your getting-started page, opened in the browser (always, second) | `demos/01-getting-started-page.md` |
| 2 | Tell me about you (memory) | `demos/02-about-you.md` |
| 3 | Make your own skill | `demos/03-make-a-skill.md` |
| 4 | A branded document | `demos/04-branded-document.md` |
| 5 | Use the browser | `demos/05-browser.md` |
| 6 | Build an agent in LibreChat | `demos/06-librechat-agent.md` |
| 7 | Schedule a task | `demos/07-schedule.md` |
| 8 | Training videos (the library plays in the chat) | `demos/08-video-library.md` |

## The guide tab

Their getting-started page lives in its own browser tab, the guide tab, from
demo 1 to the end. Every site the tour opens (the model viewer, LibreChat)
goes in a new tab with `preview_start`, never with `navigate` on the guide
tab, and every browser step passes the tab id it means. Do not publish the
page as an artifact: an artifact takes over the side panel and hides the
browser.

## Finish

After the last demo, rebuild the page with the same `build_page.py` command
as demo 1 (it now carries every card), `navigate` the guide tab to the same
file address so it reloads, and present the file with `present_files` so they
can keep and print it (demo 1, step 3). Then say in three lines what they now
have (the page, the skill, the document, anything they created) and close
with: "Whenever you want to see what else I can do, just ask me to show you."
