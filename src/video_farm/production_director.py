"""Autonomous director: storyboard -> direction -> critique -> repair -> evidence audit -> Kokoro -> visuals -> edit -> QC."""
from __future__ import annotations
import argparse, hashlib, json, logging, re, shutil, wave, os, subprocess
from pathlib import Path
from typing import Any
from copy import copy
from pydantic import BaseModel, ConfigDict, Field
from PIL import Image

from .common import read_json, write_json
from .config import load_settings
from .storyboard import create_storyboard
from .llm_structured import StructuredLLMRouter
from .director_models import DirectorBatch, CritiqueBatch
from .director_visuals import (render_beat_visual, render_stock_overlay,
                               audit_visual_assets, audit_final_video_frames)
from .director_sources import audit_claim_sources
from .director_audio import build_master_audio, SAMPLE_RATE
from .director_assembler import assemble_director_video
from .text_normalization import normalize_for_speech
from .kokoro_engine import synthesize_kokoro
from .pixabay_media import fetch_pixabay, PixabayError
from .director_shots import plan_shots
from .director_motion import render_motion_graphic, _clean_labels

log=logging.getLogger("video_farm.production_director")

DIRECTOR_SYSTEM="""Ты — главный режиссёр монтажа AI Video Factory RU, создающий качественный
русскоязычный технологический видеоролик. Тебе дана готовая раскадровка с точными
voice_text. Не переписывай и не сокращай речь. Раздели voice_text каждой сцены на 1–4
ПОСЛЕДОВАТЕЛЬНЫХ ФРАГМЕНТА spoken_text. Склейка spoken_text в исходном порядке с обычными
пробелами должна в точности сохранить исходную речь (все слова, пунктуацию и порядок).
Это не субтитры и не пересказ: каждый spoken_text — точный непрерывный фрагмент оригинала.
ЗВУК — ОСНОВНОЙ И САМОСТОЯТЕЛЬНЫЙ КАНАЛ ОБЪЯСНЕНИЯ:
зритель должен понять тему, ход рассуждений, факты и выводы, даже если слушает ролик,
не глядя на экран. Все важные сведения, выводы, цифры и причинно-следственные связи
обязательно произносятся диктором. Изображение только дополняет и иллюстрирует речь;
оно не должно быть единственным носителем существенной информации.
ВИЗУАЛЬНАЯ РЕЖИССУРА:
сначала сформулируй смысловую идею фрагмента, затем придумай кадр, который помогает
понять эту идею. Не превращай последовательные слова диктора в отдельные карточки.
Не копируй spoken_text в on_screen_text и не используй слова диктора как текст интерфейса,
поисковый запрос, подписи к объектам или названия элементов схемы. Рендерер использует
spoken_text только для озвучки; экранные подписи задаются отдельно и кратко.
Делай минимальное количество речевых фрагментов: обычно один фрагмент на законченную мысль. Не дроби предложение на карточки отдельных слов. Один визуальный образ может сопровождать несколько соседних фраз, если мысль не изменилась.
Меняй кадр при изменении идеи, действия или объекта объяснения, а не просто на границе WAV.

Каждому фрагменту назначай визуал по смыслу целой мысли, а не по каждому слову или отдельной фразе. Так как Kokoro
озвучивает каждый фрагмент отдельно, длительность визуала будет привязана к реальному WAV
этого фрагмента, а не к придуманному проценту сцены.

РАЗРЕШЁННЫЕ АДАПТЕРЫ — ТОЛЬКО ДВА:
1) stock / pixabay: реальные фото или видеоматериалы. Для каждого stock beat дай 2–4
конкретных английских search_queries, описывающих объект/действие в кадре.
При выборе реального видеоряда активно рассматривай ФОТО Pixabay для предметов,
людей, устройств, рабочих мест, документов и обстановки. Для реального действия
(печатает, листает, нажимает, работает) предпочитай подходящее видео. Не своди stock
только к видео: в содержательном ролике должны быть и релевантные фотографии, и видео,
когда предмет материала позволяет подобрать их без натяжки. Для абстрактных процессов
используй объясняющую графику. Не выбирай нерелевантный сток ради квоты.
2) rendered / internal_renderer: локальная оригинальная графика. Поддерживаемые шаблоны:
comparison (сравнение двух объектов), diagram/scheme (последовательность этапов), text
(типографический акцент), illustration (смысловая графическая метафора), screencast
(только явно маркированная учебная симуляция интерфейса), quote (короткая мысль), joke
(визуальная шутка). Для реальных фото/видео используй только stock.
ПРАВИЛО РЕАЛЬНОГО ВИДЕОРЯДА:
- Для реальных физических действий (печатает, нажимает мышь, работает со смартфоном,
  листает документы или работает за компьютером) сначала ищи соответствующий stock/video.
- Для абстрактного механизма LLM, токенов и вероятностного выбора используй motion graphics.
- Не выбирай нерелевантный сток ради разнообразия: соответствие речи важнее квоты.
- Не показывай выдуманные проценты и числовые вероятности даже в симуляции.
ВАЖНОЕ РАЗДЕЛЕНИЕ ПОЛЕЙ:
- visual_description — внутренняя режиссёрская инструкция для программы. НИКОГДА не должна
  становиться надписью или заголовком в готовом кадре.
- on_screen_text — только реальные короткие слова/подписи, которые зритель должен увидеть.
  Не пиши туда описания картинки, указания художнику, слова «макет», «стилизованный»,
  «появляется», «слева/справа», «фон», «иконка», «на экране» и т.п.
- Для illustration опиши конкретный объект/метафору в visual_description, а on_screen_text
  оставь пустым или заполни 1–3 короткими смысловыми подписями.
- Для diagram/scheme задай 3–4 реальные подписи этапов в on_screen_text, если они нужны.
- Для screencast не выдумывай фактические ответы, проценты и интерфейсы реальных продуктов;
  показывай только учебную симуляцию, явно помеченную на кадре.
НИКОГДА не возвращай manual, screencast strategy, generated или других провайдеров.
Визуальные типы чередуй осмысленно, не ставь одинаковые шаблоны подряд без необходимости.
Экранные надписи по-русски, до 40 символов. Не вставляй английский учебный текст в русскую
речь. Не придумывай измеренные проценты, количественные сравнения или источники. Если пример
условный, явно пометь его условность. Не делай chart с фиктивными данными.
Не генерируй музыкальные мелодии, тональные подложки или частые SFX. Музыка подключается отдельным реальным аудиофайлом на этапе сведения. Звук диктора всегда главный и должен оставаться разборчивым; эффекты допустимы только редкие и осмысленные. claims — только
фактические утверждения из речи/визуала и URL-кандидаты, не подтверждённые факты.
Для каждого beat укажи motion и при необходимости короткие SFX. Заполняй ВСЕ поля схемы:
если claims нет — claims=[]; если cue нет — music_cue=""; для gen_prompt без промпта — null;
для отсутствующих SFX и подписей — пустые списки. Верни по одному плану на каждый переданный
scene_id и только для них.

PHOTO_EDITORIAL_POLICY_ENGINE_2_3
ПРИОРИТЕТ ФОТОГРАФИЙ И ВИДЕО — ОБЯЗАТЕЛЬНОЕ РЕЖИССЁРСКОЕ РЕШЕНИЕ:
- Сначала определи, что именно зритель должен увидеть: реальный предмет/человека/место,
  физическое действие или абстрактный процесс.
- Для конкретного статичного реального объекта или обстановки (компьютер, смартфон,
  серверная, рабочее место, документы, книги, человек за работой, офис) предпочитай
  visual_type="photo", asset_strategy="stock", provider_id="pixabay". Фотография с
  аккуратным медленным движением камеры лучше, чем декоративная локальная карточка.
- Для действия, где важно само движение (печатает, листает, нажимает, собирает,
  взаимодействует с устройством), выбирай visual_type="video" или "broll" и stock.
- Для невидимого механизма, логической связи, токенизации или вероятностного выбора
  используй rendered-графику, которая наглядно показывает изменение состояния.
- Не подменяй фотографию абстрактной иллюстрацией только потому, что illustration
  проще придумать. Если реальный объект materially помогает объяснить мысль, выбери фото.
- В десятисценном пилоте стремись найти примерно 2–4 действительно уместные фотографии,
  когда в материале есть подходящие реальные объекты/люди/места. Это редакционный ориентир,
  а не квота: никогда не добавляй нерелевантную фотографию ради числа.
- Для visual_type="photo" обязательно укажи asset_strategy="stock", provider_id="pixabay"
  и 2–4 конкретных английских поисковых запроса с предметом и контекстом кадра.
  Для visual_type="video"/"broll" также используй stock и запросы, описывающие действие.
- Не считай экранную надпись или заголовок заменой фотографии, видеоматериала либо
  объясняющей схемы. Не дроби одну мысль на несколько кадров только ради смены визуала.

EDITORIAL_POLICY_ENGINE_2_4 — РЕАЛИЗМ, ДОСТОВЕРНОСТЬ И ЦЕЛЬНОСТЬ МЫСЛИ

ПРИНЦИП «ОДНА МЫСЛЬ — ОДИН ОСНОВНОЙ ВИЗУАЛ»:
- По умолчанию сопровождай одну законченную мысль одним beat и одним основным визуальным образом.
- Не создавай отдельный beat для каждого существительного, пункта перечисления,
  короткой фразы или части сложного предложения. Запятая, пауза и смена формулировки
  сами по себе не являются причиной смены кадра.
- Новый beat оправдан, когда действительно меняется предмет объяснения, действие,
  причинно-следственный этап или визуальный аргумент. Несколько соседних фраз могут
  оставаться под одним визуальным решением.

ЗАПРЕТ ВЫДУМАННЫХ ИНТЕРФЕЙСОВ И ФАКТИЧЕСКИХ ДЕТАЛЕЙ:
- Не создавай псевдоскриншоты браузера, поисковика, чата, мессенджера, терминала,
  панели приложения, сайта, документа, письма, отчёта или страницы источника.
- Не выдумывай названия авторов и организаций, даты, URL, цитаты, логотипы, версии
  программ, названия кнопок, элементы интерфейса, результаты поиска, системные сообщения,
  числа, метрики и другие детали, которые выглядят как реальные сведения.
- Реалистичный интерфейс или документ допустим только при наличии точного подтверждённого
  содержания в исходных материалах проекта. Одного упоминания темы в речи или поискового
  запроса недостаточно, чтобы придумывать его содержимое.
- Если речь об условном примере или гипотетической ситуации, не изображай выдуманный
  экран или документ как настоящий. Используй нейтральный подходящий stock-кадр человека,
  устройства или рабочего места либо ясную абстрактную схему. Стоковый кадр — иллюстрация
  контекста, а не доказательство конкретного события, человека или результата.
- Если точного визуального подтверждения нет, опусти спорную деталь. Не заполняй пробелы
  правдоподобными выдумками.

ЭКРАННЫЙ ТЕКСТ:
- Используй on_screen_text только для короткой смысловой метки или ключевого термина,
  который уже произнесён диктором либо дословно подтверждён материалами проекта.
- Не переноси на экран всё предложение, абзац, перечисление или spoken_text целиком.
  Не превращай каждый beat в титульную карточку и не делай из надписей субтитры.
- Имена, даты, URL, числа, цитаты и названия продуктов показывай только в точном виде,
  уже присутствующем в речи и подтверждённом источником. Иначе оставляй их за кадром.
- Шаблон text используй как редкий типографический акцент, а не как замену содержательному
  изображению или как способ показать пересказ диктора. Обычно достаточно одного короткого
  термина или контрастной пары слов.

СМЫСЛОВАЯ ГРАФИКА И STOCK:
- Локальная графика оправдана, когда она наглядно раскрывает абстрактный механизм,
  последовательность состояний, причинную связь или сравнение. Она не должна быть
  декоративной заглушкой вместо подходящего фото/видео.
- Для реальных предметов, людей, устройств, рабочих мест и физических действий сначала
  рассматривай соответствующий stock Pixabay. Для условной ситуации выбирай нейтральный
  контекстный кадр, не выдавая его за документальную запись описанного события.
- Не используй случайную фотографию ради разнообразия и не подменяй ею объяснение.
  Если кадр не помогает понять именно произносимую мысль, выбери другой визуал.
- Не создавай графики, диаграммы, шкалы и числовые сравнения без реальных исходных данных.
  Условная схема должна быть явно концептуальной и не имитировать реальные измерения.
- Любые существенные факты и связи должны оставаться понятными на слух; визуал не
  добавляет новой необходимой информации и не исправляет недостаток дикторского текста.
"""

