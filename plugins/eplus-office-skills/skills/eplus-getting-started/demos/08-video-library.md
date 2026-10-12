# Demo 8: find a training video

**What it shows:** Claude can find the right EPLUS University training video,
by its title or by what is said in it, and play it from that exact moment,
with the transcript beside it.

The library is the `epu-video-library` connector (checked 2026-10-09: 118
videos). Two areas: **Courses** (Engineering: AudioVisual, Communications,
Security; Operations: Bluebeam, Project Management, Deltek; Revit: CONCEPTS
and the 16-part REVIT WEEK; Other) and **VOD Instructional Videos** (short
how-tos, two to ten minutes: CAD, Engineering, Operations, Revit). Its tools:

- `browse_library`: opens the folder tree in the chat and returns it.
- `search_videos` (query): matches titles and the spoken transcripts; returns
  `titles` and `moments`, each moment with a `ref`, `start_ms` and the line.
- `play_video` (ref, start_seconds): opens the player at that moment.

## Steps

1. Load the tools: ToolSearch `video library` and pick the `search_videos`,
   `browse_library` and `play_video` tools of the `epu-video-library`
   connector. If they are not there, say "The video library isn't connected
   on this seat, so I'll skip that one." and move on; no card.
2. Say: "EPLUS has a library of training videos. I can find the right one,
   even by what's said in it, and open it at that moment."
3. Pick one word they care about, from what they told you in demo 2 if you
   have it (their trade: "Revit", "fiber", "access control", "Bluebeam",
   "punch list"), otherwise "punch list". Search with it. Tell them in one
   line how many videos mention it and name the best one, for example:
   "Six moments across three videos; the closest is Using ACC Build for
   Punchlists, at 6:17, where they filter the punch list category."
   If there are no moments, use the first title match and start at 0; if
   there is nothing at all, search "Bluebeam" instead.
4. Open the library browser so they see the whole tree. Say: "This is
   everything: the courses on the left, the short how-to videos below."
   Leave it on screen for a few seconds.
5. Play the video from the moment you found (`start_seconds` is the moment's
   `start_ms` divided by 1000). The player appears right here in the chat,
   under your message, with the transcript below it (checked 2026-10-09; it
   never touches the side panel, so the cheat sheet stays put). Say:
   "Playing from the moment they say it, right here in the chat; the
   transcript runs under the video, and you can search inside it." Let it
   play; do nothing for ten seconds. They can pause it, scrub it or collapse
   it themselves.
6. Add the card to the cheat sheet: title "Training videos", what "I can find
   the EPLUS University video that covers something, even by what's said in
   it, and play it from that moment.", try "Find the video about ..." /
   "Where in the Revit Week videos do they cover phasing?"

## Close

- What you just saw: "I searched the training library by what people say in
  the videos, showed you the whole library, and played the right one from
  the right second."
- Try saying: "Find the training video about ..." / "Play the part where they
  explain ..."
