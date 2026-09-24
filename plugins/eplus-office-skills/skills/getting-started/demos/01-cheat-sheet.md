# Demo 1: your cheat sheet page (an artifact)

**What it shows:** Claude can build a live page (an artifact) that opens beside
the chat and can be updated as you go. The page becomes their take-away: one
card per demo with the words to ask for it again.

## Steps

1. Say: "First I'll build you a page that collects everything we try today, so
   you have a cheat sheet at the end."
2. Read `assets/cheatsheet.html` (in this skill's folder). Fill in
   `{{FIRST_NAME}}` and `{{DATE}}` (today, e.g. September 24, 2026). Leave the
   `<!-- CARDS -->` marker in place and add this demo's card just above it,
   copied from the card template in the file's comment:
   - title "Pages like this one", what "I can build live pages, dashboards and
     calculators that open beside our chat.", try "Make me a page that ..."
3. Publish it with Cowork's artifact tool (`create_artifact`), titled
   "{{FIRST_NAME}}'s Cowork cheat sheet". Keep the artifact's id; every later
   demo updates this same page with `update_artifact` by adding one card above
   the marker. Never create a second cheat sheet.
4. Artifact limits in Cowork: one self-contained HTML file, no browser storage
   (no localStorage or sessionStorage), scripts only from cdnjs. The template
   already follows these; keep it that way.

## Close

- What you just saw: "I built a page that lives next to our chat and keeps
  updating as we go."
- Try saying: "Make me a page that tracks ..." / "Turn this table into a
  dashboard."
