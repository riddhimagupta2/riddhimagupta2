"""Shared colors and helpers for every generator script."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

THEMES = {
    "dark": dict(bg="#0d1117", bar="#161b22", border="#30363d", grid="#30363d",
                 text="#e6edf3", muted="#8b949e"),
    "light": dict(bg="#ffffff", bar="#f6f8fa", border="#d0d7de", grid="#d0d7de",
                  text="#1f2328", muted="#656d76"),
}

FONT = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',monospace"


def load_profile():
    return json.loads((ASSETS / "profile.json").read_text(encoding="utf-8"))


def load_json(name):
    return json.loads((ASSETS / name).read_text(encoding="utf-8"))


def write(name, svg):
    (ASSETS / name).write_text(svg, encoding="utf-8")
    print(f"wrote assets/{name} ({len(svg) / 1024:.1f} KB)")
