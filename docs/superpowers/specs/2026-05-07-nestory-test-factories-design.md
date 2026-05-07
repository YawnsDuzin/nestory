# Nestory — Test Factories (factory-boy) 도입 설계

**작성일**: 2026-05-07
**대상 단계**: P1.2 종료 직후, P1.3 진입 전 정비
**관련 PRD**: 직접 영향 없음 (테스트 인프라). 단 PRD §5.3 v1.1 [A3] (Pydantic Discriminated Union) 의 metadata 검증 원칙을 테스트 데이터에도 동일 적용.
**관련 메모리**: `feedback_consistency_first.md` (구조성·일관성 절대 우선), `project_nestory_handoff.md` (P1.2 종료 후 권장 작업)

## 1. 배경 및 동기

Phase 1.1 + Phase 1.2 완료 시점에 통합 테스트 25개가 모두 모델 인스턴스를 직접 생성한다 (`User(...)`, `Region(...)`, `Post(...)`). 다음 문제가 발생:

1. **Boilerplate 중복** — 거의 모든 테스트 파일에 `_seed(db) -> tuple[User, Region]` 형태의 헬퍼가 존재. 시그니처·필드값이 파일마다 미묘하게 다름.
2. **Unique 필드 회피 패턴 통일 부재** — `f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com"` 같은 방어적 코드. Sequence 기반 통일된 방식 필요.
3. **Post.metadata Pydantic 검증 누락 위험** — 테스트가 `metadata_={"satisfaction_overall": 4}` 같이 자유 dict 주입. 향후 모델 진화 시 누락 필드로 silent fail 가능.
4. **P1.3 진입 전 비용 ↘** — P1.3는 Post CRUD + 이미지 파이프라인 + 5종 type 폼이 들어간다. 테스트 양이 2-3배가 될 시점에 boilerplate가 누적되면 회귀 비용 폭증.

`factory-boy`는 이미 `pyproject.toml`의 dev deps에 포함되어 있고, `app/tests/factories/` 디렉토리도 비어있는 상태로 미리 만들어져 있다. 이번 작업으로 실제 도입을 마무리한다.

## 2. 범위

### 2.1 In-scope

- **14개 도메인 모델 전부의 factory 작성**: User, Region, Post (+5종 서브), Comment, Journey, Image, BadgeApplication, BadgeEvidence, Notification, UserInterestRegion, Job, Tag, Announcement, AuditLog, Report, PostValidation
- **interaction Table 객체용 헬퍼 함수**: `post_likes`, `post_scraps`, `journey_follows`, `user_follows` (Table은 ORM 모델이 아니므로 factory가 아닌 함수 헬퍼)
- **conftest 통합**: `db` fixture가 모든 factory에 세션 주입
- **기존 25개 통합 테스트 마이그레이션** — `User(...)` 등 직접 생성 모두 factory 호출로 교체. `_seed*` 헬퍼 제거.
- **factory 자체 검증용 unit test 추가** (`app/tests/unit/test_factories.py`)

### 2.2 Out-of-scope

- 기존 도메인 모델·라우트 변경
- conftest의 `_cleanup_db` autouse fixture 변경 (TRUNCATE 패턴 유지)
- pytest-factoryboy 통합 (의존성 추가 없이 순수 factory-boy로 충분)
- Faker locale 추가 설치 (factory-boy 동봉 ko_KR로 충분)

## 3. 아키텍처

### 3.1 디렉토리 구조

```
app/tests/factories/
├── __init__.py              # 모든 factory re-export (alphabetical, models/__init__.py 컨벤션)
├── _base.py                 # BaseFactory + 공용 metadata 헬퍼
├── user.py                  # UserFactory + AdminUserFactory + RegionVerifiedUserFactory + ResidentUserFactory
├── region.py                # RegionFactory (get-or-create) + PilotRegionFactory
├── post.py                  # PostFactory + 5종 (Review/JourneyEpisode/Question/Answer/Plan)
├── comment.py
├── journey.py
├── image.py
├── badge_application.py     # BadgeApplicationFactory + BadgeEvidenceFactory
├── notification.py
├── interaction.py           # 헬퍼 함수 (Table 객체)
├── interest_region.py       # UserInterestRegionFactory
├── job.py
├── tag.py
├── moderation.py            # AnnouncementFactory + AuditLogFactory + ReportFactory
└── post_validation.py
```

