"""Jinja filters for templates."""
import html as _html
import re

import markdown as md

_IMG_ORIG_RE = re.compile(r'src="/img/(\d+)/orig"')


def markdown_to_html(text: str | None) -> str:
    """Render markdown to HTML and swap /img/{id}/orig → /img/{id}/medium.

    Raw HTML in input is escaped before markdown rendering — python-markdown 3.x
    no longer offers a safe_mode, so we pre-escape `<`, `>`, `&` to neutralize
    inline HTML/script injection while preserving markdown syntax characters.
    """
    if not text:
        return ""
    escaped = _html.escape(text, quote=False)
    html = md.markdown(escaped, extensions=["fenced_code", "nl2br"])
    html = _IMG_ORIG_RE.sub(r'src="/img/\1/medium" loading="lazy"', html)
    return html


__all__ = ["markdown_to_html"]
