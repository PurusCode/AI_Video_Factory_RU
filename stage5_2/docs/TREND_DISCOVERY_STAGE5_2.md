# AI Video Factory RU — Stage 5.2: Editor and production-fit metadata

**Версия:** 1.0.1 / 03.11.2026  
**Зависимости:** установленный Stage 4 и Stage 5.1 v1.0.1  
**Область:** автономная HTML-панель `discover-editor`; без внешних запросов.

## Реализовано

- Сохранены ручной отбор, заметки, язык, короткий/длинный формат, темы, пагинация и импорт/экспорт Stage 4.
- В `found_in` панели перенесены `order` и фактический `query` из Stage 5.1; старые отчёты без этих полей отображаются как `unknown`.
- Добавлены ручные поля `reference_format`, `production_profile`, `production_fit`, `blockers`, `asset_strategy`, `rights_status`, `fact_check_status`, `budget_status`.
- Добавлены ручные флаги требований: ведущий в кадре, человеческий голос, съёмка на месте, физический эксперимент, гость.
- Добавлены фильтры по `order`, `production_profile` и `production_fit`.
- Исправлен множественный выбор `blockers` и `asset_strategy`: вместо HTML `<select multiple>` используются отдельные флажки, чтобы варианты можно было отмечать обычным щелчком без Ctrl. Значения сохраняются в массивы `blockers` и `asset_strategy` и остаются совместимыми с schema 1.1.
- Справочник профилей читается из `config/production_profiles.json`, установленного Stage 5.1. Модель не присваивает метки по заголовкам и не классифицирует YouTube Data.
- Экспорт обновлён до editorial schema `1.1`; импорт поддерживает старую schema `1.0` и новую `1.1`, проверяет допустимые enum-значения и сохраняет старые поля и темы.
- Правило целостности: нельзя отметить `suitable_now`, если вручную указано, что нужны ведущий/человеческий голос/съёмка/эксперимент/гость — как отдельным флагом, так и соответствующим blocker. Никакие другие fit-метки автоматически не назначаются.
- HTML работает офлайн; данные API не отправляются в сеть. Сохраняется срок обновления/удаления исходного YouTube API Data.

## Установка

Из распакованного комплекта запустить PowerShell от имени текущего пользователя:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_stage5_2.ps1 -ProjectRoot "D:\my_projects\AI_Video_Factory_RU\video-farm"
```

Перед обновлением экспортируйте текущий отбор кнопкой «Экспортировать отбор JSON», чтобы сохранить сделанные вручную отметки. Установщик требует `.venv\Scripts\python.exe`, установленный Stage 4 (`src/video_farm/discovery_editor.py` и команда CLI `discover-editor`) и Stage 5.1 (`config/production_profiles.json`). Он создаёт резервную копию, переносит только модуль редактора/тест/документацию, запускает тесты; при ошибке выполняет откат. Вложенный каталог `stage5_2/config` содержит копию справочника только для тестов; установленный файл Stage 5.1 не перезаписывается. `.env`, отчёты Discovery, экспорт пользователя и ключи API не изменяются.

## Проверка

```powershell
.\.venv\Scripts\python.exe -m video_farm.cli discover-editor --help
.\.venv\Scripts\python.exe -m video_farm.cli discover-editor
.\.venv\Scripts\python.exe -m pytest -q tests/test_discovery_editor.py tests/test_discovery.py tests/test_discovery_quota.py tests/test_discovery_analysis.py
```

После установки заново выполните `discover-editor`, чтобы пересоздать `output\discovery\editor.html` с новыми флажками. Затем импортируйте ранее сохранённый `editorial.json` для того же исходного отчёта. В полях «Блокеры» и «Стратегия материалов» теперь ставятся отдельные флажки обычным щелчком мыши; удерживать Ctrl не нужно. После генерации редактора проверьте: фильтры `viewCount` / `date`, ручное заполнение профиля и пригодности, экспорт `editorial.json`, повторный импорт этого файла, импорт старого Stage 4 export schema 1.0 и сохранение старых тем/заметок.

Контейнерная проверка исправления 03.11.2026: полный интеграционный набор Stage 3–5.2 — 34 теста успешно; JavaScript реально сгенерированной HTML-страницы прошёл `node --check`. Это подтверждает регрессионную совместимость на собранной тестовой копии проекта, но не заменяет установку и визуальную приёмку на целевой Windows-машине.

## Ограничения

- `production_fit` остаётся человеческим редакторским решением; это не prediction/ML score.
- `reference_format` характеризует найденный ролик, а `production_profile` — наш самостоятельный способ раскрыть тему.
- Статус профиля описывает готовность технологии в проекте, а не разрешение использовать конкретный материал.
- Установка Stage 5.2 не означает, что Stage 5.1 прошёл Windows acceptance или что весь MVP готов к публикации.
- Не включены: auto classifier, video generation, Blender, screen capture, автоматическая публикация и изменение production LLM/TTS.
