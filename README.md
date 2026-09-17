# Генератор PDF-чеков

Скрипт читает CSV и JSON из `data`, HTML-шаблоны из `templates`, подставляет
данные выбранного `invoice_id` и создает PDF в `output`. После создания PDF
автоматически открывается системной программой Windows или macOS.

## Запуск

```bash
python -m pip install -r requirements.txt
python main.py
```

На Windows WeasyPrint также требует установленный GTK3 Runtime (это
системная зависимость самого WeasyPrint). На macOS достаточно установить
пакет через `pip`.

Можно указать другие каталоги:

```bash
python main.py --data-dir /path/to/data --templates-dir /path/to/templates --output-dir /path/to/output
```

В HTML используйте плейсхолдеры `{{ invoice_id }}`, `{{ customer.name }}` и
другие имена полей из записи. Для кириллицы скрипт использует DejaVu Sans
(если шрифт установлен в системе) с резервным Roboto/sans-serif.