**13개 파일 + _base + __init__** = 15개. `models/`와 1:1 대칭 (interaction 제외).

### 3.2 BaseFactory + 세션 결합

```python
# app/tests/factories/_base.py
from factory.alchemy import SQLAlchemyModelFactory


class BaseFactory(SQLAlchemyModelFactory):
    """모든 factory의 base. sqlalchemy_session은 conftest db fixture가 주입."""
    class Meta:
        abstract = True
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "flush"
```

```python
# app/tests/conftest.py — 추가/수정 부분
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


def _bind_factories(session):
    import app.tests.factories  # noqa: F401  # 모든 factory 클래스 등록
    from app.tests.factories._base import BaseFactory
    for cls in _all_subclasses(BaseFactory):
        cls._meta.sqlalchemy_session = session


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        _bind_factories(session)
        yield session
    finally:
        session.close()
```

**핵심 결정**:
- `persistence="flush"` — 기존 `_cleanup_db` autouse fixture의 TRUNCATE 패턴 유지. factory가 commit하지 않으므로 테스트 실패 시도 다음 테스트 시작 전 TRUNCATE로 깨끗.
- 세션 주입은 `db` fixture가 책임 — factory는 자체 SessionLocal을 만들지 않음. 테스트 코드와 같은 트랜잭션·identity map 공유.
- 재귀 서브클래스 탐색 — 신규 factory 추가 시 conftest 수정 불필요.

### 3.3 UserFactory 표본

```python
# app/tests/factories/user.py
from datetime import UTC, datetime, timedelta

import factory

from app.services.auth import hash_password
from app.models import BadgeLevel, User, UserRole
from app.tests.factories._base import BaseFactory


class UserFactory(BaseFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    display_name = factory.Faker("name", locale="ko_KR")
    password_hash = factory.LazyFunction(lambda: hash_password("test1234!"))
    role = UserRole.USER
    badge_level = BadgeLevel.INTERESTED


class AdminUserFactory(UserFactory):
    role = UserRole.ADMIN


class RegionVerifiedUserFactory(UserFactory):
    badge_level = BadgeLevel.REGION_VERIFIED
    primary_region = factory.SubFactory("app.tests.factories.region.RegionFactory")
    primary_region_id = factory.SelfAttribute("primary_region.id")

    class Meta:
        model = User
        exclude = ("primary_region",)


class ResidentUserFactory(RegionVerifiedUserFactory):
    badge_level = BadgeLevel.RESIDENT
    resident_verified_at = factory.LazyFunction(
        lambda: datetime.now(UTC) - timedelta(days=30)
    )
```

**키 결정**:
- `Sequence`로 unique 충돌 회피 (글로벌, 테스트 간 누적). `_cleanup_db` TRUNCATE는 row만 비우고 Python sequence는 유지 → 중복 없음.
- `hash_password` 실제 호출 — auth 테스트가 `verify_password` 검증할 때 필수. bcrypt 1회 호출 비용 미미.
- Trait 대신 명시 서브클래스 — Korean 의도 명확, IDE 자동완성 유리.

### 3.4 RegionFactory 표본 (get-or-create)

```python
# app/tests/factories/region.py
import factory

from app.models import Region
from app.tests.factories._base import BaseFactory


class RegionFactory(BaseFactory):
    class Meta:
        model = Region
        sqlalchemy_get_or_create = ("slug",)

    sido = "경기"
    sigungu = factory.Sequence(lambda n: f"테스트시{n}")
    slug = factory.Sequence(lambda n: f"test-{n}")
    is_pilot = False


class PilotRegionFactory(RegionFactory):
    is_pilot = True
```

