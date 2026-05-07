# Nestory Test Factories (factory-boy) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce factory-boy across all 14 domain models, replace boilerplate `_seed*` helpers in 25 integration tests with factory calls, and establish a single consistent pattern for future test data construction.

**Architecture:** One factory file per domain model under `app/tests/factories/` (mirroring `app/models/`), all subclassing a `BaseFactory` whose `sqlalchemy_session` is injected at runtime by the existing `db` conftest fixture. SubFactory + SelfAttribute + `Meta.exclude` pattern keeps relationship objects available to test code while only FK ids reach the constructor. PostFactory's metadata is derived from the post's type via Pydantic models so the JSONB always validates against `PostMetadata`.

**Tech Stack:** factory-boy 3.3+ (already in dev deps), Pydantic 2.x (existing), SQLAlchemy 2.x (existing), pytest 8.3+ (existing).

**Spec:** [`docs/superpowers/specs/2026-05-07-nestory-test-factories-design.md`](../specs/2026-05-07-nestory-test-factories-design.md)

---

## File Structure

**Created:**
- `app/tests/factories/_base.py` — `BaseFactory` (abstract `SQLAlchemyModelFactory`)
- `app/tests/factories/__init__.py` — alphabetical re-exports
- `app/tests/factories/user.py` — `UserFactory` + `AdminUserFactory` + `RegionVerifiedUserFactory` + `ResidentUserFactory`
- `app/tests/factories/region.py` — `RegionFactory` + `PilotRegionFactory`
- `app/tests/factories/post.py` — `PostFactory` + `ReviewPostFactory` + `JourneyEpisodePostFactory` + `QuestionPostFactory` + `AnswerPostFactory` + `PlanPostFactory`
- `app/tests/factories/comment.py` — `CommentFactory`
- `app/tests/factories/journey.py` — `JourneyFactory`
- `app/tests/factories/image.py` — `ImageFactory`
- `app/tests/factories/badge_application.py` — `BadgeApplicationFactory` + `BadgeEvidenceFactory`
- `app/tests/factories/notification.py` — `NotificationFactory`
- `app/tests/factories/interest_region.py` — `UserInterestRegionFactory`
- `app/tests/factories/job.py` — `JobFactory`
- `app/tests/factories/tag.py` — `TagFactory`
- `app/tests/factories/moderation.py` — `AnnouncementFactory` + `AuditLogFactory` + `ReportFactory`
- `app/tests/factories/post_validation.py` — `PostValidationFactory`
- `app/tests/factories/interaction.py` — `add_post_like` / `add_post_scrap` / `add_journey_follow` / `add_user_follow` (helper functions, no factory class — `interaction` defines `Table` objects, not ORM models)
- `app/tests/unit/test_factories.py` — sanity tests: every factory creates a row + PostFactory's 5 type subfactories produce `PostMetadata`-valid JSONB

**Modified:**
- `app/tests/conftest.py` — `db` fixture binds factories' `sqlalchemy_session`
- All 25 integration test files under `app/tests/integration/` — replace direct model construction and `_seed*` helpers with factory calls

---

## Task 1: BaseFactory + conftest binding

**Files:**
- Create: `app/tests/factories/__init__.py` (empty stub for now — will be filled in Task 8)
- Create: `app/tests/factories/_base.py`
- Modify: `app/tests/conftest.py`

- [ ] **Step 1: Create empty package marker**

Create `app/tests/factories/__init__.py` with no content (just an empty file). Re-exports go here in Task 8.

- [ ] **Step 2: Write BaseFactory**

Create `app/tests/factories/_base.py`:

```python
"""Base for all model factories. Session is injected at runtime by conftest."""
from factory.alchemy import SQLAlchemyModelFactory


class BaseFactory(SQLAlchemyModelFactory):
    """Abstract base. `sqlalchemy_session` is set by `_bind_factories(db)` in conftest.

    `persistence="flush"` keeps factory-created rows uncommitted so the autouse
    `_cleanup_db` TRUNCATE CASCADE works correctly between tests.
    """

    class Meta:
        abstract = True
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "flush"
```

- [ ] **Step 3: Add `_bind_factories` and update `db` fixture in conftest**

Modify `app/tests/conftest.py`. After the existing `_cleanup_db` fixture (around line 39), and before the existing `db` fixture, add:

```python
def _all_subclasses(cls):
    """Return every subclass of `cls` recursively, excluding `cls` itself."""
    seen = set()
    stack = [cls]
    while stack:
        c = stack.pop()
        for sub in c.__subclasses__():
            if sub not in seen:
                seen.add(sub)
                stack.append(sub)
                yield sub


def _bind_factories(session: Session) -> None:
    """Inject `session` into every BaseFactory subclass.

    Importing `app.tests.factories` triggers registration of every factory
    declared in submodules. We then walk the subclass tree and patch
    `_meta.sqlalchemy_session` so that `Factory.create()` uses the test session.
    """
    import app.tests.factories  # noqa: F401  # registers all factory classes

    from app.tests.factories._base import BaseFactory

    for cls in _all_subclasses(BaseFactory):
        cls._meta.sqlalchemy_session = session
```

Then replace the existing `db` fixture body so it calls `_bind_factories`:

```python
@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        _bind_factories(session)
        yield session
    finally:
        session.close()
```

- [ ] **Step 4: Run existing tests to confirm no regression**

Run: `uv run pytest app/tests/ -q`
Expected: all 90 tests still pass (no factory is registered yet, so binding is a no-op loop).

- [ ] **Step 5: Commit**

```powershell
git add app/tests/factories/__init__.py app/tests/factories/_base.py app/tests/conftest.py
git commit -m "feat(tests): add BaseFactory and conftest session binding for factory-boy"
```

---

## Task 2: UserFactory + RegionFactory + their unit tests

**Files:**
- Create: `app/tests/factories/user.py`
- Create: `app/tests/factories/region.py`
- Create: `app/tests/unit/test_factories.py` (initial scaffold)

- [ ] **Step 1: Write the failing test for UserFactory**

Create `app/tests/unit/test_factories.py`:

