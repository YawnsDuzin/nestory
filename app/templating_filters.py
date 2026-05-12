"""Jinja filters for templates."""
import html as _html
import re

import markdown as md

_IMG_ORIG_RE = re.compile(r'src="/img/(\d+)/orig"')
_DANGEROUS_HREF_RE = re.compile(
    r'href="\s*(?:javascript|data|vbscript)\s*:[^"]*"',
    flags=re.IGNORECASE,
)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def first_image_url(text: str | None) -> str | None:
    """Return the first markdown image URL in `text`, mapping /orig → /medium for list previews."""
    if not text:
        return None
    m = _MD_IMAGE_RE.search(text)
    if not m:
        return None
    url = m.group(1).strip()
    if url.startswith("/img/") and url.endswith("/orig"):
        return url[: -len("/orig")] + "/medium"
    return url


def strip_markdown_images(text: str | None) -> str:
    """Strip markdown image syntax — for plain-text body excerpts in list cards."""
    if not text:
        return ""
    return _MD_IMAGE_RE.sub("", text).strip()


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


__all__ = ["first_image_url", "markdown_to_html", "strip_markdown_images"]
