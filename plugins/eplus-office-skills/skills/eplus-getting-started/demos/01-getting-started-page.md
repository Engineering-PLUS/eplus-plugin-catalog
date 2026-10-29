# Demo 1: your getting-started page (always, right after demo 0)

**What it shows:** Claude can build a page and hand it over as a file. This
one is their take-away and the tour's home base: an EPLUS-branded guide with
what to ask for, every connector and its tools, the EPLUS skills in their /
menu, what to do when something goes wrong, and a card for every demo they
try. They open it in their own web browser and keep it beside the chat for the
whole tour.

The page is built by a script, never typed out: the logos and the connector
data are inlined and retyping them would be slow and error-prone. Two things
not to do with it:

- **Never open it in Claude's built-in browser.** It refuses local files
  ("opening local files is not available in this session", field result
  2026-10-29), so the call only shows the user an error.
- **Never publish it as an artifact.** An artifact takes over the side panel
  and hides the built-in browser the later demos use.

## Steps

1. Say: "First I'll make you a getting-started page. I'll add everything we
   try today to it."
2. In bash, from the outputs folder (your working folder), write the first card
   and build the page. `S` is this skill's folder as bash sees it:
   `/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-office-skills/skills/eplus-getting-started`
   (`ls /sessions` gives `<session>`).

   ```bash
   cat > cheatsheet-cards.json <<'EOF'
   [{"title": "Your getting-started page", "what": "I can build pages and files for you to keep, print and share.", "try": ["Make me a page that tracks ...", "Turn this table into a dashboard"]}]
   EOF
   python3 "$S/scripts/build_page.py" --name "<first name>" \
       --out "Claude-Guide-<FirstName>.html" --cards cheatsheet-cards.json
   ```

   Every card has three fields, and `try` is always a list with one prompt per
   entry, never several prompts joined in one string. When demo 0 ran, its
   "Your accounts" card goes first in the file, before this one. Without a
   name (demo 0 could not read the profile), leave `--name` out and write
   `Claude-Guide.html`. The / menu, the connectors and the help come from the
   skill's own files; never pass them in.
3. Hand it over with `present_files`, giving the outputs folder's Windows path
   from your environment block plus `\Claude-Guide-<FirstName>.html` (the same
   way demo 0 presents the video). Say: "Here's your page. Open it and it
   opens in your web browser; keep that window next to this one while we go."
4. Say: "It's yours to keep. The map in the middle shows everything I'm
   connected to; click any of them to see its tools. Print it with the Print
   button at the top."
5. Every later demo appends its card to `cheatsheet-cards.json` (one entry,
   same three fields). Do not rebuild the page after each demo; that happens
   once, at the end of the tour (SKILL.md, Finish), or whenever the user asks
   to see it, each time with the step 2 command, then `present_files` again
   and: "I've updated your page. Refresh it in your browser (F5) to see the
   new cards."

## Close

- What you just saw: "I built a page and handed it to you as a file. It's
  yours to keep and print, and I'll add what we try today."
- Try saying: "Make me a page that tracks ..." / "Turn this table into a
  dashboard."
