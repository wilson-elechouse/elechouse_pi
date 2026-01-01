# elechouse_pi

Small FastAPI service to render HTML + PDF from JSON data using Jinja2 templates
and Playwright.

## Service overview

Base URL: `http://<host>:8080`

The service renders HTML/PDF from a JSON payload and returns bytes in the
response. It does not store files on the server.

## Authentication (optional)

Set `API_TOKEN` to require a token. If set, `/render` and `/render/html` require
auth, while `/health` stays public.

Use either header:
- `Authorization: Bearer <token>`
- `X-API-Key: <token>`
For file downloads you can also pass `token` or `access_token` as a query
parameter, for example: `/files/<name>.pdf?token=<token>`.

## Endpoints

### GET /health

Returns:
```json
{"status":"ok"}
```

### POST /render

Returns: `application/pdf`

Query params:
- `template` (optional) Template filename from `templates/` (default:
  `proforma_invoice.html`)
- `filename` (optional) Output filename override (default: `invoice.number` or
  template name)

Response headers:
- `Content-Disposition: attachment; filename="..."`
- `X-Rendered-Filename: ...`

Example:
```bash
curl -X POST "http://<host>:8080/render?filename=PI-2025-0001" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data @data/proforma_invoice.json -o out.pdf
```

### POST /render/html

Returns: `text/html`

Query params are the same as `/render`.

Example:
```bash
curl -X POST "http://<host>:8080/render/html?template=proforma_invoice.html" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data @data/proforma_invoice.json -o out.html
```

### POST /render/link

Returns JSON with a temporary download URL and filename. The PDF is stored on
the server and cleaned up automatically after the TTL.

Response:
```json
{
  "url": "http://<host>:8080/files/PI-2025-0001-20250202T120102Z-acde1234ef.pdf",
  "filename": "PI-2025-0001-20250202T120102Z-acde1234ef.pdf",
  "expires_in": 3600
}
```

Example:
```bash
curl -X POST "http://<host>:8080/render/link?filename=PI-2025-0001" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data @data/proforma_invoice.json
```

### GET /files/{file_name}

Downloads a previously stored PDF by filename. If the file is expired it will
return 404 and remove it.

Example:
```bash
curl -L "http://<host>:8080/files/<name>.pdf?token=<token>" -o out.pdf
```

## Request data format

The JSON format is defined by the template. For the bundled
`templates/proforma_invoice.html`, use this top-level shape (see
`data/proforma_invoice.json` for a full example):

```json
{
  "seller": {},
  "invoice": {},
  "buyer": {},
  "ship_to": {},
  "items": [],
  "terms": {},
  "totals": {},
  "bank": {},
  "notes": ""
}
```

Top-level fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| seller | object | yes | Seller info used in header |
| invoice | object | yes | Invoice info; `invoice.number` drives filename |
| buyer | object | yes | Buyer info block |
| ship_to | object | optional | Shipping info; name defaults to buyer name |
| items | array | yes | Line items; used to compute amounts |
| terms | object | optional | Shipping/payment/lead time text |
| totals | object | yes | Totals table with numeric values |
| bank | object | optional | Bank details block |
| notes | string | optional | Additional notes text |

`seller`, `buyer`, `ship_to` address object:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| line1 | string | yes | Address line 1 |
| line2 | string | optional | Address line 2 |
| city | string | optional | City |
| state | string | optional | State/region |
| postal | string | optional | Postal code |
| country | string | optional | Country |

`seller` object:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | string | yes | Seller name |
| website | string | optional | Website URL |
| email | string | optional | Contact email |
| phone | string | optional | Not shown in template by default |
| address | object | yes | Address object |

`invoice` object:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| number | string | optional | Used for default filename and displayed on invoice |
| date | string | optional | Invoice date |
| incoterm | string | optional | Incoterm text |
| currency | string | optional | Currency code |

`buyer` object:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | string | optional | Buyer name |
| company | string | optional | Company name |
| contact | string | optional | Contact person |
| phone | string | optional | Phone number |
| email | string | optional | Email |
| address | object | optional | Address object |
| tax_id | string | optional | Shows only if provided |

`ship_to` object:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | string | optional | If empty, buyer name is used |
| address | object | optional | Address object |
| phone | string | optional | Phone number |

`items` array item:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | string | yes | Item name |
| model | string | optional | Model text |
| desc | string | optional | Description |
| hs_code | string | optional | HS code |
| qty | number | yes | Quantity; used in amount calculation |
| uom | string | optional | Unit of measure |
| unit_price | number | yes | Unit price; used in amount calculation |

`terms` object:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| shipping | string | optional | Shipping terms |
| payment | string | optional | Payment terms |
| lead_time | string | optional | Lead time text |
| offer_validity | string | optional | Offer validity text |

`totals` object:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| subtotal | number | yes | Subtotal amount |
| shipping | number | yes | Shipping amount |
| insurance | number | yes | Insurance amount |
| discount | number | yes | Discount (use 0 if none) |
| tax | number | yes | Tax/VAT amount |
| grand_total | number | yes | Grand total |

`bank` object:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| beneficiary | string | optional | Beneficiary name |
| name | string | optional | Bank name |
| account_no | string | optional | Account number |
| swift | string | optional | SWIFT code |
| address | string | optional | Bank address |
| iban | string | optional | Shows only if provided |
| notes | string | optional | Shows only if provided |

## Default handling and missing data

- Missing string fields render as empty text.
- Optional blocks are hidden when the value is empty (for example `tax_id`,
  `bank.iban`, `bank.notes`, `notes`).
- Numeric fields used in formatting or calculations must be numbers. If a numeric
  field is missing or not a number, rendering can fail with HTTP 500. Use `0`
  as a safe default for numeric fields.
- If `items` is empty, the table shows no line items; totals still render.
- If `invoice.number` is missing, the filename falls back to the template name.

If you need different defaults, update the template with Jinja2 `default` filters
or pre-fill missing values in the JSON payload.

## Temporary file storage (scheme A)

The `/render/link` endpoint writes PDFs to the local storage directory and
returns a download URL. Files are automatically removed after the TTL.

Environment variables:

| Name | Default | Description |
| --- | --- | --- |
| PDF_STORAGE_DIR | `/app/storage` | Directory to store PDFs |
| PDF_TTL_SECONDS | `3600` | Time-to-live in seconds; `0` disables cleanup |
| PUBLIC_BASE_URL | empty | If set, download URLs use this base |

Manual cleanup (optional):
```bash
rm -f /opt/myapp/storage/*.pdf
```

## Local run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app:app --host 0.0.0.0 --port 8080
```

## CLI

```bash
python render.py --data data/proforma_invoice.json --template proforma_invoice.html --out-dir output
```
