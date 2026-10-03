"""Generates the GitHub stats card and the most-used-languages card as SVGs.
Also writes assets/langmix.json from real API language data so the language
radar chart in ## signals is always live, not hardcoded.

Own generator on purpose: public stat services (github-readme-stats etc.) are
shared instances that go down and break the whole README section.

Run (real data):  GITHUB_TOKEN=xxx python scripts/cards.py
Run (fake data):  python scripts/cards.py --demo        # no token needed
Out: assets/card-stats-{dark,light}.svg, assets/card-langs-{dark,light}.svg
     assets/langmix.json  (consumed by radar.py for the language radar)"""
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

from theme import FONT, THEMES, load_profile, write

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    name
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(first: 1,
        contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after,
                 privacy: PUBLIC) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def gql(login, token, after=None):
    body = json.dumps({"query": QUERY, "variables": {"login": login, "after": after}}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json",
        "User-Agent": "profile-readme-cards"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GitHub API error: {data['errors']}")
    return data["data"]["user"]


def fetch(login, token):
    user, after, repos = None, None, []
    for _ in range(10):                       # up to 1000 repos
        user = gql(login, token, after)
        page = user["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return summarize(user, repos)


def summarize(user, repos):
    langs = {}
    for repo in repos:
        for e in repo["languages"]["edges"]:
            n = e["node"]
            cur = langs.setdefault(n["name"], {"size": 0, "color": n["color"] or "#8b949e"})
            cur["size"] += e["size"]
    cc = user["contributionsCollection"]
    return {
        "name": user["name"] or "",
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "langs": sorted(langs.items(), key=lambda kv: -kv[1]["size"]),
    }


DEMO = {
    "name": "Riddhima Gupta", "stars": 12, "commits": 340, "prs": 18, "issues": 6,
    "contributed": 9, "followers": 24, "repos": 15,
    "langs": [("Dart", {"size": 620, "color": "#00B4AB"}), ("Python", {"size": 210, "color": "#3572A5"}),
              ("C++", {"size": 110, "color": "#f34b7d"}), ("HTML", {"size": 40, "color": "#e34c26"}),
              ("Shell", {"size": 20, "color": "#89e051"})],
}


def head(w, h, t, title, accent):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{escape(title)}">',
            f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>',
            f'<text x="28" y="40" font-family="{FONT}" font-size="16" font-weight="700" fill="{accent}">{escape(title)}</text>']


def stats_card(d, theme, accent, username):
    t = THEMES[theme]
    who = d["name"] or username
    title = f"{who}'s GitHub stats"
    rows = [("Total stars", d["stars"]), ("Commits (1y)", d["commits"]),
            ("Pull requests", d["prs"]), ("Issues", d["issues"]),
            ("Followers", d["followers"]), ("Public repos", d["repos"]),
            ("Contributed to", d["contributed"])]
    w, h = 480, 230
    o = head(w, h, t, title, accent)
    o.append('<g><animate attributeName="opacity" from="0" to="1" dur="0.6s" fill="freeze"/>')
    for i, (label, val) in enumerate(rows):
        col, row = divmod(i, 4)
        x0 = 28 + col * 215
        y = 84 + row * 34
        o.append(f'<g><circle cx="{x0+4}" cy="{y-5}" r="4" fill="{accent}"/>'
                 f'<text x="{x0+18}" y="{y}" font-family="{FONT}" font-size="13" fill="{t["muted"]}">{escape(label)}</text>'
                 f'<text x="{x0+185}" y="{y}" text-anchor="end" font-family="{FONT}" font-size="14" '
                 f'font-weight="700" fill="{t["text"]}">{val:,}</text></g>')
    o.append("</g></svg>")
    return "\n".join(o)


def langs_card(d, theme, accent):
    t = THEMES[theme]
    top = d["langs"][:8]
    total = sum(v["size"] for _, v in top) or 1
    rows = (len(top) + 1) // 2
    w, h = 480, 100 + rows * 28
    o = head(w, h, t, "Most used languages", accent)
    bx, bw = 28, 424
    o.append(f'<clipPath id="bar"><rect x="{bx}" y="58" width="{bw}" height="10" rx="5"/></clipPath>')
    o.append('<g clip-path="url(#bar)">')
    x = bx
    for name, v in top:
        seg = bw * v["size"] / total
        o.append(f'<rect x="{x:.1f}" y="58" width="{seg:.1f}" height="10" fill="{v["color"]}"/>')
        x += seg
    o.append("</g>")
    for i, (name, v) in enumerate(top):
        col, row = divmod(i, rows)
        x0, y = 28 + col * 215, 102 + row * 28
        pct = 100 * v["size"] / total
        o.append(f'<circle cx="{x0+5}" cy="{y-4}" r="5" fill="{v["color"]}"/>'
                 f'<text x="{x0+18}" y="{y}" font-family="{FONT}" font-size="13" fill="{t["text"]}">{escape(name)}</text>'
                 f'<text x="{x0+185}" y="{y}" text-anchor="end" font-family="{FONT}" font-size="13" '
                 f'fill="{t["muted"]}">{pct:.1f}%</text>')
    o.append("</svg>")
    return "\n".join(o)


def langmix_from_data(data):
    """Convert the langs list from fetch() into the langmix.json radar format.

    Scores are normalised so the top language is always 100, giving the radar
    useful spread rather than tiny absolute-byte percentages.
    """
    top = data["langs"][:8]
    if not top:
        return None
    max_size = max(v["size"] for _, v in top) or 1
    axes = [
        {"label": name, "value": round(100 * v["size"] / max_size)}
        for name, v in top
        if round(100 * v["size"] / max_size) >= 5   # skip tiny slivers
    ]
    # radar.py needs at least 3 axes
    if len(axes) < 3:
        return None
    return {"title": "language mix", "note": "Auto-generated from GitHub API. Do not edit.", "axes": axes}


if __name__ == "__main__":
    p = load_profile()
    if "--demo" in sys.argv:
        data = DEMO
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("Set GITHUB_TOKEN (or run with --demo to preview fake numbers).")
        data = fetch(os.environ.get("GH_USER", p["username"]), token)
    for theme in THEMES:
        write(f"card-stats-{theme}.svg", stats_card(data, theme, p["accent"], p["username"]))
        write(f"card-langs-{theme}.svg", langs_card(data, theme, p["accent"]))
    # Keep the language radar in ## signals in sync with real repo data
    lm = langmix_from_data(data)
    if lm:
        from theme import ASSETS
        (ASSETS / "langmix.json").write_text(
            json.dumps(lm, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote assets/langmix.json ({len(lm['axes'])} languages)")
