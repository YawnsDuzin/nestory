"""Tests for markdown_to_html Jinja filter."""
from app.templating_filters import markdown_to_html


def test_basic_markdown_to_html():
    html = markdown_to_html("# Heading\n\nparagraph")
    assert "<h1>" in html and "Heading" in html
    assert "<p>paragraph</p>" in html


def test_image_url_swap_orig_to_medium():
    html = markdown_to_html("![](/img/42/orig)")
    assert 'src="/img/42/medium"' in html
    assert 'loading="lazy"' in html
    assert "/img/42/orig" not in html


def test_image_swap_only_affects_internal_urls():
    html = markdown_to_html("![](https://other.com/img/42/orig)")
    assert "https://other.com/img/42/orig" in html
    assert "/medium" not in html


def test_raw_html_is_escaped():
    html = markdown_to_html('<script>alert(1)</script>\n\nhi')
    assert "<script>" not in html  # markdown lib escapes by default
    assert "alert(1)" in html  # text is preserved escaped


def test_fenced_code_block():
    html = markdown_to_html("```\nprint('hi')\n```")
    assert "<code>" in html
    assert "print('hi')" in html


def test_nl2br_converts_single_newlines():
    html = markdown_to_html("line1\nline2")
    assert "<br" in html


def test_javascript_url_neutralized():
    """Markdown link [x](javascript:alert(1)) must not produce executable href."""
    html = markdown_to_html("[click](javascript:alert(1))")
    assert 'href="#"' in html
    assert "javascript:" not in html


def test_data_url_neutralized():
    html = markdown_to_html("[x](data:text/html,<script>alert(1)</script>)")
    assert 'href="#"' in html
    assert "data:" not in html


def test_vbscript_url_neutralized():
    html = markdown_to_html("[x](VBScript:msgbox('xss'))")
    assert 'href="#"' in html
    assert "vbscript" not in html.lower()


def test_safe_https_url_preserved():
    html = markdown_to_html("[example](https://example.com/page)")
    assert 'href="https://example.com/page"' in html


def test_safe_relative_url_preserved():
    html = markdown_to_html("[home](/feed)")
    assert 'href="/feed"' in html


def test_image_with_title_still_swaps():
    """Pin behavior: ![alt](/img/1/orig "caption") still gets variant swap."""
    html = markdown_to_html('![alt](/img/1/orig "caption")')
    assert 'src="/img/1/medium"' in html
    assert 'loading="lazy"' in html
