"""Animated two-panel terminal dashboard banner.

  LEFT  panel  VISUAL.MAP   dot-cloud shapes (globe, torus, cube) that spin, then
                            your portrait as a 1-bit dither (optional, see below)
  RIGHT panel  SYSTEM.INFO  LIVE badge, @handle pill, right-aligned key/value rows

Run:   python scripts/banner/generate.py
Out:   assets/banner-dark.svg, assets/banner-light.svg
Photo: put a photo at assets/photo.jpg (path set in assets/profile.json) and pip install pillow.
       Best result: plain background, face well lit. "photo_light": "ink" (default) draws dark areas as dots
       on the light theme; "same" keeps the dark theme's look.
       No photo -> the portrait step is simply skipped.
QA:    python scripts/banner/generate.py --still globe|torus|cube|portrait   (frozen frame, no animation)

Animation is SMIL (<animate>), which GitHub renders inside <img>. Without
animation support the first frame / full text is shown (static fallback).
"""
import math
import pathlib
import sys
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from theme import FONT, load_profile, write  # noqa: E402

W, H = 1000, 470
LX, LW = 20, 340                      # left panel
RX, RW = 376, 604                     # right panel
PY, PH = 54, 400                      # panel top / height
CX, CY, RAD = 190, 252, 118           # viz centre + radius
LEAD, TAIL = 0.3, 0.7                 # seconds before first / after last segment

PAL = {
    "dark": dict(win="#0a1224", bar="#0d1830", panel="#0d1a33", line="#1a2c52", text="#e8eefc",
                 muted="#6f86ab", dot="#9aa8ff", ok="#2fd4b5", live="#ff4d5e", pill="#12385a", mix=0.0),
    "light": dict(win="#eef3fa", bar="#e3eaf5", panel="#ffffff", line="#d0d7de", text="#1f2328",
                  muted="#656d76", dot="#3b4cc0", ok="#0f8f78", live="#d1242f", pill="#dbeefb", mix=0.45),
}


def darken(hexcol, amount):
    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(int(c * (1 - amount)) for c in (r, g, b))


# ---------------------------------------------------------------- 3D dot clouds
def rot_x(p, a):
    x, y, z = p
    return x, y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)


def rot_y(p, a):
    x, y, z = p
    return x * math.cos(a) + z * math.sin(a), y, -x * math.sin(a) + z * math.cos(a)


def globe_pts(n=620):
    out = []
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - y * y)
        phi = i * math.pi * (3 - math.sqrt(5))
        out.append((math.cos(phi) * r, y, math.sin(phi) * r))
    return out


def torus_pts(nu=38, nv=14, big=0.72, small=0.3):
    out = []
    for i in range(nu):
        u = 2 * math.pi * i / nu
        for j in range(nv):
            v = 2 * math.pi * j / nv
            r = big + small * math.cos(v)
            out.append((r * math.cos(u), small * math.sin(v), r * math.sin(u)))
    return out


