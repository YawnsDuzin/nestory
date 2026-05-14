"""Jinja filters for templates."""
import html as _html
import re
from datetime import UTC, datetime

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


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_HEADING_RE = re.compile(r"^#+\s+", flags=re.MULTILINE)
_IMG_ONLY_LINE_RE = re.compile(r"^!\[[^\]]*\]\([^)]+\)\s*$")


def _is_image_only_paragraph(paragraph: str) -> bool:
    lines = [ln.strip() for ln in paragraph.splitlines() if ln.strip()]
    return bool(lines) and all(_IMG_ONLY_LINE_RE.fullmatch(ln) for ln in lines)


def excerpt(body: str | None, max_chars: int = 140) -> str:
    """Strip image-only paragraphs + light markdown, join with space, truncate."""
    if not body:
        return ""
    chunks: list[str] = []
    for paragraph in body.split("\n\n"):
        stripped = paragraph.strip()
        if not stripped or _is_image_only_paragraph(stripped):
            continue
        cleaned = _HEADING_RE.sub("", stripped)
        cleaned = _BOLD_RE.sub(r"\1", cleaned)
        cleaned = _MD_IMAGE_RE.sub("", cleaned)  # strip inline image syntax
        cleaned = " ".join(line.strip() for line in cleaned.splitlines() if line.strip())
        chunks.append(cleaned)
    text = " ".join(chunks)
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text


def first_paragraph(body: str | None, max_chars: int = 140) -> str:
    """Return only the first non-empty, non-image-only paragraph as a single line.

    Hero quote 카드용 — bullet list가 포함된 본문이 excerpt 처럼 한 덩어리로
    뭉쳐 보이는 문제를 회피한다. 첫 단락은 보통 한 줄 헤드라인이므로 짧고
    인상적인 인용으로 노출된다.
    """
    if not body:
        return ""
    for paragraph in body.split("\n\n"):
        stripped = paragraph.strip()
        if not stripped or _is_image_only_paragraph(stripped):
            continue
        cleaned = _HEADING_RE.sub("", stripped)
        cleaned = _BOLD_RE.sub(r"\1", cleaned)
        cleaned = _MD_IMAGE_RE.sub("", cleaned)
        cleaned = " ".join(line.strip() for line in cleaned.splitlines() if line.strip())
        if len(cleaned) > max_chars:
            return cleaned[:max_chars].rstrip() + "…"
        return cleaned
    return ""


def resident_year(verified_at: datetime | None) -> str:
    """Return '{N}년차' label, or '' when verified_at is None.

    0년차도 1년차로 표시 (UI 친화), 미래 시각은 1년차로 clamp.
    """
    if verified_at is None:
        return ""
    days = (datetime.now(UTC) - verified_at).days
    years = max(1, days // 365)
    return f"{years}년차"


__all__ = [
    "excerpt",
    "first_image_url",
    "first_paragraph",
    "markdown_to_html",
    "resident_year",
    "strip_markdown_images",
]