**키 결정**:
- `get_or_create=("slug",)` — 동일 slug가 이미 있으면 재사용. `PostFactory`가 `SubFactory(RegionFactory)`로 호출해도 다른 테스트에서 만든 region과 충돌하지 않음 (TRUNCATE로 사이클 사이 비워짐).

### 3.5 PostFactory + metadata 자동 채움 (핵심)

```python
# app/tests/factories/post.py
import factory

from app.models import Post
from app.models._enums import PostStatus, PostType
from app.schemas.post_metadata import (
    AnswerMetadata,
    JourneyEpMeta,
    JourneyEpisodeMetadata,
    PlanMetadata,
    QuestionMetadata,
    ReviewMetadata,
)
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


def _default_metadata(post_type: PostType) -> dict:
    """post_type에 맞는 Pydantic 검증 통과하는 최소 dict 반환."""
    if post_type == PostType.REVIEW:
        return ReviewMetadata(
            house_type="단독", size_pyeong=30, satisfaction_overall=4
        ).model_dump(by_alias=False, exclude_none=True)
    if post_type == PostType.JOURNEY_EPISODE:
        return JourneyEpisodeMetadata(
            journey_ep_meta=JourneyEpMeta(phase="입주", period_label="2026-04")
        ).model_dump(by_alias=False, exclude_none=True)
    if post_type == PostType.QUESTION:
        return QuestionMetadata().model_dump(by_alias=False)
    if post_type == PostType.ANSWER:
        return AnswerMetadata().model_dump(by_alias=False)
    if post_type == PostType.PLAN:
        return PlanMetadata(
            target_move_year=2027,
            budget_total_manwon_band="5000-10000",
            construction_intent="undecided",
        ).model_dump(by_alias=False)
    raise ValueError(f"Unknown post_type: {post_type}")


class PostFactory(BaseFactory):
    class Meta:
        model = Post
        exclude = ("author", "region")

    author = factory.SubFactory(UserFactory)
    author_id = factory.SelfAttribute("author.id")
    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    type = PostType.REVIEW
    title = factory.Faker("sentence", nb_words=4, locale="ko_KR")
    body = factory.Faker("paragraph", nb_sentences=3, locale="ko_KR")
    status = PostStatus.DRAFT

    @factory.lazy_attribute
    def metadata_(self):
        return _default_metadata(self.type)


class ReviewPostFactory(PostFactory):
    type = PostType.REVIEW


class JourneyEpisodePostFactory(PostFactory):
    type = PostType.JOURNEY_EPISODE
    journey = factory.SubFactory("app.tests.factories.journey.JourneyFactory")
    journey_id = factory.SelfAttribute("journey.id")
    episode_no = factory.Sequence(lambda n: n + 1)

    class Meta:
        model = Post
        exclude = ("author", "region", "journey")


class QuestionPostFactory(PostFactory):
    type = PostType.QUESTION


class AnswerPostFactory(PostFactory):
    type = PostType.ANSWER
    parent_post = factory.SubFactory(QuestionPostFactory)
    parent_post_id = factory.SelfAttribute("parent_post.id")

    class Meta:
        model = Post
        exclude = ("author", "region", "parent_post")


class PlanPostFactory(PostFactory):
    type = PostType.PLAN
```

**키 결정**:
- Pydantic 모델 → `model_dump()` → JSONB dict. DB 저장값이 항상 PostMetadata 검증 통과. CLAUDE.md의 "쓰기 경로는 PostMetadata 통과 후 DB" 원칙을 테스트 데이터에도 적용.
- `lazy_attribute`가 `self.type` 참조 → type 변경 시 metadata 자동 일치.
- 테스트가 metadata 일부만 override 가능: `PostFactory(metadata_={**meta, "satisfaction_overall": 1})`.
- SubFactory + SelfAttribute 패턴: 관계 객체로 잡고 FK id만 컬럼에 전달. `exclude`로 ORM 객체는 Post 생성자에 안 넘김.

### 3.6 나머지 12개 factory

