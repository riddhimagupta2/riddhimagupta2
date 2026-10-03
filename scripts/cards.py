"""Generates the GitHub stats card and the most-used-languages card as SVGs.

Own generator on purpose: public stat services (github-readme-stats etc.) are
shared instances that go down and break the whole README section.

Run (real data):  GITHUB_TOKEN=xxx python scripts/cards.py
Run (fake data):  python scripts/cards.py --demo        # no token needed
Out: assets/card-stats-{dark,light}.svg, assets/card-langs-{dark,light}.svg
"""
import json
import os
import pathlib
import sys
import urllib.request
from xml.sax.saxutils import escape

from theme import FONT, ROOT, THEMES, load_profile, write

API = "https://api.github.com/graphql"
CACHE_DIR = ROOT / ".cache"
CACHE_FILE = CACHE_DIR / "github_data.json"

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    name
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(first: 100,
        contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
    repositories(ownerAffiliations: OWNER, first: 100, after: $after,
                 privacy: PUBLIC) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        description
        isFork
        stargazerCount
        forkCount
        repositoryTopics(first: 10) {
          nodes {
            topic {
              name
            }
          }
        }
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
    if not data.get("data") or not data["data"].get("user"):
        raise SystemExit(f"GitHub API error: user '{login}' not found or no data returned.")
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
    data = summarize(user, repos)
    save_cache(data)
    return data


def save_cache(data):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"Warning: could not write cache file: {e}", file=sys.stderr)


def load_cache():
    if CACHE_FILE.is_file():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def summarize(user, repos):
    langs = {}
    repo_details = []

    for repo in repos:
        # Collect languages per repo
        repo_lang_dict = {}
        for e in repo.get("languages", {}).get("edges", []):
            n = e["node"]
            repo_lang_dict[n["name"]] = e["size"]
            # Language totals for most used languages card come from owned original repositories
            if not repo.get("isFork"):
                cur = langs.setdefault(n["name"], {"size": 0, "color": n["color"] or "#8b949e"})
                cur["size"] += e["size"]

        # Collect topics
        topics = [
            t["topic"]["name"]
            for t in repo.get("repositoryTopics", {}).get("nodes", [])
            if t.get("topic") and t["topic"].get("name")
        ]

        repo_details.append({
            "name": repo.get("name") or "",
            "description": repo.get("description") or "",
            "is_fork": bool(repo.get("isFork")),
            "stars": repo.get("stargazerCount", 0),
            "forks": repo.get("forkCount", 0),
            "topics": topics,
            "languages": repo_lang_dict,
        })

    cc = user.get("contributionsCollection", {})
    commits = cc.get("totalCommitContributions", 0) + cc.get("restrictedContributionsCount", 0)
    owned_original = [r for r in repos if not r.get("isFork")]

    return {
        "name": user.get("name") or "",
        "stars": sum(r.get("stargazerCount", 0) for r in owned_original),
        "commits": commits,
        "prs": user.get("pullRequests", {}).get("totalCount", 0),
        "issues": user.get("issues", {}).get("totalCount", 0),
        "contributed": user.get("repositoriesContributedTo", {}).get("totalCount", 0),
        "followers": user.get("followers", {}).get("totalCount", 0),
        "repos": len(owned_original),
        "total_public_repos": user.get("repositories", {}).get("totalCount", len(repos)),
        "langs": sorted(langs.items(), key=lambda kv: -kv[1]["size"]),
        "repo_details": repo_details,
    }


DEMO = {
    "name": "Riddhima Gupta", "stars": 12, "commits": 340, "prs": 18, "issues": 6,
    "contributed": 9, "followers": 24, "repos": 14, "total_public_repos": 45,
    "langs": [("Dart", {"size": 1975338, "color": "#00B4AB"}),
              ("Python", {"size": 1500000, "color": "#3572A5"}),
              ("C++", {"size": 593626, "color": "#f34b7d"}),
              ("JavaScript", {"size": 420000, "color": "#f1e05a"}),
              ("HTML", {"size": 331233, "color": "#e34c26"})],
    "repo_details": [
        {"name": "DocTalk", "description": "Healthcare appointment app with Firebase & REST API", "is_fork": False, "stars": 2, "topics": ["flutter", "firebase"], "languages": {"Dart": 739350, "HTML": 133424}},
        {"name": "aurasync_ai", "description": "Cross-platform mobile application", "is_fork": False, "stars": 1, "topics": ["flutter", "dart"], "languages": {"Dart": 203431, "C++": 25745}},
        {"name": "Boutique_management", "description": "Flutter shop app", "is_fork": False, "stars": 0, "topics": ["flutter"], "languages": {"Dart": 309966, "C++": 26939}},
        {"name": "snapii", "description": "Flutter REST API photo app", "is_fork": False, "stars": 0, "topics": ["api", "flutter"], "languages": {"Dart": 299099, "C++": 25242}},
        {"name": "strings_and_decompiled_zip", "description": "FastAPI Django service for APK analysis", "is_fork": True, "stars": 0, "topics": ["django", "api"], "languages": {"Python": 80000}},
        {"name": "Truxify", "description": "Open-source Flutter logistics platform", "is_fork": True, "stars": 1, "topics": ["flutter", "open-source"], "languages": {"Dart": 500000}},
        {"name": "Uni-Event", "description": "Campus event platform with Firebase", "is_fork": True, "stars": 0, "topics": ["firebase"], "languages": {"JavaScript": 200000}},
        {"name": "AI-dev-assistant", "description": "GSSoC 2026 AI tool", "is_fork": True, "stars": 0, "topics": ["python", "open-source"], "languages": {"Python": 120000}},
        {"name": "WalkMate", "description": "C++ database utility", "is_fork": False, "stars": 0, "topics": ["database", "cpp"], "languages": {"C++": 24799, "Dart": 5865}},
    ]
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


if __name__ == "__main__":
    p = load_profile()
    if "--demo" in sys.argv:
        print("Running cards.py in --demo mode (fake data)")
        data = DEMO
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("Error: GITHUB_TOKEN environment variable is not set. Run with --demo for local testing.")
        target_user = os.environ.get("GH_USER") or p.get("username", "riddhimagupta2")
        print(f"Fetching GitHub statistics for user: {target_user} ...")
        data = fetch(target_user, token)
        print(f"Successfully fetched real GitHub data for {target_user}: "
              f"{data['stars']} stars, {data['commits']} commits, {data['repos']} repos, {len(data['langs'])} languages.")

    for theme in THEMES:
        write(f"card-stats-{theme}.svg", stats_card(data, theme, p["accent"], p["username"]))
        write(f"card-langs-{theme}.svg", langs_card(data, theme, p["accent"]))
