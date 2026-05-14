"""Tests for first_paragraph Jinja filter — hero 캐러셀 인용용."""
from app.templating_filters import first_paragraph


def test_first_paragraph_returns_empty_for_none():
    assert first_paragraph(None) == ""


def test_first_paragraph_returns_empty_for_empty_string():
    assert first_paragraph("") == ""


def test_first_paragraph_returns_short_body_unchanged():
    assert first_paragraph("짧은 본문", 140) == "짧은 본문"


def test_first_paragraph_returns_only_first_paragraph_not_joined():
    body = "첫 단락.\n\n둘째 단락. 노출되면 안됨."
    out = first_paragraph(body)
    assert out == "첫 단락."
    assert "둘째 단락" not in out


def test_first_paragraph_drops_bullet_list_body():
    """양평 1년차 후기 시드 — bullet list가 인용에 끼어들지 않는다."""
    body = (
        "도시에서 양평으로 이주 1년차.\n\n"
        "**의외로 좋은 점**\n"
        "- 동네 카페 사장님과 친해짐\n"
        "- 마트 배송이 의외로 빠름\n"
        "- 밤하늘이 정말 다름\n\n"
        "**별로인 점**\n"
        "- 응급실까지 30분"
    )
    out = first_paragraph(body, 140)
    assert out == "도시에서 양평으로 이주 1년차."
    assert "의외로 좋은 점" not in out
    assert "동네 카페" not in out
    assert "별로인 점" not in out


def test_first_paragraph_truncates_long_first_paragraph_with_ellipsis():
    body = "가" * 200 + "\n\n둘째 단락"
    out = first_paragraph(body, 140)
    assert out.endswith("…")
    assert len(out) == 141
    assert "둘째 단락" not in out


def test_first_paragraph_skips_image_only_first_paragraph():
    body = "![](/img/1/orig)\n\n실제 첫 단락"
    assert first_paragraph(body) == "실제 첫 단락"


def test_first_paragraph_strips_bold_markers():
    body = "**제목 같은 첫 줄**\n\n본문"
    out = first_paragraph(body)
    assert out == "제목 같은 첫 줄"
    assert "**" not in out


def test_first_paragraph_strips_heading_markers():
    body = "# 제목\n\n본문 내용"
    out = first_paragraph(body)
    assert out == "제목"


def test_first_paragraph_collapses_internal_newlines_within_first_paragraph():
    """첫 단락 내부 줄바꿈은 공백으로 — 다단계 paragraph가 아닌 경우 한 줄 인용."""
    body = "긴 첫 단락이\n두 줄에 걸쳐 있을 때\n공백으로 합쳐진다."
    out = first_paragraph(body)
    assert out == "긴 첫 단락이 두 줄에 걸쳐 있을 때 공백으로 합쳐진다."


def test_first_paragraph_returns_empty_when_only_images():
    body = "![](/img/1/orig)\n\n![](/img/2/orig)"
    assert first_paragraph(body) == ""
