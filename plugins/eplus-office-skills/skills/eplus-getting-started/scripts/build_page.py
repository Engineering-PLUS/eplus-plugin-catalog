#!/usr/bin/env python3
"""
build_page.py -- build the "Getting started with Claude" page as one HTML file.

Fills assets/getting-started.html with assets/cheatsheet-content.json (what to
ask for, the / menu: EPLUS skills and Claude's own, background skills, what to
do when something goes wrong) and assets/connectors.json (every connector, who
built it, what each tool does), and inlines the EPLUS logo and icon from the
eplus-branding skill as data URIs, so the page is one self-contained file with
no external requests. The model never retypes the page: it runs this script.
When a skill is added to or removed from the catalog, update eplus_skills or
background_skills in cheatsheet-content.json.

Without --name or --cards it builds the shared page everyone sees, which is
what gets hosted. With them it builds one person's copy.

    python3 build_page.py --out getting-started.html
    python3 build_page.py --name "Victor" --out <outputs>/Claude-Guide-Victor.html \
        [--cards <outputs>/cheatsheet-cards.json]

--cards   JSON list of {"title", "what", "try"}, one per demo done, in order.
"""
import argparse
import base64
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ASSETS = os.path.join(SKILL, "assets")
LOGOS = os.path.join(os.path.dirname(SKILL), "eplus-branding", "assets", "logos")


def data_uri(name):
    path = os.path.join(LOGOS, name)
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        sys.exit(f"ERROR: logo not found at {path}; is the eplus-branding skill installed beside this one?")


def load(name):
    with open(os.path.join(ASSETS, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cards", default=None)
    ap.add_argument("--date", default=None, help="shown date (default today)")
    args = ap.parse_args()

    cards = []
    if args.cards and os.path.isfile(args.cards):
        with open(args.cards, encoding="utf-8") as f:
            cards = json.load(f) or []
    # One copy button per prompt: a "try" written as one string of prompts
    # joined with " / " (seen in the field, 2026-10-29) is split back apart.
    for c in cards:
        tries = c.get("try", [])
        tries = tries if isinstance(tries, list) else [tries]
        c["try"] = [p.strip().strip('"') for t in tries for p in str(t).split(" / ") if p.strip()]
    content = load("cheatsheet-content.json")
    connectors = load("connectors.json")
    for c in connectors["connectors"]:
        if c["maker"] not in connectors["makers"]:
            sys.exit(f"ERROR: connector {c['name']!r} has unknown maker {c['maker']!r}")
    slash = [c["command"] for c in content.get("eplus_skills", []) + content["commands"]]
    dupes = sorted({s for s in slash if slash.count(s) > 1})
    if dupes:
        sys.exit(f"ERROR: listed more than once in the / menu: {dupes}")

    data = {
        "name": args.name.strip(),
        "date": args.date or datetime.date.today().strftime("%B %d, %Y").replace(" 0", " "),
        "cards": cards,
        "content": content,
        "connectors": connectors,
    }
    # "</" would end the <script> block early; JSON allows the escaped form.
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    with open(os.path.join(ASSETS, "getting-started.html"), encoding="utf-8") as f:
        page = f.read()
    fills = {
        "{{LOGO_WHITE}}": data_uri("EPlus-Logo-White.png"),
        "{{ICON}}": data_uri("EPlus-Icon.png"),
        "{{DATA}}": blob,
    }
    for k, v in fills.items():
        page = page.replace(k, v)
    left = [k for k in fills if k in page]
    if left:
        sys.exit(f"ERROR: placeholders left in the page: {left}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(page)
    n_tools = sum(len(c["tools"]) for c in connectors["connectors"])
    print(f"page: {args.out}  ({len(connectors['connectors'])} connectors, {n_tools} tools, "
          f"{len(cards)} demo card(s), {len(slash)} / menu entries, {os.path.getsize(args.out) // 1024} KB)")


if __name__ == "__main__":
    main()
