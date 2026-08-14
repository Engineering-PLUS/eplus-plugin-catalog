#!/usr/bin/env python3
"""PreToolUse hook for analyze_document.

When the model calls analyze_document with a file_path that exists locally,
this hook uploads the raw file bytes to the Document Analysis engine's
/upload endpoint (same {status, job_id, ...} response as the tool) and then
DENIES the tool call with that JSON in the reason. The model reads the
job_id out of the denial and continues with get_job_status — the encoded
file never enters the transcript, so the context window stays clean.

If file_path is absent, not a local file, or the upload fails, the hook
stays silent and the tool call proceeds untouched.
"""
import json
import os
import sys
import urllib.request

UPLOAD_URL = "http://20.9.42.66:8651/upload"
TOKEN = "af19f84270b9b2ff993fa7246c08067d84188ac01ae4fa4134c695ba4aa36de7"


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path or not os.path.isfile(file_path):
        return

    try:
        with open(file_path, "rb") as f:
            data = f.read()
        req = urllib.request.Request(
            UPLOAD_URL,
            data=data,
            headers={
                "Authorization": "Bearer " + TOKEN,
                "X-Filename": os.path.basename(file_path),
                "Content-Type": "application/octet-stream",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=110) as resp:
            body = resp.read().decode("utf-8", "replace").strip()
    except Exception:
        # Fall back to the normal tool call; a real error will surface there.
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                body
                + " — file already uploaded by hook; do NOT resubmit "
                  "analyze_document for this file, poll get_job_status(job_id) "
                  "from this payload instead."
            ),
        }
    }))


if __name__ == "__main__":
    main()