CRITIC_SYSTEM="""Ты — независимый AI-редактор и технический режиссёр, не автор первоначального плана.
Проверяй визуальное решение в сравнении с точным voice_text каждого фрагмента. Критерии:
0) audio_independence: всю существенную информацию можно понять только на слух; никакой факт или вывод не спрятан исключительно в надписи, схеме или графике;
1) relevance: кадр объясняет именно произносимую мысль;
2) coverage: spoken_text фрагменты без пропусков, повторов, перестановок и переписывания;
3) feasibility: только доступные Pixabay stock и локальный renderer; без обещаний эффектов,
которых он не умеет; без operator-only manual/screencast;
4) clarity: достаточно конкретный кадр, читабельный русский текст, нет одинаковых карточек подряд;
   visual_description — только внутренняя инструкция, on_screen_text — только короткая надпись
   зрителю. Отклоняй планы, в которых описание сцены предлагается показать как текст.
5) factual risk: нет выдуманных процентов, графиков без данных, псевдофактов и несуществующих
источников. Не считай доступность ссылки подтверждением утверждения.
Если есть существенная проблема, verdict=revise и revision_brief должен указывать конкретное
исправление. relevance_score, feasibility_score и narration_coverage_score — целые оценки 0..5;
factual_risk обязателен. Заполняй problems=[] и revision_brief="" при отсутствии замечаний.
Проверяй ВСЕ сцены и возвращай ровно один review на каждый scene_id.

PHOTO_SELECTION_REVIEW_ENGINE_2_3 — CONSISTENT EDITORIAL POLICY

ВЫБОР ФОТО И ВИДЕО:
- Фото подходит для реального статичного объекта, человека, рабочего места,
  устройства, документа, страницы или места, когда этот образ помогает
  понять речь.
- Видео предпочитай, когда физическое движение само является важной частью
  объяснения: печатает, нажимает, листает, ставит штамп и т.п.
- Статичная фотография страницы 404 допустима. Не требуй видео только потому,
  что сцена могла бы быть динамичнее или эмоциональнее.
- Не требуй фото для абстрактного механизма, схемы или логической связи.
- Если важны конкретные читаемые имена, даты, ссылки или элементы интерфейса,
  локальная графика может быть лучше случайного стокового экрана с нечитаемым
  текстом. Не требуй stock вместо rendered в таких случаях.
- Не требуй сложных физических анимаций и VFX от локального renderer.
- Не считай визуальное разнообразие самоцелью. Соответствие речи важнее.

САМОСТОЯТЕЛЬНОСТЬ ДИКТОРСКОЙ ДОРОЖКИ:
- Вся существенная информация должна быть произнесена диктором.
- Если авторы, дата, ссылка или другой элемент уже названы в spoken_text,
  их визуальное отображение допустимо и желательно как иллюстрация речи.
- Короткая подпись, повторяющая уже произнесённое слово или смысл, сама по
  себе не означает, что визуал заменяет аудио.
- Блокируй только тогда, когда существенный факт, вывод или причинная связь
  присутствует исключительно в изображении и отсутствует в речи.
- Не трактуй визуальную иллюстрацию произнесённого факта как новый факт.

БЛОКИРУЮЩИЕ ПРОБЛЕМЫ И РЕДАКТОРСКИЕ РЕКОМЕНДАЦИИ:
- verdict="revise" используй только при существенном дефекте: искажена или
  потеряна речь, визуал противоречит или явно не соответствует речи, способ
  производства технически невыполним, визуал добавляет вводящий в заблуждение
  непроизнесённый факт либо существует высокий фактический риск.
- При блокирующей проблеме хотя бы одна из оценок relevance_score,
  feasibility_score или narration_coverage_score должна быть ниже 4.
- Если все три оценки 4..5 и factual_risk не high, замечание является
  рекомендацией, а не основанием для остановки производства. Используй
  verdict="accept". Рекомендацию можно сохранить в problems, но revision_brief
  оставь пустым.
- Не меняй verdict на revise только потому, что другой тип материала был бы
  немного выразительнее или эстетически предпочтительнее.
- Не меняй уже подходящее решение на противоположное без новой объективной
  причины. Если фото подходит для статичной сцены, не требуй видео ради движения;
  если точная графика лучше передаёт читаемый интерфейс, не требуй случайный сток.

EDITORIAL_REVIEW_ENGINE_2_4 — ПРОВЕРКА ДОСТОВЕРНОСТИ И ЦЕЛЬНОСТИ

Дополнительно проверь каждый кадр на выдуманные детали и ложное впечатление документальности:
- Блокируй реалистичный псевдоинтерфейс, поисковую выдачу, чат, документ, письмо,
  скриншот, цитату, имя, дату, URL, логотип, числовое значение или результат, если его
  точное содержание не подтверждено исходными материалами проекта.
- Блокируй визуал, который приписывает реальному человеку, компании или продукту действие,
  интерфейс либо результат, не подтверждённые источниками. Не принимай правдоподобие
  изображения за доказательство факта.
- Нейтральный stock-кадр человека за компьютером или устройства допустим как иллюстрация
  условной ситуации. Не требуй, чтобы он документально показывал описанное событие.
- Если подпись добавляет новый факт, а не кратко обозначает уже произнесённую мысль,
  это существенная проблема. Простое повторение ключевого произнесённого термина допустимо.
- Проверяй, что text-карточка не заменяет содержательный визуал и не дублирует целое
  предложение диктора. Короткая метка сама по себе не является нарушением.
- Не требуй отдельного кадра на каждое предложение, слово или пункт перечисления.
  Одна законченная мысль может оставаться под одним сильным визуальным решением.
- Не считай универсальный stock-кадр новым фактическим утверждением, если он явно служит
  только нейтральной иллюстрацией контекста и не изображает конкретное событие как факт.

Существенную выдуманную фактическую деталь, ложную документальность или противоречие
речи оценивай как блокирующую проблему. Эстетическое предпочтение другого кадра,
небольшая повторяемость или допустимая типографическая метка — рекомендация, а не
автоматическое основание для verdict="revise".
"""

