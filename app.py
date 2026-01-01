from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from jinja2 import TemplateNotFound

from renderer import html_to_pdf_bytes, render_html

DEFAULT_TEMPLATE = "proforma_invoice.html"
FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

logger = logging.getLogger("pdf_pi")

def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid %s=%s; using %s", name, value, default)
        return default


API_TOKEN = os.getenv("API_TOKEN")
PDF_STORAGE_DIR = Path(os.getenv("PDF_STORAGE_DIR", "/app/storage"))
PDF_TTL_SECONDS = _env_int("PDF_TTL_SECONDS", 3600)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

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


def _build_storage_filename(base_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:10]
    return f"{base_name}-{stamp}-{suffix}.pdf"


def _ensure_storage_dir() -> None:
    try:
        PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.exception("Failed to create storage dir %s", PDF_STORAGE_DIR)
        raise HTTPException(status_code=500, detail="storage unavailable") from exc


def _is_expired(path: Path, now: Optional[float] = None) -> bool:
    if PDF_TTL_SECONDS <= 0:
        return False
    if now is None:
        now = time.time()
    return path.stat().st_mtime < now - PDF_TTL_SECONDS


def _cleanup_expired_files() -> None:
    if PDF_TTL_SECONDS <= 0:
        return
    now = time.time()
    for file_path in PDF_STORAGE_DIR.glob("*.pdf"):
        try:
            if _is_expired(file_path, now):
                file_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to delete expired file %s", file_path)


async def _delete_later(path: Path, delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to delete file %s", path)


def _schedule_cleanup(path: Path) -> None:
    if PDF_TTL_SECONDS > 0:
        asyncio.create_task(_delete_later(path, PDF_TTL_SECONDS))


def _build_file_url(request: Request, filename: str) -> str:
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/files/{filename}"
    return f"{str(request.base_url).rstrip('/')}/files/{filename}"


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
    if not token:
        token = request.query_params.get("token", "").strip()
    if not token:
        token = request.query_params.get("access_token", "").strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.on_event("startup")
async def startup() -> None:
    _ensure_storage_dir()
    _cleanup_expired_files()


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


@app.post("/render/link")
async def render_link(
    payload: dict,
    request: Request,
    template: str = DEFAULT_TEMPLATE,
    filename: Optional[str] = None,
    _: None = Depends(_require_token),
) -> dict:
    _ensure_storage_dir()
    _cleanup_expired_files()
    try:
        html = render_html(template, payload)
    except TemplateNotFound as exc:
        raise HTTPException(status_code=400, detail=f"template not found: {exc.name}") from exc

    pdf_bytes = await html_to_pdf_bytes(html)
    base_name = _pick_base_filename(payload, template, filename)
    stored_name = _build_storage_filename(base_name)
    file_path = PDF_STORAGE_DIR / stored_name
    file_path.write_bytes(pdf_bytes)
    _schedule_cleanup(file_path)

    url = _build_file_url(request, stored_name)
    return {
        "url": url,
        "filename": stored_name,
        "expires_in": PDF_TTL_SECONDS,
    }


@app.get("/files/{file_name}", name="download_file")
async def download_file(
    file_name: str,
) -> FileResponse:
    if Path(file_name).name != file_name or not file_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="invalid filename")

    file_path = PDF_STORAGE_DIR / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    if _is_expired(file_path):
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to delete expired file %s", file_path)
        raise HTTPException(status_code=404, detail="file expired")

    return FileResponse(file_path, media_type="application/pdf", filename=file_name)
