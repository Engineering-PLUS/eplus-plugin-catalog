# Demo 7: schedule a task

**What it shows:** Claude can run a task on a schedule (once at a set time, or
every week) without being asked each time.

## Steps

1. Say: "I can do things on a schedule. Let's set up a small one so you see how
   it works."
2. Offer two options with one `AskUserQuestion`:
   - **A one-time test in about 5 minutes (recommended)**: a short "Your
     first scheduled task ran" message with one tip about Claude.
   - **A weekly Monday check-in at 8 AM**: a short start-of-week note built
     from what they told you in demo 2 (their projects and how they like
     answers).
3. Say: "Cowork will ask your permission to create a scheduled task. That's
   this one; you can delete it any time." Then create it with Cowork's
   scheduled task tool (`create_scheduled_task`), with a clear name
   ("Getting started test" or "Monday check-in") and a prompt that is
   self-contained (it runs later with no memory of this chat).
4. Show them the list of their scheduled tasks (`list_scheduled_tasks`) and
   where to find it. For the one-time test, tell them to look for the result in
   about five minutes.
5. Offer to delete it now or keep it. Delete only on a clear yes
   (`delete_scheduled_task`).
6. Add the card to the cheat sheet: title "Scheduled tasks", what "Ask me to
   do something every day, every week, or at a set time.", try "Every Monday
   at 8, ..." / "Remind me on Friday to ..."

## Close

- What you just saw: "I set up a task that runs on its own at the time you
  chose."
- Try saying: "Every Friday at 3, summarize ..." / "Show me my scheduled
  tasks."
