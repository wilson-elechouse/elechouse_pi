from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from jinja2 import TemplateNotFound

from renderer import html_to_pdf_bytes, render_html

DEFAULT_TEMPLATE = "proforma_invoice.html"
FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
API_TOKEN = os.getenv("API_TOKEN")

logger = logging.getLogger("pdf_pi")

app = FastAPI()


def _sanitize_filename(value: str) -> str:
    cleaned = FILENAME_SAFE.sub("_", value).strip("._-")
    return cleaned or "document"


def _pick_base_filename(payload: dict, template: str, filename: Optional[str]) -> str:
    if filename:
        base = Path(filename).stem
    else:
        invoice = payload.get("invoice") or {}
        base = invoice.get("number") or Path(template).stem
    return _sanitize_filename(str(base))


def _require_token(request: Request) -> None:
    if not API_TOKEN:
        return
    auth = request.headers.get("authorization", "")
    token = ""
    parts = auth.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
    if not token:
        token = request.headers.get("x-api-key", "").strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/render")
async def render(
    payload: dict,
    template: str = DEFAULT_TEMPLATE,
    filename: Optional[str] = None,
    _: None = Depends(_require_token),
) -> Response:
    try:
        html = render_html(template, payload)
    except TemplateNotFound as exc:
        raise HTTPException(status_code=400, detail=f"template not found: {exc.name}") from exc

    pdf_bytes = await html_to_pdf_bytes(html)
    base_name = _pick_base_filename(payload, template, filename)
    pdf_name = f"{base_name}.pdf"
    logger.info("render pdf template=%s filename=%s", template, pdf_name)
    headers = {
        "Content-Disposition": f'attachment; filename="{pdf_name}"',
        "X-Rendered-Filename": pdf_name,
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.post("/render/html")
async def render_html_endpoint(
    payload: dict,
    template: str = DEFAULT_TEMPLATE,
    filename: Optional[str] = None,
    _: None = Depends(_require_token),
) -> Response:
    try:
        html = render_html(template, payload)
    except TemplateNotFound as exc:
        raise HTTPException(status_code=400, detail=f"template not found: {exc.name}") from exc

    base_name = _pick_base_filename(payload, template, filename)
    html_name = f"{base_name}.html"
    logger.info("render html template=%s filename=%s", template, html_name)
    headers = {
        "Content-Disposition": f'inline; filename="{html_name}"',
        "X-Rendered-Filename": html_name,
    }
    return Response(content=html, media_type="text/html", headers=headers)
