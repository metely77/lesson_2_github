"""Interactive generator of invoice PDFs from CSV/JSON data and HTML templates."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
INVOICE_ID_KEYS = ("invoice_id", "invoiceid", "invoice id")
PLACEHOLDER_RE = re.compile(r"{{\s*([\w.-]+)\s*}}|{([\w.-]+)}")


def normalize_key_name(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def read_data_file(path: Path) -> list[dict[str, Any]]:
    """Read one supported data file and return a list of invoice records."""
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return [dict(row) for row in csv.DictReader(file)]

    with path.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)
    return normalize_json_records(payload)


def normalize_json_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("JSON-массив должен содержать объекты.")
        return [dict(item) for item in payload]
    if not isinstance(payload, dict):
        raise ValueError("JSON должен содержать объект или массив объектов.")

    for key in ("invoices", "data", "records"):
        if isinstance(payload.get(key), list):
            return normalize_json_records(payload[key])

    # Also accept {"INV-001": {...}, "INV-002": {...}}.
    if payload and all(isinstance(value, dict) for value in payload.values()):
        records = []
        for invoice_id, value in payload.items():
            record = dict(value)
            if find_invoice_id(record) is None:
                record["invoice_id"] = invoice_id
            records.append(record)
        return records
    return [dict(payload)]


def find_invoice_id(record: dict[str, Any]) -> Any:
    explicit_values = []
    fallback_values = []

    for key, value in record.items():
        normalized = normalize_key_name(key)
        if normalized in INVOICE_ID_KEYS and value is not None and str(value).strip():
            explicit_values.append(value)
        elif normalized == "id" and value is not None and str(value).strip():
            fallback_values.append(value)

    if explicit_values:
        return explicit_values[0]
    if fallback_values:
        return fallback_values[0]
    return None


def list_supported_files(folder: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not folder.exists():
        return []
    results: list[Path] = []
    for path in folder.iterdir():
        if path.is_file() and path.suffix.lower() in suffixes:
            results.append(path)
    return sorted(results, key=lambda item: item.name.lower())


def select_option(options: list[Path], prompt: str) -> Path:
    if not options:
        raise ValueError(f"Не найдено ни одного варианта для выбора: {prompt}.")
    while True:
        answer = input(f"{prompt} [1-{len(options)}]: ").strip()
        try:
            index = int(answer) - 1
            return options[index]
        except (ValueError, IndexError):
            print("Введите номер существующего варианта.")


def select_invoice(records: list[dict[str, Any]]) -> dict[str, Any]:
    invoices = [(find_invoice_id(record), record) for record in records]
    invoices = [(invoice_id, record) for invoice_id, record in invoices if invoice_id is not None]
    if not invoices:
        raise ValueError("В выбранном файле нет поля invoice_id.")

    print("\nДоступные чеки:")
    for number, (invoice_id, _) in enumerate(invoices, 1):
        print(f"  {number}. {invoice_id}")
    while True:
        answer = input(f"Выберите чек [1-{len(invoices)}]: ").strip()
        try:
            return invoices[int(answer) - 1][1]
        except (ValueError, IndexError):
            print("Введите номер существующего чека.")


def render_template(template: str, record: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1) or match.group(2)
        value: Any = record
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return ""
            value = value[part]
        return html.escape(str(value if value is not None else ""))

    return PLACEHOLDER_RE.sub(replace, template)


def font_css() -> str:
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "DejaVuSans.ttf",
        Path("/Library/Fonts/DejaVu Sans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for font_path in candidates:
        if font_path.is_file():
            uri = font_path.as_uri()
            return f"@font-face {{ font-family: InvoiceDejaVu; src: url('{uri}'); }}\n"
    return ""


def generate_pdf(template_path: Path, record: dict[str, Any], output_dir: Path) -> Path:
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise RuntimeError(
            "WeasyPrint не загрузился. Установите зависимости из requirements.txt; "
            "в Windows также нужен GTK3 Runtime."
        ) from error

    template = template_path.read_text(encoding="utf-8-sig")
    document = render_template(template, record)
    document = (
        f"<style>{font_css()}body {{ font-family: InvoiceDejaVu, 'DejaVu Sans', "
        f"Roboto, sans-serif; }}</style>{document}"
    )
    invoice_id = str(find_invoice_id(record)).strip()
    safe_invoice_id = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", invoice_id) or "invoice"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"invoice_{safe_invoice_id}.pdf"
    HTML(string=document, base_url=str(template_path.parent)).write_pdf(str(output_path))
    return output_path


def open_file(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=True)
    else:
        subprocess.run(["xdg-open", str(path)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Генерация PDF-чека из CSV/JSON и HTML.")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_DIR / "data")
    parser.add_argument("--templates-dir", type=Path, default=PROJECT_DIR / "templates")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "output")
    args = parser.parse_args()

    def list_supported_files(folder: Path, suffixes: tuple[str, ...]) -> list[Path]:
        results: list[Path] = []
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in suffixes:
                results.append(path)
        return sorted(results, key=lambda item: item.name.lower())

    data_files = list_supported_files(args.data_dir, (".csv", ".json"))
    templates = list_supported_files(args.templates_dir, (".html",))
    print("=== Генератор PDF-чеков ===\n")
    print("Файлы данных:")
    for number, path in enumerate(data_files, 1):
        print(f"  {number}. {path.name}")
    print("\nHTML-шаблоны:")
    for number, path in enumerate(templates, 1):
        print(f"  {number}. {path.name}")

    data_path = select_option(data_files, "Выберите файл данных")
    template_path = select_option(templates, "Выберите HTML-шаблон")
    records = read_data_file(data_path)
    record = select_invoice(records)
    output_path = generate_pdf(template_path, record, args.output_dir)
    print(f"\nPDF сохранен: {output_path}")
    open_file(output_path)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(1)
