"""양평군 허브 4개 탭(후기·Journey·질문·이웃) 데모 데이터 시드.

idempotent: 동일 username/email 사용자는 재생성하지 않으며, 같은 작성자 + 동일 title 의
post/journey 가 이미 있으면 건너뜀.

선행 조건:
  uv run python -m scripts.seed_regions   # 양평군 (slug=yangpyeong) 존재 필요

실행:
  uv run python -m scripts.seed_yangpyeong_demo

이미지: picsum.photos 에서 deterministic seed 로 받아 media/ 디렉토리에 저장하고
Image row(status=READY, orig 만 채움 — /img/{id}/medium 요청 시 라우트가 orig 로 fallback).
"""
from __future__ import annotations

import io
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import Image, Journey, Post, Region, User
from app.models._enums import ImageStatus, PostType
from app.models.user import BadgeLevel
from app.schemas.post_metadata import (
    JourneyEpisodeMetadata,
    JourneyEpMeta,
    QuestionMetadata,
    ReviewMetadata,
)
from app.services import auth as auth_service
from app.services import posts as posts_service

YP_SLUG = "yangpyeong"
DEFAULT_PASSWORD = "demo1234"  # noqa: S105 — 로컬 데모 계정


# ---------- 유틸 ----------


def _region(db: Session) -> Region:
    region = db.query(Region).filter(Region.slug == YP_SLUG).one_or_none()
    if region is None:
        raise SystemExit(
            f"Region slug={YP_SLUG} not found. Run: uv run python -m scripts.seed_regions"
        )
    return region


def _get_or_create_user(
    db: Session,
    *,
    email: str,
    username: str,
    display_name: str,
    bio: str,
    badge_level: BadgeLevel,
    primary_region: Region,
    resident_days_ago: int | None,
) -> User:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is not None:
        return user
    user = auth_service.create_user_with_password(
        db,
        email=email,
        username=username,
        display_name=display_name,
        password=DEFAULT_PASSWORD,
    )
    user.bio = bio
    user.badge_level = badge_level
    user.primary_region_id = primary_region.id
    if resident_days_ago is not None:
        user.resident_verified_at = datetime.now(UTC) - timedelta(days=resident_days_ago)
    db.flush()
    return user


def _fetch_image_bytes(seed: int, w: int = 1200, h: int = 800) -> bytes | None:
    """picsum.photos 에서 deterministic 이미지를 받아 bytes 반환. 실패하면 None."""
    url = f"https://picsum.photos/seed/{seed}/{w}/{h}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nestory-seed/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 — 고정 호스트
            return r.read()
    except (TimeoutError, urllib.error.URLError, OSError) as e:
        print(f"  ! 이미지 받기 실패 (seed={seed}): {e}")
        return None


def _store_demo_image(db: Session, owner: User, raw: bytes) -> Image | None:
    """raw bytes 를 media/ 에 저장 + Image row(status=READY, orig 만) 생성."""
    try:
        with PILImage.open(io.BytesIO(raw)) as pil:
            width, height = pil.size
            fmt = (pil.format or "").lower()
    except Exception as e:  # noqa: BLE001
        print(f"  ! 이미지 디코드 실패: {e}")
        return None
    ext = {"jpeg": "jpg", "png": "png", "webp": "webp"}.get(fmt, "jpg")

    settings = get_settings()
    uid = uuid4().hex
    rel_path = f"images/{uid}/orig.{ext}"
    full = Path(settings.image_base_path) / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(raw)

    img = Image(
        owner_id=owner.id,
        file_path_orig=rel_path,
        status=ImageStatus.READY,
        width=width,
        height=height,
        size_bytes=len(raw),
    )
    db.add(img)
    db.flush()
    return img


def _attach_image(db: Session, author: User, seed: int) -> str:
    """이미지 1장 받아 저장 후 본문에 삽입할 markdown 반환. 실패 시 빈 문자열."""
    raw = _fetch_image_bytes(seed)
    if raw is None:
        return ""
    img = _store_demo_image(db, author, raw)
    if img is None:
        return ""
    return f"![](/img/{img.id}/orig)"


def _set_published_at(post: Post, days_ago: int) -> None:
    """발행 시각을 분산시켜 피드 정렬이 자연스럽도록."""
    post.published_at = datetime.now(UTC) - timedelta(days=days_ago, hours=days_ago * 2)


def _has_post(db: Session, *, author_id: int, title: str, type_: PostType) -> bool:
    return (
        db.query(Post.id)
        .filter(
            Post.author_id == author_id,
            Post.title == title,
            Post.type == type_,
            Post.deleted_at.is_(None),
        )
        .first()
        is not None
    )


# ---------- 시드 데이터 ----------


