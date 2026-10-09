# Demo 5: use the browser (runs on its own, in a fresh chat)

**What it shows:** Claude can open websites in the built-in browser, read
them, click through them, and hand the tab back to the user.

**Before anything:** if a page (artifact) has been built in this chat, do not
open the browser. Say: "The browser needs the side panel to itself. Start a
new chat and say: show me the browser." and stop. This demo is never part of
the tour (SKILL.md explains).

The demo site is the EPLUS model viewer (BIM model review). This is the only
address the tour opens, exactly as written, including the `?k=` part, which is
the share key that lets the page open without the passcode prompt (like an
Autodesk share link):

`https://models.eplus-ai.net/sgct?k=U3B0mgtXscVXItVIItQZJHepLbmRYMoD`

If the passcode page appears anyway, say the link is not working today and
skip to step 5 with a public site the user names. Never ask for or type a
passcode.

What is on the page (checked 2026-10-09): it opens on **HAC Design Large
Datahall**, 1,638 elements, 37.5 x 59.4 x 7.1 m.

- Top left: the model name, with **Elements** (count) and **Extent** (size in
  metres) under it, then a **Manage models** link. Do not open the model name
  (it is a picker) or Manage models (admin page): stay on this model.
- Bottom toolbar: **Fit** (key F; views 1 top, 2 front, 3 right, 4 back,
  5 left, 0 start), **Section** (key X), **Background** (key B), **Full
  screen**.
- The Section panel has three axis buttons, "Cut from the left and right"
  (X), "Cut from the bottom and top" (Y, the vertical axis), "Cut from the
  back and front" (Z), two sliders "Cut from the bottom" and "Cut from the
  top" (range inputs, 0 to 1000), and "Remove every cut" (Reset).
- Bottom left: a walk pad (W/A/S/D forward, left, back, right; Q/E down, up;
  Fast x3 or hold Shift) for moving through the data hall.
- The 3D scene is drawn on a canvas, so read the page text for names and
  numbers. Keys need the canvas focused: click the middle of the scene once
  before pressing a view key. Wait for "Preparing scene" to leave the page
  text before doing anything.

## Steps

Keep moving: the user watches the pane, they do not need to answer anything
in this demo.

1. Say: "I'll open one of our 3D models in the browser and walk through it with
   you. You can take over the tab at any time."
2. Open the address above in the browser pane, then call the browser's tab
   list (`tabs_context`): its last line says whether the pane is displayed or
   hidden. It is hidden whenever the cheat sheet or another artifact holds the
   side panel, and nothing in the app offers a switch. If hidden, say exactly:
   "The browser opened behind your cheat sheet. Press Ctrl+Shift+B, or the
   browser button, to watch." Then wait five seconds and carry on; do not ask
   them to confirm.
3. Read the page text. Tell them the model name, element count and extent in
   one line.
4. The section cut: a vertical plane across the hall, never the top-down
   cut. In this order, each as its own action so they see it happen:
   - Say: "I'll cut the hall in half, straight across the rack rows." Click
     the middle of the scene once (keys need the canvas focused), press `x`.
   - Use `find` for "Cut from the back and front" and click it, then `find`
     "Cut from the front" and set it to **500** with `form_input` (the middle
     of the hall; the sliders run 0 to 1000). Wait 8 seconds. Say: "Half the
     hall is gone, so you're looking straight into the cut racks and the
     trays above them."
   - Say: "Same cut from the side." Click the scene, press `3` (right view),
     wait 6 seconds.
   - Take one screenshot for yourself to confirm the cut is visible (do not
     describe the screenshot; they are watching the pane).
   - Say: "And back to the start view with the cut removed." `find` "Remove
     every cut", click it, click the scene, press `0`, wait 3 seconds.
   Never drag the slider by pixels: a small drag cuts almost nothing. The
   whole sequence should take about half a minute, not five seconds.
5. Tell them the tab is theirs: they can rotate, zoom and walk through the hall
   with W/A/S/D, and you can read any website the same way, fill in forms,
   and pull information out of pages.
6. If `cheatsheet-cards.json` exists in the outputs folder (it will not in a
   fresh chat), add the card: title "Websites", what "I can open a site in
   the browser, read it, click through it and pull out what you need.", try
   "Open ... and find ..." / "Compare these two pages." Otherwise skip the
   card; there is no page to rebuild in this chat.

## Close

- What you just saw: "I opened a website, read it and used its tools, and the
  tab is yours."
- Try saying: "Open <site> and tell me ..." / "Look up ... on the
  manufacturer's site."
