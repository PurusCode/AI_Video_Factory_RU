from __future__ import annotations

"""Broad YouTube candidate discovery.

The report keeps API-returned values raw. It does not calculate view velocity,
trend scores, channel-relative ratios, sentiment, or inferred video tags.
Search-stream labels are user-configured query scopes, not automatic video
categorization. Additional derived metrics require YouTube's separate approval.
"""

import datetime as dt
import logging
import re
from pathlib import Path
from typing import Any

import requests

from .common import read_json, write_json
from .config import Settings

log = logging.getLogger(__name__)
API = "https://www.googleapis.com/youtube/v3"

# The labels describe configured search requests only. They are not model-
# generated labels assigned to videos. Query terms are deliberately broad.
TOPIC_STREAMS: tuple[dict[str, str], ...] = (
    {"id": "news", "title": "Новости и события", "query_ru": "новости|события|что произошло|обзор событий", "query_global": "news|current events|what happened|explained"},
    {"id": "technology_science", "title": "Технологии и наука", "query_ru": "технологии|наука|космос|изобретения|исследования", "query_global": "technology|science|space|inventions|research"},
    {"id": "business_economy", "title": "Экономика, бизнес и финансы", "query_ru": "экономика|бизнес|финансы|рынки|предпринимательство", "query_global": "economy|business|finance|markets|entrepreneurship"},
    {"id": "sports", "title": "Спорт", "query_ru": "спорт|футбол|баскетбол|теннис|единоборства", "query_global": "sports|football|basketball|tennis|UFC"},
    {"id": "gaming", "title": "Игры и гейминг", "query_ru": "игры|видеоигры|гейминг|игровые новинки|прохождение", "query_global": "gaming|video games|new games|gameplay|game review"},
    {"id": "entertainment", "title": "Кино, музыка и развлечения", "query_ru": "кино|сериалы|музыка|шоу|развлечения", "query_global": "movies|TV series|music|entertainment|show"},
    {"id": "autos_transport", "title": "Автомобили и транспорт", "query_ru": "автомобили|авто|транспорт|тест-драйв|новые модели", "query_global": "cars|automotive|transport|car review|new models"},
    {"id": "travel_food_lifestyle", "title": "Путешествия, еда и образ жизни", "query_ru": "путешествия|туризм|еда|кулинария|образ жизни", "query_global": "travel|tourism|food|cooking|lifestyle"},
    {"id": "education_history", "title": "Образование и история", "query_ru": "история|образование|документальный фильм|объяснение|научпоп", "query_global": "history|education|documentary|explained|learning"},
    {"id": "diy_home", "title": "Дом, ремонт и DIY", "query_ru": "ремонт|сделай сам|строительство|дом|мастерская", "query_global": "DIY|home improvement|construction|house|workshop"},
)

WINDOWS_DAYS = (1, 7)
DEFAULT_MAX_RESULTS = 25
DEFAULT_MAX_PAGES = 2
DEFAULT_SEARCH_CALL_BUDGET = 90  # leave room under the default 100 calls/day
CHART_REGIONS = ("RU", "US")


