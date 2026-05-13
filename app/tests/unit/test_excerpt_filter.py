"""Tests for excerpt Jinja filter."""
from app.templating_filters import excerpt


def test_excerpt_returns_empty_for_none():
    assert excerpt(None) == ""


def test_excerpt_returns_empty_for_empty_string():
    assert excerpt("") == ""


def test_excerpt_returns_short_body_unchanged():
    assert excerpt("짧은 본문", 140) == "짧은 본문"


def test_excerpt_truncates_long_body_with_ellipsis():
    body = "가" * 200
    out = excerpt(body, 140)
    assert out.endswith("…")
    assert len(out) == 141  # 140 chars + "…"


def test_excerpt_skips_image_only_paragraphs():
    body = "![](/img/1/orig)\n\n실제 본문입니다."
    assert excerpt(body) == "실제 본문입니다."


def test_excerpt_keeps_paragraph_with_text_and_inline_image():
    body = "텍스트와 ![](/img/1/orig) 이미지가 섞임"
    out = excerpt(body)
    # image-only 가 아니므로 paragraph 전체 보존, but inline image syntax stripped
    assert "텍스트와" in out
    assert "이미지가 섞임" in out
    assert "![" not in out  # inline image markdown not leaked
    assert "/img/1/orig" not in out


def test_excerpt_joins_multiple_paragraphs_with_space():
    body = "첫 단락.\n\n둘째 단락."
    assert excerpt(body) == "첫 단락. 둘째 단락."


def test_excerpt_strips_bold_markers():
    body = "**의외로 좋은 점**\n\n동네 카페 사장님과 친해짐"
    out = excerpt(body)
    assert "**" not in out
    assert "의외로 좋은 점" in out
    assert "동네 카페 사장님과 친해짐" in out


def test_excerpt_strips_heading_markers():
    body = "# 제목\n\n본문 내용"
    out = excerpt(body)
    assert "#" not in out
    assert "제목" in out
    assert "본문 내용" in out


def test_excerpt_alice_yp_seed_review_round_trip():
    """시드 데이터 alice_yp 5년차 후기 — T·C축 데이터가 hero 인용에 모두 노출되는지."""
    body = (
        "5년 살아보니 후회 비용이 보이네요.\n\n"
        "1. 단열 (북측 벽 보강): 약 800만원\n"
        "2. 화목난로 굴뚝 위치 잘못: 재시공 220만원\n"
        "3. 진입로 콘크리트 두께 부족: 보수 150만원\n\n"
        "이 셋만 처음에 잘했어도 천만원 가까이 아꼈을 거예요."
    )
    out = excerpt(body, 140)
    assert "5년 살아보니" in out  # T축 (시간) 노출
    assert "단열" in out  # C축 (후회비용) 노출
    assert "800만원" in out  # 구체적 금액 노출


def test_excerpt_returns_empty_when_only_images():
    body = "![](/img/1/orig)\n\n![](/img/2/orig)"
    assert excerpt(body) == ""


def test_excerpt_keeps_caption_after_image_on_same_line():
    """Image syntax followed by caption text on the same line: caption survives."""
    body = "![](/img/1.png) 단열 시공 사진"
    out = excerpt(body)
    # paragraph survives because the line is not image-only after the caption
    assert "단열 시공 사진" in out
    assert "![" not in out  # image syntax stripped


def test_excerpt_drops_paragraph_when_only_image_with_alt_text():
    """Image with alt text but nothing else on the line is still image-only."""
    body = "![alt text describing image](/img/2.png)\n\n실제 본문"
    out = excerpt(body)
    assert out == "실제 본문"
