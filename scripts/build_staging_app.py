#!/usr/bin/env python3
"""Build an isolated Continuity full-application staging artifact.

Not used by the existing synthetic preview workflow.
Never copy the repository's browser configuration.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit, unquote

CSS = {
    'assets/css/continuity-live-canvas.css',
    'assets/css/continuity-live-observatory.css',
    'assets/css/continuity-record-relationship-visuals.css',
    'assets/css/continuity-relationship-inspector.css',
    'assets/css/styles.css',
}

JS = {
    'assets/js/auth.js',
    'assets/js/continuity-authenticated-relationship-feed.js',
    'assets/js/continuity-live-canvas.js',
    'assets/js/continuity-live-observatory.js',
    'assets/js/continuity-record-relationship-visuals.js',
    'assets/js/continuity-record-relationships.js',
    'assets/js/continuity-relationship-composer.js',
    'assets/js/continuity-relationship-data-boundary.js',
    'assets/js/continuity-relationship-inspector.js',
    'assets/js/dashboard.js',
    'assets/js/manual-projects.js',
    'assets/js/reset-password.js',
}

CONFIG = 'config/supabase-config.js'
PAGES = {'index.html', 'reset-password.html'}
ASSETS = CSS | JS | {CONFIG}

ALLOWED_CDN = (
    'https://cdn.jsdelivr.net/npm/'
    '@supabase/supabase-js@2.118.0'
)

REF_RE = re.compile(r'[a-z0-9]{20}\Z')
KEY_RE = re.compile(
    r'sb_publishable_[A-Za-z0-9_-]{8,}\Z'
)


class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.has_base = False

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)

        if tag == 'base':
            self.has_base = True

        if tag == 'script' and attrs.get('src'):
            self.refs.append(attrs['src'])

        elif tag == 'link' and attrs.get('href'):
            if 'stylesheet' not in attrs.get('rel', '').split():
                raise ValueError('Unreviewed linked resource')
            self.refs.append(attrs['href'])

        elif tag in {
            'img', 'source', 'audio', 'video',
            'iframe', 'object', 'embed'
        }:
            if any(
                attrs.get(key)
                for key in ('src', 'srcset', 'poster', 'data')
            ):
                raise ValueError('Unreviewed embedded resource')


def config_value(source, key):
    pattern = (
        r'^\s*' + re.escape(key) +
        r'\s*:\s*([\'"])([^\'"\r\n]+)\1'
    )
    match = re.search(pattern, source, re.M)

    if not match:
        raise ValueError(
            'Existing browser configuration cannot be '
            'safely compared'
        )

    return match.group(2)


def staging_settings(repo, env):
    project_ref = env.get(
        'CONTINUITY_STAGING_SUPABASE_PROJECT_REF', ''
    )
    url = env.get(
        'CONTINUITY_STAGING_SUPABASE_URL', ''
    )
    key = env.get(
        'CONTINUITY_STAGING_SUPABASE_PUBLISHABLE_KEY', ''
    )

    if not REF_RE.fullmatch(project_ref):
        raise ValueError(
            'Dedicated staging Supabase project ref required'
        )

    if url != f'https://{project_ref}.supabase.co':
        raise ValueError(
            'Staging URL must match declared staging project'
        )

    if not KEY_RE.fullmatch(key):
        raise ValueError(
            'Staging publishable key required; '
            'secret and legacy JWT keys forbidden'
        )

    if env.get('CONTINUITY_STAGING_OAUTH_BASE_URL'):
        raise ValueError(
            'Staging OAuth requires separate backend review'
        )

    existing = repo / 'frontend' / CONFIG

    if existing.is_symlink() or not existing.is_file():
        raise ValueError('Existing configuration unavailable')

    current = existing.read_text(encoding='utf-8')

    live_url = config_value(current, 'url')
    live_key = config_value(current, 'publishableKey')

    if url == live_url or key == live_key:
        raise ValueError(
            'Staging settings match the existing application'
        )

    return {
        'url': url,
        'publishableKey': key,
        'oauthBaseUrl': '',
    }


def check_page(frontend, name):
    path = frontend / name

    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or unsafe application page')

    html = path.read_text(encoding='utf-8')
    references = Resources()
    references.feed(html)

    if references.has_base:
        raise ValueError('Base element changes path resolution')

    local = set()
    external = []

    for reference in references.refs:
        parsed = urlsplit(reference.strip())

        if parsed.scheme or parsed.netloc:
            external.append(reference.strip())
            continue

        if not parsed.path or parsed.path.startswith('/'):
            raise ValueError('Unsafe asset path')

        relative = unquote(parsed.path)

        if (
            relative not in ASSETS
            or (
                parsed.query
                and not re.fullmatch(
                    r'v=[0-9]+', parsed.query
                )
            )
            or parsed.fragment
            or relative in local
        ):
            raise ValueError(
                'Unreviewed or malformed asset: ' + relative
            )

        local.add(relative)

    if external != [ALLOWED_CDN]:
        raise ValueError('Unreviewed external dependency')

    return html, local


def build(repo, destination, env):
    repo = repo.resolve()
    frontend = (repo / 'frontend').resolve()

    if not frontend.is_dir():
        raise ValueError('Frontend directory missing')

    settings = staging_settings(repo, env)

    pages = {
        name: check_page(frontend, name)
        for name in PAGES
    }

    references = set.union(
        *(assets for _, assets in pages.values())
    )

    if references != ASSETS:
        raise ValueError(
            'Application dependencies differ from '
            'the reviewed asset manifest'
        )

    for relative in CSS | JS:
        path = frontend / relative

        if (
            path.is_symlink()
            or not path.is_file()
            or not path.resolve().is_relative_to(frontend)
        ):
            raise ValueError(
                'Missing or unsafe asset: ' + relative
            )

        if relative in CSS:
            body = path.read_text(encoding='utf-8')

            if re.search(
                r'@import\b|url\s*\(', body, re.I
            ):
                raise ValueError(
                    'Nested CSS assets require review'
                )

    # Check copied source for embedded backend configuration.
    backend_pattern = (
        r'https?://[a-z0-9]{20}\.supabase\.co'
        r'|sb_(?:secret|publishable)_[A-Za-z0-9_-]+'
    )

    for html, _ in pages.values():
        if re.search(backend_pattern, html):
            raise ValueError(
                'Embedded backend configuration in HTML'
            )

    for relative in CSS | JS:
        body = (frontend / relative).read_text(
            encoding='utf-8'
        )

        if re.search(backend_pattern, body):
            raise ValueError(
                'Embedded backend configuration in assets'
            )

        if relative in JS and re.search(
            r'\bimport\s*\(', body
        ):
            raise ValueError(
                'Dynamic imports require separate review'
            )

    destination = destination.resolve()

    if (
        destination == frontend
        or destination.is_relative_to(frontend)
    ):
        raise ValueError(
            'Output cannot be inside frontend source'
        )

    if destination.exists() and (
        not destination.is_dir()
        or any(destination.iterdir())
    ):
        raise ValueError('Output directory must be empty')

    generated_config = (
        '// Generated staging configuration; OAuth disabled.\n'
        'window.SUPABASE_CONFIG = '
        + json.dumps(
            settings, separators=(',', ':')
        )
        + ';\n'
    )

    destination.mkdir(parents=True, exist_ok=True)

    for name, (html, _) in pages.items():
        (destination / name).write_text(
            html, encoding='utf-8'
        )

    for relative in sorted(CSS | JS):
        target = destination / relative
        target.parent.mkdir(
            parents=True, exist_ok=True
        )
        shutil.copy2(frontend / relative, target)

    target = destination / CONFIG
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        generated_config, encoding='utf-8'
    )

    (destination / '.nojekyll').write_text(
        '', encoding='utf-8'
    )

    files = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob('*')
        if path.is_file()
    }

    assert files == ASSETS | PAGES | {'.nojekyll'}

    print(
        f'Full-app staging artifact validated: '
        f'{len(files)} allowlisted files'
    )
    print(
        'Existing Supabase config not copied; '
        'OAuth disabled; no deployment'
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    build(
        Path(__file__).resolve().parent.parent,
        Path(args.output),
        dict(os.environ),
    )
