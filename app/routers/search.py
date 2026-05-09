"""Search routes — /search (q + region + type + sort + page)."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import Region, User
from app.models._enums import PostType
from app.services import search as search_service
from app.templating import templates

router = APIRouter(tags=["search"])


@router.get("/search", response_class=HTMLResponse)
def search(
    request: Request,
    q: str = "",
    region: str = "",  # region slug; empty = all
    # NOTE: `type` shadows the Python built-in here intentionally —
    # the URL contract requires ?type=review. Rebound to `post_type` below.
    type: str = "",  # post type value; empty = all  # noqa: A002
    sort: Literal["relevance", "latest", "popular"] = "relevance",
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    region_id: int | None = None
    if region:
        r = db.scalar(select(Region).where(Region.slug == region))
        region_id = r.id if r else None

    post_type: PostType | None = None
    if type:
        try:
            post_type = PostType(type)
        except ValueError:
            post_type = None

    all_regions = list(
        db.scalars(
            select(Region).order_by(Region.is_pilot.desc(), Region.sigungu)
        ).all()
    )

    if not q.strip():
        # Empty query — render form only, no results section
        return templates.TemplateResponse(
            request,
            "pages/search.html",
            {
                "q": "",
                "region": region,
                "type": type,
                "sort": sort,
                "all_regions": all_regions,
                "result": None,
                "page": page,
                "page_size": search_service.PAGE_SIZE,
                "current_user": current_user,
            },
        )

    result = search_service.search_posts(
        db,
        q,
        region_id=region_id,
        post_type=post_type,
        sort=sort,
        page=page,
    )
    return templates.TemplateResponse(
        request,
        "pages/search.html",
        {
            "q": q,
            "region": region,
            "type": type,
            "sort": sort,
            "all_regions": all_regions,
            "result": result,
            "page": page,
            "page_size": search_service.PAGE_SIZE,
            "current_user": current_user,
        },
    )
