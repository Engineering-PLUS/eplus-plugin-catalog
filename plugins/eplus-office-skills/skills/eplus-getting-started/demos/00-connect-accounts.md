# Demo 0: connect your accounts (always first)

**What it shows:** Claude can see who the user is through their Microsoft 365
account, and the EPLUS connectors (Microsoft 365, the video library, PlanGrid,
the knowledge hubs) only work once the user has signed in to them in the app.
A first-time user has not, so this demo gets them signed in before anything
else, and gives the tour their name.

Two facts to keep straight:

- You cannot sign the user in, but you can put the **sign-in card** in front
  of them: `suggest_connectors` shows a card with a **Connect** button for
  each connector you pass it. The user clicks it, signs in to Microsoft and
  approves in Authenticator. The same sign-in lives in **Settings,
  Connectors** (a **Connect** button per connector, and after an app update a
  **Reconnect** button on anything that signed out). That is what the video
  shows (2 min 15 s, recorded 2026-10-14).
- The video library connector needs a sign-in too, so the video cannot depend
  on it. It ships inside this skill at `assets/videos/connectors-and-updates.mp4`.
  In bash the skill folder is at a fixed path inside the session mount:
  `/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-office-skills/skills/eplus-getting-started`
  where `<session>` is the one name `ls /sessions` prints. `.local-plugins`
  is a hidden folder: a plain `ls` of the mount shows only `outputs` and
  `uploads`, and that does not mean the skill folder is missing. Never search
  for the file with `find`; use the path.

## Steps

1. Load the Microsoft 365 profile tool: ToolSearch `Microsoft 365 get_me` and
   pick `get_me` on the `Microsoft_365` connector. Call it. It returns
   `displayName`, `mail`, `userPrincipalName`, `id` and `jobTitle` (often
   empty; never rely on it).
2. **If it returns a profile:** say "I can see your Microsoft 365 account:
   <displayName>, <mail>. I'll call you <first word of displayName>." The
   first word of `displayName` is their first name for the whole tour; never
   ask for it. Keep the display name, email and job title (when present) for
   demo 2. Skip to step 6.
3. **If it fails or the tool is missing** (an authentication error, "not
   connected", or no `get_me` in the tool list), the user has not signed in
   yet. Show the sign-in card:
   - Load it with ToolSearch `select:mcp__mcp-registry__suggest_connectors`
     (if that name is not found, ToolSearch `suggest_connectors`).
   - Call it with `keywords` `["account"]` and `uuids` holding the Microsoft
     365 connector's server id: the part between `mcp__` and the next `__` in
     the failed tool's name. Add the video library's server id the same way
     when one of its tools (`play_video`) is in the tool list.
   - If `get_me` was not in the tool list at all, there is no failed name to
     take the id from: ToolSearch `search_mcp_registry`, search "Microsoft
     365", and pass the `directoryUuid` it returns.

   Say first, in one line: "Your Microsoft 365 account isn't connected to
   Claude yet. Click Connect on the card, sign in, and approve it in your
   Authenticator app."

   **Only if the card cannot be shown** (no `suggest_connectors`, or it
   errors), fall back to the video. Say: "Before we start, your accounts need
   to be connected to Claude. This two-minute video shows how: Settings,
   Connectors, then Connect on each one. Microsoft 365 will ask you to
   approve the sign-in in your Authenticator app." Then play the video,
   trying the better player first:
   - If the video library's `play_video` tool is in the tool list, call it
     with `share_url` =
     `https://220221.sharepoint.com/:v:/s/EPUVideoLibrary/IQATR-UbI3j-R7BTwLCDtElTAbD6rVU6nwD_4FMzE0F6Nuk?e=oVSQt3`.
     If it plays, the player and transcript appear in the chat.
   - If that tool is absent or errors (it needs its own sign-in), use the
     file. One bash call, exactly this, with `<session>` from `ls /sessions`:

     ```bash
     S=/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-office-skills/skills/eplus-getting-started
     cp "$S/assets/videos/connectors-and-updates.mp4" /sessions/<session>/mnt/outputs/Connectors-and-updates.mp4 && ls -la /sessions/<session>/mnt/outputs/Connectors-and-updates.mp4
     ```

     Then show it with `present_files`, giving the outputs folder's Windows
     path from your environment block plus `\Connectors-and-updates.mp4`
     (the same way demo 1 presents the cheat sheet). Say: "Open the video
     above; it plays in your video player." Only if the copy itself fails
     (the `ls` shows nothing), fall back to the written steps: Settings,
     Connectors, Connect on Microsoft 365 and approve in Authenticator, then
     Connect on the video library, and tell the user the file sits in the
     skill folder on their computer; never claim the sandbox cannot reach it.
4. Say: "Tell me when you're signed in. I'll wait." This is the one place in
   the tour where waiting for the user is right: nothing works until they
   have signed in.
5. When they say they are done, call `get_me` again. If it works, do step 2.
   If it still fails, say: "Microsoft 365 isn't connected yet. We can carry on
   and come back to it; if the Connect button won't take, tell Victor." Do
   not ask their name: carry on without one (the cheat sheet is then titled
   "Claude cheat sheet", and greetings leave the name out).
6. Add the card to the cheat sheet: title "Your accounts", what "Once you've
   signed in under Settings, Connectors, I can use your Microsoft 365 (mail,
   calendar, Teams, SharePoint), the video library and the EPLUS project
   tools.", try "What's on my calendar tomorrow?" / "Search SharePoint for ..."
   Remind them in one line: "After an app update, anything marked Reconnect
   in Settings, Connectors needs one click to come back."

## Close

- What you just saw: "I checked who you are through your Microsoft 365
  account, and your connectors are signed in."
- Try saying: "Who am I signed in as?" / "Find my meetings this week."
