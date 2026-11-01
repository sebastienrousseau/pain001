# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import sys
from pathlib import Path

import pain001

sys.path.insert(0, str(Path(__file__).parent / "_ext"))

project = "Pain001"
copyright = "2023-2026, Pain001. All rights reserved."
author = "Sebastien Rousseau"
release = pain001.__version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_design",
    "myst_parser",
    "search_hygiene",
]

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "readme-template.md",
    "adr/template.md",
]

# Document definitions in their owning modules rather than indexing every
# public re-export again through package __all__ declarations.
autodoc_default_options = {"ignore-module-all": True}
# Attribute prose remains visible as fields; autodoc owns the indexed member
# declarations, avoiding duplicate targets for dataclass fields.
napoleon_use_ivar = True

# MyST Parser configuration
myst_enable_checkboxes = True
myst_heading_anchors = 3


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
# Absolute site root: Sphinx emits <link rel="canonical"> from it, and
# search_hygiene builds sitemap.xml and the redirect stubs against it.
html_baseurl = "https://docs.pain001.com/"
# robots.txt, copied verbatim into the output root.
html_extra_path = ["_extra"]

# Retired URLs and the page that replaced each. GitHub Pages cannot
# issue server redirects, so search_hygiene writes a stub at every old
# path that meta-refreshes to its target and names it as canonical.
# Targets are indexable API pages, never the noindex _modules sources.
# The build fails if a source is still built or a target is not.
_TEMPLATE_PAGES = [
    f"pain001.templates.{message}.html"
    for message in (
        *(f"pain.001.001.{n:02d}" for n in range(3, 14)),
        "pain.008.001.02",
        "pain.008.001.08",
    )
]
_XML_SOURCES = "_modules/pain001/xml/"
search_hygiene_redirects = {
    # f129ebc folded these pages into their parent package pages.
    "pain001.constants.html": "pain001.html#module-pain001.constants",
    **dict.fromkeys(_TEMPLATE_PAGES, "pain001.templates.html"),
    # d39ccd7 removed these modules; viewcode pages are noindex now.
    **{
        f"{_XML_SOURCES}create_xml_v{n}.html": (
            "pain001.xml.html#module-pain001.xml.generate_xml"
        )
        for n in (3, 4, 5, 7, 8, 10, 11)
    },
    f"{_XML_SOURCES}create_common_elements.html": (
        "pain001.xml.html#module-pain001.xml.create_xml_element"
    ),
}

# PyData theme configuration
html_theme_options = {
    "navbar_start": ["navbar-logo"],
    "navbar_center": ["navbar-nav"],
    "navbar_end": ["navbar-icon-links"],
    "navbar_persistent": [],
    "primary_sidebar_end": ["indices"],
    "footer_start": ["copyright"],
    "footer_end": ["sphinx-version"],
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/sebastienrousseau/pain001",
            "icon": "fab fa-github-square",
            "type": "fontawesome",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/pain001/",
            "icon": "fas fa-box",
            "type": "fontawesome",
        },
    ],
    "external_links": [
        {"name": "pain001.com", "url": "https://pain001.com"},
    ],
    "use_edit_page_button": True,
    "show_nav_level": 2,
}

html_context = {
    "github_user": "sebastienrousseau",
    "github_repo": "pain001",
    "github_version": "main",
    "doc_path": "docs",
    "default_mode": "light",
}
