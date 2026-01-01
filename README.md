# elechouse_pi

Small FastAPI service to render HTML + PDF from JSON data with Jinja2 and Playwright.

## Local run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app:app --host 0.0.0.0 --port 8080
```

## API

- `POST /render` returns `application/pdf`
- `POST /render/html` returns rendered HTML

Example request body: `data/proforma_invoice.json`

Optional query params:
- `template` to select a template filename
- `filename` to control the output name (defaults to `invoice.number` or template name)

Responses include:
- `Content-Disposition` with the filename
- `X-Rendered-Filename` with the filename

### Auth (optional)

Set `API_TOKEN` to require a token. Use either header:
- `Authorization: Bearer <token>`
- `X-API-Key: <token>`

## CLI

```bash
python render.py --data data/proforma_invoice.json --template proforma_invoice.html --out-dir output
```
