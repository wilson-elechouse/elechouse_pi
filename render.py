from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict

from renderer import html_to_pdf_bytes, render_html


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render HTML + PDF from JSON data.")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/proforma_invoice.json"),
        help="Path to JSON data file.",
    )
    parser.add_argument(
        "--template",
        type=str,
        default="proforma_invoice.html",
        help="Template filename from templates/.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output"),
        help="Directory for rendered files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_json(args.data)
    html = render_html(args.template, data)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.template).stem
    html_path = args.out_dir / f"{stem}.html"
    pdf_path = args.out_dir / f"{stem}.pdf"

    html_path.write_text(html, encoding="utf-8")
    pdf_bytes = asyncio.run(html_to_pdf_bytes(html))
    pdf_path.write_bytes(pdf_bytes)

    print(f"HTML: {html_path}")
    print(f"PDF: {pdf_path}")


if __name__ == "__main__":
    main()
