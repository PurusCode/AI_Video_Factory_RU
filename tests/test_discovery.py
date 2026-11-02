import datetime as dt
import json
from pathlib import Path

import pytest

from video_farm.config import Settings
from video_farm.discovery import (
    TOPIC_STREAMS, discover_youtube, purge_expired_discovery_output,
)


def _settings(api_key="test-key"):
    return Settings(
        root=Path('.'), data_dir=Path('data'), output_dir=Path('output'),
        cache_dir=Path('cache'), broll_dir=Path('broll'), images_dir=Path('images'),
        audio_dir=Path('audio'), ffmpeg='ffmpeg', ffprobe='ffprobe',
        width=1920, height=1080, fps=25, bitrate='4500k', gop=50,
        youtube_api_key=api_key, pexels_api_key='', pixabay_api_key='',
        tts_engine='piper', tts_language='ru', tts_speaker='ru_RU-dmitri-medium',
        tts_speed=0.9, providers=[],
    )


def test_default_search_is_multitopic_bilingual_and_paginated(tmp_path, monkeypatch):
    calls = []
    search_number = 0

    def fake_get(path, params, api_key):
        nonlocal search_number
        calls.append((path, dict(params), api_key))
        if path == 'search':
            search_number += 1
            page = params.get('pageToken')
            # Each first page advertises one further page; second page ends.
            token = None if page else f"next-{search_number}"
            video_id = f"v-{search_number}-{1 if not page else 2}"
            return {
                'pageInfo': {'totalResults': 2},
                'nextPageToken': token,
                'items': [{
                    'id': {'kind': 'youtube#video', 'videoId': video_id},
                    'snippet': {
                        'title': f'Title {video_id}', 'channelId': 'channel-1',
                        'channelTitle': 'Channel', 'publishedAt': '2026-11-02T08:00:00Z',
                    },
                }],
            }
        if params.get('chart') == 'mostPopular':
            return {'items': [{
                'id': f"popular-{params['regionCode']}",
                'snippet': {'title': 'Popular chart item', 'channelId': 'c',
                            'channelTitle': 'Popular channel',
                            'publishedAt': '2026-11-02T07:00:00Z', 'categoryId': '20'},
                'statistics': {'viewCount': '5000'},
                'contentDetails': {'duration': 'PT8M'},
            }]}
        items = []
        for video_id in params['id'].split(','):
            items.append({
                'id': video_id,
                'snippet': {'title': f'Title {video_id}', 'channelId': 'c',
                            'channelTitle': 'Channel',
                            'publishedAt': '2026-11-02T08:00:00Z', 'categoryId': '28'},
                'statistics': {'viewCount': '12345', 'likeCount': '321', 'commentCount': '20'},
                'contentDetails': {'duration': 'PT5M20S'},
            })
        return {'items': items}

    monkeypatch.setattr('video_farm.discovery._get', fake_get)
    fixed_now = dt.datetime(2026, 11, 2, 12, 0, tzinfo=dt.timezone.utc)
    report = discover_youtube(_settings(), tmp_path, now=fixed_now)

    # 10 streams × 2 markets × 2 windows × 2 pages = 80 search.list calls.
    assert len(TOPIC_STREAMS) == 10
    assert report['quota_usage']['search_list_calls'] == 80
    assert len([call for call in calls if call[0] == 'search']) == 80
    assert len(report['search_sets']) == 40
    assert all(item['pages_fetched'] == 2 for item in report['search_sets'])
    assert all(item['window_days'] in (1, 7) for item in report['search_sets'])

    ru = next(call[1] for call in calls if call[0] == 'search' and call[1].get('regionCode') == 'RU')
    global_search = next(call[1] for call in calls if call[0] == 'search' and 'regionCode' not in call[1])
    assert ru['relevanceLanguage'] == 'ru'
    assert global_search['relevanceLanguage'] == 'en'
    assert 'pageToken' not in ru
    assert 'pageToken' in next(call[1] for call in calls if call[0] == 'search' and call[1].get('pageToken'))

    # Raw stats have been filled by videos.list and duplicates are recorded once.
    candidate = report['unique_candidates'][0]
    assert candidate['view_count'] == 12345
    assert candidate['like_count'] == 321
    assert candidate['duration'] == 'PT5M20S'
    assert isinstance(candidate['found_in'], list)
    assert report['candidate_count'] == len(report['unique_candidates'])
    assert len(report['most_popular_charts']['RU']['videos']) == 1
    assert report['quota_usage']['videos_list_chart_calls'] == 2

    saved = json.loads((tmp_path / 'discovery.json').read_text(encoding='utf-8'))
    assert saved['schema_version'] == '2.0'
    assert saved['search_design']['topic_streams'][0]['id'] == 'news'
    assert (tmp_path / 'discovery.md').is_file()
    md = (tmp_path / 'discovery.md').read_text(encoding='utf-8')
    assert 'Новости и события' in md
    assert 'Зарубежная выдача' in md
    assert 'mostPopular' in md
    assert 'скорость прироста' in md.lower()


