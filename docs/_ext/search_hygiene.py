# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Keep docs.pain001.com crawlable without dead or duplicate URLs.

GitHub Pages cannot issue server redirects, so each retired URL gets a
static stub that meta-refreshes to the page that replaced it and names
that page as canonical. Pages a search engine should not index (the
viewcode ``_modules`` sources, the search page and the generated
indexes) carry ``noindex, follow``. ``sitemap.xml`` lists only the
indexable documents, so it never names a stub or a ``noindex`` page.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

NOINDEX_PREFIXES = ("_modules/",)
NOINDEX_PAGES = frozenset({"genindex", "py-modindex", "search"})
ROBOTS_META = '<meta name="robots" content="noindex, follow" />\n'


def is_noindex(pagename: str) -> bool:
    """Return True for a page that must stay out of the search index."""
    return pagename in NOINDEX_PAGES or pagename.startswith(NOINDEX_PREFIXES)


def render_stub(base_url: str, target: str) -> str:
    """Return the HTML of a redirect stub pointing at ``target``."""
    canonical = html.escape(base_url + target.split("#", 1)[0])
    url = html.escape("/" + target)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        f'    <meta http-equiv="refresh" content="0; url={url}" />\n'
        f'    <link rel="canonical" href="{canonical}" />\n'
        "    <title>This page has moved</title>\n"
        "  </head>\n"
        "  <body>\n"
        f'    <p>This page has moved to <a href="{url}">{url}</a>.</p>\n'
        "  </body>\n"
        "</html>\n"
    )


def render_sitemap(base_url: str, pagenames: list[str]) -> str:
    """Return a sitemap listing the indexable pages in ``pagenames``."""
    urls = sorted(
        base_url + name + ".html" for name in pagenames if not is_noindex(name)
    )
    entries = "".join(
        f"  <url><loc>{escape(url)}</loc></url>\n" for url in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}"
        "</urlset>\n"
    )


def check_redirects(
    redirects: dict[str, str], pagenames: set[str]
) -> list[str]:
    """Return a message for each redirect that is shadowed or dangling."""
    problems = []
    for source, target in sorted(redirects.items()):
        if source.removesuffix(".html") in pagenames:
            problems.append(f"{source} is still built; drop its redirect")
        target_page = target.split("#", 1)[0].removesuffix(".html")
        if target_page not in pagenames:
            problems.append(f"{source} -> {target}: target is not built")
    return problems


def _page_context(
    app: Any, pagename: str, templatename: str, context: dict, doctree: Any
) -> None:
    if is_noindex(pagename):
        context["metatags"] = context.get("metatags", "") + ROBOTS_META
        # A noindex page that names itself canonical sends mixed signals.
        context["pageurl"] = None


def _write_outputs(app: Any, exception: Exception | None) -> None:
    if exception is not None or app.builder.format != "html":
        return
    base_url = app.config.html_baseurl
    outdir = Path(app.outdir)
    pagenames = set(app.env.found_docs)
    redirects = app.config.search_hygiene_redirects
    problems = check_redirects(redirects, pagenames)
    if problems:
        raise RuntimeError("; ".join(problems))
    for source, target in redirects.items():
        stub = outdir / source
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text(render_stub(base_url, target), encoding="utf-8")
    sitemap = render_sitemap(base_url, sorted(pagenames))
    (outdir / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def setup(app: Any) -> dict[str, Any]:
    """Register the redirect map, the noindex hook and the outputs."""
    app.add_config_value("search_hygiene_redirects", {}, "html")
    app.connect("html-page-context", _page_context)
    app.connect("build-finished", _write_outputs)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
