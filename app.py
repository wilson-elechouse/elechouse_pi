from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response
from jinja2 import TemplateNotFound

from renderer import html_to_pdf_bytes, render_html

DEFAULT_TEMPLATE = "proforma_invoice.html"

app = FastAPI()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/render")
async def render(payload: dict, template: str = DEFAULT_TEMPLATE) -> Response:
    try:
        html = render_html(template, payload)
    except TemplateNotFound as exc:
        raise HTTPException(status_code=400, detail=f"template not found: {exc.name}") from exc

    pdf_bytes = await html_to_pdf_bytes(html)
    return Response(content=pdf_bytes, media_type="application/pdf")


@app.post("/render/html")
async def render_html_endpoint(payload: dict, template: str = DEFAULT_TEMPLATE) -> Response:
    try:
        html = render_html(template, payload)
    except TemplateNotFound as exc:
        raise HTTPException(status_code=400, detail=f"template not found: {exc.name}") from exc

    return Response(content=html, media_type="text/html")