REPAIR_SYSTEM="""Ты — режиссёр-исполнитель. Звук — самостоятельный и основной канал объяснения: все важные сведения должны быть произнесены диктором; визуал только дополняет речь и не копирует её. Исправь планы только для переданных сцен по замечаниям
критика. Обязательно сохрани spoken_text как точные непрерывные фрагменты исходного voice_text,
в полном объёме, в прежнем порядке. Не меняй смысл. Используй только stock/pixabay либо
rendered/internal_renderer; никакого manual, screencast strategy или generated. Не добавляй
непроверенных чисел, процентов и фактов. Русские экранные подписи короткие. Верни полный
DirectorBatch для всех переданных сцен.

PHOTO_SELECTION_REPAIR_ENGINE_2_3
При исправлении визуального плана: реальные статичные объекты, устройства, люди,
документы и места в первую очередь показывай фотографиями Pixabay (visual_type="photo",
asset_strategy="stock", provider_id="pixabay"). Реальные действия показывай видео/broll.
Абстрактные механизмы объясняй локальной графикой. Не добавляй случайный сток ради квоты.

EDITORIAL_REPAIR_ENGINE_2_4 — НЕ ВЫДУМЫВАЙ И НЕ ДРОБИ БЕЗ ПРИЧИНЫ

При исправлении плана соблюдай дополнительные ограничения:
- Не создавай фиктивные интерфейсы сайтов, чатов, приложений, поисковиков, документов,
  писем и терминалов. Не выдумывай читаемые имена, даты, URL, цитаты, логотипы, числа,
  метрики, названия кнопок или результаты.
- Для условной ситуации используй нейтральный соответствующий stock-кадр либо
  концептуальную графику; не представляй постановочное изображение как доказательство
  конкретного реального события.
- Экранная подпись должна быть короткой и уже произнесённой/подтверждённой. Не копируй
  на экран предложение диктора и не превращай план в набор текстовых карточек.
- Сохраняй одну законченную мысль в одном beat, если нет реального изменения действия,
  объекта объяснения или причинно-следственного этапа. Не дроби речь ради разнообразия.
- Локальная графика должна объяснять механизм или связь, а не быть декоративной заглушкой
  вместо подходящей фотографии или видеозаписи.
"""

