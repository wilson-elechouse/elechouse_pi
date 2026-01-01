from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"

_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)
_env.globals["enumerate"] = enumerate


def render_html(template_name: str, data: Dict[str, Any]) -> str:
    try:
        template = _env.get_template(template_name)
    except TemplateNotFound as exc:
        raise TemplateNotFound(template_name) from exc
    return template.render(**data)


async def html_to_pdf_bytes(html: str) -> bytes:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        pdf_bytes = await page.pdf(format="A4", print_background=True)
        await browser.close()
    return pdf_bytes
