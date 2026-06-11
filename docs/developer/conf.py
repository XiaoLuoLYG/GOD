from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

project = "GOD"
author = "GOD contributors"
copyright = f"{datetime.now().year}, GOD contributors"
release = "0.2.0"
version = "0.2"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
DOCS_DIR = Path(__file__).resolve().parent
templates_path = ["_templates"] if (DOCS_DIR / "_templates").exists() else []

html_theme = "furo"
html_title = "GOD Developer Docs"
html_short_title = "GOD Docs"
html_static_path = ["_static"] if (DOCS_DIR / "_static").exists() else []

html_theme_options = {
    "navigation_with_keys": True,
    "source_repository": "https://github.com/XiaoLuoLYG/GOD/",
    "source_branch": "main",
    "source_directory": "docs/developer/",
}

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "undoc-members": False,
}
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = True

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "html_image",
    "linkify",
    "replacements",
    "strikethrough",
    "tasklist",
]
myst_heading_anchors = 3

rst_epilog = f"""
.. |repo_root| replace:: {ROOT}
"""