def _get(path: str, params: dict[str, Any], api_key: str) -> dict[str, Any]:
    response = requests.get(
        f"{API}/{path}", params={**params, "key": api_key}, timeout=35
    )
    if response.status_code >= 400:
        # Do not include request URL: it contains the API key.
        raise RuntimeError(
            f"YouTube API {response.status_code} for {path}: {response.text[:700]}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"YouTube API returned an unexpected response for {path}.")
    return payload


def _rfc3339(value: dt.datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _iso_duration_seconds(value: str | None) -> int | None:
    """Parse ISO-8601 duration only for display/filtering; retain original duration too."""
    if not value:
        return None
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return None
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _video_record_from_detail(detail: dict[str, Any]) -> dict[str, Any] | None:
    video_id = detail.get("id")
    if not video_id:
        return None
    snippet = detail.get("snippet", {}) or {}
    statistics = detail.get("statistics", {}) or {}
    content = detail.get("contentDetails", {}) or {}
    duration = content.get("duration")
    return {
        "video_id": str(video_id),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": snippet.get("title", ""),
        "channel_id": snippet.get("channelId", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "view_count": int(statistics["viewCount"]) if "viewCount" in statistics else None,
        "like_count": int(statistics["likeCount"]) if "likeCount" in statistics else None,
        "comment_count": int(statistics["commentCount"]) if "commentCount" in statistics else None,
        "duration": duration,
        "duration_seconds": _iso_duration_seconds(duration),
        "category_id": snippet.get("categoryId"),
    }


def _search_record(search_item: dict[str, Any]) -> dict[str, Any] | None:
    resource_id = search_item.get("id", {})
    video_id = resource_id.get("videoId") if isinstance(resource_id, dict) else None
    if not video_id:
        return None
    snippet = search_item.get("snippet", {}) or {}
    return {
        "video_id": str(video_id),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": snippet.get("title", ""),
        "channel_id": snippet.get("channelId", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "view_count": None,
        "like_count": None,
        "comment_count": None,
        "duration": None,
        "duration_seconds": None,
        "category_id": None,
    }


def _fetch_video_details(video_ids: list[str], api_key: str) -> tuple[dict[str, dict[str, Any]], int]:
    details: dict[str, dict[str, Any]] = {}
    calls = 0
    # videos.list accepts up to 50 IDs in one request.
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start:start + 50]
        if not batch:
            continue
        response = _get(
            "videos",
            {"part": "snippet,statistics,contentDetails", "id": ",".join(batch)},
            api_key,
        )
        calls += 1
        for item in response.get("items", []):
            if isinstance(item, dict) and item.get("id"):
                details[str(item["id"])] = item
    return details, calls


def _load_popular_charts(api_key: str) -> tuple[dict[str, Any], int]:
    """Fetch YouTube's own mostPopular chart for two explicit regions.

    The chart is a supplemental signal only. Official docs describe it as including
    trending music, movies and gaming videos; it is not an all-topic global chart.
    """
    charts: dict[str, Any] = {}
    calls = 0
    for region in CHART_REGIONS:
        payload = _get(
            "videos",
            {"part": "snippet,statistics,contentDetails", "chart": "mostPopular",
             "regionCode": region, "maxResults": 50},
            api_key,
        )
        calls += 1
        videos = []
        for item in payload.get("items", []):
            if isinstance(item, dict):
                record = _video_record_from_detail(item)
                if record:
                    videos.append(record)
        charts[region] = {"region_code": region, "videos": videos}
    return charts, calls


def _merge_candidates(
    sets: list[dict[str, Any]],
    charts: dict[str, Any],
    details: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for result_set in sets:
        for record in result_set["videos"]:
            video_id = record["video_id"]
            if video_id not in candidates:
                candidates[video_id] = dict(record)
                candidates[video_id]["found_in"] = []
            candidates[video_id]["found_in"].append({
                "market": result_set["market"],
                "stream_id": result_set["stream_id"],
                "stream_title": result_set["stream_title"],
                "window_days": result_set["window_days"],
                "order": result_set["order"],
            })
    for chart_region, chart in charts.items():
        for record in chart["videos"]:
            video_id = record["video_id"]
            if video_id not in candidates:
                candidates[video_id] = dict(record)
                candidates[video_id]["found_in"] = []
            candidates[video_id]["found_in"].append({
                "market": f"mostPopular:{chart_region}",
                "stream_id": "youtube_most_popular_chart",
                "stream_title": "YouTube mostPopular chart",
                "window_days": None,
                "order": "youtube_algorithm",
            })
    # Fill each unique candidate from the batched details lookup, retaining the
    # search snippet if a video has disappeared or is no longer accessible.
    for video_id, item in candidates.items():
        detail = details.get(video_id)
        if detail:
            refreshed = _video_record_from_detail(detail)
            if refreshed:
                refreshed["found_in"] = item["found_in"]
                candidates[video_id] = refreshed
    return candidates


def _fmt(value: int | None) -> str:
    return "н/д" if value is None else f"{value:,}".replace(",", " ")


def _make_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Ежедневный обзор популярных видео — YouTube",
        "",
        f"- Сформировано (UTC): `{report['generated_at_utc']}`",
        f"- Источник: {report['source']}",
        f"- Уникальных видео в объединённом списке: **{report['candidate_count']}**",
        f"- Поисковых запросов: **{report['quota_usage']['search_list_calls']}**",
        "",
        "> Поисковые направления ниже — заранее настроенные запросы, а не автоматическая классификация видео.",
        "> Сортировка `viewCount` и счётчики взяты из YouTube API. Они не показывают скорость прироста просмотров.",
        "> Это выборка по запросам, а не полный рейтинг всех видео YouTube.",
        "",
    ]

    for result_set in report["search_sets"]:
        region_name = "Россия" if result_set["market"] == "ru" else "Зарубежная выдача (без ограничения региона; приоритет английского языка)"
        lines += [
            f"## {region_name} · {result_set['stream_title']} · публикации за {result_set['window_days']} дн.",
            "",
            f"Поисковый запрос: `{result_set['query']}` · Страниц: {result_set['pages_fetched']} · Видео в этой выборке: {len(result_set['videos'])}",
            "",
            "| Просмотры | Лайки | Комментарии | Дата публикации | Длительность | Канал | Видео |",
            "|---:|---:|---:|---|---|---|---|",
        ]
        shown = result_set["videos"][:10]
        for video in shown:
            title = str(video.get("title", "")).replace("|", "\\|").replace("\n", " ")
            channel = str(video.get("channel_title", "")).replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {_fmt(video.get('view_count'))} | {_fmt(video.get('like_count'))} "
                f"| {_fmt(video.get('comment_count'))} | {video.get('published_at', '')} "
                f"| {video.get('duration') or 'н/д'} | {channel} | [{title}]({video.get('url', '')}) |"
            )
        if not shown:
            lines.append("| — | — | — | — | — | — | Нет результатов |")
        if len(result_set["videos"]) > 10:
            lines.append(f"\nВ JSON-файле сохранены все {len(result_set['videos'])} результатов этого поискового набора; здесь показаны первые 10.")
        if result_set["has_more_pages"]:
            lines.append("\nУ API оставались следующие страницы; достигнут настроенный лимит страниц.")
        lines.append("")

    lines += ["## Отдельный чарт YouTube mostPopular", "",
              "Это собственная подборка YouTube. По документации она охватывает прежде всего музыкальные, кино- и игровые видео, поэтому не заменяет тематический поиск.", ""]
    for region, chart in report["most_popular_charts"].items():
        lines += [f"### Регион {region}", "", "| Просмотры | Дата публикации | Длительность | Канал | Видео |", "|---:|---|---|---|---|"]
        for video in chart["videos"][:25]:
            title = str(video.get("title", "")).replace("|", "\\|").replace("\n", " ")
            channel = str(video.get("channel_title", "")).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {_fmt(video.get('view_count'))} | {video.get('published_at', '')} | {video.get('duration') or 'н/д'} | {channel} | [{title}]({video.get('url', '')}) |")
        lines.append("")

    lines += [
        "## Как читать отчёт и ограничения",
        "",
        "- Российская выдача: `regionCode=RU`, языковой приоритет `ru`.",
        "- Зарубежная выдача: `relevanceLanguage=en`, без `regionCode`; это международный поиск с приоритетом английского, а не выборка всех стран или только США.",
        "- Периоды: последние 24 часа и 7 дней; поиск сортируется YouTube API по общему числу просмотров (`viewCount`).",
        "- YouTube предупреждает, что `viewCount` вместе с фильтром даты может возвращать неполную выборку. Пагинация обрабатывает до заданного лимита страниц, но не делает поиск исчерпывающим.",
        "- Повторения по направлениям и периодам объединяются по `video_id` в `unique_candidates`; в `found_in` сохраняется происхождение результата.",
        "- Скорость роста, трендовые баллы, отношения просмотров/лайков, автоматические тематические теги и анализ комментариев не рассчитываются.",
        "- В отчёт включены сырые счётчики и названия из API. Их требуется обновить или удалить в течение 30 календарных дней.",
        "- Квота `search.list` ограничена отдельным ежедневным лимитом; в этой конфигурации заложено не более 90 поисковых вызовов, чтобы оставить небольшой резерв.",
        "",
    ]
    return "\n".join(lines)


def purge_expired_discovery_output(out_dir: Path, *, now: dt.datetime | None = None) -> bool:
    """Delete this module's raw API report after its 30-day refresh deadline."""
    json_path = out_dir / "discovery.json"
    if not json_path.is_file():
        return False
    try:
        report = read_json(json_path)
        deadline = report.get("refresh_or_delete_by_utc")
        if not deadline:
            return False
        deadline_dt = dt.datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
        current = now or dt.datetime.now(dt.timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        expired = current.astimezone(dt.timezone.utc) >= deadline_dt.astimezone(dt.timezone.utc)
    except (OSError, ValueError, TypeError):
        return False
    if not expired:
        return False
    json_path.unlink(missing_ok=True)
    (out_dir / "discovery.md").unlink(missing_ok=True)
    # Stage 3 reports contain copied YouTube API fields and share the same deadline.
    (out_dir / "topics.json").unlink(missing_ok=True)
    (out_dir / "topics.md").unlink(missing_ok=True)
    # Stage 4 page embeds raw YouTube API fields; editor export contains video IDs.
    (out_dir / "editor.html").unlink(missing_ok=True)
    (out_dir / "editorial.json").unlink(missing_ok=True)
    return True


def discover_youtube(
    settings: Settings,
    out_dir: Path,
    *,
    query: str | None = None,
    region: str = "RU",
    language: str = "ru",
    max_results: int = DEFAULT_MAX_RESULTS,
    max_pages: int = DEFAULT_MAX_PAGES,
    search_call_budget: int = DEFAULT_SEARCH_CALL_BUDGET,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Search broad configured directions, RU and international, 1d and 7d.

    Default workload: 10 streams × 2 markets × 2 windows = 40 first-page calls;
    up to 2 pages per stream/window = 80 search.list calls maximum. A custom
    --query narrows a run to one free-form query per market and time window.
    """
    if not settings.youtube_api_key:
        raise RuntimeError("Не задан YOUTUBE_API_KEY. Поиск использует официальный YouTube Data API v3.")
    if not 1 <= int(max_results) <= 50:
        raise ValueError("max_results должен быть в диапазоне от 1 до 50")
    if not 1 <= int(max_pages) <= 3:
        raise ValueError("max_pages должен быть в диапазоне от 1 до 3")
    if not 1 <= int(search_call_budget) <= 100:
        raise ValueError("search_call_budget должен быть в диапазоне от 1 до 100")
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    generated_at = _rfc3339(now)
    expires_at = _rfc3339(now + dt.timedelta(days=30))

    streams = ([{"id": "custom", "title": "Пользовательский запрос", "query_ru": query.strip(), "query_global": query.strip()}]
               if query and query.strip() else list(TOPIC_STREAMS))
    if query is not None and not str(query).strip():
        raise ValueError("Пользовательский поисковый запрос не должен быть пустым")

    markets = [
        {"id": "ru", "region_code": region.upper().strip(), "language": language.strip(), "query_key": "query_ru"},
        {"id": "global", "region_code": None, "language": "en", "query_key": "query_global"},
    ]

    search_calls = 0
    search_sets: list[dict[str, Any]] = []
    all_search_records: dict[str, dict[str, Any]] = {}
    budget_exhausted = False

    for days in WINDOWS_DAYS:
        published_after = _rfc3339(now - dt.timedelta(days=days))
        for market in markets:
            for stream in streams:
                q = stream[market["query_key"]]
                result_set: dict[str, Any] = {
                    "market": market["id"], "region_code": market["region_code"],
                    "language_priority": market["language"],
                    "stream_id": stream["id"], "stream_title": stream["title"],
                    "query": q, "window_days": days, "order": "viewCount",
                    "published_after": published_after, "api_total_results": None,
                    "pages_fetched": 0, "has_more_pages": False, "videos": [],
                }
                page_token = None
                seen_ids: set[str] = set()
                for page_number in range(1, max_pages + 1):
                    if search_calls >= search_call_budget:
                        result_set["has_more_pages"] = bool(page_token) or page_number == 1
                        budget_exhausted = True
                        break
                    params: dict[str, Any] = {
                        "part": "snippet", "type": "video", "q": q,
                        "maxResults": int(max_results), "order": "viewCount",
                        "publishedAfter": published_after,
                        "relevanceLanguage": market["language"],
                        "safeSearch": "moderate",
                    }
                    if market["region_code"]:
                        params["regionCode"] = market["region_code"]
                    if page_token:
                        params["pageToken"] = page_token
                    response = _get("search", params, settings.youtube_api_key)
                    search_calls += 1
                    result_set["pages_fetched"] += 1
                    if result_set["api_total_results"] is None:
                        result_set["api_total_results"] = (response.get("pageInfo") or {}).get("totalResults")
                    for item in response.get("items", []):
                        if not isinstance(item, dict):
                            continue
                        record = _search_record(item)
                        if not record:
                            continue
                        video_id = record["video_id"]
                        if video_id in seen_ids:
                            continue
                        seen_ids.add(video_id)
                        result_set["videos"].append(record)
                        all_search_records.setdefault(video_id, record)
                    page_token = response.get("nextPageToken")
                    if not page_token:
                        break
                result_set["has_more_pages"] = bool(page_token)
                search_sets.append(result_set)
                if budget_exhausted:
                    break
            if budget_exhausted:
                break
        if budget_exhausted:
            break

    # One batched details lookup for the unique set avoids a videos.list call for
    # every search page. The API accepts up to 50 IDs per call.
    details, detail_calls = _fetch_video_details(list(all_search_records), settings.youtube_api_key)
    for result_set in search_sets:
        for index, record in enumerate(result_set["videos"]):
            detail = details.get(record["video_id"])
            if detail:
                rich = _video_record_from_detail(detail)
                if rich:
                    result_set["videos"][index] = rich

    charts, chart_calls = _load_popular_charts(settings.youtube_api_key)
    # Add chart IDs to the detail lookup (chart records already contain full stats).
    unique_candidates = _merge_candidates(search_sets, charts, details)

    report: dict[str, Any] = {
        "schema_version": "2.0",
        "source": "YouTube Data API v3",
        "generated_at_utc": generated_at,
        "refresh_or_delete_by_utc": expires_at,
        "search_design": {
            "markets": [
                {"id": "ru", "region_code": region.upper().strip(), "relevance_language": language.strip()},
                {"id": "global", "region_code": None, "relevance_language": "en"},
            ],
            "topic_streams": streams,
            "window_days": list(WINDOWS_DAYS),
            "order": "viewCount",
            "max_results_per_page": int(max_results),
            "max_pages_per_search": int(max_pages),
            "search_call_budget": int(search_call_budget),
        },
        "search_sets": search_sets,
        "most_popular_charts": charts,
        "unique_candidates": list(unique_candidates.values()),
        "candidate_count": len(unique_candidates),
        "search_budget_exhausted": budget_exhausted,
        "quota_usage": {
            "search_list_calls": search_calls,
            "search_list_quota_units": search_calls,
            "videos_list_calls": detail_calls + chart_calls,
            "videos_list_detail_calls": detail_calls,
            "videos_list_chart_calls": chart_calls,
            "videos_list_quota_units": detail_calls + chart_calls,
            "note": "search.list uses its separate daily Search Queries bucket (default 100 calls/day); videos.list uses the standard Data API quota.",
        },
        "notes": [
            "Search-stream names identify preconfigured search requests; they are not automatically inferred video tags.",
            "All displayed counters are raw YouTube API fields; no view velocity or custom score is calculated.",
            "International search has no regionCode and uses English as relevanceLanguage priority, not as a language filter.",
            "The mostPopular chart is supplemental and not a full all-topic trending list.",
            "Non-Authorized Data must be refreshed or deleted within 30 calendar days.",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "discovery.json", report)
    (out_dir / "discovery.md").write_text(_make_markdown(report), encoding="utf-8")
    return report
