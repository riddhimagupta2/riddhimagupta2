"""Draws radar charts from assets/skills.json and assets/langmix.json.

Run:  python scripts/radar.py
Out:  assets/radar-{dark,light}.svg  and  assets/radar-langs-{dark,light}.svg
"""
import math
from xml.sax.saxutils import escape

from theme import FONT, THEMES, load_json, load_profile, write

W, H, CX, CY, R = 480, 440, 240, 238, 122


def radar(data, theme, accent):
    t = THEMES[theme]
    axes = data["axes"]
    n = len(axes)
    if n < 3:
        raise SystemExit("A radar chart needs at least 3 axes.")

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
        x, y, *_ = pt(i, a["value"] / 100)
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
    accent = load_profile()["accent"]
    for src, prefix in (("skills.json", "radar"), ("langmix.json", "radar-langs")):
        data = load_json(src)
        for theme in THEMES:
            write(f"{prefix}-{theme}.svg", radar(data, theme, accent))