```python
"""Sanity tests for every factory. Each factory should produce a persisted row
and (where applicable) a Pydantic-valid metadata payload."""
from sqlalchemy.orm import Session

from app.models import BadgeLevel, Region, User, UserRole


def test_user_factory_creates_user(db: Session) -> None:
    from app.tests.factories import UserFactory

    user = UserFactory()
    assert user.id is not None
    assert user.email.endswith("@example.com")
    assert user.role == UserRole.USER
    assert user.badge_level == BadgeLevel.INTERESTED
    # password_hash must be a real argon2 hash, not plaintext
    assert user.password_hash and user.password_hash.startswith("$argon2")


def test_admin_user_factory(db: Session) -> None:
    from app.tests.factories import AdminUserFactory

    admin = AdminUserFactory()
    assert admin.role == UserRole.ADMIN


def test_region_factory_creates_region(db: Session) -> None:
    from app.tests.factories import RegionFactory

    r = RegionFactory()
    assert r.id is not None
    assert r.sido == "경기"
    assert r.slug.startswith("test-")


def test_region_factory_get_or_create(db: Session) -> None:
    from app.tests.factories import RegionFactory

    r1 = RegionFactory(slug="dup-slug")
    r2 = RegionFactory(slug="dup-slug")
    assert r1.id == r2.id


def test_region_verified_user_factory_has_primary_region(db: Session) -> None:
    from app.tests.factories import RegionVerifiedUserFactory

    u = RegionVerifiedUserFactory()
    assert u.badge_level == BadgeLevel.REGION_VERIFIED
    assert u.primary_region_id is not None
    region = db.query(Region).filter_by(id=u.primary_region_id).one()
    assert region is not None


def test_resident_user_factory(db: Session) -> None:
    from app.tests.factories import ResidentUserFactory

    u = ResidentUserFactory()
    assert u.badge_level == BadgeLevel.RESIDENT
    assert u.resident_verified_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest app/tests/unit/test_factories.py -v`
Expected: ImportError — `cannot import name 'UserFactory' from 'app.tests.factories'`

- [ ] **Step 3: Write UserFactory**

Create `app/tests/factories/user.py`:

```python
"""User factory and badge-level variants."""
from datetime import UTC, datetime, timedelta

import factory

from app.models import BadgeLevel, User, UserRole
from app.services.auth import hash_password
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
    class Meta:
        model = User
        exclude = ("primary_region",)

    badge_level = BadgeLevel.REGION_VERIFIED
    primary_region = factory.SubFactory("app.tests.factories.region.RegionFactory")
    primary_region_id = factory.SelfAttribute("primary_region.id")


class ResidentUserFactory(RegionVerifiedUserFactory):
    class Meta:
        model = User
        exclude = ("primary_region",)

    badge_level = BadgeLevel.RESIDENT
    resident_verified_at = factory.LazyFunction(
        lambda: datetime.now(UTC) - timedelta(days=30)
    )
```

- [ ] **Step 4: Write RegionFactory**

Create `app/tests/factories/region.py`:

```python
"""Region factory with get-or-create on slug."""
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

- [ ] **Step 5: Wire re-exports in `__init__.py`**

Replace `app/tests/factories/__init__.py` with:

```python
from app.tests.factories.region import PilotRegionFactory, RegionFactory
from app.tests.factories.user import (
    AdminUserFactory,
    RegionVerifiedUserFactory,
    ResidentUserFactory,
    UserFactory,
)