각 factory는 `UserFactory` 패턴을 그대로 복제. SubFactory를 ORM 객체로 잡고 `*_id` SelfAttribute + `Meta.exclude`로 컬럼만 전달하는 패턴 일관 적용. 모델 실제 필드명 기준:

- **CommentFactory** (`comments`): `post = SubFactory(PostFactory)` + `post_id = SelfAttribute("post.id")`, `author = SubFactory(UserFactory)` + `author_id = SelfAttribute("author.id")`, `body = Faker("paragraph", nb_sentences=2, locale="ko_KR")`, `status = CommentStatus.VISIBLE`. `parent_id` 기본 None. `Meta.exclude = ("post", "author")`.

- **JourneyFactory** (`journeys`): `author = SubFactory(UserFactory)` + `author_id`, `region = SubFactory(RegionFactory)` + `region_id`, `title = Faker("sentence", locale="ko_KR")`, `status = JourneyStatus.IN_PROGRESS`. `description`/`start_date`/`cover_image_id` 기본 None. `Meta.exclude = ("author", "region")`.

- **ImageFactory** (`images`): `owner = SubFactory(UserFactory)` + `owner_id`, `file_path_orig = Sequence(lambda n: f"images/{n}/orig.jpg")`, `status = ImageStatus.READY`. `post_id`/`file_path_thumb`/`file_path_medium`/`file_path_webp`/`width`/`height`/`size_bytes`/`alt_text` 모두 nullable, 기본 None. `order_idx = 0`. `Meta.exclude = ("owner",)`.

- **BadgeApplicationFactory** (`badge_applications`): `user = SubFactory(UserFactory)` + `user_id`, `region = SubFactory(RegionFactory)` + `region_id`, `requested_level = BadgeRequestedLevel.REGION_VERIFIED`, `status = BadgeApplicationStatus.PENDING`. `Meta.exclude = ("user", "region")`.

- **BadgeEvidenceFactory** (`badge_evidence`): `application = SubFactory(BadgeApplicationFactory)` + `application_id = SelfAttribute("application.id")`, `evidence_type = EvidenceType.UTILITY_BILL`, `file_path = Sequence(lambda n: f"evidence/{n}/test.jpg")`. `Meta.exclude = ("application",)`.

- **NotificationFactory** (`notifications`): `user = SubFactory(UserFactory)` + `user_id`, `type = NotificationType.SYSTEM`, `is_read = False`. `source_user_id`/`target_type`/`target_id` 기본 None. `Meta.exclude = ("user",)`.

- **UserInterestRegionFactory** (`user_interest_regions` — 복합 PK `(user_id, region_id)`): `user = SubFactory(UserFactory)` + `user_id`, `region = SubFactory(RegionFactory)` + `region_id`, `priority = 1`. `Meta.exclude = ("user", "region")`.

- **JobFactory** (`jobs`): `kind = JobKind.NOTIFICATION`, `payload = {}`, `status = JobStatus.QUEUED`. `attempts`/`max_attempts`/`run_after` server default 사용.

- **TagFactory** (`tags`): `name = Sequence(lambda n: f"태그{n}")`, `slug = Sequence(lambda n: f"tag-{n}")`. `Meta.sqlalchemy_get_or_create = ("slug",)`.

- **AnnouncementFactory** (`announcements`): `author = SubFactory(AdminUserFactory)` + `author_id`, `title = Faker("sentence", locale="ko_KR")`, `body = Faker("paragraph", locale="ko_KR")`, `pinned = False`. `Meta.exclude = ("author",)`.

- **AuditLogFactory** (`audit_logs`): `actor = SubFactory(AdminUserFactory)` + `actor_id`, `action = AuditAction.BADGE_APPROVED`, `target_type = "badge_applications"`, `target_id = Sequence(lambda n: n + 1)`. `note` nullable 기본 None. `Meta.exclude = ("actor",)`.

- **ReportFactory** (`reports`): `reporter = SubFactory(UserFactory)` + `reporter_id`, `target_type = "posts"`, `target_id = Sequence(lambda n: n + 1)`, `reason = ReportReason.SPAM`, `status = ReportStatus.PENDING`. `detail`/`handled_by`/`handled_at` nullable. `Meta.exclude = ("reporter",)`.