NEIGHBORS = [
    {
        "email": "alice.yp@example.com",
        "username": "alice_yp",
        "display_name": "앨리스",
        "bio": "5년차 거주자. 단독주택 짓고 살아요. 텃밭과 도서관이 일상.",
        "badge": BadgeLevel.RESIDENT,
        "days_ago": 800,
    },
    {
        "email": "bob.yp@example.com",
        "username": "bob_carpenter",
        "display_name": "밥",
        "bio": "직접 건축 3년차. 단열·구조 질문 환영합니다.",
        "badge": BadgeLevel.RESIDENT,
        "days_ago": 420,
    },
    {
        "email": "carol.yp@example.com",
        "username": "carol_garden",
        "display_name": "캐롤",
        "bio": "1년차 입주. 정원 가꾸기와 사계절 기록 중.",
        "badge": BadgeLevel.RESIDENT,
        "days_ago": 200,
    },
    {
        "email": "evan.yp@example.com",
        "username": "evan_remote",
        "display_name": "이반",
        "bio": "원격근무 + 양평. 작업실 짓는 중.",
        "badge": BadgeLevel.RESIDENT,
        "days_ago": 90,
    },
    {
        "email": "dave.yp@example.com",
        "username": "dave_planning",
        "display_name": "데이브",
        "bio": "이주 검토 중. 1년 살아보기 진행.",
        "badge": BadgeLevel.REGION_VERIFIED,
        "days_ago": None,
    },
]


REVIEWS = [
    {
        "author_idx": 0,
        "title": "3년차 후기 — 단열에서 후회한 한 가지",
        "body": (
            "양평 단독 짓고 3년 살아본 후기.\n\n"
            "겨울이 길어서 외벽 단열재를 한 단계 더 두껍게 했어야 했어요.\n"
            "특히 북쪽 벽면. 1월 평균 기온이 서울보다 2-3도 낮습니다.\n\n"
            "그래도 가장 잘한 선택은 남향 배치 + 큰 창. 햇볕 들 때 난방 꺼도 따뜻해요."
        ),
        "image_seeds": [11, 12],
        "meta": {"house_type": "단독", "size_pyeong": 32, "satisfaction_overall": 4},
        "days_ago": 14,
    },
    {
        "author_idx": 1,
        "title": "직접 건축 2년차 — 구조설계는 절대 셀프 금지",
        "body": (
            "DIY 정신으로 시작했다가 구조계산만은 외주했습니다. 잘한 결정.\n\n"
            "지반조사 → 구조설계 → 인허가 → 시공 순서로 갔는데 구조 부분은\n"
            "전문가 검토가 필수예요. 보 두께·지붕 하중 계산 잘못하면 보강 비용이\n"
            "신축보다 비쌉니다.\n\n"
            "참고로 양평은 적설하중 기준이 까다로워요."
        ),
        "image_seeds": [21],
        "meta": {"house_type": "단독", "size_pyeong": 28, "satisfaction_overall": 5},
        "days_ago": 30,
    },
    {
        "author_idx": 2,
        "title": "1년차 후기 — 의외로 좋았던 점, 별로였던 점",
        "body": (
            "도시에서 양평으로 이주 1년차.\n\n"
            "**의외로 좋은 점**\n"
            "- 동네 카페 사장님과 친해짐\n"
            "- 마트 배송이 의외로 빠름\n"
            "- 밤하늘이 정말 다름\n\n"
            "**별로인 점**\n"
            "- 응급실까지 30분\n"
            "- 택배 픽업이 가끔 누락됨\n"
            "- 겨울 도로 결빙"
        ),
        "image_seeds": [33, 34],
        "meta": {"house_type": "타운하우스", "size_pyeong": 24, "satisfaction_overall": 4},
        "days_ago": 5,
    },
    {
        "author_idx": 0,
        "title": "정착 5년차 — 가장 큰 후회 비용 Top 3",
        "body": (
            "5년 살아보니 후회 비용이 보이네요.\n\n"
            "1. 단열 (북측 벽 보강): 약 800만원\n"
            "2. 화목난로 굴뚝 위치 잘못: 재시공 220만원\n"
            "3. 진입로 콘크리트 두께 부족: 보수 150만원\n\n"
            "이 셋만 처음에 잘했어도 천만원 가까이 아꼈을 거예요."
        ),
        "image_seeds": [45],
        "meta": {"house_type": "단독", "size_pyeong": 35, "satisfaction_overall": 5},
        "days_ago": 60,
    },
]


