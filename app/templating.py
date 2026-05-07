from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.templating_filters import markdown_to_html

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["markdown"] = markdown_to_html
