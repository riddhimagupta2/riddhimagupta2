"""Builds the animated terminal banner (types itself out, then loops).

Run:  python scripts/banner/generate.py
Out:  assets/banner-dark.svg  and  assets/banner-light.svg
Uses SMIL <animate>, which GitHub renders inside <img>. If a viewer blocks
animation, every line simply shows fully typed (static fallback).
"""
import pathlib
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from theme import FONT, THEMES, load_profile, write  # noqa: E402

CW, FS, LH = 9.6, 16, 30          # char width, font size, line height
WIDTH, LEFT, TOP, KEYCOLS = 960, 36, 92, 11
HOLD = 4.0                        # seconds to keep the finished screen


def type_anim(start, nchars, per_char, total):
    """SMIL values/keyTimes that reveal a clip rect one character at a time."""
    vals, kts = [0.0], [0.0]
    for k in range(1, nchars + 1):
        vals.append(k * CW + (14 if k == nchars else 0))
        kts.append((start + (k - 1) * per_char) / total)
    vals += [0.0, 0.0]
    kts += [(total - 1.0) / total, 1.0]
    v = ";".join(f"{x:.1f}" for x in vals)
    k = ";".join(f"{x:.5f}" for x in kts)
    return (f'<animate attributeName="width" values="{v}" keyTimes="{k}" '
            f'calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/>')


def build(theme):
    p, t = load_profile(), THEMES[theme]
    accent = p["accent"]
    rows = [("cmd", p["command"], None)] + [("out", k, v) for k, v in p["lines"]]

    # timeline
    clock, plan = 0.5, []
    for kind, a, b in rows:
        n = len(a) + 2 if kind == "cmd" else 2 + KEYCOLS + len(b)
        per = 0.06 if kind == "cmd" else 0.022
        plan.append((clock, n, per))
        clock += n * per + (0.45 if kind == "cmd" else 0.2)
    last_start = clock
    total = last_start + HOLD

    height = TOP + (len(rows) + 1) * LH + 14
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" '
         f'width="{WIDTH}" height="{height}" role="img" aria-label="profile.sh --live">',
         '<defs>']
    for i, (s, n, per) in enumerate(plan):
        y = TOP + i * LH
        full = n * CW + 14
        o.append(f'<clipPath id="c{i}"><rect x="{LEFT-4}" y="{y-20}" width="{full:.1f}" height="{LH}">'
                 f'{type_anim(s, n, per, total)}</rect></clipPath>')
    o.append('</defs>')
    o.append(f'<rect x="0.5" y="0.5" width="{WIDTH-1}" height="{height-1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>')
    o.append(f'<path d="M0.5 12.5a12 12 0 0 1 12-12h{WIDTH-25}a12 12 0 0 1 12 12V46H0.5z" fill="{t["bar"]}"/>')
    o.append(f'<line x1="0" y1="46" x2="{WIDTH}" y2="46" stroke="{t["border"]}"/>')
    for cx, col in ((28, "#ff5f56"), (50, "#ffbd2e"), (72, "#27c93f")):
        o.append(f'<circle cx="{cx}" cy="23" r="6" fill="{col}"/>')
    o.append(f'<text x="{WIDTH/2}" y="28" text-anchor="middle" font-family="{FONT}" font-size="13" '
             f'fill="{t["muted"]}">{escape(p["username"])} - profile.sh</text>')

    for i, (kind, a, b) in enumerate(rows):
        y = TOP + i * LH
        o.append(f'<g clip-path="url(#c{i})" font-family="{FONT}" font-size="{FS}">')
        if kind == "cmd":
            o.append(f'<text x="{LEFT}" y="{y}" fill="{accent}" font-weight="700">$</text>')
            o.append(f'<text x="{LEFT+2*CW}" y="{y}" fill="{t["text"]}">{escape(a)}</text>')
        else:
            o.append(f'<text x="{LEFT}" y="{y}" fill="{accent}">&gt;</text>')
            o.append(f'<text x="{LEFT+2*CW}" y="{y}" fill="{t["muted"]}">{escape(a)}</text>')
            o.append(f'<text x="{LEFT+(2+KEYCOLS)*CW}" y="{y}" fill="{t["text"]}">{escape(b)}</text>')
        o.append('</g>')

    # final prompt with blinking cursor, appears after the last line is typed
    y = TOP + len(rows) * LH
    o.append(f'<g font-family="{FONT}" font-size="{FS}"><text x="{LEFT}" y="{y}" fill="{accent}" font-weight="700">$'
             f'<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;{last_start/total:.5f};{(total-1)/total:.5f};1" '
             f'calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/></text>')
    o.append(f'<rect x="{LEFT+2*CW}" y="{y-15}" width="9" height="19" fill="{accent}">'
             f'<animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" repeatCount="indefinite"/></rect></g>')
    o.append('</svg>')
    return "\n".join(o)


if __name__ == "__main__":
    for theme in THEMES:
        write(f"banner-{theme}.svg", build(theme))
