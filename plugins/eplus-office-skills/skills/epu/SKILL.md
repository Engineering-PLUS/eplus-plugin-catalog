---
name: "epu"
description: "Open the EPU video library at its root folder. Use when the user types /epu."
---

# EPU

Open the EPU video library at its root.

## Instructions

1. Call `mcp__epu-video-library__browse_library` with no arguments (default `refresh: false`).
2. Do not output any text before or after the tool call. No greeting, no summary, no list of folders or videos, no follow-up question. The library browser that opens is the entire response.
3. If the tool returns an error, reply with one short sentence stating the error and nothing else.