- **PostValidationFactory** (`post_validations`): `post = SubFactory(PostFactory)` + `post_id`, `validator = SubFactory(RegionVerifiedUserFactory)` + `validator_user_id = SelfAttribute("validator.id")`, `vote = ValidationVote.CONFIRM`. `note` nullable 기본 None. `Meta.exclude = ("post", "validator")`.

### 3.7 interaction 헬퍼 (Table 객체)

```python
# app/tests/factories/interaction.py
"""interaction은 Table 객체이므로 factory가 아닌 헬퍼 함수.

각 함수는 (session, *args) 시그니처. 테스트가 다음과 같이 호출:
    add_post_like(db, user, post)
"""
from datetime import UTC, datetime

from app.models.interaction import (
    journey_follows, post_likes, post_scraps, user_follows,
)


def add_post_like(session, user, post):
    session.execute(post_likes.insert().values(
        user_id=user.id, post_id=post.id, created_at=datetime.now(UTC),
    ))
    session.flush()


def add_post_scrap(session, user, post):
    session.execute(post_scraps.insert().values(
        user_id=user.id, post_id=post.id, created_at=datetime.now(UTC),
    ))
    session.flush()


def add_journey_follow(session, user, journey):
    session.execute(journey_follows.insert().values(
        user_id=user.id, journey_id=journey.id, created_at=datetime.now(UTC),
    ))
    session.flush()


def add_user_follow(session, follower, following):
    session.execute(user_follows.insert().values(
        follower_id=follower.id, following_id=following.id, created_at=datetime.now(UTC),
    ))
    session.flush()
```

### 3.8 __init__.py re-export

```python
# app/tests/factories/__init__.py
from app.tests.factories.badge_application import (
    BadgeApplicationFactory, BadgeEvidenceFactory,
)
from app.tests.factories.comment import CommentFactory
from app.tests.factories.image import ImageFactory
from app.tests.factories.interaction import (  # noqa: F401  # 헬퍼 함수
    add_journey_follow, add_post_like, add_post_scrap, add_user_follow,
)
from app.tests.factories.interest_region import UserInterestRegionFactory
from app.tests.factories.job import JobFactory
from app.tests.factories.journey import JourneyFactory
from app.tests.factories.moderation import (
    AnnouncementFactory, AuditLogFactory, ReportFactory,
)
from app.tests.factories.notification import NotificationFactory
from app.tests.factories.post import (
    AnswerPostFactory, JourneyEpisodePostFactory, PlanPostFactory,
    PostFactory, QuestionPostFactory, ReviewPostFactory,
)
from app.tests.factories.post_validation import PostValidationFactory
from app.tests.factories.region import PilotRegionFactory, RegionFactory
from app.tests.factories.tag import TagFactory
from app.tests.factories.user import (
    AdminUserFactory, RegionVerifiedUserFactory, ResidentUserFactory, UserFactory,
)

__all__ = [
    "AdminUserFactory",
    "AnnouncementFactory",
    "AnswerPostFactory",
    "AuditLogFactory",
    "BadgeApplicationFactory",
    "BadgeEvidenceFactory",
    "CommentFactory",
    "ImageFactory",
    "JobFactory",
    "JourneyEpisodePostFactory",
    "JourneyFactory",
    "NotificationFactory",
    "PilotRegionFactory",
    "PlanPostFactory",
    "PostFactory",
    "PostValidationFactory",
    "QuestionPostFactory",
    "RegionFactory",
    "RegionVerifiedUserFactory",
    "ReportFactory",
    "ResidentUserFactory",
    "ReviewPostFactory",
    "TagFactory",
    "UserFactory",
    "UserInterestRegionFactory",
    "add_journey_follow",
    "add_post_like",
    "add_post_scrap",
    "add_user_follow",
]
```

## 4. 마이그레이션 전략

### 4.1 단계

