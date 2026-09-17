"""Interactive invoice PDF generator."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
PLACEHOLDER_RE = re.compile(r"{{\s*([\w.-]+)\s*}}")
INVOICE_KEYS = ("invoice_id", "invoice id", "invoice", "id")


def list_files(directory: Path, suffixes: tuple[str, ...]) -> list[Path]:
    """Return matching files in a directory in a stable order."""
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in suffixes),
        key=lambda path: path.name.lower(),
    )


def load_data(path: Path) -> list[dict[str, Any]]:
    """Load records from a CSV or JSON file."""
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return [dict(row) for row in csv.DictReader(file)]

    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8-sig") as file:
            payload = json.load(file)
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = payload.get("invoices", payload.get("data", [payload]))
        else:
            raise ValueError("JSON должен содержать объект или массив объектов.")
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise ValueError("JSON должен содержать список объектов счетов.")
        return [dict(item) for item in records]

    raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}")


def invoice_id(record: dict[str, Any]) -> str | None:
    """Find the invoice identifier using common field names."""
    for key in INVOICE_KEYS:
        if key in record and record[key] not in (None, ""):
            return str(record[key])
    return None


def choose_item(items: list[Path], title: str) -> Path:
    """Print a numbered menu and return the selected item."""
    print(f"\n{title}")
    for number, item in enumerate(items, start=1):
        print(f"  {number}. {item.name}")
    while True:
        try:
            selected = int(input("Введите номер варианта: ")) - 1
        except ValueError:
            print("Введите целое число.")
            continue
        if 0 <= selected < len(items):
            return items[selected]
        print(f"Выберите число от 1 до {len(items)}.")


def choose_invoice(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Print available invoices and return the selected record."""
    options = [(invoice_id(record), record) for record in records]
    options = [(identifier, record) for identifier, record in options if identifier is not None]
    if not options:
        raise ValueError("В выбранном файле не найдено поле invoice_id (или id).")

    print("\nДоступные чеки:")
    for number, (identifier, _) in enumerate(options, start=1):
        print(f"  {number}. {identifier}")
    while True:
        try:
            selected = int(input("Введите номер чека: ")) - 1
        except ValueError:
            print("Введите целое число.")
            continue
        if 0 <= selected < len(options):
            return options[selected][1]
        print(f"Выберите число от 1 до {len(options)}.")


def render_template(template: str, record: dict[str, Any]) -> str:
    """Replace {{ field }} placeholders with HTML-escaped record values."""
    from html import escape

    def replace(match: re.Match[str]) -> str:
        value: Any = record
        for part in match.group(1).split("."):
            if not isinstance(value, dict) or part not in value:
                return ""
            value = value[part]
        return escape("" if value is None else str(value))

    return PLACEHOLDER_RE.sub(replace, template)


def font_face_css() -> str:
    """Use a known installed DejaVu Sans/Roboto font when available."""
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "DejaVuSans.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "Roboto-Regular.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Roboto-Regular.ttf"),
        Path.home() / "Library/Fonts/Roboto-Regular.ttf",
    ]
    for font_path in candidates:
        if font_path.is_file():
            return f'@font-face {{ font-family: "InvoiceFont"; src: url("{font_path.as_uri()}"); }}'
    return ""


def generate_pdf(record: dict[str, Any], template_path: Path, output_dir: Path) -> Path:
    """Render one invoice to a PDF and return its path."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise RuntimeError(
            "WeasyPrint не удалось запустить. На Windows установите GTK3 runtime "
            "с официальной страницы WeasyPrint и повторите запуск."
        ) from error

    identifier = invoice_id(record)
    if identifier is None:
        raise ValueError("У выбранного чека отсутствует invoice id.")
    template = template_path.read_text(encoding="utf-8")
    html = render_template(template, record)
    css = f"{font_face_css()} body {{ font-family: InvoiceFont, 'DejaVu Sans', Roboto, sans-serif; }}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"invoice_{re.sub(r'[^A-Za-z0-9_.-]+', '_', identifier)}.pdf"
    HTML(string=f"<style>{css}</style>{html}", base_url=str(template_path.parent)).write_pdf(str(output_path))
    return output_path


def open_file(path: Path) -> None:
    """Open a file with the platform's default application."""
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=True)
    else:
        subprocess.run(["xdg-open", str(path)], check=True)


def main() -> None:
    data_files = list_files(DATA_DIR, (".csv", ".json"))
    template_files = list_files(TEMPLATES_DIR, (".html", ".htm"))
    print("Генератор PDF-чеков")
    print(f"\nДоступные файлы данных ({DATA_DIR}):")
    if not data_files:
        print("  Файлы CSV или JSON не найдены.")
        return
    for number, path in enumerate(data_files, start=1):
        print(f"  {number}. {path.name}")
    print(f"\nДоступные HTML-шаблоны ({TEMPLATES_DIR}):")
    if not template_files:
        print("  HTML-шаблоны не найдены.")
        return
    for number, path in enumerate(template_files, start=1):
        print(f"  {number}. {path.name}")

    try:
        data_path = choose_item(data_files, "Выберите файл данных:")
        template_path = choose_item(template_files, "Выберите HTML-шаблон:")
        records = load_data(data_path)
        record = choose_invoice(records)
        output_path = generate_pdf(record, template_path, OUTPUT_DIR)
        print(f"\nPDF успешно сохранен: {output_path}")
        open_file(output_path)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"\nОшибка: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
