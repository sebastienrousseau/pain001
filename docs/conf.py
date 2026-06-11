# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import pain001

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
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# MyST Parser configuration
myst_enable_checkboxes = True
myst_heading_anchors = 3


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]

# PyData theme configuration
html_theme_options = {
    "navbar_start": ["navbar-logo"],
    "navbar_center": ["navbar-nav"],
    "navbar_end": ["navbar-icon-links"],
    "navbar_persistent": [],
    "primary_sidebar_end": ["indices"],
    "footer_items": ["copyright", "sphinx-version"],
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
