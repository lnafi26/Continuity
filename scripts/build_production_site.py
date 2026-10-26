#!/usr/bin/env python3
"""Build only the reviewed Continuity production artifact.

A versioned mode gate keeps production on its current holding page until a
separate, explicitly reviewed PR changes the mode to the synthetic preview.
No backend, auth, Supabase config, or HF runtime is copied into this output.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil

from build_staging_site import build as build_synthetic_preview

MODES = {"holding", "synthetic-preview"}


class HoldingPageCheck(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "link", "iframe", "object", "embed", "form", "base", "img"}:
            raise ValueError("Holding page contains an unreviewed element: " + tag)
        if any(
            key.startswith("on") or key in {"src", "srcset", "href", "action", "formaction"}
            for key in attributes
        ):
            raise ValueError("Holding page contains external/interactive attributes")
        if tag == "meta" and attributes.get("http-equiv", "").lower() == "refresh":
            raise ValueError("Holding page must not redirect")


def read_mode(repo: Path) -> str:
    config = repo / "deploy" / "production-release.json"
    if config.is_symlink() or not config.is_file():
        raise ValueError("Production release configuration missing or unsafe")
    settings = json.loads(config.read_text(encoding="utf-8"))
    if (
        not isinstance(settings, dict)
        or set(settings) != {"schema_version", "mode"}
        or settings["schema_version"] != 1
        or type(settings["schema_version"]) is not int
        or not isinstance(settings["mode"], str)
        or settings["mode"] not in MODES
    ):
        raise ValueError("Production release configuration is invalid")
    return settings["mode"]


def build(repo: Path, destination: Path, *, mode: str | None = None) -> str:
    repo = repo.resolve()
    if mode is None:
        mode = read_mode(repo)
    if mode not in MODES:
        raise ValueError("Unknown production mode")
    destination = destination.resolve()
    source_frontend = (repo / "frontend").resolve()
    if destination == source_frontend or destination.is_relative_to(source_frontend):
        raise ValueError("Output must not be placed under source frontend")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Production output directory must be empty")

    if mode == "synthetic-preview":
        # Reuse exactly the same allowlisted static build proven on staging.
        build_synthetic_preview(repo, destination)
    else:
        holding = repo / "deploy" / "production" / "index.html"
        if holding.is_symlink() or not holding.is_file():
            raise ValueError("Production holding page missing")
        html = holding.read_text(encoding="utf-8")
        if "<html" not in html or "Continuity" not in html:
            raise ValueError("Unexpected production holding page")
        if re.search(r"@import\b|url\s*\(|javascript:", html, re.IGNORECASE):
            raise ValueError("Holding page contains unreviewed loading")
        checker = HoldingPageCheck()
        checker.feed(html)
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(holding, destination / "index.html")

    output = sorted(path.relative_to(destination).as_posix()
                    for path in destination.rglob("*") if path.is_file())
    if mode == "holding" and output != ["index.html"]:
        raise ValueError("Holding build must contain only index.html")
    if mode == "synthetic-preview" and (
        len(output) < 4 or output[0] != ".nojekyll" or "index.html" not in output
    ):
        raise ValueError("Synthetic preview build does not match expected structure")
    print(f"Production release mode: {mode}; files: {len(output)}")
    print(f"Output directory: {destination}")
    return mode


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/production")
    args = parser.parse_args()
    build(Path(__file__).resolve().parent.parent, Path(args.output))
