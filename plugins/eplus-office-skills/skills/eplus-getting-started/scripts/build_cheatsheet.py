#!/usr/bin/env python3
"""
build_cheatsheet.py -- build the printable Cowork cheat sheet as one HTML file.

Fills assets/cheatsheet.html from assets/cheatsheet-content.json (the fixed
reference: what to ask for, slash commands, what to do when something goes
wrong) plus the demos this user has done (a small cards JSON the tour keeps),
and inlines the EPLUS logo and icon from the eplus-branding skill as data URIs,
so the page is one self-contained file that opens anywhere and prints as it
looks. The model never retypes the page or the logos: it runs this script and
publishes or presents the file it writes.

    python3 build_cheatsheet.py --name "Victor" --out <outputs>/Cowork-Cheat-Sheet-Victor.html \
        [--cards <outputs>/cheatsheet-cards.json] \
        [--skill "punch-report=Build a draft punch report from a PlanGrid project" ...]

--cards   JSON list of {"title", "what", "try"}, one per demo done, in order.
          Missing or empty: the "What we tried together" section is left out.
--skill   repeatable NAME=DESCRIPTION for the EPLUS skills in the user's
          / menu; none given: the "Your EPLUS skills" section is left out.
"""
import argparse
import base64
import datetime
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
LOGOS = os.path.join(os.path.dirname(SKILL), "eplus-branding", "assets", "logos")
NOTE_LINES = 14


def data_uri(name):
    path = os.path.join(LOGOS, name)
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        sys.exit(f"ERROR: logo not found at {path}; is the eplus-branding skill installed beside this one?")


def esc(s):
    return html.escape(str(s), quote=False)


def card(title, what, tries):
    tries = tries if isinstance(tries, list) else [tries]
    lines = "".join(f'<p class="try"><b>Try:</b> "{esc(t)}"</p>' for t in tries if t)
    return f'<div class="card"><h3>{esc(title)}</h3><p>{esc(what)}</p>{lines}</div>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cards", default=None)
    ap.add_argument("--skill", action="append", default=[])
    ap.add_argument("--date", default=None, help="shown date (default today)")
    args = ap.parse_args()

    with open(os.path.join(SKILL, "assets", "cheatsheet.html"), encoding="utf-8") as f:
        page = f.read()
    with open(os.path.join(SKILL, "assets", "cheatsheet-content.json"), encoding="utf-8") as f:
        content = json.load(f)

    cards = []
    if args.cards and os.path.isfile(args.cards):
        with open(args.cards, encoding="utf-8") as f:
            cards = json.load(f) or []
    tried = ""
    if cards:
        tried = ('<h2>What we tried together</h2><div class="cards">'
                 + "".join(card(c["title"], c["what"], c.get("try", "")) for c in cards) + "</div>")

    skills = ""
    pairs = [s.split("=", 1) for s in args.skill if "=" in s]
    if pairs:
        rows = "".join(f"<tr><td>/{esc(n.strip().lstrip('/'))}</td><td>{esc(d.strip())}</td></tr>" for n, d in pairs)
        skills = f"<h2>Your EPLUS skills</h2><table><thead><tr><th>Type</th><th>What it does</th></tr></thead>{rows}</table>"

    builtin = ('<table class="plain"><thead><tr><th>Skill</th><th>What it does</th><th>Ask</th></tr></thead>'
               + "".join(f"<tr><td>{esc(b['skill'])}</td><td>{esc(b['does'])}</td><td class=\"ask\">{esc(b['ask'])}</td></tr>"
                         for b in content["builtin_skills"]) + "</table>")

    commands = ("<table><thead><tr><th>Command</th><th>What it does</th></tr></thead>"
                + "".join(f"<tr><td>{esc(c['command'])}</td><td>{esc(c['does'])}</td></tr>"
                          for c in content["commands"]) + "</table>")

    help_ = content["help"]
    help_html = (f"<p>{esc(help_['intro'])}</p><ol>"
                 + "".join(f"<li>{esc(s)}</li>" for s in help_["steps"]) + "</ol>")

    date = args.date or datetime.date.today().strftime("%B %d, %Y").replace(" 0", " ")
    name = args.name.strip()
    fills = {
        "{{LOGO}}": data_uri("EPlus-Logo.png"),
        "{{ICON}}": data_uri("EPlus-Icon.png"),
        "{{TITLE}}": esc(f"{name}'s Claude cheat sheet" if name else "Claude cheat sheet"),
        "{{SUBTITLE}}": esc(f"Claude in Cowork, {date}"),
        "{{TRIED}}": tried,
        "{{CAPABILITIES}}": "".join(card(c["title"], c["what"], c["try"]) for c in content["capabilities"]),
        "{{SKILLS}}": skills,
        "{{BUILTIN}}": builtin,
        "{{COMMANDS}}": commands,
        "{{HELP}}": help_html,
        "{{NOTE_LINES}}": '<div class="line"></div>' * NOTE_LINES,
    }
    for k, v in fills.items():
        page = page.replace(k, v)
    left = [k for k in fills if k in page]
    if left:
        sys.exit(f"ERROR: placeholders left in the page: {left}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"cheat sheet: {args.out}  ({len(cards)} demo card(s), {len(pairs)} EPLUS skill(s), "
          f"{os.path.getsize(args.out) // 1024} KB)")


if __name__ == "__main__":
    main()
