from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import RegionFactory, ResidentUserFactory, ReviewPostFactory


def test_home_renders_html(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Nestory" in r.text


def test_home_shows_login_cta_when_anonymous(client: TestClient) -> None:
    r = client.get("/")
    assert "시작하기" in r.text or "로그인" in r.text


def test_login_page_renders(client: TestClient) -> None:
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert "이메일" in r.text
    assert "카카오" in r.text


def test_signup_page_renders(client: TestClient) -> None:
    r = client.get("/auth/signup")
    assert r.status_code == 200
    assert 'name="password"' in r.text


def test_home_shows_username_when_logged_in(client: TestClient) -> None:
    client.post(
        "/auth/signup",
        data={
            "email": "f@ex.com",
            "username": "frank",
            "display_name": "프랭크",
            "password": "password12",
        },
    )
    r = client.get("/")
    assert "@frank" in r.text


# ---------------------------------------------------------------------------
# Hero redesign — anonymous landing
# ---------------------------------------------------------------------------


def test_anonymous_home_hero_shows_t_axis_headline(client: TestClient) -> None:
    """헤드라인이 PRD T축(1년차 / 3년차) 카피를 직접 노출."""
    r = client.get("/")
    assert r.status_code == 200
    assert "1년차에 좋다는 후기는 많아도" in r.text
    assert "3년차의 진실은 어디서 듣나요" in r.text


def test_anonymous_home_renders_when_no_featured_testimonial(
    client: TestClient,
) -> None:
    """published review 0건 — featured 카드 미렌더, 페이지는 200."""
    r = client.get("/")
    assert r.status_code == 200
    # featured 카드가 없어도 페르소나 3카드는 렌더
    assert "예비 입주자" in r.text
    assert "1-3년차 거주자" in r.text
    assert "5년+ 베테랑" in r.text


def test_anonymous_home_persona_card_links(client: TestClient) -> None:
    """페르소나 카드 클릭 → 각각 wizard·signup·signup."""
    r = client.get("/")
    body = r.text
    # 예비 입주자 → /match/wizard
    assert 'href="/match/wizard"' in body
    # 1-3년차·5년+ → /auth/signup (정확히 2회 — 페르소나 카드 2개)
    # 본문 중 다른 위치(보조 텍스트 링크)에서 한 번 더 노출 → 총 3회
    assert body.count('href="/auth/signup"') >= 2


def test_anonymous_home_hero_renders_featured_testimonial(
    client: TestClient,
    db: Session,
) -> None:
    """published REVIEW가 있으면 hero에 featured 인용 카드가 렌더되고,
    동일 post가 '인기 후기' 그리드에 중복 노출되지 않음."""
    region = RegionFactory(slug="hero-featured-region")
    author = ResidentUserFactory(
        username="alice_yp",
        resident_verified_at=datetime.now(UTC) - timedelta(days=365 * 5),
    )
    top_review = ReviewPostFactory(
        author=author,
        region=region,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        view_count=999,
        title="정착 5년차 — 가장 큰 후회 비용 Top 3",
        body=(
            "5년 살아보니 후회 비용이 보이네요.\n\n"
            "1. 단열 (북측 벽 보강): 약 800만원\n"
            "2. 화목난로 굴뚝 위치 잘못: 재시공 220만원"
        ),
    )
    db.commit()

    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # featured 인용 본문 일부 노출
    assert "5년 살아보니 후회 비용이 보이네요" in body
    # attribution: 거주 연차 라벨 + 사용자 이름
    assert "5년차" in body
    assert "@alice_yp" in body
    # 인기 후기 그리드에 동일 post 의 detail link 가 추가로 노출되지 않음
    # (hero 카드에서 1번, popular_reviews 그리드에서 0번 → 총 1번)
    detail_url_marker = f'href="/post/{top_review.id}"'
    assert body.count(detail_url_marker) == 1