__all__ = [
    "AdminUserFactory",
    "PilotRegionFactory",
    "RegionFactory",
    "RegionVerifiedUserFactory",
    "ResidentUserFactory",
    "UserFactory",
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest app/tests/unit/test_factories.py -v`
Expected: all 6 tests pass.

- [ ] **Step 7: Run full suite**

Run: `uv run pytest app/tests/ -q`
Expected: 90 + 6 = 96 tests pass.

- [ ] **Step 8: Lint**

Run: `uv run ruff check app/`
Expected: clean.

- [ ] **Step 9: Commit**

```powershell
git add app/tests/factories/user.py app/tests/factories/region.py app/tests/factories/__init__.py app/tests/unit/test_factories.py
git commit -m "feat(tests): add UserFactory and RegionFactory with sanity tests"
```

---

## Task 3: PostFactory + 5 type subfactories

**Files:**
- Create: `app/tests/factories/post.py`
- Modify: `app/tests/factories/__init__.py`
- Modify: `app/tests/unit/test_factories.py`

- [ ] **Step 1: Write the failing test**

Append to `app/tests/unit/test_factories.py`:

```python
def test_review_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter
    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import ReviewPostFactory

    p = ReviewPostFactory()
    assert p.id is not None
    assert p.type == PostType.REVIEW
    payload = {**p.metadata_, "__post_type__": "review"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_journey_episode_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter
    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import JourneyEpisodePostFactory

    p = JourneyEpisodePostFactory()
    assert p.type == PostType.JOURNEY_EPISODE
    assert p.journey_id is not None
    assert p.episode_no is not None
    payload = {**p.metadata_, "__post_type__": "journey_episode"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_question_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter
    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import QuestionPostFactory

    p = QuestionPostFactory()
    assert p.type == PostType.QUESTION
    payload = {**p.metadata_, "__post_type__": "question"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_answer_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter
    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import AnswerPostFactory

    p = AnswerPostFactory()
    assert p.type == PostType.ANSWER
    assert p.parent_post_id is not None
    payload = {**p.metadata_, "__post_type__": "answer"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_plan_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter
    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import PlanPostFactory

    p = PlanPostFactory()
    assert p.type == PostType.PLAN
    payload = {**p.metadata_, "__post_type__": "plan"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_post_factory_override_metadata_field(db: Session) -> None:
    from app.tests.factories import ReviewPostFactory

    p = ReviewPostFactory(
        metadata_={"house_type": "단독", "size_pyeong": 30, "satisfaction_overall": 1}
    )
    assert p.metadata_["satisfaction_overall"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_factories.py -v -k "post_factory"`
Expected: ImportError on `ReviewPostFactory`.

- [ ] **Step 3: Write PostFactory**

Create `app/tests/factories/post.py`:

```python
"""Post factory with type-aware metadata defaults."""
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
    """Return a Pydantic-valid minimal dict for the given post type.

    Excluded keys (`type_tag` / aliased `__post_type__`) are not stored on
    Post.metadata — type is the canonical discriminator.
    """
    if post_type == PostType.REVIEW:
        d = ReviewMetadata(
            house_type="단독", size_pyeong=30, satisfaction_overall=4
        ).model_dump(by_alias=False, exclude_none=True)
    elif post_type == PostType.JOURNEY_EPISODE:
        d = JourneyEpisodeMetadata(
            journey_ep_meta=JourneyEpMeta(phase="입주", period_label="2026-04")
        ).model_dump(by_alias=False, exclude_none=True)
    elif post_type == PostType.QUESTION:
        d = QuestionMetadata().model_dump(by_alias=False)
    elif post_type == PostType.ANSWER:
        d = AnswerMetadata().model_dump(by_alias=False)
    elif post_type == PostType.PLAN:
        d = PlanMetadata(
            target_move_year=2027,
            budget_total_manwon_band="5000-10000",
            construction_intent="undecided",
        ).model_dump(by_alias=False)
    else:
        raise ValueError(f"Unknown post_type: {post_type}")
    d.pop("type_tag", None)
    return d


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
    class Meta:
        model = Post
        exclude = ("author", "region", "journey")

    type = PostType.JOURNEY_EPISODE
    journey = factory.SubFactory("app.tests.factories.journey.JourneyFactory")
    journey_id = factory.SelfAttribute("journey.id")
    episode_no = factory.Sequence(lambda n: n + 1)


class QuestionPostFactory(PostFactory):
    type = PostType.QUESTION


class AnswerPostFactory(PostFactory):
    class Meta:
        model = Post
        exclude = ("author", "region", "parent_post")

    type = PostType.ANSWER
    parent_post = factory.SubFactory(QuestionPostFactory)
    parent_post_id = factory.SelfAttribute("parent_post.id")


class PlanPostFactory(PostFactory):
    type = PostType.PLAN
```

Note: `JourneyEpisodePostFactory` references `app.tests.factories.journey.JourneyFactory` as a string (lazy import) because Task 4 creates it. Tests for `JourneyEpisodePostFactory` will fail until Task 4 ships — this is acceptable since we run them at Step 5.

- [ ] **Step 4: Update `__init__.py` re-exports**

Replace `app/tests/factories/__init__.py` with:

```python
from app.tests.factories.post import (
    AnswerPostFactory,
    JourneyEpisodePostFactory,
    PlanPostFactory,
    PostFactory,
    QuestionPostFactory,
    ReviewPostFactory,
)
from app.tests.factories.region import PilotRegionFactory, RegionFactory
from app.tests.factories.user import (
    AdminUserFactory,
    RegionVerifiedUserFactory,
    ResidentUserFactory,
    UserFactory,
)

__all__ = [
    "AdminUserFactory",
    "AnswerPostFactory",
    "JourneyEpisodePostFactory",
    "PilotRegionFactory",
    "PlanPostFactory",
    "PostFactory",
    "QuestionPostFactory",
    "RegionFactory",
    "RegionVerifiedUserFactory",
    "ResidentUserFactory",
    "ReviewPostFactory",
    "UserFactory",
]
```

- [ ] **Step 5: Run all post tests except journey_episode (skip until Task 4)**

Run: `uv run pytest app/tests/unit/test_factories.py -v -k "post_factory and not journey_episode"`
Expected: 5 tests pass (review, question, answer, plan, override).

- [ ] **Step 6: Run full suite**

Run: `uv run pytest app/tests/ -q --deselect app/tests/unit/test_factories.py::test_journey_episode_post_factory_metadata_validates`
Expected: passes (we exclude the one test that needs JourneyFactory).

- [ ] **Step 7: Lint**

Run: `uv run ruff check app/`
Expected: clean.

- [ ] **Step 8: Commit**

```powershell
git add app/tests/factories/post.py app/tests/factories/__init__.py app/tests/unit/test_factories.py
git commit -m "feat(tests): add PostFactory with 5 type-aware subfactories"
```

---

## Task 4: Content factories (Comment, Journey, Image)

**Files:**
- Create: `app/tests/factories/comment.py`
- Create: `app/tests/factories/journey.py`
- Create: `app/tests/factories/image.py`
- Modify: `app/tests/factories/__init__.py`
- Modify: `app/tests/unit/test_factories.py`

- [ ] **Step 1: Write failing tests**

Append to `app/tests/unit/test_factories.py`:

```python
def test_comment_factory(db: Session) -> None:
    from app.models._enums import CommentStatus
    from app.tests.factories import CommentFactory

    c = CommentFactory()
    assert c.id is not None
    assert c.post_id is not None
    assert c.author_id is not None
    assert c.status == CommentStatus.VISIBLE


def test_journey_factory(db: Session) -> None:
    from app.models._enums import JourneyStatus
    from app.tests.factories import JourneyFactory

    j = JourneyFactory()
    assert j.id is not None
    assert j.author_id is not None
    assert j.region_id is not None
    assert j.status == JourneyStatus.IN_PROGRESS


def test_image_factory(db: Session) -> None:
    from app.models._enums import ImageStatus
    from app.tests.factories import ImageFactory

    img = ImageFactory()
    assert img.id is not None
    assert img.owner_id is not None
    assert img.file_path_orig.startswith("images/")
    assert img.status == ImageStatus.READY
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_factories.py::test_comment_factory app/tests/unit/test_factories.py::test_journey_factory app/tests/unit/test_factories.py::test_image_factory -v`
Expected: ImportError on the new factories.

- [ ] **Step 3: Write CommentFactory**

Create `app/tests/factories/comment.py`:

```python
"""Comment factory."""
import factory

from app.models import Comment
from app.models._enums import CommentStatus
from app.tests.factories._base import BaseFactory
from app.tests.factories.post import PostFactory
from app.tests.factories.user import UserFactory


class CommentFactory(BaseFactory):
    class Meta:
        model = Comment
        exclude = ("post", "author")

    post = factory.SubFactory(PostFactory)
    post_id = factory.SelfAttribute("post.id")
    author = factory.SubFactory(UserFactory)
    author_id = factory.SelfAttribute("author.id")

    body = factory.Faker("paragraph", nb_sentences=2, locale="ko_KR")
    status = CommentStatus.VISIBLE
```

- [ ] **Step 4: Write JourneyFactory**

Create `app/tests/factories/journey.py`:

```python
"""Journey factory."""
import factory

from app.models import Journey
from app.models._enums import JourneyStatus
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


class JourneyFactory(BaseFactory):
    class Meta:
        model = Journey
        exclude = ("author", "region")

    author = factory.SubFactory(UserFactory)
    author_id = factory.SelfAttribute("author.id")
    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    title = factory.Faker("sentence", nb_words=3, locale="ko_KR")
    status = JourneyStatus.IN_PROGRESS
```

- [ ] **Step 5: Write ImageFactory**

Create `app/tests/factories/image.py`:

```python
"""Image factory."""
import factory

from app.models import Image
from app.models._enums import ImageStatus
from app.tests.factories._base import BaseFactory
from app.tests.factories.user import UserFactory


class ImageFactory(BaseFactory):
    class Meta:
        model = Image
        exclude = ("owner",)

    owner = factory.SubFactory(UserFactory)
    owner_id = factory.SelfAttribute("owner.id")

    file_path_orig = factory.Sequence(lambda n: f"images/{n}/orig.jpg")
    status = ImageStatus.READY
    order_idx = 0
```

- [ ] **Step 6: Update `__init__.py`**

Add `CommentFactory`, `JourneyFactory`, `ImageFactory` imports and `__all__` entries (alphabetical). The full file after this step:

```python
from app.tests.factories.comment import CommentFactory
from app.tests.factories.image import ImageFactory
from app.tests.factories.journey import JourneyFactory
from app.tests.factories.post import (
    AnswerPostFactory,
    JourneyEpisodePostFactory,
    PlanPostFactory,
    PostFactory,
    QuestionPostFactory,
    ReviewPostFactory,
)
from app.tests.factories.region import PilotRegionFactory, RegionFactory
from app.tests.factories.user import (
    AdminUserFactory,
    RegionVerifiedUserFactory,
    ResidentUserFactory,
    UserFactory,
)

__all__ = [
    "AdminUserFactory",
    "AnswerPostFactory",
    "CommentFactory",
    "ImageFactory",
    "JourneyEpisodePostFactory",
    "JourneyFactory",
    "PilotRegionFactory",
    "PlanPostFactory",
    "PostFactory",
    "QuestionPostFactory",
    "RegionFactory",
    "RegionVerifiedUserFactory",
    "ResidentUserFactory",
    "ReviewPostFactory",
    "UserFactory",
]
```

- [ ] **Step 7: Run all factory unit tests (now JourneyEpisode should pass too)**

Run: `uv run pytest app/tests/unit/test_factories.py -v`
Expected: all tests pass including `test_journey_episode_post_factory_metadata_validates` (which was deselected in Task 3).

- [ ] **Step 8: Run full suite**

Run: `uv run pytest app/tests/ -q`
Expected: clean.

- [ ] **Step 9: Lint**

Run: `uv run ruff check app/`
Expected: clean.

- [ ] **Step 10: Commit**

```powershell
git add app/tests/factories/comment.py app/tests/factories/journey.py app/tests/factories/image.py app/tests/factories/__init__.py app/tests/unit/test_factories.py
git commit -m "feat(tests): add Comment/Journey/Image factories"
```

---

## Task 5: Badge factories (BadgeApplication, BadgeEvidence)

**Files:**
- Create: `app/tests/factories/badge_application.py`
- Modify: `app/tests/factories/__init__.py`
- Modify: `app/tests/unit/test_factories.py`

- [ ] **Step 1: Write failing tests**

Append to `app/tests/unit/test_factories.py`:

```python
def test_badge_application_factory(db: Session) -> None:
    from app.models._enums import BadgeApplicationStatus, BadgeRequestedLevel
    from app.tests.factories import BadgeApplicationFactory

    app = BadgeApplicationFactory()
    assert app.id is not None
    assert app.user_id is not None
    assert app.region_id is not None
    assert app.requested_level == BadgeRequestedLevel.REGION_VERIFIED
    assert app.status == BadgeApplicationStatus.PENDING


def test_badge_evidence_factory(db: Session) -> None:
    from app.models._enums import EvidenceType
    from app.tests.factories import BadgeEvidenceFactory

    e = BadgeEvidenceFactory()
    assert e.id is not None
    assert e.application_id is not None
    assert e.evidence_type == EvidenceType.UTILITY_BILL
    assert e.file_path.startswith("evidence/")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_factories.py::test_badge_application_factory app/tests/unit/test_factories.py::test_badge_evidence_factory -v`
Expected: ImportError.

- [ ] **Step 3: Write BadgeApplication + BadgeEvidence factories**

Create `app/tests/factories/badge_application.py`:

```python
"""BadgeApplication and BadgeEvidence factories."""
import factory

from app.models import BadgeApplication, BadgeEvidence
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
)
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


class BadgeApplicationFactory(BaseFactory):
    class Meta:
        model = BadgeApplication
        exclude = ("user", "region")

    user = factory.SubFactory(UserFactory)
    user_id = factory.SelfAttribute("user.id")
    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    requested_level = BadgeRequestedLevel.REGION_VERIFIED
    status = BadgeApplicationStatus.PENDING


class BadgeEvidenceFactory(BaseFactory):
    class Meta:
        model = BadgeEvidence
        exclude = ("application",)

    application = factory.SubFactory(BadgeApplicationFactory)
    application_id = factory.SelfAttribute("application.id")

    evidence_type = EvidenceType.UTILITY_BILL
    file_path = factory.Sequence(lambda n: f"evidence/{n}/test.jpg")
```

- [ ] **Step 4: Update `__init__.py`**

Add to imports:
```python
from app.tests.factories.badge_application import (
    BadgeApplicationFactory,
    BadgeEvidenceFactory,
)
```
And add `"BadgeApplicationFactory"`, `"BadgeEvidenceFactory"` to `__all__` (alphabetical position).

- [ ] **Step 5: Run new tests**

Run: `uv run pytest app/tests/unit/test_factories.py::test_badge_application_factory app/tests/unit/test_factories.py::test_badge_evidence_factory -v`
Expected: pass.

- [ ] **Step 6: Run full suite**

Run: `uv run pytest app/tests/ -q`
Expected: clean.

- [ ] **Step 7: Lint and commit**

```powershell
uv run ruff check app/
git add app/tests/factories/badge_application.py app/tests/factories/__init__.py app/tests/unit/test_factories.py
git commit -m "feat(tests): add BadgeApplication and BadgeEvidence factories"
```

---

## Task 6: Remaining 8 factories (Notification, UserInterestRegion, Job, Tag, Announcement, AuditLog, Report, PostValidation)

**Files:**
- Create: `app/tests/factories/notification.py`
- Create: `app/tests/factories/interest_region.py`
- Create: `app/tests/factories/job.py`
- Create: `app/tests/factories/tag.py`
- Create: `app/tests/factories/moderation.py`
- Create: `app/tests/factories/post_validation.py`
- Modify: `app/tests/factories/__init__.py`
- Modify: `app/tests/unit/test_factories.py`

- [ ] **Step 1: Write failing tests**

Append to `app/tests/unit/test_factories.py`:

```python
def test_notification_factory(db: Session) -> None:
    from app.models._enums import NotificationType
    from app.tests.factories import NotificationFactory

    n = NotificationFactory()
    assert n.id is not None
    assert n.user_id is not None
    assert n.type == NotificationType.SYSTEM
    assert n.is_read is False


def test_user_interest_region_factory(db: Session) -> None:
    from app.tests.factories import UserInterestRegionFactory

    uir = UserInterestRegionFactory()
    assert uir.user_id is not None
    assert uir.region_id is not None
    assert uir.priority == 1


def test_job_factory(db: Session) -> None:
    from app.models._enums import JobKind, JobStatus
    from app.tests.factories import JobFactory

    j = JobFactory()
    assert j.id is not None
    assert j.kind == JobKind.NOTIFICATION
    assert j.status == JobStatus.QUEUED
    assert j.payload == {}


def test_tag_factory(db: Session) -> None:
    from app.tests.factories import TagFactory

    t = TagFactory()
    assert t.id is not None
    assert t.slug.startswith("tag-")


def test_tag_factory_get_or_create(db: Session) -> None:
    from app.tests.factories import TagFactory

    t1 = TagFactory(slug="dup-tag")
    t2 = TagFactory(slug="dup-tag")
    assert t1.id == t2.id


def test_announcement_factory(db: Session) -> None:
    from app.models import UserRole
    from app.tests.factories import AnnouncementFactory

    a = AnnouncementFactory()
    assert a.id is not None
    assert a.author_id is not None
    assert a.pinned is False


def test_audit_log_factory(db: Session) -> None:
    from app.models._enums import AuditAction
    from app.tests.factories import AuditLogFactory

    log = AuditLogFactory()
    assert log.id is not None
    assert log.actor_id is not None
    assert log.action == AuditAction.BADGE_APPROVED
    assert log.target_type == "badge_applications"


def test_report_factory(db: Session) -> None:
    from app.models._enums import ReportReason, ReportStatus
    from app.tests.factories import ReportFactory

    r = ReportFactory()
    assert r.id is not None
    assert r.reporter_id is not None
    assert r.target_type == "posts"
    assert r.reason == ReportReason.SPAM
    assert r.status == ReportStatus.PENDING


def test_post_validation_factory(db: Session) -> None:
    from app.models import BadgeLevel
    from app.models._enums import ValidationVote
    from app.tests.factories import PostValidationFactory

    pv = PostValidationFactory()
    assert pv.id is not None
    assert pv.post_id is not None
    assert pv.validator_user_id is not None
    assert pv.vote == ValidationVote.CONFIRM
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_factories.py -v -k "notification or interest_region or job_factory or tag_factory or announcement or audit_log or report_factory or post_validation"`
Expected: ImportErrors.

- [ ] **Step 3: Write NotificationFactory**

Create `app/tests/factories/notification.py`:

```python
"""Notification factory."""
import factory

from app.models import Notification
from app.models._enums import NotificationType
from app.tests.factories._base import BaseFactory
from app.tests.factories.user import UserFactory


class NotificationFactory(BaseFactory):
    class Meta:
        model = Notification
        exclude = ("user",)

    user = factory.SubFactory(UserFactory)
    user_id = factory.SelfAttribute("user.id")

    type = NotificationType.SYSTEM
    is_read = False
```

- [ ] **Step 4: Write UserInterestRegionFactory**

Create `app/tests/factories/interest_region.py`:

```python
"""UserInterestRegion factory (composite PK on user_id + region_id)."""
import factory

from app.models import UserInterestRegion
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


class UserInterestRegionFactory(BaseFactory):
    class Meta:
        model = UserInterestRegion
        exclude = ("user", "region")

    user = factory.SubFactory(UserFactory)
    user_id = factory.SelfAttribute("user.id")
    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    priority = 1
```

- [ ] **Step 5: Write JobFactory**

Create `app/tests/factories/job.py`:

```python
"""Job factory (background queue)."""
import factory

from app.models import Job
from app.models._enums import JobKind, JobStatus
from app.tests.factories._base import BaseFactory


class JobFactory(BaseFactory):
    class Meta:
        model = Job

    kind = JobKind.NOTIFICATION
    payload = factory.LazyFunction(dict)
    status = JobStatus.QUEUED
```

- [ ] **Step 6: Write TagFactory**

Create `app/tests/factories/tag.py`:

```python
"""Tag factory with get-or-create on slug."""
import factory

from app.models import Tag
from app.tests.factories._base import BaseFactory


class TagFactory(BaseFactory):
    class Meta:
        model = Tag
        sqlalchemy_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"태그{n}")
    slug = factory.Sequence(lambda n: f"tag-{n}")
```

- [ ] **Step 7: Write moderation factories (Announcement, AuditLog, Report)**

Create `app/tests/factories/moderation.py`:

```python
"""Announcement, AuditLog, Report factories."""
import factory

from app.models import Announcement, AuditLog, Report
from app.models._enums import AuditAction, ReportReason, ReportStatus
from app.tests.factories._base import BaseFactory
from app.tests.factories.user import AdminUserFactory, UserFactory


class AnnouncementFactory(BaseFactory):
    class Meta:
        model = Announcement
        exclude = ("author",)

    author = factory.SubFactory(AdminUserFactory)
    author_id = factory.SelfAttribute("author.id")

    title = factory.Faker("sentence", nb_words=4, locale="ko_KR")
    body = factory.Faker("paragraph", nb_sentences=2, locale="ko_KR")
    pinned = False


class AuditLogFactory(BaseFactory):
    class Meta:
        model = AuditLog
        exclude = ("actor",)

    actor = factory.SubFactory(AdminUserFactory)
    actor_id = factory.SelfAttribute("actor.id")

    action = AuditAction.BADGE_APPROVED
    target_type = "badge_applications"
    target_id = factory.Sequence(lambda n: n + 1)


class ReportFactory(BaseFactory):
    class Meta:
        model = Report
        exclude = ("reporter",)

    reporter = factory.SubFactory(UserFactory)
    reporter_id = factory.SelfAttribute("reporter.id")

    target_type = "posts"
    target_id = factory.Sequence(lambda n: n + 1)
    reason = ReportReason.SPAM
    status = ReportStatus.PENDING
```

- [ ] **Step 8: Write PostValidationFactory**

Create `app/tests/factories/post_validation.py`:

```python
"""PostValidation factory (Pillar V cross-validation votes)."""
import factory

from app.models import PostValidation
from app.models._enums import ValidationVote
from app.tests.factories._base import BaseFactory
from app.tests.factories.post import PostFactory
from app.tests.factories.user import RegionVerifiedUserFactory


class PostValidationFactory(BaseFactory):
    class Meta:
        model = PostValidation
        exclude = ("post", "validator")

    post = factory.SubFactory(PostFactory)
    post_id = factory.SelfAttribute("post.id")
    validator = factory.SubFactory(RegionVerifiedUserFactory)
    validator_user_id = factory.SelfAttribute("validator.id")

    vote = ValidationVote.CONFIRM
```

- [ ] **Step 9: Update `__init__.py` with all new factories**

Replace `app/tests/factories/__init__.py` with the complete final form (alphabetical):

```python
from app.tests.factories.badge_application import (
    BadgeApplicationFactory,
    BadgeEvidenceFactory,
)
from app.tests.factories.comment import CommentFactory
from app.tests.factories.image import ImageFactory
from app.tests.factories.interest_region import UserInterestRegionFactory
from app.tests.factories.job import JobFactory
from app.tests.factories.journey import JourneyFactory
from app.tests.factories.moderation import (
    AnnouncementFactory,
    AuditLogFactory,
    ReportFactory,
)
from app.tests.factories.notification import NotificationFactory
from app.tests.factories.post import (
    AnswerPostFactory,
    JourneyEpisodePostFactory,
    PlanPostFactory,
    PostFactory,
    QuestionPostFactory,
    ReviewPostFactory,
)
from app.tests.factories.post_validation import PostValidationFactory
from app.tests.factories.region import PilotRegionFactory, RegionFactory
from app.tests.factories.tag import TagFactory
from app.tests.factories.user import (
    AdminUserFactory,
    RegionVerifiedUserFactory,
    ResidentUserFactory,
    UserFactory,
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
]
```

- [ ] **Step 10: Run all factory tests**

Run: `uv run pytest app/tests/unit/test_factories.py -v`
Expected: all tests pass.

- [ ] **Step 11: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: clean.

- [ ] **Step 12: Commit**

```powershell
git add app/tests/factories/notification.py app/tests/factories/interest_region.py app/tests/factories/job.py app/tests/factories/tag.py app/tests/factories/moderation.py app/tests/factories/post_validation.py app/tests/factories/__init__.py app/tests/unit/test_factories.py
git commit -m "feat(tests): add remaining 8 factories (Notification/InterestRegion/Job/Tag/Moderation/PostValidation)"
```

---

## Task 7: interaction.py helpers

**Files:**
- Create: `app/tests/factories/interaction.py`
- Modify: `app/tests/factories/__init__.py`
- Modify: `app/tests/unit/test_factories.py`

- [ ] **Step 1: Write failing tests**

Append to `app/tests/unit/test_factories.py`:

```python
def test_add_post_like_helper(db: Session) -> None:
    from sqlalchemy import select

    from app.models.interaction import post_likes
    from app.tests.factories import PostFactory, UserFactory, add_post_like

    post = PostFactory()
    user = UserFactory()
    add_post_like(db, user, post)

    rows = db.execute(
        select(post_likes).where(post_likes.c.post_id == post.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].user_id == user.id


def test_add_post_scrap_helper(db: Session) -> None:
    from sqlalchemy import select

    from app.models.interaction import post_scraps
    from app.tests.factories import PostFactory, UserFactory, add_post_scrap

    post = PostFactory()
    user = UserFactory()
    add_post_scrap(db, user, post)

    rows = db.execute(
        select(post_scraps).where(post_scraps.c.post_id == post.id)
    ).all()
    assert len(rows) == 1


def test_add_journey_follow_helper(db: Session) -> None:
    from sqlalchemy import select

    from app.models.interaction import journey_follows
    from app.tests.factories import JourneyFactory, UserFactory, add_journey_follow

    journey = JourneyFactory()
    user = UserFactory()
    add_journey_follow(db, user, journey)

    rows = db.execute(
        select(journey_follows).where(journey_follows.c.journey_id == journey.id)
    ).all()
    assert len(rows) == 1


def test_add_user_follow_helper(db: Session) -> None:
    from sqlalchemy import select

    from app.models.interaction import user_follows
    from app.tests.factories import UserFactory, add_user_follow

    follower = UserFactory()
    following = UserFactory()
    add_user_follow(db, follower, following)

    rows = db.execute(
        select(user_follows).where(user_follows.c.follower_id == follower.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].following_id == following.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_factories.py -v -k "add_post_like or add_post_scrap or add_journey_follow or add_user_follow"`
Expected: ImportError on the helpers.

- [ ] **Step 3: Write helper module**

Create `app/tests/factories/interaction.py`:

```python
"""Helpers for M:N junction Tables (post_likes, post_scraps, etc).

These are not factory_boy `Factory` classes because the underlying objects
are SQLAlchemy `Table` instances, not ORM models. They take the active session
explicitly so callers can use them alongside ORM-backed factories.
"""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.interaction import (
    journey_follows,
    post_likes,
    post_scraps,
    user_follows,
)


def add_post_like(session: Session, user, post) -> None:
    session.execute(
        post_likes.insert().values(
            user_id=user.id, post_id=post.id, created_at=datetime.now(UTC)
        )
    )
    session.flush()


def add_post_scrap(session: Session, user, post) -> None:
    session.execute(
        post_scraps.insert().values(
            user_id=user.id, post_id=post.id, created_at=datetime.now(UTC)
        )
    )
    session.flush()


def add_journey_follow(session: Session, user, journey) -> None:
    session.execute(
        journey_follows.insert().values(
            user_id=user.id, journey_id=journey.id, created_at=datetime.now(UTC)
        )
    )
    session.flush()


def add_user_follow(session: Session, follower, following) -> None:
    session.execute(
        user_follows.insert().values(
            follower_id=follower.id,
            following_id=following.id,
            created_at=datetime.now(UTC),
        )
    )
    session.flush()
```

- [ ] **Step 4: Re-export helpers in `__init__.py`**

Add to `app/tests/factories/__init__.py`:

```python
from app.tests.factories.interaction import (  # noqa: F401  # helper functions
    add_journey_follow,
    add_post_like,
    add_post_scrap,
    add_user_follow,
)
```

And add to `__all__` (alphabetical):
```python
    "add_journey_follow",
    "add_post_like",
    "add_post_scrap",
    "add_user_follow",
```

- [ ] **Step 5: Run helper tests**

Run: `uv run pytest app/tests/unit/test_factories.py -v -k "add_post_like or add_post_scrap or add_journey_follow or add_user_follow"`
Expected: pass.

- [ ] **Step 6: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: clean.

- [ ] **Step 7: Commit**

```powershell
git add app/tests/factories/interaction.py app/tests/factories/__init__.py app/tests/unit/test_factories.py
git commit -m "feat(tests): add interaction helper functions for M:N junction tables"
```

---

## Task 8: Migrate model unit-style integration tests

**Migrating these 7 files** (single-model tests with `_seed`-style helpers):
- `app/tests/integration/test_user_model.py`
- `app/tests/integration/test_region_model.py`
- `app/tests/integration/test_post_model.py`
- `app/tests/integration/test_post_validation_model.py`
- `app/tests/integration/test_post_metadata_schema.py`
- `app/tests/integration/test_comment_model.py`
- `app/tests/integration/test_journey_model.py`

**Migration recipe (apply to every test file):**
1. Replace direct constructors `User(...)`, `Region(...)`, `Post(...)` with the matching factory.
2. Delete `_seed`/`_make_*` private helpers — call factories directly.
3. Where a test asserted on specific values that the factory now generates randomly, use explicit kwargs to fix those values. Example: `UserFactory(email="alice@example.com")`.
4. Imports: replace `from app.models import ...` of model classes (when only used for construction) with `from app.tests.factories import ...`.

- [ ] **Step 1: Migrate `test_user_model.py`**

Read the existing file, identify each direct `User(...)` call, replace with `UserFactory(...)` preserving any explicit kwargs the test relies on. Delete `_seed`/`_make_user` helpers.

Example transformation (illustrative — adapt to actual file content):
```python
# Before
def test_create_user(db):
    u = User(email="a@example.com", username="a", display_name="A", password_hash="x")
    db.add(u); db.flush()
    assert u.id is not None

# After
from app.tests.factories import UserFactory

def test_create_user(db):
    u = UserFactory(email="a@example.com", username="a", display_name="A")
    assert u.id is not None
```

- [ ] **Step 2: Run `test_user_model.py`**

Run: `uv run pytest app/tests/integration/test_user_model.py -v`
Expected: all tests pass.

- [ ] **Step 3: Migrate `test_region_model.py`**

Same recipe — replace `Region(...)` with `RegionFactory(...)`. Note the get-or-create behavior: if a test creates two regions with the same `slug`, the factory will return the same row (matching the natural-key behavior the test almost certainly already documents).

- [ ] **Step 4: Run `test_region_model.py`**

Run: `uv run pytest app/tests/integration/test_region_model.py -v`
Expected: pass.

- [ ] **Step 5: Migrate `test_post_model.py`**

Replace the `_seed(db)` helper with direct `ReviewPostFactory()` (or `PostFactory(type=...)`). The factory handles author + region creation via SubFactory. For tests that depend on a specific `metadata_` shape, pass it explicitly: `ReviewPostFactory(metadata_={...})`. For tests that don't care, just call `ReviewPostFactory()`.

- [ ] **Step 6: Run `test_post_model.py`**

Run: `uv run pytest app/tests/integration/test_post_model.py -v`
Expected: pass.

- [ ] **Step 7: Migrate `test_post_validation_model.py`**

Replace direct construction with `PostValidationFactory(...)`. Note: `validator_user_id` is the actual column name (not `voter_id`).

- [ ] **Step 8: Run `test_post_validation_model.py`**

Run: `uv run pytest app/tests/integration/test_post_validation_model.py -v`
Expected: pass.

- [ ] **Step 9: Migrate `test_post_metadata_schema.py`**

This file likely tests Pydantic schemas directly (not DB). It probably needs no factory changes — leave it untouched if no model construction is present. Read first to confirm.

- [ ] **Step 10: Migrate `test_comment_model.py`**

Replace with `CommentFactory()` / `CommentFactory(parent_id=parent.id)` for thread tests.

- [ ] **Step 11: Run `test_comment_model.py`**

Run: `uv run pytest app/tests/integration/test_comment_model.py -v`
Expected: pass.

- [ ] **Step 12: Migrate `test_journey_model.py`**

Replace with `JourneyFactory()`.

- [ ] **Step 13: Run `test_journey_model.py`**

Run: `uv run pytest app/tests/integration/test_journey_model.py -v`
Expected: pass.

- [ ] **Step 14: Run full suite and lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: clean.

- [ ] **Step 15: Commit**

```powershell
git add app/tests/integration/test_user_model.py app/tests/integration/test_region_model.py app/tests/integration/test_post_model.py app/tests/integration/test_post_validation_model.py app/tests/integration/test_post_metadata_schema.py app/tests/integration/test_comment_model.py app/tests/integration/test_journey_model.py
git commit -m "test: migrate model unit-style tests to factory-boy"
```

---

## Task 9: Migrate remaining model integration tests + interaction/notification/moderation/tag

**Migrating these 6 files:**
- `app/tests/integration/test_image_model.py`
- `app/tests/integration/test_tag_model.py`
- `app/tests/integration/test_interaction_model.py`
- `app/tests/integration/test_interest_region_model.py`
- `app/tests/integration/test_notification_model.py`
- `app/tests/integration/test_moderation_model.py`

- [ ] **Step 1: Migrate `test_image_model.py`**

Replace with `ImageFactory()`. Note actual fields: `owner_id`, `file_path_orig` (not `original_url`).

- [ ] **Step 2: Migrate `test_tag_model.py`**

Replace with `TagFactory()`. Note get-or-create on slug.

- [ ] **Step 3: Migrate `test_interaction_model.py`**

Use the helper functions: `add_post_like(db, user, post)` etc.

- [ ] **Step 4: Migrate `test_interest_region_model.py`**

Replace with `UserInterestRegionFactory()`.

- [ ] **Step 5: Migrate `test_notification_model.py`**

Replace with `NotificationFactory(...)`. Note: field is `type`, `is_read` (not `notification_type`, `read_at`).

- [ ] **Step 6: Migrate `test_moderation_model.py`**

Replace with `AnnouncementFactory()`, `AuditLogFactory()`, `ReportFactory()`. Note: `target_type` (not `target_table`), `note` on AuditLog (not `metadata`).

- [ ] **Step 7: Run all six**

Run: `uv run pytest app/tests/integration/test_image_model.py app/tests/integration/test_tag_model.py app/tests/integration/test_interaction_model.py app/tests/integration/test_interest_region_model.py app/tests/integration/test_notification_model.py app/tests/integration/test_moderation_model.py -v`
Expected: all pass.

- [ ] **Step 8: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: clean.

- [ ] **Step 9: Commit**

```powershell
git add app/tests/integration/test_image_model.py app/tests/integration/test_tag_model.py app/tests/integration/test_interaction_model.py app/tests/integration/test_interest_region_model.py app/tests/integration/test_notification_model.py app/tests/integration/test_moderation_model.py
git commit -m "test: migrate Image/Tag/Interaction/InterestRegion/Notification/Moderation tests to factory-boy"
```

---

## Task 10: Migrate badge service/route tests

**Migrating these 6 files (all from Phase 1.2):**
- `app/tests/integration/test_badge_application_model.py`
- `app/tests/integration/test_badges_service.py`
- `app/tests/integration/test_me_badge_routes.py`
- `app/tests/integration/test_admin_badge_routes.py`
- `app/tests/integration/test_deps_guards.py`
- `app/tests/integration/test_evidence_storage.py`

These typically have rich `_seed*` helpers because they construct user + region + application + evidence chains.

- [ ] **Step 1: Migrate `test_badge_application_model.py`**

Replace with `BadgeApplicationFactory()` and `BadgeEvidenceFactory()`.

- [ ] **Step 2: Migrate `test_badges_service.py`**

Service-layer tests — replace user/region/application setup with factories. Service function calls (`apply`, `approve`, etc.) stay the same.

- [ ] **Step 3: Migrate `test_me_badge_routes.py`**

Route tests use `client` fixture. Replace setup with factories. Login simulation (cookie/session) stays the same.

- [ ] **Step 4: Migrate `test_admin_badge_routes.py`**

Same as Step 3 but admin routes. Use `AdminUserFactory()` for the actor.

- [ ] **Step 5: Migrate `test_deps_guards.py`**

Tests for `require_login`, `require_badge`, `require_admin`, `require_resident_in_region`. Use `RegionVerifiedUserFactory()` and `ResidentUserFactory()` to create users at specific badge levels.

- [ ] **Step 6: Migrate `test_evidence_storage.py`**

If this tests file storage primitives (no DB), no factory changes needed. Read first to confirm.

- [ ] **Step 7: Run all six**

Run: `uv run pytest app/tests/integration/test_badge_application_model.py app/tests/integration/test_badges_service.py app/tests/integration/test_me_badge_routes.py app/tests/integration/test_admin_badge_routes.py app/tests/integration/test_deps_guards.py app/tests/integration/test_evidence_storage.py -v`
Expected: all pass.

- [ ] **Step 8: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: clean.

- [ ] **Step 9: Commit**

```powershell
git add app/tests/integration/test_badge_application_model.py app/tests/integration/test_badges_service.py app/tests/integration/test_me_badge_routes.py app/tests/integration/test_admin_badge_routes.py app/tests/integration/test_deps_guards.py app/tests/integration/test_evidence_storage.py
git commit -m "test: migrate badge service/route tests to factory-boy"
```

---

## Task 11: Migrate end-to-end and worker/auth tests

**Migrating these 8 files:**
- `app/tests/integration/test_badge_workflow_e2e.py`
- `app/tests/integration/test_evidence_cleanup_handler.py`
- `app/tests/integration/test_kakao_callback.py`
- `app/tests/integration/test_auth_service_db.py`
- `app/tests/integration/test_bootstrap_admin.py`
- `app/tests/integration/test_job_model.py`
- `app/tests/integration/test_job_queue.py`
- `app/tests/integration/test_handlers_registry.py`
- `app/tests/integration/test_worker_e2e.py`

- [ ] **Step 1: Migrate `test_badge_workflow_e2e.py`**

The largest E2E test. Replace setup chains with factories. Workflow assertions stay.

- [ ] **Step 2: Migrate `test_evidence_cleanup_handler.py`**

Worker handler test. Use `BadgeApplicationFactory`/`BadgeEvidenceFactory`/`JobFactory`. Handler invocation stays.

- [ ] **Step 3: Migrate `test_kakao_callback.py`**

OAuth callback test. Replace pre-existing user setup (if any) with `UserFactory(kakao_id=...)`.

- [ ] **Step 4: Migrate `test_auth_service_db.py`**

Auth service tests. Replace user setup with `UserFactory()`. Note: `password_hash` is now a real argon2 hash (`UserFactory` calls `hash_password("test1234!")`), so `verify_password(user, "test1234!")` will work.

- [ ] **Step 5: Migrate `test_bootstrap_admin.py`**

Bootstrap creates the first admin. Tests likely assert a row appears — keep direct queries, use factories only where the test seeds data.

- [ ] **Step 6: Migrate `test_job_model.py`**

Replace `Job(...)` with `JobFactory(...)`. Note: default status is `JobStatus.QUEUED`.

- [ ] **Step 7: Migrate `test_job_queue.py`**

Queue ops (enqueue/dequeue/mark_succeeded). Use `JobFactory()` for setup.

- [ ] **Step 8: Migrate `test_handlers_registry.py`**

Registry test. Probably no DB models — read first; if no construction, leave untouched.

- [ ] **Step 9: Migrate `test_worker_e2e.py`**

Worker round-trip. Use `JobFactory()` to enqueue.

- [ ] **Step 10: Run all nine**

Run: `uv run pytest app/tests/integration/test_badge_workflow_e2e.py app/tests/integration/test_evidence_cleanup_handler.py app/tests/integration/test_kakao_callback.py app/tests/integration/test_auth_service_db.py app/tests/integration/test_bootstrap_admin.py app/tests/integration/test_job_model.py app/tests/integration/test_job_queue.py app/tests/integration/test_handlers_registry.py app/tests/integration/test_worker_e2e.py -v`
Expected: all pass.

- [ ] **Step 11: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: clean.

- [ ] **Step 12: Commit**

```powershell
git add app/tests/integration/test_badge_workflow_e2e.py app/tests/integration/test_evidence_cleanup_handler.py app/tests/integration/test_kakao_callback.py app/tests/integration/test_auth_service_db.py app/tests/integration/test_bootstrap_admin.py app/tests/integration/test_job_model.py app/tests/integration/test_job_queue.py app/tests/integration/test_handlers_registry.py app/tests/integration/test_worker_e2e.py
git commit -m "test: migrate E2E/worker/auth tests to factory-boy"
```

---

## Task 12: Final DoD validation + remaining files

**Files to verify:**
- `app/tests/integration/test_seed_regions.py` — verifies the seed_regions migration; should not need factory changes
- `app/tests/integration/test_health.py` — health endpoint; no models
- `app/tests/integration/test_pages.py` — public pages; may use factories for fixtures

- [ ] **Step 1: Read `test_seed_regions.py`, `test_health.py`, `test_pages.py`**

If any contain direct model construction, migrate per the same recipe.

- [ ] **Step 2: Migrate any remaining tests if needed**

If migrations are needed, repeat the recipe and run each file. If not, skip to Step 3.

- [ ] **Step 3: Verify no direct model construction remains in `app/tests/integration/`**

Run: `uv run python -c "import subprocess; r = subprocess.run(['rg', '-n', '--type', 'py', r'(?:^|[^A-Za-z_])(User|Region|Post|Comment|Journey|Image|BadgeApplication|BadgeEvidence|Notification|UserInterestRegion|Job|Tag|Announcement|AuditLog|Report|PostValidation)\\(', 'app/tests/integration/'], capture_output=True, text=True); print(r.stdout); print('STDERR:', r.stderr)"`

Expected: empty output. Any matches must be reviewed — they're either:
- Legitimate (e.g., `Post.query.filter(Post.id == ...)` is `Post.` not `Post(`, but `isinstance(x, User)` is fine too because of the `(` immediately following — recheck the regex to ensure only constructor calls match)
- Missed migrations (fix and recommit)

If regex produces false positives, narrow it to require non-`.` prefix and a non-`,` suffix that suggests a constructor call.

- [ ] **Step 4: Verify no `_seed*` boilerplate helpers remain**

Run: `uv run python -c "import subprocess; r = subprocess.run(['rg', '-n', '--type', 'py', r'^def _(seed|make_user|make_region|make_post|make_comment|make_journey|make_application|make_evidence)', 'app/tests/integration/'], capture_output=True, text=True); print(r.stdout)"`

Expected: empty output.

- [ ] **Step 5: Run final full suite**

Run: `uv run pytest app/tests/ -q`
Expected: pre-existing 90 + factory unit tests (~25) ≈ 115+ pass.

- [ ] **Step 6: Final lint**

Run: `uv run ruff check app/`
Expected: clean.

- [ ] **Step 7: Confirm CLAUDE.md alignment — single test file diff sanity check**

Pick `app/tests/integration/test_post_model.py` (or any migrated file) and run:
```powershell
git log -p --follow app/tests/integration/test_post_model.py | Select-Object -First 100
```
Confirm: line count went down (boilerplate removed), readability improved, factory imports present.

- [ ] **Step 8: Commit any remaining changes**

```powershell
git add app/tests/integration/
git commit -m "test: complete factory-boy migration and verify DoD" -m "All 25 integration tests now use factory-boy. Direct model construction removed."
```

(If Step 4–6 produced no diff, skip the commit.)

---

## Self-Review Notes

- **Spec coverage**: Sections 3.1 (structure), 3.2 (BaseFactory), 3.3 (UserFactory), 3.4 (RegionFactory), 3.5 (PostFactory), 3.6 (12 remaining), 3.7 (interaction helpers), 3.8 (re-export), 4.1 (migration steps), 4.2 (DoD) — every requirement covered by Tasks 1–12.
- **Type/name consistency**: `validator_user_id` (PostValidation), `target_type` (Report/AuditLog), `is_read` (Notification), `owner_id` + `file_path_orig` (Image), `following_id` (user_follows), `JobStatus.QUEUED` — all matched against actual models. `app.services.auth.hash_password` import path verified.
- **No placeholders**: All steps include exact paths, code, commands, and expected output.
