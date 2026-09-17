# Генератор PDF-чеков

Скрипт `main.py` читает CSV/JSON из `data`, HTML-шаблоны из `templates`,
подставляет выбранный счет и сохраняет PDF в `output`.

## Установка и запуск

```bash
python -m pip install -r requirements.txt
python main.py
```

На Windows WeasyPrint также требует GTK3 runtime (Pango и другие системные
библиотеки); установите его по инструкции из
[документации WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html).

В HTML-шаблоне используйте плейсхолдеры вида `{{ invoice_id }}` или
`{{ customer.name }}`. Для кириллицы скрипт использует установленный
DejaVu Sans/Roboto, а затем резервный системный шрифт.