JOURNEYS = [
    {
        "author_idx": 1,
        "title": "터잡기부터 입주까지 — 양평 단독 짓기",
        "description": "토지 매입 → 설계 → 시공 → 입주까지 1년 6개월의 기록.",
        "cover_seed": 51,
        "start_days_ago": 600,
        "episodes": [
            {
                "title": "터잡기 — 토지 매입 결정 과정",
                "body": (
                    "양평 안에서도 시군구마다 분위기가 달라요. 3개 면을 6개월 다닌 끝에\n"
                    "지금 자리를 골랐습니다. 마을 안쪽 + 차로 5분 거리에 면사무소·마트가\n"
                    "있는 것이 핵심이었어요."
                ),
                "phase": "터",
                "period_label": "2024-08",
                "image_seeds": [52, 53],
                "days_ago": 480,
            },
            {
                "title": "건축 — 구조 → 골조 → 외장",
                "body": (
                    "2층 경량 목구조. 골조 한 달, 단열·외장 한 달 반.\n"
                    "겨울 시공이라 콘크리트 양생 일정이 까다로웠습니다."
                ),
                "phase": "건축",
                "period_label": "2025-01~03",
                "image_seeds": [61, 62],
                "days_ago": 300,
            },
            {
                "title": "입주 — 첫 겨울 적응기",
                "body": (
                    "이사 후 첫 겨울. 화목난로 + 시스템 에어컨 조합으로 버텼습니다.\n"
                    "예상 외 지출은 차량용 스노우 체인과 진입로 제설 장비."
                ),
                "phase": "입주",
                "period_label": "2025-04",
                "image_seeds": [71],
                "days_ago": 150,
            },
            {
                "title": "1년차 — 정원과 텃밭 첫 수확",
                "body": (
                    "토마토·바질·고추를 심었는데 고라니가 가장 큰 적이었습니다.\n"
                    "1년차 후기는 별도 게시판에 정리 예정."
                ),
                "phase": "1년차",
                "period_label": "2026-04",
                "image_seeds": [82, 83],
                "days_ago": 14,
            },
        ],
    },
    {
        "author_idx": 2,
        "title": "도시 직장인의 1년 살아보기",
        "description": "전세 임대로 시작한 양평 1년 살아보기 기록.",
        "cover_seed": 91,
        "start_days_ago": 240,
        "episodes": [
            {
                "title": "1개월 — 통근 가능성 테스트",
                "body": (
                    "용산까지 1시간 20분. 주 3회 출근으로는 견딜 만하지만 매일은 무리."
                ),
                "phase": "입주",
                "period_label": "2025-09",
                "image_seeds": [92],
                "days_ago": 220,
            },
            {
                "title": "6개월 — 동네에 익숙해지기",
                "body": (
                    "수목원 산책로, 5일장, 단골 카페가 생겼습니다.\n"
                    "근처 거주자 분들과 소모임도 시작."
                ),
                "phase": "1년차",
                "period_label": "2026-03",
                "image_seeds": [101, 102],
                "days_ago": 60,
            },
        ],
    },
]


QUESTIONS = [
    {
        "author_idx": 4,  # dave_planning (예비 입주자)
        "title": "양평 북쪽 면 단열 기준 어디까지 강화해야 하나요?",
        "body": (
            "예비 입주자입니다. 양평 북쪽 면 (양서·서종 라인) 검토 중인데,\n"
            "단열재 두께·등급을 어디까지 올려야 하는지 거주하시는 분들 의견 부탁드립니다.\n"
            "현재 외벽 200T 검토 중인데 부족할까요?"
        ),
        "tags": ["단열", "북향", "신축"],
        "image_seeds": [111],
        "days_ago": 2,
    },
    {
        "author_idx": 4,
        "title": "응급실까지 평균 시간이 얼마나 걸리시나요?",
        "body": (
            "고령 부모님 모시고 이주 검토 중. 양평군립의료원까지 새벽 평일/주말 시간이\n"
            "어떻게 다른지, 사설 응급이송 가입 추천 여부도 궁금합니다."
        ),
        "tags": ["의료", "응급실"],
        "image_seeds": [],
        "days_ago": 7,
    },
    {
        "author_idx": 4,
        "title": "겨울 진입로 결빙 — 어떻게 대비하셨나요?",
        "body": (
            "마을 안쪽 부지가 마음에 드는데, 진입로 경사가 있어서 겨울 결빙이 걱정됩니다.\n"
            "체인·열선·염화칼슘 중 실제로 효과 있는 게 뭔지 알려주세요."
        ),
        "tags": ["겨울", "진입로", "결빙"],
        "image_seeds": [121],
        "days_ago": 10,
    },
    {
        "author_idx": 3,  # evan_remote — RESIDENT이지만 질문 가능
        "title": "광인터넷 회선 — 어느 통신사가 안정적인가요?",
        "body": (
            "원격근무용 안정 회선이 중요합니다. 양평 안에서 KT·SK·LG 중\n"
            "안정성 차이가 큰지, 백업회선 (5G 라우터) 같이 쓰시는 분 계신지."
        ),
        "tags": ["인터넷", "원격근무"],
        "image_seeds": [],
        "days_ago": 4,
    },
    {
        "author_idx": 4,
        "title": "양평 5일장 — 가볼 만한 곳 추천해주세요",
        "body": "가족 데려가서 가볼 만한 5일장 일정과 추천 가게 알려주세요.",
        "tags": ["5일장", "맛집"],
        "image_seeds": [131],
        "days_ago": 1,
    },
]


