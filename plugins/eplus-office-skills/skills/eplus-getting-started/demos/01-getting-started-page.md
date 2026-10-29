# Demo 1: your getting-started page (always, right after demo 0)

**What it shows:** Claude can build a page and open it in the built-in
browser. This one is their take-away and the tour's home base: an
EPLUS-branded guide with what to ask for, every connector and its tools, the
EPLUS skills in their / menu, what to do when something goes wrong, and a card
for every demo they try. It stays open in its own browser tab for the whole
tour.

The page is built by a script, never typed out: the logos and the connector
data are inlined and retyping them would be slow and error-prone. It is not an
artifact: do not publish it with the artifact tools.

## Steps

1. Say: "First I'll make you a getting-started page and open it in the
   browser. I'll add everything we try today to it."
2. In bash, from the outputs folder (your working folder), write the first card
   and build the page. `S` is this skill's folder as bash sees it:
   `/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-office-skills/skills/eplus-getting-started`
   (`ls /sessions` gives `<session>`).

   ```bash
   cat > cheatsheet-cards.json <<'EOF'
   [{"title": "Your getting-started page", "what": "I can build pages and open them in the browser beside our chat.", "try": "Make me a page that tracks ..."}]
   EOF
   python3 "$S/scripts/build_page.py" --name "<first name>" \
       --out "Claude-Guide-<FirstName>.html" --cards cheatsheet-cards.json
   ```

   When demo 0 ran, its "Your accounts" card goes first in the file, before
   this one (same three fields). Without a name (demo 0 could not read the
   profile), leave `--name` out and
   write `Claude-Guide.html`. The / menu, the connectors and the help come from
   the skill's own files; never pass them in.
3. Open it in the built-in browser, in a new tab:
   - The file's Windows path is the outputs folder's Windows path from your
     environment block plus `\Claude-Guide-<FirstName>.html` (the same path
     demo 0 uses for the video). Turn it into a file address: `file:///`, then
     the path with every `\` as `/` and every space as `%20`, for example
     `file:///C:/Users/jdoe/Documents/Claude/Claude-Guide-Jane.html`.
   - Open that address with the browser's `preview_start` (it opens a new
     tab). Keep the tab id it returns: this is **the guide tab**. Nothing else
     ever loads in the guide tab; every other site in the tour opens in a new
     tab.
   - Call `tabs_context`. Its last line says whether the browser is showing.
     If it is hidden or not open, say: "Your page is open in the browser.
     Press Ctrl+Shift+B, or the browser button, to see it." Wait five seconds
     and carry on.
   - **If the browser refuses the file** (an error instead of a tab), do not
     retry and do not make an artifact. Show the file with `present_files`
     (the Windows path above) and say: "Open that file and it opens in your
     web browser." Carry on with the tour; at the end the same file is
     rebuilt and shown again.
4. Say: "This is yours to keep. The map in the middle shows everything I'm
   connected to; click any of them to see its tools. Print it with the Print
   button at the top."
5. Every later demo appends its card to `cheatsheet-cards.json` (one entry,
   same three fields). Do not rebuild the page after each demo; that happens
   once, at the end of the tour (SKILL.md, Finish), or whenever the user asks
   to see it, each time with the step 2 command, then `navigate` the guide
   tab to the same file address so it reloads (or `present_files` again if
   the browser refused it).

## Close

- What you just saw: "I built a page and opened it in the browser. It's yours
  to keep and print, and I'll add what we try today."
- Try saying: "Make me a page that tracks ..." / "Turn this table into a
  dashboard."
