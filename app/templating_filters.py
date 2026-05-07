"""Jinja filters for templates."""
import html as _html
import re

import markdown as md

_IMG_ORIG_RE = re.compile(r'src="/img/(\d+)/orig"')
_DANGEROUS_HREF_RE = re.compile(
    r'href="\s*(?:javascript|data|vbscript)\s*:[^"]*"',
    flags=re.IGNORECASE,
)


def markdown_to_html(text: str | None) -> str:
    """Render markdown to HTML and swap /img/{id}/orig → /img/{id}/medium.

    Security:
    - HTML is pre-escaped so raw <script>/<img onerror=...> injected by users
      is rendered as text, not executed. python-markdown 3.x has no safe_mode.
    - Dangerous URL schemes (javascript:, data:, vbscript:) in markdown link
      hrefs are replaced with href="#" — markdown's [text](url) syntax
      bypasses the pre-escape.
    """
    if not text:
        return ""
    escaped = _html.escape(text, quote=False)
    html = md.markdown(escaped, extensions=["fenced_code", "nl2br"])
    html = _IMG_ORIG_RE.sub(r'src="/img/\1/medium" loading="lazy"', html)
    html = _DANGEROUS_HREF_RE.sub('href="#"', html)
    return html


__all__ = ["markdown_to_html"]
