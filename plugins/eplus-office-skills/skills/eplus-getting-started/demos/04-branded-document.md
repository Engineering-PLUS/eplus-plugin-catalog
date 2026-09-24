# Demo 4: a branded document

**What it shows:** skills working together. The `eplus-branding` skill knows
the EPLUS colors, fonts and logos, the Word skill knows how to build a
document, and Claude combines them into a finished, editable deliverable.

## Steps

1. Say: "Now I'll make you a real Word document with our branding, so you can
   see how skills stack."
2. Load the `eplus-branding` skill and follow it (Arial, Primary Blue headings,
   the EPLUS logo from its assets). Then build a one-page `.docx` with the
   built-in Word (docx) skill:
   - Title: "Getting started with Claude, {{first name}}"
   - A short "About you" block from demo 2 (skip it if they skipped demo 2)
   - "What Claude can do for you": one line per demo they have seen so far,
     each with its "Try saying" prompt
   - Footer: "Engineering Plus" and today's date
3. Save it in the session outputs folder as
   `Getting-Started-{{FirstName}}.docx` and show it with `present_files` so it
   appears as a file card they can open.
4. Point out the three parts: "The branding skill picked the colors and logo,
   the Word skill built the file, and it's a normal Word document you can
   edit."
5. Add the card to the cheat sheet: title "Branded documents", what "Ask for a
   report, memo or one-pager and I'll build it in EPLUS branding as Word,
   PowerPoint, Excel or PDF.", try "Make a one-page memo about ... in EPLUS
   branding"

## Close

- What you just saw: "Two skills, branding and Word, built one finished
  document."
- Try saying: "Make a memo about ... with our branding" / "Turn this into a
  PowerPoint in EPLUS style."
