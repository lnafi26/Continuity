#!/usr/bin/env python3
"""Build a public-safe, synthetic Continuity Night Observatory Pages artifact.

Only the synthetic preview and its explicitly referenced local
night-observatory CSS/JS are eligible. Do not publish frontend/ wholesale.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets: list[str] = []
        self.has_base = False

    def handle_starttag(self, tag, pairs):
        values = dict(pairs)
        if tag == "base":
            self.has_base = True
        if tag == "script" and values.get("src"):
            self.assets.append(values["src"])
        elif tag == "link" and values.get("href"):
            if "stylesheet" not in values.get("rel", "").split():
                raise ValueError("Unexpected linked resource")
            self.assets.append(values["href"])
        elif tag in {"img", "source", "audio", "video", "iframe"}:
            if any(values.get(key) for key in ("src", "srcset", "poster")):
                raise ValueError("Unreviewed embedded resource: " + tag)


def checked_asset(frontend: Path, reference: str) -> tuple[Path, Path]:
    uri = urlsplit(reference.strip())
    if uri.scheme or uri.netloc or not uri.path or uri.path.startswith("/"):
        raise ValueError("Disallowed external/root-relative asset: " + reference)
    relative = Path(unquote(uri.path))
    if (
        len(relative.parts) != 3
        or relative.parts[0] != "assets"
        or relative.parts[1] not in ("css", "js")
        or not relative.name.startswith("night-observatory-")
        or relative.suffix != (".css" if relative.parts[1] == "css" else ".js")
    ):
        raise ValueError("Disallowed staging asset: " + reference)
    full = frontend / relative
    if full.is_symlink() or not full.is_file() or not full.resolve().is_relative_to(frontend):
        raise ValueError("Missing or unsafe asset: " + reference)
    return full, relative


def build(repo: Path, destination: Path) -> None:
    repo = repo.resolve()
    frontend = (repo / "frontend").resolve()
    preview = frontend / "night-observatory-preview.html"
    if not preview.is_file() or preview.is_symlink():
        raise ValueError("Synthetic preview not found")
    html = preview.read_text(encoding="utf-8")
    references = References()
    references.feed(html)
    if references.has_base:
        raise ValueError("Base tag changes relative resolution")
    if len(references.assets) < 2 or len(references.assets) > 80:
        raise ValueError("Unusual number of preview assets")
    if len(references.assets) != len(set(references.assets)):
        raise ValueError("Duplicate asset reference")

    assets = [checked_asset(frontend, value) for value in references.assets]
    required = {
        Path("assets/css/night-observatory-shell.css"),
        Path("assets/js/night-observatory-selection.js"),
        Path("assets/js/night-observatory-branching-visuals.js"),
        Path("assets/js/night-observatory-junction-inspector.js"),
    }
    if not required.issubset({rel for _, rel in assets}):
        raise ValueError("Missing essential Night Observatory dependencies")

    # Fail closed if future preview code introduces network access,
    # imported assets, or dynamic loading without explicit review.
    network_api = re.compile(
        r"\bfetch\s*\(|\b(?:XMLHttpRequest|WebSocket|EventSource|sendBeacon)\b|"
        r"\bimport\s*\(", re.IGNORECASE
    )
    inline_html = re.sub(r"<script[^>]*src=[^>]*>.*?</script>", "", html, flags=re.I | re.S)
    if network_api.search(inline_html):
        raise ValueError("Unexpected network API in public preview HTML")
    for full, relative in assets:
        body = full.read_text(encoding="utf-8")
        if relative.suffix == ".css":
            if re.search(r"@import\b|url\s*\(", body, re.IGNORECASE):
                raise ValueError("CSS nested imports/assets need review: " + str(relative))
        elif network_api.search(body):
            raise ValueError("Network API/dynamic loading needs review: " + str(relative))

    destination = destination.resolve()
    if destination == frontend or destination.is_relative_to(frontend):
        raise ValueError("Output must not be inside source frontend")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Output directory must be empty")
    destination.mkdir(parents=True, exist_ok=True)

    if not re.search(r'<meta\s+name=["\']robots["\']', html, re.I):
        if html.count("<head>") != 1:
            raise ValueError("Ambiguous HTML head")
        html = html.replace(
            "<head>",
            '<head>\n  <meta name="robots" content="noindex, nofollow">',
            1,
        )
    (destination / "index.html").write_text(html, encoding="utf-8")
    (destination / ".nojekyll").write_text("", encoding="utf-8")
    for source, relative in assets:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    count = len([p for p in destination.rglob("*") if p.is_file()])
    assert count == len(assets) + 2
    print(f"Staging bundle: {count} files, {len(assets)} local assets, no external dependencies")
    print(f"Output: {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/staging")
    args = parser.parse_args()
    build(Path(__file__).resolve().parent.parent, Path(args.output))