def test_custom_query_reduces_to_one_stream_and_checks_budget(tmp_path, monkeypatch):
    search_calls = []

    def fake_get(path, params, api_key):
        if path == 'search':
            search_calls.append(params)
            return {'items': [], 'pageInfo': {'totalResults': 0}}
        if params.get('chart') == 'mostPopular':
            return {'items': []}
        return {'items': []}

    monkeypatch.setattr('video_farm.discovery._get', fake_get)
    report = discover_youtube(
        _settings(), tmp_path, query='локальная нейросеть|local AI',
        max_pages=1, search_call_budget=4,
        now=dt.datetime(2026, 11, 2, 12, 0, tzinfo=dt.timezone.utc),
    )
    assert len(search_calls) == 4  # 1 stream × 2 markets × 2 windows
    assert report['search_budget_exhausted'] is False
    assert all('локальная нейросеть' in item['query'] for item in report['search_sets'])


def test_search_budget_marks_report_partial(tmp_path, monkeypatch):
    def fake_get(path, params, api_key):
        if path == 'search':
            return {'items': [], 'pageInfo': {'totalResults': 0}, 'nextPageToken': 'next'}
        if params.get('chart') == 'mostPopular':
            return {'items': []}
        return {'items': []}

    monkeypatch.setattr('video_farm.discovery._get', fake_get)
    report = discover_youtube(
        _settings(), tmp_path, max_pages=2, search_call_budget=3,
        now=dt.datetime(2026, 11, 2, 12, 0, tzinfo=dt.timezone.utc),
    )
    assert report['quota_usage']['search_list_calls'] == 3
    assert report['search_budget_exhausted'] is True


def test_discovery_validation(tmp_path):
    with pytest.raises(RuntimeError, match='YOUTUBE_API_KEY'):
        discover_youtube(_settings(api_key=''), tmp_path)
    with pytest.raises(ValueError, match='1 до 50'):
        discover_youtube(_settings(), tmp_path, max_results=51)
    with pytest.raises(ValueError, match='1 до 3'):
        discover_youtube(_settings(), tmp_path, max_pages=4)
    with pytest.raises(ValueError, match='1 до 100'):
        discover_youtube(_settings(), tmp_path, search_call_budget=101)
    with pytest.raises(ValueError, match='пустым'):
        discover_youtube(_settings(), tmp_path, query='  ')
    with pytest.raises(ValueError, match='timezone-aware'):
        discover_youtube(_settings(), tmp_path, now=dt.datetime(2026, 11, 2))


def test_cleanup_deletes_only_expired_discovery_report(tmp_path):
    report = {'refresh_or_delete_by_utc': '2026-11-01T00:00:00Z'}
    (tmp_path / 'discovery.json').write_text(json.dumps(report), encoding='utf-8')
    (tmp_path / 'discovery.md').write_text('report', encoding='utf-8')
    unrelated = tmp_path / 'keep.txt'
    unrelated.write_text('keep', encoding='utf-8')
    now = dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc)
    assert purge_expired_discovery_output(tmp_path, now=now) is True
    assert not (tmp_path / 'discovery.json').exists()
    assert not (tmp_path / 'discovery.md').exists()
    assert unrelated.read_text(encoding='utf-8') == 'keep'


def test_cleanup_keeps_unexpired_discovery_report(tmp_path):
    report = {'refresh_or_delete_by_utc': '2026-12-01T00:00:00Z'}
    (tmp_path / 'discovery.json').write_text(json.dumps(report), encoding='utf-8')
    (tmp_path / 'discovery.md').write_text('report', encoding='utf-8')
    now = dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc)
    assert purge_expired_discovery_output(tmp_path, now=now) is False
    assert (tmp_path / 'discovery.json').exists()