# ---------- 시드 함수 ----------


def seed_neighbors(db: Session, region: Region) -> list[User]:
    users: list[User] = []
    for spec in NEIGHBORS:
        user = _get_or_create_user(
            db,
            email=spec["email"],
            username=spec["username"],
            display_name=spec["display_name"],
            bio=spec["bio"],
            badge_level=spec["badge"],
            primary_region=region,
            resident_days_ago=spec["days_ago"],
        )
        users.append(user)
    return users


def seed_reviews(db: Session, region: Region, users: list[User]) -> int:
    created = 0
    for spec in REVIEWS:
        author = users[spec["author_idx"]]
        if _has_post(db, author_id=author.id, title=spec["title"], type_=PostType.REVIEW):
            continue
        body = spec["body"]
        for seed in spec["image_seeds"]:
            md = _attach_image(db, author, seed)
            if md:
                body += "\n\n" + md
        meta = ReviewMetadata(**spec["meta"])
        post = posts_service.create_review(db, author, region, meta, spec["title"], body)
        _set_published_at(post, spec["days_ago"])
        created += 1
    return created


def seed_journeys(db: Session, region: Region, users: list[User]) -> tuple[int, int]:
    created_j, created_e = 0, 0
    for spec in JOURNEYS:
        author = users[spec["author_idx"]]
        journey = (
            db.query(Journey)
            .filter(Journey.author_id == author.id, Journey.title == spec["title"])
            .one_or_none()
        )
        if journey is None:
            cover = _attach_image(db, author, spec["cover_seed"])
            cover_id = None
            if cover:
                m = re.search(r"/img/(\d+)/", cover)
                cover_id = int(m.group(1)) if m else None
            journey = posts_service.create_journey(
                db,
                author,
                region,
                title=spec["title"],
                description=spec["description"],
                start_date=(
                    datetime.now(UTC) - timedelta(days=spec["start_days_ago"])
                ).date(),
                cover_image_id=cover_id,
            )
            created_j += 1

        for ep_spec in spec["episodes"]:
            if _has_post(
                db,
                author_id=author.id,
                title=ep_spec["title"],
                type_=PostType.JOURNEY_EPISODE,
            ):
                continue
            body = ep_spec["body"]
            for seed in ep_spec["image_seeds"]:
                md = _attach_image(db, author, seed)
                if md:
                    body += "\n\n" + md
            ep_meta = JourneyEpisodeMetadata(
                journey_ep_meta=JourneyEpMeta(
                    phase=ep_spec["phase"], period_label=ep_spec["period_label"]
                )
            )
            ep = posts_service.create_journey_episode(
                db, author, journey, ep_meta, ep_spec["title"], body
            )
            _set_published_at(ep, ep_spec["days_ago"])
            created_e += 1
    return created_j, created_e


def seed_questions(db: Session, region: Region, users: list[User]) -> int:
    created = 0
    for spec in QUESTIONS:
        author = users[spec["author_idx"]]
        if _has_post(db, author_id=author.id, title=spec["title"], type_=PostType.QUESTION):
            continue
        body = spec["body"]
        for seed in spec["image_seeds"]:
            md = _attach_image(db, author, seed)
            if md:
                body += "\n\n" + md
        meta = QuestionMetadata(tags=spec["tags"][:10])
        post = posts_service.create_question(db, author, region, meta, spec["title"], body)
        _set_published_at(post, spec["days_ago"])
        created += 1
    return created


# ---------- 엔트리 ----------


def main() -> None:
    db = SessionLocal()
    try:
        region = _region(db)
        print(f"→ 시드 대상 지역: {region.sido} {region.sigungu} (slug={region.slug})")

        neighbors = seed_neighbors(db, region)
        db.flush()
        print(f"  · 이웃(거주자/지역인증): {len(neighbors)}명 확보 (이미 있던 사용자 포함)")

        n_rev = seed_reviews(db, region, neighbors)
        print(f"  · 후기 신규 생성: {n_rev}건")

        n_j, n_ep = seed_journeys(db, region, neighbors)
        print(f"  · Journey 신규: {n_j}개 · 에피소드 신규: {n_ep}건")

        n_q = seed_questions(db, region, neighbors)
        print(f"  · 질문 신규 생성: {n_q}건")

        db.commit()
        print("✅ 시드 완료. 로그인: 각 계정 비밀번호 = 'demo1234'")
        print("   예) alice.yp@example.com / demo1234")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
