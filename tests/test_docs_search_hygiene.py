# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Pin the docs redirect stubs, noindex rules and sitemap contract."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.check_docs_sitemap import check_url, main

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://docs.pain001.com/"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hygiene = _load("search_hygiene", ROOT / "docs/_ext/search_hygiene.py")


def _conf_redirects() -> dict[str, str]:
    sys.modules.setdefault("search_hygiene", hygiene)
    conf = _load("docs_conf", ROOT / "docs/conf.py")
    return conf.search_hygiene_redirects


def test_retired_urls_reported_by_search_console_redirect() -> None:
    """The 404s Search Console reported each have a stub and a target."""
    redirects = _conf_redirects()
    assert redirects["pain001.constants.html"] == (
        "pain001.html#module-pain001.constants"
    )
    assert redirects["pain001.templates.pain.001.001.04.html"] == (
        "pain001.templates.html"
    )
    for n in (3, 5, 7, 8, 10, 11):
        source = f"_modules/pain001/xml/create_xml_v{n}.html"
        assert not redirects[source].startswith("_modules/")


def test_deployment_checks_the_built_sitemap() -> None:
    workflow = (ROOT / ".github/workflows/docs.yml").read_text()
    assert "scripts/check_docs_sitemap.py docs/_build/html" in workflow


def test_viewcode_and_index_pages_are_noindex() -> None:
    assert hygiene.is_noindex("_modules/pain001/xml/generate_xml")
    assert hygiene.is_noindex("_modules/index")
    assert hygiene.is_noindex("genindex")
    assert hygiene.is_noindex("search")
    assert not hygiene.is_noindex("pain001.xml")


def test_noindex_page_drops_its_canonical() -> None:
    context = {"metatags": "", "pageurl": BASE + "search.html"}
    hygiene._page_context(None, "search", "", context, None)
    assert "noindex" in context["metatags"]
    assert context["pageurl"] is None
    indexed = {"metatags": "", "pageurl": BASE + "pain001.html"}
    hygiene._page_context(None, "pain001", "", indexed, None)
    assert indexed == {"metatags": "", "pageurl": BASE + "pain001.html"}


def test_stub_refreshes_and_names_target_canonical() -> None:
    stub = hygiene.render_stub(BASE, "pain001.html#module-pain001.constants")
    assert 'content="0; url=/pain001.html#module-pain001.constants"' in stub
    assert f'<link rel="canonical" href="{BASE}pain001.html" />' in stub
    assert "noindex" not in stub


def test_sitemap_lists_only_indexable_pages() -> None:
    sitemap = hygiene.render_sitemap(
        BASE, ["index", "_modules/pain001/xml/generate_xml", "search"]
    )
    assert f"<loc>{BASE}index.html</loc>" in sitemap
    assert "_modules" not in sitemap
    assert "search.html" not in sitemap


def test_redirect_check_flags_shadowed_and_dangling_entries() -> None:
    pages = {"index", "pain001"}
    assert hygiene.check_redirects({"old.html": "pain001.html#x"}, pages) == []
    problems = hygiene.check_redirects(
        {"index.html": "pain001.html", "gone.html": "missing.html"}, pages
    )
    assert problems == [
        "gone.html -> missing.html: target is not built",
        "index.html is still built; drop its redirect",
    ]


def _app(tmp_path: Path, redirects: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        builder=SimpleNamespace(format="html"),
        config=SimpleNamespace(
            html_baseurl=BASE, search_hygiene_redirects=redirects
        ),
        outdir=str(tmp_path),
        env=SimpleNamespace(found_docs={"index", "pain001"}),
    )


def test_build_writes_stubs_and_sitemap(tmp_path: Path) -> None:
    app = _app(tmp_path, {"_modules/old.html": "pain001.html"})
    hygiene._write_outputs(app, None)
    assert (tmp_path / "_modules/old.html").is_file()
    assert "pain001.html" in (tmp_path / "sitemap.xml").read_text()


def test_build_fails_on_bad_redirect_and_skips_on_error(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="target is not built"):
        hygiene._write_outputs(_app(tmp_path, {"a.html": "nope.html"}), None)
    hygiene._write_outputs(_app(tmp_path, {}), RuntimeError("build failed"))
    assert not (tmp_path / "sitemap.xml").exists()


def _page(site: Path, name: str, head: str) -> None:
    (site / name).write_text(f"<html><head>{head}</head></html>")


def test_sitemap_checker_accepts_only_canonical_indexable_pages(
    tmp_path: Path,
) -> None:
    _page(tmp_path, "ok.html", f'<link rel="canonical" href="{BASE}ok.html"')
    _page(
        tmp_path,
        "hidden.html",
        '<meta name="robots" content="noindex, follow" />',
    )
    _page(tmp_path, "other.html", f'<link rel="canonical" href="{BASE}x">')
    assert check_url(tmp_path, BASE + "ok.html") is None
    assert "noindex" in check_url(tmp_path, BASE + "hidden.html")
    assert "canonical" in check_url(tmp_path, BASE + "other.html")
    assert "not in the build" in check_url(tmp_path, BASE + "gone.html")
    assert "outside" in check_url(tmp_path, "https://pain001.com/")


def test_sitemap_checker_exit_codes(tmp_path: Path) -> None:
    _page(tmp_path, "ok.html", f'<link rel="canonical" href="{BASE}ok.html"')
    urlset = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    (tmp_path / "sitemap.xml").write_text(
        f"{urlset}<url><loc>{BASE}ok.html</loc></url></urlset>"
    )
    assert main(["check", str(tmp_path)]) == 0
    (tmp_path / "sitemap.xml").write_text(f"{urlset}</urlset>")
    assert main(["check", str(tmp_path)]) == 1
