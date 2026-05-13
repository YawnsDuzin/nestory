from datetime import UTC, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.templating_filters import (
    excerpt,
    first_image_url,
    markdown_to_html,
    strip_markdown_images,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["excerpt"] = excerpt
templates.env.filters["markdown"] = markdown_to_html
templates.env.filters["first_image_url"] = first_image_url
templates.env.filters["strip_md_images"] = strip_markdown_images
templates.env.globals["now"] = lambda: datetime.now(UTC)
