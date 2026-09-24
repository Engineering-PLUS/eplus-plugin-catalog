# Demo 3: make your own skill

**What it shows:** a skill is a saved set of instructions Claude follows every
time. Anyone can make one by describing a task they repeat, and it then shows
up in their `/` menu.

## Steps

1. Say: "A skill is a recipe I follow the same way every time. Let's make one
   for something you do a lot."
2. Offer three ideas built from what they told you in demo 2 (or ask their role
   if you skipped it), plus "something else". Good defaults:
   - **my-weekly-update**: turns rough notes into their weekly status update,
     in the format they like.
   - **my-site-walk-notes**: cleans up site-walk notes into tidy observations
     grouped by trade.
   - **my-email-reply**: drafts a reply to a client or contractor email in a
     professional EPLUS tone.
3. Write the skill: a kebab-case name starting with `my-`, a one-line
   description saying when to use it, and short step-by-step instructions
   (under 40 lines) that use what you know about them (their trade, how they
   like answers). Show it to them in a few lines before saving.
4. Say: "Cowork will now ask your permission to save a skill to your account.
   That's this one; saying no is fine." Then load and call Cowork's
   `save_skill` (ToolSearch `select:mcp__cowork__save_skill` first) with
   `name`, `description` and `content`.
5. Show them where it lives: "Type `/` and you'll see it in your menu, or just
   describe the task and I'll pick it up." Mention that a skill can also carry
   reference files (a style guide, a template) and that you can build one of
   those whenever they ask.
6. Add the card to the cheat sheet: title "Your own skills", what "Describe a
   task you repeat and I'll save it as a skill in your / menu.", try "Make a
   skill that ..." / "Change my <skill name> skill so it ..."

## Close

- What you just saw: "I turned something you do often into a skill you can
  reuse with one command."
- Try saying: "Make a skill that ..." / "Update my skill so it ..."
