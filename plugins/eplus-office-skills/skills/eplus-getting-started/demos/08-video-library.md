# Demo 8: the training video library

**What it shows:** EPLUS University's training videos play right in the chat,
with the spoken transcript following along, and the whole library can be
browsed and searched from the same player, including by what is said in the
videos.

The library is the `epu-video-library` connector (118 videos, checked
2026-10-09). Since player v4 (2026-10-14) **one `play_video` call renders the
whole thing**: the video, a Transcript tab that follows playback and can be
searched, and a Library tab with the folder tree and a search box over titles,
folders and transcripts. `browse_library` renders a second, separate widget,
and every `search_videos` call adds more results to the chat. **This demo
makes exactly one tool call.** No browsing, no searching, no second video.

The video to play is the library's own introduction:
`EPLUS University Video Library Intro.mp4`, 2 min 28 s, at the top of the
library, ref `01HYRW3YUH76QRJ5KXDNBJVEJQWLHPDNPS`.

## Steps

1. Load the tool: ToolSearch `play_video` and pick the `epu-video-library`
   connector's `play_video`. If it is not there, say "The video library isn't
   connected on this seat, so I'll skip that one." and move on; no card.
2. Say: "EPLUS has a library of training videos, and they play right here in
   the chat. Here's the library's own two-minute introduction."
3. Call `play_video` once, with `ref` set to the ref above and nothing else.
   The player appears under your message. If the call errors because the ref
   is not found (the file was moved), call `search_videos` once with
   `"Video Library Intro"`, take the first title's `ref`, and play that. That
   is the only case where a second call is allowed.
4. Say: "The Transcript tab follows the video and you can search inside it.
   The Library tab is every training video we have, with a search box that
   also looks through what people say in them. Try it after the tour." Then
   do nothing for ten seconds; the player is theirs. Do not describe the
   library, do not list folders or videos, do not open anything else.
5. Add the card to their page: title "Training videos", what "I can find
   the EPLUS University video that covers something, even by what's said in
   it, and play it from that moment.", try "Find the video about ..." /
   "Play the part where they explain ..."

## Close

- What you just saw: "The training library plays in the chat, with the
  transcript alongside and the whole library a tab away."
- Try saying: "Find the training video about ..." / "Play the part where they
  explain ..."