1. **factory 전체 작성** + `app/tests/unit/test_factories.py` (각 factory 1회 호출 → row 생성 + 핵심 invariant 검증). 풀 pytest 통과.
2. **conftest 수정** (`db` fixture에 `_bind_factories` 추가). 기존 테스트 영향 없음 — factory 사용 안 하면 binding은 무동작.
3. **모델 단순한 테스트부터 마이그레이션** — `test_user_model.py`, `test_region_model.py` 등 단일 모델 테스트. 1-2 파일씩 변경 후 `pytest -q` 실행.
4. **복합 테스트 마이그레이션** — `test_post_model.py`, `test_badge_workflow_e2e.py` 등 다중 모델 의존. 도메인별 묶음(badge/post/journey 등).
5. **잔존 검증** — `grep -rn "User(\|Region(\|Post(" app/tests/integration/` 결과 0건 확인.

### 4.2 Definition of Done

- [ ] `pytest app/tests/ -q` 통과 (현재 90개 + 약 14-20개 factory unit test 추가)
- [ ] `ruff check app/` 통과
- [ ] `app/tests/integration/`에서 모델 클래스 직접 생성자 호출 0건 (`User(`, `Region(`, `Post(`, `Comment(`, ...)
- [ ] `_seed`/`_make_*` boilerplate 헬퍼 함수 잔존 0건
- [ ] PostFactory 5종 type 모두 `app.schemas.post_metadata.PostMetadata` 검증 통과 (factory unit test에서 명시 검증)
- [ ] `app/tests/factories/__init__.py` re-export가 alphabetical (models/__init__.py 컨벤션 일치)
- [ ] CLAUDE.md "Working conventions"의 일관성 원칙 준수 (Phase 0의 user.py 패턴 보존)

## 5. 리스크 및 완화

| 리스크 | 완화 |
|---|---|
| Sequence 글로벌 누적이 다른 테스트 모듈에 누수 | TRUNCATE는 row만 비우고 sequence number는 Python 객체라 무관. 오히려 누적이 unique 보장 ✅ |
| Region get_or_create가 stale id 재사용 | Region에 deleted_at 없음, TRUNCATE로 매 테스트 사이 비워짐 → 무관 ✅ |
| JourneyEpisodePostFactory의 `episode_no` Sequence가 다른 journey와 충돌 | (journey_id, episode_no) unique constraint 가정. P1.3에서 episode 본격 사용 시점에 (journey 단위 sequence) 패턴 재검토. 현재 P1.1 Journey 테스트는 episode 없이 row만 만듦 → 미충돌 |
| factory.SubFactory가 N+1 row 폭증 | 각 테스트는 `_cleanup_db`로 격리. 1 테스트당 row 수 변화 없음 |
| hash_password bcrypt 비용 누적 | 1 호출 ≈ 50-100ms. 90개 테스트 × 1 user ≈ 5-10초. 허용 가능. 필요 시 BCRYPT_ROUNDS 환경 변수로 테스트 환경에서 4 rounds로 낮추는 별도 최적화 (out-of-scope) |

## 6. 비목표 (확인용)

- pytest-factoryboy 통합 (자동 fixture 생성). 명시 import가 더 명확.
- Factory의 post-generation hook으로 자동 commit. flush만 사용.
- 기존 `_cleanup_db` autouse fixture 변경.
- Faker 추가 locale 설치.
- 도메인 모델·라우트·서비스 코드 변경.

## 7. 후속 작업 (이 spec 외)

- **P1.3 시작 시점**: PostFactory의 metadata 패턴이 5종 type 추가 시점에 정확히 작동하는지 검증. 신규 type 추가 시 `_default_metadata`에 분기 추가 필수.
- **이미지 파이프라인 (P1.3)**: ImageFactory에 `original_url`/`thumb_url` 등 P1.3에서 신규 컬럼 추가 시 갱신.
- **factory.LazyAttribute로 trait 합성**: P1.3+ 에서 시나리오 테스트 (예: "approved badge 가진 user의 published review post") 작성 시 trait 도입 검토. 현재는 명시 서브클래스로 충분.
