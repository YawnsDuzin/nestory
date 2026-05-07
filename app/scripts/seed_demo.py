"""Demo data seeder. Run via: uv run python -m app.scripts.seed_demo [--reset]

Creates a realistic snapshot of the platform: 4 pilot regions, 6 users (1 admin
+ 2 residents + 2 region-verified + 1 interested), 12 reviews, 2 Journeys with
5 total episodes, 4 questions with 7 answers, and a sprinkle of likes/scraps.

Designed to populate /, /discover, /hub/{slug}, /search, /feed, /u/{username}
with believable content for manual QA.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models._enums import BadgeLevel, PostStatus, PostType
from app.tests.factories import (
    AdminUserFactory,
    AnswerPostFactory,
    JourneyEpisodePostFactory,
    JourneyFactory,
    PilotRegionFactory,
    QuestionPostFactory,
    RegionVerifiedUserFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
    add_post_like,
    add_post_scrap,
)
from app.tests.factories._base import BaseFactory


def _bind_session(session) -> None:
    """Inject the seeder session into every BaseFactory subclass."""
    for cls in _all_subclasses(BaseFactory):
        cls._meta.sqlalchemy_session = session


def _all_subclasses(cls):
    seen = set()
    stack = [cls]
    while stack:
        c = stack.pop()
        for sub in c.__subclasses__():
            if sub not in seen:
                seen.add(sub)
                stack.append(sub)
                yield sub


def _truncate_all(session) -> None:
    """Equivalent to conftest TRUNCATE — used when --reset flag passed."""
    from app.db.base import Base

    table_names = [t.name for t in Base.metadata.tables.values() if t.name != "alembic_version"]
    if not table_names:
        return
    joined = ", ".join(table_names)
    session.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
    session.commit()


def _now() -> datetime:
    return datetime.now(UTC)


def seed(reset: bool = False) -> None:
    session = SessionLocal()
    try:
        _bind_session(session)
        if reset:
            _truncate_all(session)
            print("Truncated all tables.")

        # Regions
        regions = {
            "yangpyeong": PilotRegionFactory(
                slug="yangpyeong",
                sido="경기도",
                sigungu="양평군",
                description="서울 1시간, 한강 따라 자리 잡은 정착지.",
            ),
            "yeongwol": PilotRegionFactory(
                slug="yeongwol",
                sido="강원도",
                sigungu="영월군",
                description="자연·역사 함께 즐기는 강원도 남부.",
            ),
            "hongcheon": PilotRegionFactory(
                slug="hongcheon",
                sido="강원도",
                sigungu="홍천군",
                description="청정 자연 + 합리적 부지 가격.",
            ),
            "gokseong": PilotRegionFactory(
                slug="gokseong",
                sido="전라남도",
                sigungu="곡성군",
                description="기차마을 곡성, 따뜻한 남부 정착.",
            ),
        }

        # Users (1 admin + 2 residents + 2 region_verified + 1 interested)
        admin = AdminUserFactory(username="admin", display_name="관리자")
        resident_a = ResidentUserFactory(
            username="yangpyeong-1",
            display_name="양평 1년차",
            primary_region_id=regions["yangpyeong"].id,
            resident_verified_at=_now() - timedelta(days=400),
        )
        resident_b = ResidentUserFactory(
            username="hongcheon-3",
            display_name="홍천 3년차",
            primary_region_id=regions["hongcheon"].id,
            resident_verified_at=_now() - timedelta(days=1200),
        )
        rv_a = RegionVerifiedUserFactory(
            username="yeongwol-newcomer",
            primary_region_id=regions["yeongwol"].id,
        )
        rv_b = RegionVerifiedUserFactory(
            username="gokseong-newcomer",
            primary_region_id=regions["gokseong"].id,
        )
        interested = UserFactory(
            username="prospective",
            display_name="검토 중",
            badge_level=BadgeLevel.INTERESTED,
        )
        all_users = [admin, resident_a, resident_b, rv_a, rv_b, interested]

        # 12 reviews — split across the 4 regions, written by residents
        reviews = []
        review_data = [
            (
                "양평 1년차 — 단열 다시 하면 두께 두 배",
                "외장 단열 100mm로 시공했는데 다음 겨울 결로 흔적이 남았다."  # noqa: E501
                " 2년차 이후 추가 단열을 했고 그 비용이 절약 가능했다.",
            ),
            (
                "홍천 3년차 — 보일러보다 화목난로",
                "장기 정착이라면 화목난로 + 태양광이 절대 정답."
                " 초기 비용 700만원이지만 5년차부터 회수된다.",
            ),
            (
                "양평 2년차 — 마당 잔디 후회",
                "잔디 관리에 주말마다 4시간씩 들어간다. 처음부터 클로버나 야생초로 갔어야 했다.",
            ),
            (
                "홍천 — 인터넷 속도 체크 필수",
                "전원주택 구입 전 인터넷 속도 50Mbps 이상 가능한지 확인 필수."
                " 우리는 30Mbps로 만족스럽지 않다.",
            ),
        ]
        for i, (title, body) in enumerate(review_data):
            author = resident_a if i % 2 == 0 else resident_b
            region = regions["yangpyeong"] if author == resident_a else regions["hongcheon"]
            reviews.append(
                ReviewPostFactory(
                    author=author,
                    region=region,
                    title=title,
                    body=body,
                    status=PostStatus.PUBLISHED,
                    published_at=_now() - timedelta(days=random.randint(1, 90)),
                    view_count=random.randint(50, 500),
                )
            )
        # Pad to 12 with shorter generic reviews
        for _ in range(12 - len(reviews)):
            author = random.choice([resident_a, resident_b])
            region = regions["yangpyeong"] if author == resident_a else regions["hongcheon"]
            reviews.append(
                ReviewPostFactory(
                    author=author,
                    region=region,
                    status=PostStatus.PUBLISHED,
                    published_at=_now() - timedelta(days=random.randint(1, 365)),
                    view_count=random.randint(20, 200),
                )
            )

        # 2 Journeys + 5 episodes
        journey_yp = JourneyFactory(
            author=resident_a,
            region=regions["yangpyeong"],
            title="양평 정착기 — 터잡기에서 1년차까지",
            description="2025년 가을, 서울에서 양평으로 이사한 가족의 기록.",
            start_date=date(2025, 9, 1),
        )
        journey_hc = JourneyFactory(
            author=resident_b,
            region=regions["hongcheon"],
            title="홍천 3년 — 전원생활의 진짜 비용",
            description="화목난로, 태양광, 텃밭의 5년 사이 변화 기록.",
            start_date=date(2023, 5, 1),
        )

        for ep_no, title in enumerate(
            [
                "1화 — 부지 매입과 토목 견적",
                "2화 — 설계 기간 6개월",
                "3화 — 시공 시작 1개월",
            ],
            start=1,
        ):
            JourneyEpisodePostFactory(
                journey=journey_yp,
                author=resident_a,
                region=regions["yangpyeong"],
                episode_no=ep_no,
                title=title,
                status=PostStatus.PUBLISHED,
                published_at=_now() - timedelta(days=random.randint(60, 200)),
            )

        for ep_no, title in enumerate(
            ["1화 — 첫 겨울 화목난로 도입", "2화 — 두 번째 봄, 텃밭 시작"],
            start=1,
        ):
            JourneyEpisodePostFactory(
                journey=journey_hc,
                author=resident_b,
                region=regions["hongcheon"],
                episode_no=ep_no,
                title=title,
                status=PostStatus.PUBLISHED,
                published_at=_now() - timedelta(days=random.randint(100, 400)),
            )

        # 4 questions + 7 answers
        questions = []
        for title, body, asker, region in [
            (
                "양평 동향에 단독, 단열재 추천?",
                "남향 한정 일조량 좋습니다. 셀룰로오스 vs 우레탄 어느 것이 좋을까요?",
                interested,
                regions["yangpyeong"],
            ),
            (
                "홍천 부지 1000평, 시공사 추천",
                "주말주택 목적, 60평 단층 계획.",
                interested,
                regions["hongcheon"],
            ),
            (
                "영월 2년차 거주, 기름값 얼마?",
                "월 평균 난방비 궁금합니다.",
                rv_a,
                regions["yeongwol"],
            ),
            (
                "곡성 지역 인터넷·통신 환경",
                "재택근무 가능한지?",
                rv_b,
                regions["gokseong"],
            ),
        ]:
            q = QuestionPostFactory(
                author=asker,
                region=region,
                title=title,
                body=body,
                status=PostStatus.PUBLISHED,
                published_at=_now() - timedelta(days=random.randint(1, 60)),
                view_count=random.randint(10, 100),
            )
            questions.append(q)

        # Add answers — average ~2 per question
        answer_authors = [resident_a, resident_b]
        for q in questions:
            for answer_author in random.sample(answer_authors, k=min(2, len(answer_authors))):
                if random.random() > 0.3:  # ~70% chance each resident answers
                    AnswerPostFactory(
                        author=answer_author,
                        region=q.region,
                        parent_post=q,
                        status=PostStatus.PUBLISHED,
                        published_at=q.published_at + timedelta(hours=random.randint(2, 48)),
                    )

        session.commit()

        # Likes + scraps — random sprinkle
        for review in reviews:
            for user in random.sample(all_users, k=random.randint(0, 3)):
                add_post_like(session, user, review)
            for user in random.sample(all_users, k=random.randint(0, 2)):
                add_post_scrap(session, user, review)
        session.commit()

        # Summary
        from sqlalchemy import func, select

        from app.models import Post, Region, User

        def _count(q):
            return session.scalar(select(func.count(Post.id)).where(q))

        print("Seeded:")
        print(f"  Regions: {session.scalar(select(func.count(Region.id)))}")
        print(f"  Users: {session.scalar(select(func.count(User.id)))}")
        print(f"  Posts: {session.scalar(select(func.count(Post.id)))}")
        print(f"  ↳ Reviews: {_count(Post.type == PostType.REVIEW)}")
        print(f"  ↳ Journey episodes: {_count(Post.type == PostType.JOURNEY_EPISODE)}")
        print(f"  ↳ Questions: {_count(Post.type == PostType.QUESTION)}")
        print(f"  ↳ Answers: {_count(Post.type == PostType.ANSWER)}")

    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Nestory demo seeder")
    parser.add_argument("--reset", action="store_true", help="TRUNCATE all tables before seeding")
    args = parser.parse_args()
    seed(reset=args.reset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
