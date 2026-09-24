# Demo 1: your cheat sheet page (an artifact)

**What it shows:** Claude can build a page (an artifact) that opens beside the
chat. This one is their take-away: a printable EPLUS-branded cheat sheet with
what to ask for, the slash commands, what to do when something goes wrong,
lines for their own notes, and a card for every demo they try.

The page is built by a script, never typed out: the logos are inlined images
and retyping them would be slow and error-prone.

## Steps

1. Say: "First I'll make you a cheat sheet you can keep and print. I'll add
   everything we try today to it."
2. In bash, from the outputs folder (your working folder), write the first card
   and build the page. `S` is this skill's folder as bash sees it:
   `/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-office-skills/skills/eplus-getting-started`
   (`ls /sessions` gives `<session>`).

   ```bash
   cat > cheatsheet-cards.json <<'EOF'
   [{"title": "Pages like this one", "what": "I can build live pages, dashboards and calculators that open beside our chat.", "try": "Make me a page that tracks ..."}]
   EOF
   python3 "$S/scripts/build_cheatsheet.py" --name "<first name>" \
       --out "Cowork-Cheat-Sheet-<FirstName>.html" --cards cheatsheet-cards.json \
       --skill "<name>=<one-line description>" ...
   ```

   Pass one `--skill` for each EPLUS skill in the user's `/` menu, with its
   short description: every skill in your skill list from an `eplus-*` plugin
   **except** the background ones users never pick (model-routing,
   workflow-packager, plangrid-extraction, error-reporting). Include
   `eplus-getting-started` itself. The built-in Anthropic skills are already on
   the page; do not pass them.
3. Show it with Cowork's artifact tool (`create_artifact`), titled
   "<first name>'s Claude cheat sheet", using that file: if the tool takes a
   file path, give it the path; if it takes the HTML text, read the file and
   pass it unchanged. Then also show the file itself with `present_files`, and
   tell them: "Open that file in your browser and use Print this page (or
   Ctrl+P) to print it."
4. Every later demo appends its card to `cheatsheet-cards.json` (one entry,
   same three fields). Do not rebuild or republish the page after each demo;
   that happens once, at the end of the tour (SKILL.md, Finish), or whenever
   the user asks to see it.

## Close

- What you just saw: "I built a page that opens next to our chat. It's yours
  to keep and print, and I'll add what we try today."
- Try saying: "Make me a page that tracks ..." / "Turn this table into a
  dashboard."
