# Demo 5: use the browser

**What it shows:** Claude can open websites in the built-in browser, read
them, click through them, and hand the tab back to the user.

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
4. The section cut, in this order, each as its own action so they see it
   happen:
   - Click the middle of the scene, press `1`. Say: "Top view. The overhead
     cable trays cover everything."
   - Press `x`. Use `find` for "Cut from the bottom and top" and click it, then
     `find` "Cut from the top" and set it to **500** with `form_input` (half
     the building height). Say: "Now I've cut the model in half horizontally:
     the trays are gone and you're looking at the rack rows like a floor
     plan."
   - Take one screenshot for yourself to confirm the rows are visible (do not
     describe the screenshot; they are watching the pane).
   - `find` "Remove every cut", click it, press `0`. Say: "And back to the
     start view."
   Never drag the slider by pixels: a small drag cuts almost nothing.
5. Tell them the tab is theirs: they can rotate, zoom and walk through the hall
   with W/A/S/D, and you can read any website the same way, fill in forms,
   and pull information out of pages.
6. Add the card to the cheat sheet: title "Websites", what "I can open a site
   in the browser, read it, click through it and pull out what you need.",
   try "Open ... and find ..." / "Compare these two pages."

## Close

- What you just saw: "I opened a website, read it and used its tools, and the
  tab is yours."
- Try saying: "Open <site> and tell me ..." / "Look up ... on the
  manufacturer's site."
