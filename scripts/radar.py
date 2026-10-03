"""Draws radar charts derived dynamically from real GitHub data.

1. Signals Radar: Transparent score (0-100) derived from GitHub repository metadata
   (languages, topics, descriptions, names, and contribution activity).
2. Language Radar: Generated from actual repository language usage from repositories
   owned by the user.

Run (real data):  GITHUB_TOKEN=xxx python scripts/radar.py
Run (fake data):  python scripts/radar.py --demo        # local preview only
Out: assets/radar-{dark,light}.svg  and  assets/radar-langs-{dark,light}.svg
"""
import math
import os
import sys
from xml.sax.saxutils import escape

from cards import DEMO, fetch, load_cache
from theme import FONT, THEMES, load_profile, write

W, H, CX, CY, R = 480, 440, 240, 238, 122


def calc_signals(data):
    """Calculate transparent 0-100 signals from GitHub repository evidence.

    Calculation methodology:
    - Flutter: Evidence from Dart repositories, flutter apps, and mobile projects.
    - Firebase: Evidence from repos integrating Firebase, Firestore, or cloud backends.
    - Django: Evidence from Python backend services, Django, FastAPI, and APIs.
    - REST APIs: Evidence from repositories consuming or serving HTTP REST endpoints.
    - SQL: Evidence from database-backed repositories and SQL schema/query usage.
    - Open Source: Evidence from user's real GitHub activity: Pull Requests, contributed repos,
      issues, commits, and collaborative/forked open-source projects (e.g. GSSoC 2026).
    """
    repos = data.get("repo_details", [])

    # 1. Flutter evidence
    flutter_count = 0
    dart_bytes = 0
    for r in repos:
        combined = f"{r['name']} {r['description']} {' '.join(r.get('topics', []))}".lower()
        has_dart = "Dart" in r.get("languages", {})
        has_flutter_kw = "flutter" in combined or "dart" in combined
        if has_dart or has_flutter_kw:
            flutter_count += 1
            dart_bytes += r.get("languages", {}).get("Dart", 0)
    # Dart repo count (up to 60) + volume bonus (up to 30) + base (10)
    flutter_score = min(100, max(20, flutter_count * 12 + min(30, dart_bytes // 60_000) + 10))

    # 2. Firebase evidence
    firebase_count = 0
    for r in repos:
        combined = f"{r['name']} {r['description']} {' '.join(r.get('topics', []))}".lower()
        if any(k in combined for k in ("firebase", "firestore", "fcm")):
            firebase_count += 1
    # Firebase is integrated in key apps (DocTalk, Uni-Event)
    firebase_score = min(100, max(25, firebase_count * 25 + 35))

    # 3. Django & Python backend evidence
    django_count = 0
    for r in repos:
        combined = f"{r['name']} {r['description']} {' '.join(r.get('topics', []))}".lower()
        is_py = "Python" in r.get("languages", {})
        has_kw = any(k in combined for k in ("django", "drf", "fastapi", "flask", "backend"))
        if has_kw or (is_py and "api" in combined):
            django_count += 1
    django_score = min(100, max(25, django_count * 20 + 35))

    # 4. REST APIs evidence
    api_count = 0
    for r in repos:
        combined = f"{r['name']} {r['description']} {' '.join(r.get('topics', []))}".lower()
        if any(k in combined for k in ("api", "rest", "endpoint", "postman", "http", "crud")):
            api_count += 1
    api_score = min(100, max(25, api_count * 12 + 30))

    # 5. SQL & database evidence
    sql_count = 0
    for r in repos:
        combined = f"{r['name']} {r['description']} {' '.join(r.get('topics', []))}".lower()
        if any(k in combined for k in ("sql", "database", "postgres", "mysql", "sqlite")):
            sql_count += 1
    sql_score = min(100, max(20, sql_count * 20 + 30))

    # 6. Open Source / Community contribution evidence
    prs = data.get("prs", 0)
    contributed = data.get("contributed", 0)
    issues = data.get("issues", 0)
    commits = data.get("commits", 0)
    forks_count = sum(1 for r in repos if r.get("is_fork"))
    open_source_score = min(100, max(20, int(prs * 3 + contributed * 4 + issues * 2 + (commits / 25) + forks_count * 2)))

    return {
        "title": "signals",
        "axes": [
            {"label": "Flutter", "value": flutter_score},
            {"label": "Firebase", "value": firebase_score},
            {"label": "Django", "value": django_score},
            {"label": "REST APIs", "value": api_score},
            {"label": "SQL", "value": sql_score},
            {"label": "Open Source", "value": open_source_score},
        ]
    }


def calc_langs(data):
    """Calculate actual repository language usage from user's owned repositories.

    Takes the language breakdown of each owned repository, calculates the language
    usage share across the portfolio, and normalizes across the top core languages.
    Do NOT invent percentages: all numbers derive strictly from GitHub repository bytes.
    """
    repos = [r for r in data.get("repo_details", []) if not r.get("is_fork")]
    if not repos:
        # Fallback to summarized langs if repo details are empty
        top = data.get("langs", [])[:5]
        total = sum(v["size"] for _, v in top) or 1
        axes = [{"label": name, "value": round(100 * v["size"] / total)} for name, v in top]
        return {"title": "language stack", "axes": axes}

    # Aggregate project usage share across owned repos
    shares = {}
    total_owned_repos = len(repos)
    for r in repos:
        rlangs = r.get("languages", {})
        repo_total = sum(rlangs.values()) or 1
        for lang, sz in rlangs.items():
            shares[lang] = shares.get(lang, 0.0) + (sz / repo_total)

    # Convert to average percentage across repositories
    avg_shares = {lang: (score / total_owned_repos) * 100 for lang, score in shares.items()}

    # Select core languages: Dart, Python, C++, HTML, JavaScript
    core_keys = ["Dart", "Python", "C++", "HTML", "JavaScript"]
    selected = [k for k in core_keys if k in avg_shares]
    if len(selected) < 3:
        # Take the top languages by share if core list has < 3
        sorted_langs = sorted(avg_shares.items(), key=lambda kv: -kv[1])
        selected = [k for k, _ in sorted_langs[:5]]

    sub_total = sum(avg_shares[k] for k in selected) or 1.0
    axes = [
        {"label": k, "value": round((avg_shares[k] / sub_total) * 100)}
        for k in selected
    ]

    return {
        "title": "language stack",
        "axes": axes
    }


def radar(data, theme, accent):
    t = THEMES[theme]
    axes = data["axes"]
    n = len(axes)
    if n < 3:
        raise SystemExit(f"A radar chart needs at least 3 axes, got {n}.")

    def pt(i, frac, extra=0):
        a = math.radians(-90 + i * 360 / n)
        r = R * frac + extra
        return CX + r * math.cos(a), CY + r * math.sin(a), math.cos(a), math.sin(a)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'width="{W}" height="{H}" role="img" aria-label="{escape(data["title"])} radar chart">',
           f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>',
           f'<text x="{W/2}" y="38" text-anchor="middle" font-family="{FONT}" font-size="15" '
           f'font-weight="700" fill="{accent}">{escape(data["title"])}</text>']

    for ring in (0.2, 0.4, 0.6, 0.8, 1.0):
        pts = " ".join(f"{pt(i, ring)[0]:.1f},{pt(i, ring)[1]:.1f}" for i in range(n))
        out.append(f'<polygon points="{pts}" fill="none" stroke="{t["grid"]}" stroke-width="1"/>')
    for i in range(n):
        x, y, _, _ = pt(i, 1)
        out.append(f'<line x1="{CX}" y1="{CY}" x2="{x:.1f}" y2="{y:.1f}" stroke="{t["grid"]}"/>')

    pts = " ".join(f"{pt(i, max(0, min(100, a['value'])) / 100)[0]:.1f},"
                   f"{pt(i, max(0, min(100, a['value'])) / 100)[1]:.1f}" for i, a in enumerate(axes))
    out.append(f'<polygon points="{pts}" fill="{accent}" fill-opacity="0.25" stroke="{accent}" '
               f'stroke-width="2" stroke-linejoin="round">'
               f'<animate attributeName="opacity" from="0" to="1" dur="1.2s" fill="freeze"/></polygon>')

    for i, a in enumerate(axes):
        x, y, *_ = pt(i, max(0, min(100, a["value"])) / 100)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{accent}">'
                   f'<title>{escape(a["label"])}: {a["value"]}</title></circle>')
        lx, ly, c, s = pt(i, 1, 20)
        anchor = "start" if c > 0.25 else "end" if c < -0.25 else "middle"
        ly += -2 if s < -0.5 else 12 if s > 0.5 else 5
        out.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-family="{FONT}" '
                   f'font-size="13" fill="{t["text"]}">{escape(a["label"])}</text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    p = load_profile()
    if "--demo" in sys.argv:
        print("Running radar.py in --demo mode (fake data)")
        data = DEMO
    else:
        # Check if cards.py already cached fresh live data
        data = load_cache()
        if not data:
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
            if not token:
                raise SystemExit("Error: GITHUB_TOKEN environment variable is not set. Run with --demo for local testing.")
            target_user = os.environ.get("GH_USER") or p.get("username", "riddhimagupta2")
            print(f"Fetching GitHub data for radar charts ({target_user}) ...")
            data = fetch(target_user, token)

    signals_data = calc_signals(data)
    langs_data = calc_langs(data)

    print("Calculated Signals Radar axes:", signals_data["axes"])
    print("Calculated Languages Radar axes:", langs_data["axes"])

    for theme in THEMES:
        write(f"radar-{theme}.svg", radar(signals_data, theme, p["accent"]))
        write(f"radar-langs-{theme}.svg", radar(langs_data, theme, p["accent"]))
