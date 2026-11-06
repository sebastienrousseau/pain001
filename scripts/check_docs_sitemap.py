# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Check that a built docs site's sitemap lists only indexable pages.

Every ``<loc>`` in ``sitemap.xml`` must name a page that exists in the
build, carries no ``noindex`` and declares itself canonical. Run after
``sphinx-build``::

    python scripts/check_docs_sitemap.py docs/_build/html
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.etree import ElementTree

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
BASE_URL = "https://docs.pain001.com/"
CANONICAL = re.compile(r'<link rel="canonical" href="([^"]+)"')
NOINDEX = re.compile(r'<meta name="robots" content="[^"]*noindex')


def sitemap_urls(site: Path) -> list[str]:
    """Return every ``<loc>`` in the site's sitemap.xml."""
    root = ElementTree.parse(site / "sitemap.xml").getroot()
    return [loc.text or "" for loc in root.iter(f"{NS}loc")]


def check_url(site: Path, url: str) -> str | None:
    """Return why ``url`` does not belong in the sitemap, or None."""
    if not url.startswith(BASE_URL):
        return f"{url}: outside {BASE_URL}"
    page = site / url.removeprefix(BASE_URL)
    if not page.is_file():
        return f"{url}: not in the build"
    text = page.read_text(encoding="utf-8")
    if NOINDEX.search(text):
        return f"{url}: page is noindex"
    match = CANONICAL.search(text)
    if match is None or match.group(1) != url:
        return f"{url}: canonical is not self"
    return None


def main(argv: list[str]) -> int:
    """Check the build named in ``argv`` and report each problem."""
    site = Path(argv[1]) if len(argv) > 1 else Path("docs/_build/html")
    urls = sitemap_urls(site)
    problems = [p for url in urls if (p := check_url(site, url))]
    for problem in problems:
        print(problem, file=sys.stderr)
    if not urls:
        print("sitemap.xml lists no pages", file=sys.stderr)
    print(f"{len(urls)} sitemap URLs, {len(problems)} problems")
    return 1 if problems or not urls else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