def _norm(text: str) -> str:
    return re.sub(r"\s+"," ",str(text or "")).strip()

def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(path)

def _check_exact_coverage(plan: dict[str,Any], scene: dict[str,Any]) -> None:
    combined=" ".join(x["spoken_text"] for x in plan["beats"])
    if _norm(combined)!=_norm(scene["voice_text"]):
        raise ValueError(f"{scene['id']}: spoken_text beats do not exactly preserve narration")
    if not plan["beats"]: raise ValueError(f"{scene['id']}: no visual beats")

def _make_director_plan(settings: Any, scenes: list[dict[str,Any]], batch_size: int,
                        out_path: Path) -> list[dict[str,Any]]:
    progress_path=out_path.with_suffix(".progress.json")
    source_fp=hashlib.sha256(json.dumps(scenes,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    completed={}
    if progress_path.exists():
        saved=read_json(progress_path)
        if saved.get("source_sha256")!=source_fp:
            raise ValueError("Director checkpoint belongs to different input; choose a new output directory")
        completed=saved.get("completed",{})
    pending=[s for s in scenes if s["id"] not in completed]
    for offset in range(0,len(pending),batch_size):
        batch=pending[offset:offset+batch_size]
        payload=[{"scene_id":s["id"],"voice_text":s["voice_text"],
            "meaning":s.get("meaning",""),"purpose":s.get("purpose","")} for s in batch]
        prompt="Создай точный режиссёрский план для этих сцен:\n"+json.dumps(payload,ensure_ascii=False)
        result=StructuredLLMRouter(settings).complete(DirectorBatch,DIRECTOR_SYSTEM,prompt,
                                                       temperature=0.25,max_tokens=8500).plans
        if {p.scene_id for p in result}!={s["id"] for s in batch} or len(result)!=len(batch):
            raise ValueError("Director returned missing/duplicate scene IDs")
        invalid=[]
        for p in result:
            pdata=p.model_dump(mode="json")
            scene=next(x for x in batch if x["id"]==p.scene_id)
            try:
                _check_exact_coverage(pdata,scene)
                completed[p.scene_id]=pdata
            except ValueError as exc:
                invalid.append({"scene":scene,"bad_plan":pdata,"error":str(exc)})
        if invalid:
            repair_payload=[{"scene_id":x["scene"]["id"],"voice_text":x["scene"]["voice_text"],
                             "previous_plan":x["bad_plan"],"validation_error":x["error"]} for x in invalid]
            corrected=StructuredLLMRouter(settings).complete(DirectorBatch,REPAIR_SYSTEM,
                "КРИТИЧЕСКАЯ ОШИБКА: spoken_text должен в точности покрывать исходную речь. "
                "Исправь только эти планы; каждый фрагмент должен быть точной непрерывной частью voice_text.\n"
                +json.dumps(repair_payload,ensure_ascii=False),temperature=0.05,max_tokens=8500).plans
            expected={x["scene"]["id"] for x in invalid}
            if {p.scene_id for p in corrected}!=expected or len(corrected)!=len(expected):
                raise ValueError("Narration exact-coverage repair returned incomplete scene set")
            for p in corrected:
                pdata=p.model_dump(mode="json")
                scene=next(x["scene"] for x in invalid if x["scene"]["id"]==p.scene_id)
                _check_exact_coverage(pdata,scene)
                completed[p.scene_id]=pdata
        _atomic_json(progress_path,{"source_sha256":source_fp,"completed":completed,"status":"in_progress"})
        log.info("AI director checkpoint: %d/%d scenes",len(completed),len(scenes))
    plans=[completed[s["id"]] for s in scenes]
    _atomic_json(out_path,{"plans":plans,"status":"complete","scene_count":len(plans),"source_sha256":source_fp})
    _atomic_json(progress_path,{"source_sha256":source_fp,"completed":completed,"status":"complete"})
    return plans

def _critic_settings(settings: Any) -> Any:
    """Optionally route the critic to a different configured provider/model.

    DIRECTOR_CRITIC_PROVIDER=auto|primary|secondary. Default auto preserves the
    project's normal MWS -> Ollama provider order; `secondary` allows a genuinely
    separate local critic without changing the main director route.
    """
    policy=os.getenv("DIRECTOR_CRITIC_PROVIDER","auto").strip().lower()
    if policy=="auto": return settings
    if policy not in ("primary","secondary"):
        raise ValueError("DIRECTOR_CRITIC_PROVIDER must be auto, primary or secondary")
    providers=list(getattr(settings,"providers",[]))
    selected=[p for p in providers if str(getattr(p,"name","")).lower()==policy]
    if not selected:
        raise ValueError(f"DIRECTOR_CRITIC_PROVIDER={policy} is not configured in .env")
    clone=copy(settings); clone.providers=selected
    return clone

def _is_blocking_review(review: dict[str, Any]) -> bool:
    """Only material quality failures block production; preferences remain advisory."""
    if str(review.get("factual_risk", "")).lower() == "high":
        return True

    score_keys = (
        "relevance_score",
        "feasibility_score",
        "narration_coverage_score",
    )
    try:
        scores = [int(review[key]) for key in score_keys]
    except (KeyError, TypeError, ValueError):
        # Fail closed when a critic response is incomplete or malformed.
        return True

    if any(score < 0 or score > 5 for score in scores):
        return True

    return min(scores) < 4


def _critique(settings: Any, scenes: list[dict[str,Any]], plans: list[dict[str,Any]]) -> dict[str,Any]:
    by_id={p["scene_id"]:p for p in plans}
    payload=[]
    for s in scenes:
        p=by_id[s["id"]]
        payload.append({"scene_id":s["id"],"voice_text":s["voice_text"],"meaning":s.get("meaning"),
                        "plan":p})
    result=StructuredLLMRouter(_critic_settings(settings)).complete(CritiqueBatch,CRITIC_SYSTEM,
        "Проведи независимую редакторскую проверку:\n"+json.dumps(payload,ensure_ascii=False),
        temperature=0.1,max_tokens=min(8500,1800+len(scenes)*600))
    ids={s["id"] for s in scenes}
    if {x.scene_id for x in result.reviews}!=ids or len(result.reviews)!=len(ids):
        raise ValueError("AI critic did not return exactly one review per scene")
    return result.model_dump(mode="json")

def _repair(settings: Any, scenes: list[dict[str,Any]], plans: list[dict[str,Any]],
            critique: dict[str,Any]) -> list[dict[str,Any]]:
    bad={r["scene_id"]:r for r in critique["reviews"] if r["verdict"]=="revise" or r["factual_risk"]=="high" or
         min(r["relevance_score"],r["feasibility_score"],r["narration_coverage_score"])<3}
    if not bad: return plans
    scene_by={s["id"]:s for s in scenes}; plan_by={p["scene_id"]:p for p in plans}
    payload=[]
    for sid,review in bad.items():
        payload.append({"scene_id":sid,"voice_text":scene_by[sid]["voice_text"],
                        "meaning":scene_by[sid].get("meaning"),"current_plan":plan_by[sid],
                        "critic_problems":review["problems"],"revision_brief":review["revision_brief"]})
    revised=StructuredLLMRouter(settings).complete(DirectorBatch,REPAIR_SYSTEM,
        "Исправь проблемные режиссёрские планы:\n"+json.dumps(payload,ensure_ascii=False),
        temperature=0.1,max_tokens=min(8500,2200+len(bad)*1400)).plans
    if {p.scene_id for p in revised}!=set(bad) or len(revised)!=len(bad):
        raise ValueError("Auto-repair returned missing/duplicate scene IDs")
    out=[]
    for old in plans:
        replacement=next((p.model_dump(mode="json") for p in revised if p.scene_id==old["scene_id"]),None)
        out.append(replacement or old)
    for plan in out: _check_exact_coverage(plan,scene_by[plan["scene_id"]])
    return out

def _validate_pixabay_asset(settings: Any, asset: dict[str,Any], kind: str) -> tuple[bool,str]:
    """Decode/probe the downloaded source before it is admitted to the timeline."""
    path=Path(asset.get("path") or "")
    if not path.is_file(): return False,"file_missing"
    if path.stat().st_size<1024: return False,"file_too_small"
    if kind=="photo":
        try:
            with Image.open(path) as image:
                width,height=image.size
                image.verify()
            if width<640 or height<360: return False,f"image_resolution_too_small_{width}x{height}"
            return True,f"image_ok_{width}x{height}"
        except Exception as exc:
            return False,f"image_decode_failed_{type(exc).__name__}"
    try:
        result=subprocess.run([str(settings.ffprobe),"-v","error","-show_entries",
            "format=duration:stream=codec_type,width,height","-of","json",str(path)],
            capture_output=True,text=True,encoding="utf-8",errors="replace",check=True)
        probe=json.loads(result.stdout)
        streams=[x for x in probe.get("streams",[]) if x.get("codec_type")=="video"]
        if not streams: return False,"video_stream_missing"
        width=int(streams[0].get("width") or 0); height=int(streams[0].get("height") or 0)
        duration=float(probe.get("format",{}).get("duration") or 0)
        if width<640 or height<360: return False,f"video_resolution_too_small_{width}x{height}"
        if duration<0.6: return False,f"video_duration_too_short_{duration:.2f}s"
        return True,f"video_ok_{width}x{height}_{duration:.2f}s"
    except Exception as exc:
        return False,f"video_probe_failed_{type(exc).__name__}"

def _asset_for_beat(settings: Any, scene: dict[str,Any], beat: dict[str,Any],
                    visuals_dir: Path, warnings: list[str], index: int,
                    duration: float) -> dict[str,Any]:
    strategy = str(beat.get("asset_strategy") or "").lower()
    if strategy == "stock":
        requested_kind = "video" if beat.get("visual_type") in ("broll", "video") else "photo"
        queries = beat.get("search_queries", [])[:4]
        local_errors: list[str] = []
        rate_limited = False
        asset = None

        try:
            asset = fetch_pixabay(settings, queries, requested_kind, visuals_dir)
        except PixabayError as exc:
            local_errors.append(str(exc))
            warnings.append(f"{scene['id']}: Pixabay {requested_kind}: {exc}")
            rate_limited = exc.is_rate_limited

        # A suitable still image is an acceptable editorial substitute for unavailable
        # motion footage, but never continue querying Pixabay after a 429 response.
        if asset is None and requested_kind == "video" and not rate_limited:
            try:
                asset = fetch_pixabay(settings, queries, "photo", visuals_dir)
                if asset:
                    asset.update({
                        "requested_media_type": "video",
                        "selection_fallback": "video_to_photo",
                        "fallback_reason": "no_usable_video_candidate",
                    })
            except PixabayError as exc:
                local_errors.append(str(exc))
                warnings.append(f"{scene['id']}: Pixabay photo fallback: {exc}")
                rate_limited = exc.is_rate_limited

        if asset is not None:
            actual_kind = "video" if asset.get("media_type") == "video" else "photo"
            valid, check_note = _validate_pixabay_asset(settings, asset, actual_kind)
            if valid:
                path = Path(asset["path"])
                asset.update({
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "asset_check": check_note,
                    "visible_text": _clean_labels(beat),
                    "requested_media_type": asset.get("requested_media_type", requested_kind),
                })
                screen_text = asset["visible_text"]
                if screen_text:
                    overlay = render_stock_overlay(
                        screen_text, visuals_dir / f"{scene['id']}_{index:02d}_overlay.png"
                    )
                    asset["overlay_path"] = str(overlay.resolve())
                return asset
            local_errors.append(f"selected asset rejected: {check_note}")
            warnings.append(f"{scene['id']}: Pixabay asset rejected ({check_note})")

        failure_path = visuals_dir / f"{scene['id']}_{index:02d}_asset_failure.json"
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "manual_review_required",
            "scene_id": scene["id"],
            "beat_index": index,
            "requested_media_type": requested_kind,
            "search_queries": queries,
            "rate_limited": rate_limited,
            "errors": local_errors,
            "policy": "stock assets are never silently replaced by local motion graphics",
        }
        failure_path.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(
            f"{scene['id']}/b{index:02d}: подходящий стоковый материал не получен; "
            f"локальная графика не подставлена. Отчёт: {failure_path}"
        )

    if strategy != "rendered":
        raise ValueError(f"{scene['id']}/b{index:02d}: unsupported asset_strategy={strategy!r}")

    # The local renderer is only allowed when the director explicitly selected rendered.
    clip = render_motion_graphic(
        settings, scene, beat,
        visuals_dir / f"{scene['id']}_{index:02d}_motion.mp4", duration,
    )
    meta_path = clip.with_suffix(clip.suffix + ".meta.json")
    meta = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    return {
        "path": str(clip.resolve()),
        "media_type": "video",
        "source": "AI Video Factory local renderer",
        "source_url": None,
        "creator": "Project renderer",
        "license_name": "Project original graphics",
        "rights_status": "project_generated",
        "sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
        "template_id": meta.get("template_id"),
        "visual_family": meta.get("visual_family"),
        "visible_text": meta.get("visible_text", []),
        "requested_media_type": "rendered",
    }


def _wav_duration(path: Path) -> float:
    with wave.open(str(path),"rb") as wf:
        if wf.getframerate()<=0: raise ValueError(f"Invalid WAV sample rate: {path}")
        return wf.getnframes()/wf.getframerate()

def _produce(settings: Any, scenes: list[dict[str,Any]], plans: list[dict[str,Any]],
             out_dir: Path, speed: float) -> tuple[list[dict[str,Any]],dict[str,Any]]:
    if str(getattr(settings,"tts_engine","kokoro")).lower()!="kokoro" or str(getattr(settings,"tts_speaker","dima")).lower()!="dima":
        raise RuntimeError("Autonomous production is pinned to Kokoro Dima; no silent engine fallback")
    if not 0.5<=speed<=2.0: raise ValueError("TTS speed must be 0.5..2.0")
    audio_dir=out_dir/"audio"; visuals_dir=out_dir/"visuals"
    audio_dir.mkdir(parents=True,exist_ok=True); visuals_dir.mkdir(parents=True,exist_ok=True)
    scene_by={s["id"]:s for s in scenes}
    prepared=[]; flat=[]
    for plan in plans:
        scene=scene_by[plan["scene_id"]]
        for bi,beat in enumerate(plan["beats"],1):
            block_id=f"{scene['id']}_b{bi:02d}"
            raw=beat["spoken_text"].strip()
            normalized=normalize_for_speech(raw)
            if not normalized: raise ValueError(f"{block_id}: empty text after TTS normalization")
            prepared.append((block_id,{"heading":scene.get("meaning","")},raw,normalized))
            flat.append((scene,plan,beat,block_id,bi))
    audio_manifest=synthesize_kokoro(settings,prepared,audio_dir,speed)
    if audio_manifest.get("status")!="complete": raise RuntimeError("Kokoro did not synthesize all beat WAVs")
    audio_by={x["id"]:x for x in audio_manifest["blocks"]}
    beats=[]; warnings=[]; cursor=0.0
    for scene,plan,beat,block_id,bi in flat:
        row=audio_by.get(block_id)
        if not row: raise RuntimeError(f"Kokoro manifest missing {block_id}")
        wav=audio_dir/row["file"]
        duration=_wav_duration(wav)
        asset=_asset_for_beat(settings,scene,beat,visuals_dir,warnings,bi,duration)
        beats.append({"scene_id":scene["id"],"beat_id":f"b{bi:02d}",
            "shot_id":beat.get("shot_id"),"source_beat_id":beat.get("source_beat_id"),
            "cut_reason":beat.get("cut_reason"),
            "spoken_text":beat["spoken_text"],"audio_path":str(wav.resolve()),
            "audio_duration_sec":duration,"visual_path":asset["path"],
            "media_type":asset["media_type"],"overlay_path":asset.get("overlay_path"),
            "source":asset.get("source"),"source_url":asset.get("source_url"),
            "creator":asset.get("creator"),"license_name":asset.get("license_name"),
            "sha256":asset.get("sha256"),"asset_check":asset.get("asset_check","motion_graphics_video_created"),
            "asset_query":asset.get("query"),"candidate_count":asset.get("candidate_count"),
            "selected_tags":asset.get("selected_tags"),"selected_resolution":asset.get("selected_resolution"),
            "pixabay_type":asset.get("pixabay_type"),"rights_status":asset.get("rights_status"),
            "requested_media_type":asset.get("requested_media_type"),
            "selection_fallback":asset.get("selection_fallback"),
            "fallback_reason":asset.get("fallback_reason"),
            "duration_ratio":None,"motion":beat.get("motion","static"),
            "transition_in":beat.get("transition_in","cut"),
            "audio_sfx":[x.model_dump(mode="json") if hasattr(x,"model_dump") else x for x in beat.get("audio_sfx",[])],
            "music_cue":plan.get("music_cue","") ,"on_screen_text":beat.get("on_screen_text",[]),
            "visible_text":asset.get("visible_text",beat.get("on_screen_text",[])),
            "visual_type":beat.get("visual_type"),"visual_description":beat.get("visual_description"),
            "template_id":asset.get("template_id"),"visual_family":asset.get("visual_family"),
            "overlay_path":asset.get("overlay_path"),
            "start_sec_estimate":round(cursor,4)})
        cursor += duration
    return beats,{"status":"complete","audio_manifest":str((audio_dir/"manifest.json").resolve()),
                  "beat_count":len(beats),"speech_seconds":round(sum(x["audio_duration_sec"] for x in beats),4),
                  "warnings":warnings}

def _post_qc(settings: Any, beats: list[dict[str,Any]], source_audit: dict[str,Any],
             audio_report: dict[str,Any], assembly: dict[str,Any], video_path: Path,
             out_path: Path, visual_audit: dict[str,Any]|None=None) -> dict[str,Any]:
    errors=[]; warnings=[]
    if visual_audit:
        errors.extend(visual_audit.get("errors",[]))
        warnings.extend(visual_audit.get("warnings",[]))
    if not video_path.is_file(): errors.append("Final MP4 missing")
    if len(beats)!=assembly.get("beat_count"): errors.append("Beat count mismatch")
    for b in beats:
        if not Path(b["audio_path"]).is_file(): errors.append(f"{b['scene_id']}/{b['beat_id']}: WAV missing")
        if not Path(b["visual_path"]).is_file(): errors.append(f"{b['scene_id']}/{b['beat_id']}: visual missing")
    probe=assembly.get("ffprobe",{}); streams=probe.get("streams",[])
    if not any(x.get("codec_type")=="video" for x in streams): errors.append("MP4 video stream missing")
    if not any(x.get("codec_type")=="audio" for x in streams): errors.append("MP4 audio stream missing")
    sync_tolerance=max(0.12,len(beats)/max(1,int(getattr(settings,"fps",25)))+0.08)
    if abs(float(audio_report.get("duration_seconds",0))-float(assembly.get("duration_sec",0)))>sync_tolerance:
        errors.append("Master audio and final video durations do not match")
    audio_slots=audio_report.get("timeline",[])
    video_slots=assembly.get("timeline",[])
    if len(audio_slots)!=len(beats) or len(video_slots)!=len(beats):
        errors.append("Audio/video timeline beat count mismatch")
    else:
        for a,v in zip(audio_slots,video_slots):
            if a["scene_id"]!=v["scene_id"] or a["beat_id"]!=v["beat_id"]:
                errors.append(f"Timeline identity mismatch: {a['scene_id']}/{a['beat_id']}")
            if abs(float(a["start_sec"])-float(v["start_sec"]))>0.02 or abs(float(a["end_sec"])-float(v["end_sec"]))>0.03:
                errors.append(f"Timeline offset mismatch: {a['scene_id']}/{a['beat_id']}")
    if not source_audit.get("facts_verified",False): warnings.append("Facts remain unverified; human review required")
    report={"status":"failed" if errors else ("passed_with_warnings" if warnings else "passed"),
        "errors":errors,"warnings":warnings,"video":str(video_path.resolve()),
        "beat_count":len(beats),"duration_sec":assembly.get("duration_sec"),
        "technical_audio_video_sync":"passed" if not errors else "failed",
        "semantic_frame_to_speech_review":"human_review_required",
        "visual_audit":visual_audit or {"status":"not_run"},
        "facts_verified":False,"claims_policy":"No automated claim is marked verified."}
    _atomic_json(out_path,report)
    return report

def _summarize_media_mix(beats: list[dict[str,Any]]) -> dict[str,int]:
    """Count actual media origins; local MP4 graphics are not Pixabay videos."""
    photos=sum(1 for beat in beats if beat.get("source")=="Pixabay" and beat.get("media_type")=="image")
    videos=sum(1 for beat in beats if beat.get("source")=="Pixabay" and beat.get("media_type")=="video")
    local=sum(1 for beat in beats if beat.get("source")=="AI Video Factory local renderer")
    known=photos+videos+local
    return {"total_assets":len(beats),"pixabay_photos":photos,"pixabay_videos":videos,
            "local_motion_graphics":local,"other_assets":len(beats)-known}


def run_pipeline(*, script_path: Path|None, storyboard_path: Path|None, out_dir: Path,
                 scene_limit: int|None=10, batch_size: int=2, speed: float=0.9,
                 revision_rounds: int=2, settings: Any|None=None,
                 music_path: Path|None=None,
                 music_metadata: dict[str,Any]|None=None) -> dict[str,Any]:
    settings=settings or load_settings()
    if music_path is not None and not Path(music_path).is_file():
        raise FileNotFoundError(f"Музыкальный файл не найден: {music_path}")
    if (script_path is None)==(storyboard_path is None):
        raise ValueError("Specify exactly one of script_path or storyboard_path")
    if not 1<=batch_size<=4: raise ValueError("batch_size must be 1..4")
    if not 0<=revision_rounds<=3: raise ValueError("revision_rounds must be 0..3")
    out_dir.mkdir(parents=True,exist_ok=True)
    draft_path=out_dir/"storyboard_draft.json"
    if script_path:
        create_storyboard(settings,script_path,draft_path)
    else:
        shutil.copy2(storyboard_path,draft_path)
    source=read_json(draft_path)
    scenes=source.get("scenes") or []
    if scene_limit:
        if scene_limit<1: raise ValueError("scene_limit must be >=1")
        scenes=scenes[:scene_limit]
    if not scenes: raise ValueError("No scenes available after scene limit")
    ids=[x["id"] for x in scenes]
    if len(ids)!=len(set(ids)): raise ValueError("Duplicate scene IDs in storyboard")
    source["scenes"]=scenes
    pilot_path=out_dir/"pilot_storyboard.json"; _atomic_json(pilot_path,source)

    plan_path=out_dir/"director_plan.json"
    if plan_path.exists():
        cached=read_json(plan_path)
        plans=cached.get("plans",[])
        expected_fp=hashlib.sha256(json.dumps(scenes,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        if cached.get("source_sha256") and cached.get("source_sha256")!=expected_fp:
            raise ValueError("Existing director_plan.json belongs to changed narration/scene data; choose a fresh output directory")
        if {x["scene_id"] for x in plans}!=set(ids):
            raise ValueError("Existing director_plan.json belongs to different scene set; choose a fresh output directory")
        for p in plans: _check_exact_coverage(p,next(s for s in scenes if s["id"]==p["scene_id"]))
    else:
        plans=_make_director_plan(settings,scenes,batch_size,plan_path)

    review_history=[]
    for round_no in range(revision_rounds+1):
        critique=_critique(settings,scenes,plans)
        review_history.append({"round":round_no,"critique":critique})
        _atomic_json(out_dir/f"director_critique_round_{round_no+1}.json",critique)
        bad=[x for x in critique["reviews"] if _is_blocking_review(x)]
        if not bad or round_no==revision_rounds: break
        plans=_repair(settings,scenes,plans,critique)
        _atomic_json(plan_path,{"plans":plans,"repaired":True,"round":round_no+1})
    unresolved=[x for x in critique["reviews"] if _is_blocking_review(x)]
    recommendations=[
        x for x in critique["reviews"]
        if not _is_blocking_review(x)
        and (x.get("verdict")=="revise" or x.get("problems") or x.get("revision_brief"))
    ]
    _atomic_json(out_dir/"director_review.json",{"history":review_history,
        "unresolved":unresolved,"recommendations":recommendations,
        "status":"blocked" if unresolved else (
            "accepted_with_recommendations" if recommendations else "accepted"
        ),
        "human_review_required":True})
    if unresolved:
        raise RuntimeError(f"AI critic still reports {len(unresolved)} unresolved scene(s); no production started. See director_review.json")
    _atomic_json(plan_path,{"plans":plans,"status":"accepted_by_ai_critic","scene_count":len(plans)})

    # Shot-level EDL: exact narration anchors; timestamps come from measured WAVs.
    shot_plan_path=out_dir/"shot_plan.json"
    shot_result=plan_shots(settings,scenes,plans,shot_plan_path,batch_size=batch_size)
    shot_plans=shot_result["plans"]
    source_audit=audit_claim_sources(settings,plans,out_dir/"source_audit.json")
    beats,production=_produce(settings,scenes,shot_plans,out_dir/"production",speed)
    asset_audit=audit_visual_assets(beats,out_dir/"visual_asset_audit.json",ffmpeg=settings.ffmpeg)
    production["visual_asset_audit_status"]=asset_audit["status"]
    production["visual_asset_audit_errors"]=asset_audit["errors"]
    production["visual_asset_audit_warnings"]=asset_audit["warnings"]
    audio_report=build_master_audio(beats,out_dir/"production"/"audio_master.wav",
        music_path=music_path,music_metadata=music_metadata,ffmpeg=settings.ffmpeg)
    # Align each visual to the measured speech fragment WAV, then add the same planned pause.
    assembly=assemble_director_video(settings,beats,Path(audio_report["path"]),
        out_dir/"final.mp4",out_dir/"production"/"assembly",pause_seconds=0.12)
    final_visual_audit=audit_final_video_frames(
        out_dir/"final.mp4",assembly.get("timeline",[]),out_dir/"visual_audit.json",
        out_dir/"visual_contact_sheet.jpg",ffmpeg=settings.ffmpeg)
    visual_errors=asset_audit.get("errors",[])+final_visual_audit.get("errors",[])
    visual_warnings=asset_audit.get("warnings",[])+final_visual_audit.get("warnings",[])
    visual_audit={
        "status":"failed" if visual_errors else ("passed_with_warnings" if visual_warnings else "passed"),
        "errors":visual_errors,"warnings":visual_warnings,
        "asset_audit_path":str((out_dir/"visual_asset_audit.json").resolve()),
        "final_video_audit_path":str((out_dir/"visual_audit.json").resolve()),
        "final_video":final_visual_audit,
    }
    production["visual_audit_status"]=visual_audit["status"]
    production["visual_audit_errors"]=visual_errors
    production["visual_audit_warnings"]=visual_warnings
    qc=_post_qc(settings,beats,source_audit,audio_report,assembly,out_dir/"final.mp4",
                out_dir/"postproduction_qc.json",visual_audit=visual_audit)
    contact=Path(final_visual_audit["contact_sheet"])
    beat_slots=audio_report.get("timeline",[])
    timeline_beats=[]
    for b,slot in zip(beats,beat_slots):
        timeline_beats.append({**{k:b.get(k) for k in ("scene_id","beat_id","spoken_text","audio_path","audio_duration_sec","visual_path","media_type","source","source_url","creator","license_name","sha256","motion","transition_in","visual_type","template_id","visual_family","on_screen_text","visible_text","visual_description","asset_query","candidate_count","selected_tags","selected_resolution","pixabay_type","rights_status","requested_media_type","selection_fallback","fallback_reason")},
                               "start_sec":slot["start_sec"],"voice_end_sec":slot["voice_end_sec"],"end_sec":slot["end_sec"]})
    _atomic_json(out_dir/"production_timeline.json",{"audio":audio_report,"beats":timeline_beats})
    media_mix=_summarize_media_mix(beats)
    production["media_mix"]=media_mix
    media_manifest={"status":"complete","asset_count":len(beats),
        "summary":media_mix,
        "assets":[{"scene_id":b["scene_id"],"beat_id":b["beat_id"],"path":b["visual_path"],
            "media_type":b["media_type"],"source":b["source"],"source_url":b.get("source_url"),
            "creator":b.get("creator"),"license_name":b.get("license_name"),
            "rights_status":"review_required" if b.get("source_url") else "project_generated",
            "sha256":b.get("sha256"),"asset_check":b.get("asset_check"),
            "asset_query":b.get("asset_query"),"candidate_count":b.get("candidate_count"),
            "selected_tags":b.get("selected_tags"),"selected_resolution":b.get("selected_resolution"),
            "pixabay_type":b.get("pixabay_type"),"rights_status":b.get("rights_status"),
            "visual_type":b.get("visual_type"),"template_id":b.get("template_id"),
            "visual_family":b.get("visual_family"),"visible_text":b.get("visible_text",[])} for b in beats],
        "audio_manifest":production.get("audio_manifest"),
        "audio_master":audio_report["path"],"music_track":audio_report.get("music_track"),
        "note":"Pixabay attribution and rights must be reviewed before publication."}
    _atomic_json(out_dir/"media_manifest.json",media_manifest)
    report={"status":"complete" if not qc["errors"] else "failed",
        "scene_count":len(scenes),"beat_count":len(beats),"video":str((out_dir/"final.mp4").resolve()),
        "contact_sheet":str(contact.resolve()),"director_plan":str(plan_path.resolve()),
        "source_audit":str((out_dir/"source_audit.json").resolve()),
        "visual_audit":str((out_dir/"visual_audit.json").resolve()),
        "visual_asset_audit":str((out_dir/"visual_asset_audit.json").resolve()),
        "media_manifest":str((out_dir/"media_manifest.json").resolve()),"production":production,
        "audio":audio_report,"assembly":assembly,"postproduction_qc":qc,
        "facts_verified":False,"human_review_required":True}
    _atomic_json(out_dir/"director_report.json",report)
    return report

def main(argv: list[str]|None=None)->int:
    parser=argparse.ArgumentParser(prog="video-farm-director",description="Autonomous AI Video Factory production director")
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--script",type=Path,help="script.json: farm creates semantic storyboard")
    source.add_argument("--storyboard",type=Path,help="existing semantic storyboard draft")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--scene-limit",type=int,default=10)
    parser.add_argument("--batch-size",type=int,default=2)
    parser.add_argument("--speed",type=float,default=0.9)
    parser.add_argument("--revision-rounds",type=int,default=2)
    parser.add_argument("--music",type=Path,help="MP3/WAV/OGG background music file; optional")
    parser.add_argument("--music-title",default=None,help="Track title for the media manifest")
    parser.add_argument("--music-creator",default=None,help="Track author/creator for the media manifest")
    parser.add_argument("--music-license",default=None,help="Exact license name, e.g. Pixabay Content License")
    parser.add_argument("--music-source-url",default=None,help="Original music page URL")
    parser.add_argument("--music-source",default=None,help="Source platform, e.g. Pixabay or Mixkit")
    parser.add_argument("--verbose",action="store_true")
    args=parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",datefmt="%H:%M:%S")
    try:
        report=run_pipeline(script_path=args.script,storyboard_path=args.storyboard,
           out_dir=args.out,scene_limit=args.scene_limit,batch_size=args.batch_size,
           speed=args.speed,revision_rounds=args.revision_rounds,music_path=args.music,
           music_metadata={"title":args.music_title,"creator":args.music_creator,
                           "license":args.music_license,"source_url":args.music_source_url,
                           "source":args.music_source})
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if report["status"]=="complete" else 2
    except Exception:
        log.exception("Autonomous production failed")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
