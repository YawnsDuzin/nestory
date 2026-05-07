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
