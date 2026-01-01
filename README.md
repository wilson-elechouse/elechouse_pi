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

## CLI

```bash
python render.py --data data/proforma_invoice.json --template proforma_invoice.html --out-dir output
```