def cube_pts(per_edge=13):
    out = []
    for s in (1.0, 0.5):
        v = [(x * s, y * s, z * s) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        for a in range(8):
            for b in range(a + 1, 8):
                if sum(abs(v[a][k] - v[b][k]) > 0 for k in range(3)) == 1:
                    for t in range(per_edge):
                        f = t / (per_edge - 1)
                        out.append(tuple(v[a][k] + (v[b][k] - v[a][k]) * f for k in range(3)))
    return [(x * 0.62, y * 0.62, z * 0.62) for x, y, z in out]


def project(pts, ax, ay):
    front, back = set(), set()
    for p in pts:
        x, y, z = rot_x(rot_y(p, ay), ax)
        sx, sy = round(CX + RAD * x), round(CY + RAD * y)
        (front if z >= 0 else back).add((sx, sy))
    back -= front
    return front, back


def to_path(points):
    return "".join(f"M{x} {y}h0" for x, y in sorted(points))


SHAPES = {
    "globe": dict(label="GLOBE", pts=globe_pts, frames=30, dur=5.0,
                  pose=lambda k, n: (math.radians(18), 2 * math.pi * k / n)),
    "torus": dict(label="TORUS", pts=torus_pts, frames=30, dur=5.0,
                  pose=lambda k, n: (math.radians(38), 2 * math.pi * k / n)),
    "cube": dict(label="CUBE", pts=cube_pts, frames=24, dur=4.0,
                 pose=lambda k, n: (2 * math.pi * k / n + 0.5, 4 * math.pi * k / n)),
}


# ------------------------------------------------------------ 1-bit portrait
def portrait_points(photo, cols=130, rows=145, invert=False):
    """Floyd-Steinberg dither, serpentine scan -> set of (col,row) that get a dot."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(photo)).convert("L")
    w, h = im.size
    target = cols / rows
    if w / h > target:                     # too wide -> crop sides
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:                                  # too tall -> crop, keep the top (faces live there)
        nh = int(w / target)
        top = int((h - nh) * 0.25)
        im = im.crop((0, top, w, top + nh))
    im = ImageOps.autocontrast(im.resize((cols, rows), Image.LANCZOS), cutoff=2)
    px = [[float(im.getpixel((x, y))) for x in range(cols)] for y in range(rows)]
    dots = set()
    for y in range(rows):
        xs = range(cols) if y % 2 == 0 else range(cols - 1, -1, -1)
        d = 1 if y % 2 == 0 else -1
        for x in xs:
            old = px[y][x]
            new = 255.0 if old >= 128 else 0.0
            err = old - new
            if (new > 0) != invert:
                dots.add((x, y))
            for dx, dy, f in ((d, 0, 7 / 16), (-d, 1, 3 / 16), (0, 1, 5 / 16), (d, 1, 1 / 16)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < cols and 0 <= yy < rows:
                    px[yy][xx] += err * f
    return dots


# ------------------------------------------------------------------ SVG build
def kt(vals):
    return ";".join(f"{v:.5f}" for v in vals)


def window_anim(a, b, total):
    """opacity 0 -> 1 during [a,b) seconds of the loop, else 0."""
    return (f'<animate attributeName="opacity" values="0;1;0;0" keyTimes="{kt([0, a / total, b / total, 1])}" '
            f'calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/>')


def build(theme, still=None):
    p = load_profile()
    c = PAL[theme]
    accent = darken(p["accent"], c["mix"]) if c["mix"] else p["accent"]
    rows = p["rows"][:12]
    user = p["username"]

    # ---- segments (what the left panel shows, in order)
    segs = []
    for name, s in SHAPES.items():
        pts = s["pts"]()
        frames = []
        for k in range(s["frames"]):
            ax, ay = s["pose"](k, s["frames"])
            frames.append(project(pts, ax, ay))
        npts = max(len(f) + len(b) for f, b in frames)
        segs.append(dict(name=name, label=f'{s["label"]} · {npts} PTS', dur=s["dur"], frames=frames))

    photo = ROOT / p.get("photo", "")
    portrait_cache = ROOT / "assets" / "portrait.json"
    portrait = None
    dots = None
    if p.get("photo") and photo.is_file():
        try:
            dots = portrait_points(photo, invert=(theme == "light" and p.get("photo_light", "ink") == "ink"))
            # Cache dark and light portrait dots so CI can render portrait without raw photo.jpg
            try:
                import json
                cached = {}
                if portrait_cache.is_file():
                    try:
                        cached = json.loads(portrait_cache.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                cached[theme] = sorted(list(dots))
                portrait_cache.write_text(json.dumps(cached), encoding="utf-8")
            except Exception as e:
                print("Could not save portrait cache:", e)
        except ImportError:
            print("Pillow not installed: skipping portrait (pip install pillow)")
    elif portrait_cache.is_file():
        try:
            import json
            cached = json.loads(portrait_cache.read_text(encoding="utf-8"))
            pts = cached.get(theme) or cached.get("dark") or []
            dots = set(tuple(x) for x in pts)
        except Exception as e:
            print("Could not load portrait cache:", e)

    if dots:
        portrait = dict(name="portrait", label=f"PORTRAIT · {len(dots)} PTS · FS/SERPENTINE", dur=7.0, dots=dots)
        segs.append(portrait)

    total = LEAD + sum(s["dur"] for s in segs) + TAIL
    starts, t = {}, LEAD
    for s in segs:
        starts[s["name"]] = t
        t += s["dur"]

    anim = still is None
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'role="img" aria-label="{escape(user)} profile dashboard">']

    # ---- clip paths (row wipes + portrait scan reveal)
    o.append("<defs>")
    rx_a, rx_b = RX + 14, RX + RW - 14
    for i, _ in enumerate(rows):
        y = 122 + i * 25
        a = LEAD + i * 0.28
        an = ""
        if anim:
            an = (f'<animate attributeName="width" values="0;0;{rx_b - rx_a};{rx_b - rx_a};0" '
                  f'keyTimes="{kt([0, a / total, (a + 0.4) / total, (total - 0.3) / total, 1])}" '
                  f'calcMode="linear" dur="{total:.2f}s" repeatCount="indefinite"/>')
        o.append(f'<clipPath id="r{i}"><rect x="{rx_a}" y="{y - 16}" width="{rx_b - rx_a}" height="22">{an}</rect></clipPath>')
    if portrait:
        a = starts["portrait"]
        an = ""
        if anim:
            an = (f'<animate attributeName="height" values="0;0;290;290" '
                  f'keyTimes="{kt([0, a / total, (a + 2.0) / total, 1])}" calcMode="linear" '
                  f'dur="{total:.2f}s" repeatCount="indefinite"/>')
        o.append(f'<clipPath id="reveal"><rect x="{CX - 130}" y="{CY - 145}" width="260" height="290">{an}</rect></clipPath>')
    o.append("</defs>")

    # ---- window chrome
    o.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{c["win"]}" stroke="{c["line"]}"/>')
    o.append(f'<path d="M0.5 14.5a14 14 0 0 1 14-14h{W - 29}a14 14 0 0 1 14 14V40H0.5z" fill="{c["bar"]}"/>')
    for cx, col in ((26, "#ff5f56"), (46, "#ffbd2e"), (66, "#27c93f")):
        o.append(f'<circle cx="{cx}" cy="20" r="5.5" fill="{col}"/>')
    o.append(f'<text x="{W / 2}" y="24" text-anchor="middle" font-family="{FONT}" font-size="12" '
             f'fill="{c["muted"]}">{escape(p.get("command", "profile.sh --live"))}</text>')

    # ---- panels
    for x, w in ((LX, LW), (RX, RW)):
        o.append(f'<rect x="{x}" y="{PY}" width="{w}" height="{PH}" rx="8" fill="{c["panel"]}" stroke="{c["line"]}"/>')
        o.append(f'<line x1="{x}" y1="92" x2="{x + w}" y2="92" stroke="{c["line"]}"/>')
        o.append(f'<line x1="{x}" y1="{PY + PH - 36}" x2="{x + w}" y2="{PY + PH - 36}" stroke="{c["line"]}"/>')

    def label(x, y, txt, fill, size=11, anchor="start", weight=700, spacing=1):
        return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT}" font-size="{size}" '
                f'font-weight="{weight}" letter-spacing="{spacing}" fill="{fill}">{escape(txt)}</text>')

    # ---- LEFT: header, brackets, scanline, shapes, caption
    o.append(label(LX + 18, 78, "VISUAL.MAP", accent))
    meta = "260x290 / 1-BIT" if portrait else "DOT-CLOUD / 1-BIT"
    o.append(label(LX + LW - 18, 78, meta, c["muted"], 9.5, "end", 400, 0.5))
    bx0, bx1, by0, by1 = LX + 16, LX + LW - 16, 104, 396
    for (x, y, dx, dy) in ((bx0, by0, 1, 1), (bx1, by0, -1, 1), (bx0, by1, 1, -1), (bx1, by1, -1, -1)):
        o.append(f'<path d="M{x} {y + 10 * dy}V{y}H{x + 10 * dx}" fill="none" stroke="{c["muted"]}" stroke-width="1.2"/>')

    dot_attrs = f'fill="none" stroke="{c["dot"]}" stroke-linecap="round"'
    for s in segs:
        a, b = starts[s["name"]], starts[s["name"]] + s["dur"]
        if s["name"] == "portrait":
            if still not in (None, "portrait"):
                continue
            d = "".join(f"M{CX - 130 + 2 * x} {CY - 145 + 2 * y}h0" for x, y in sorted(s["dots"]))
            an = window_anim(a, b, total) if anim else ""
            o.append(f'<g clip-path="url(#reveal)" opacity="{1 if not anim or True else 0}">{an}'
                     f'<path d="{d}" stroke-width="1.7" {dot_attrs}/></g>')
            if anim:
                o.append(f'<g opacity="0">{window_anim(a, b, total)}'
                         f'<line x1="{CX - 130}" x2="{CX + 130}" y1="{CY - 145}" y2="{CY - 145}" stroke="{accent}" stroke-width="1.5" opacity=".8">'
                         f'<animateTransform attributeName="transform" type="translate" values="0 0;0 0;0 290;0 290" '
                         f'keyTimes="{kt([0, a / total, (a + 2.0) / total, 1])}" dur="{total:.2f}s" repeatCount="indefinite"/></line></g>')
        else:
            if still not in (None, s["name"]):
                continue
            n = len(s["frames"])
            dt = s["dur"] / n
            for k, (front, back) in enumerate(s["frames"]):
                if not anim and k != n // 4:
                    continue
                fa, fb = a + k * dt, a + (k + 1) * dt
                base = 1 if (not anim) or (s["name"] == "globe" and k == 0 and not portrait) else 0
                an = window_anim(fa, fb, total) if anim else ""
                o.append(f'<g opacity="{base}">{an}<path d="{to_path(back)}" stroke-width="1.5" stroke-opacity=".35" {dot_attrs}/>'
                         f'<path d="{to_path(front)}" stroke-width="2.4" {dot_attrs}/></g>')

    # caption (swaps with the segment)
    for s in segs:
        a, b = starts[s["name"]], starts[s["name"]] + s["dur"]
        if still not in (None, s["name"]):
            continue
        cap = label(LX + 18, PY + PH - 14, s["label"], c["muted"], 9.5, "start", 400, 0.8)
        if anim:
            cap = cap.replace("<text ", f'<text opacity="0" ', 1).replace("</text>", window_anim(a, b, total) + "</text>")
        o.append(cap)

    # ---- RIGHT: header, LIVE, pill, rows, footer
    o.append(label(RX + 18, 78, "SYSTEM.INFO", accent))
    handle = "@" + user
    pw = int(len(handle) * 6.9 + 26)
    px = RX + RW - 18 - pw
    o.append(f'<rect x="{px}" y="64" width="{pw}" height="20" rx="10" fill="{c["pill"]}"/>')
    o.append(label(px + pw / 2, 78, handle, accent, 10.5, "middle", 700, 0.3))
    live_x = px - 16
    o.append(label(live_x, 78, "LIVE", c["live"], 10, "end", 700, 0.8))
    blink = ('<animate attributeName="opacity" values="1;0.15" dur="1.2s" calcMode="discrete" repeatCount="indefinite"/>'
             if anim else "")
    o.append(f'<circle cx="{live_x - 40}" cy="74.5" r="3.5" fill="{c["live"]}">{blink}</circle>')

    for i, (k, v) in enumerate(rows):
        y = 122 + i * 25
        o.append(f'<g clip-path="url(#r{i})">'
                 + label(RX + 18, y, k, c["muted"], 12.5, "start", 400, 0)
                 + label(RX + RW - 18, y, v, c["text"], 13, "end", 500, 0)
                 + "</g>")

    fy = PY + PH - 14
    o.append(f'<circle cx="{RX + 21}" cy="{fy - 3}" r="3" fill="{c["ok"]}"/>')
    o.append(label(RX + 30, fy, p.get("status_left", "ALL SYSTEMS NOMINAL"), c["ok"], 9.5, "start", 400, 0.8))
    o.append(label(RX + RW - 18, fy, p.get("status_right", ""), c["muted"], 9.5, "end", 400, 0.8))

    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    if "--still" in sys.argv:
        which = sys.argv[sys.argv.index("--still") + 1]
        for theme in PAL:
            out = ROOT / "assets" / f"_still-{which}-{theme}.svg"
            out.write_text(build(theme, still=which), encoding="utf-8")
            print("wrote", out.name)
    else:
        for theme in PAL:
            write(f"banner-{theme}.svg", build(theme))
