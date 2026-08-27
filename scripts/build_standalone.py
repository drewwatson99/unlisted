#!/usr/bin/env python3
"""
Bundle the web app into a single self-contained HTML file.

The result has the stylesheet, application code and broker data all inlined,
so it runs with no server and no network access at all. Useful for people who
want to download one file, disconnect, and work through it offline - which is
the strongest possible version of this tool's privacy guarantee.

Usage:
    python3 scripts/build_standalone.py
    -> dist/unlisted.html
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, "web")
DIST = os.path.join(ROOT, "dist")


def main():
    index_path = os.path.join(WEB, "index.html")
    app_path = os.path.join(WEB, "app.js")
    data_path = os.path.join(WEB, "brokers.json")

    for p in (index_path, app_path, data_path):
        if not os.path.exists(p):
            print(f"error: missing {p}\n"
                  f"       run: python3 scripts/build_dataset.py", file=sys.stderr)
            return 1

    with open(index_path, encoding="utf-8") as f:
        html = f.read()
    with open(app_path, encoding="utf-8") as f:
        app = f.read()
    with open(data_path, encoding="utf-8") as f:
        payload = json.load(f)

    # Replace the fetch with an inlined constant so the page makes no requests.
    app = app.replace(
        "    const res = await fetch('brokers.json');\n"
        "    const payload = await res.json();\n",
        "    const payload = window.__UNLISTED_DATA__;\n")

    # </script> inside a JSON string would close the tag early.
    data_js = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) \
        .replace("</", "<\\/")

    bundle = (
        f'<script>window.__UNLISTED_DATA__={data_js};</script>\n'
        f'<script>\n{app}\n</script>'
    )

    html, n = re.subn(r'<script src="app\.js"></script>', lambda _: bundle, html, count=1)
    if not n:
        print("error: could not find the app.js script tag in index.html", file=sys.stderr)
        return 1

    # Note the offline nature in the title attribute-free way: a small banner.
    html = html.replace(
        '<span class="tagline">data broker opt-out workbench</span>',
        '<span class="tagline">data broker opt-out workbench · offline single file</span>')

    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "unlisted.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    kb = os.path.getsize(out) / 1024
    print(f"Wrote {out} ({kb:.0f} KB, {len(payload['brokers'])} brokers)")
    print("This file runs offline with no network requests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
