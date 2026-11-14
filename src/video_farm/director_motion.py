"""Motion-graphics renderer for Autonomous Video Engine 2.0.

Creates short, original animated visual sequences from several designed keyframes.
No new Python dependencies: Pillow draws the artwork, FFmpeg animates/transitions it.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FPS = 25
WHITE = (245, 247, 250)
MUTED = (174, 187, 204)
CYAN = (66, 218, 210)
BLUE = (87, 154, 255)
PURPLE = (173, 124, 255)
ORANGE = (255, 171, 88)
RED = (255, 95, 105)
GREEN = (101, 220, 159)
PALE = (224, 233, 245)


def _font(size: int, bold: bool = False):
    paths = (
        ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold else
        ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in paths:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _tokens(text: str) -> list[str]:
    stop = {
        "это", "как", "что", "для", "при", "или", "если", "когда", "чтобы",
        "она", "него", "него", "тебе", "только", "очень", "просто", "может",
        "будет", "который", "которая", "которые", "самое", "самый", "сам",
    }
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9-]{3,}", str(text or ""))
    return [w for w in words if w.lower() not in stop]


def _clean_labels(beat: dict[str, Any]) -> list[str]:
    """Return short editorial labels, never a transcription of the narration."""
    values = []
    spoken_words = {word.lower() for word in _tokens(str(beat.get("spoken_text") or ""))}
    for raw in beat.get("on_screen_text") or []:
        text = re.sub(r"\s+", " ", str(raw or "")).strip()
        if not text or len(text) > 40:
            continue
        if re.search(r"\d+(?:[.,]\d+)?\s*%|[×xх]\s*\d+|\bв\s+\d+\s+раз", text.lower()):
            continue
        if re.search(
            r"стилизован|макет|изобраз|покажи|на экране|в кадре|фон|иконк|слева|справа|"
            r"композици|появля|камера|ракурс|статичн|динамичн|сцена|расположен",
            text, re.IGNORECASE,
        ) and len(text.split()) >= 3:
            continue
        label_words = [word.lower() for word in _tokens(text)]
        if len(label_words) >= 4:
            overlap = sum(word in spoken_words for word in label_words) / max(1, len(label_words))
            if overlap >= 0.75:
                continue
        if text not in values:
            values.append(text)
    return values[:3]

def _motif(scene: dict[str, Any], beat: dict[str, Any]) -> str:
    """Route from visual direction and editorial context, never from narration words."""
    description = str(beat.get("visual_description") or "").lower()
    context = " ".join(str(scene.get(k) or "") for k in ("meaning", "purpose")).lower()

    def classify(text: str) -> str | None:
        if not text:
            return None
        if any(x in text for x in ("смартфон", "телефон", "мобильн", "клавиатур", "автодополн", "t9")):
            return "phone"
        if any(x in text for x in ("чат-бот", "чат бот", "интерфейс чата", "окно чата", "поле ввода", "бот пишет", "ввод текста")):
            return "chat"
        if any(x in text for x in ("404", "браузер", "url", "страница ошибки", "битая ссыл", "страниц не найден", "окно браузера")):
            return "browser"
        if any(x in text for x in ("токен", "token", "кусочек слова", "слог", "символ", "часть слова", "токенизац")):
            return "tokens"
        if any(x in text for x in ("сравнение двух", "сравнение концепц", "split-screen", "split screen", "сравнительная композиция")):
            return "comparison"
        if any(x in text for x in ("архив", "базу данных", "база данных", "папк", "книг", "библиотек", "полк", "хранилищ")):
            return "archive"
        if any(x in text for x in ("вероятност", "предсказ", "следующ", "выбор вариант", "статистическ")):
            return "probability"
        if any(x in text for x in ("роботизированн", "печать", "печатью", "штамп", "ставит печат", "красн печат")):
            return "stamp"
        if any(x in text for x in ("кристалл", "золотой свиток", "золот свиток", "свиток", "драгоценн кам")):
            return "crystal"
        if any(x in text for x in ("глитч", "искаж", "двоичн", "цифровые волны", "пиксел", "разлетающ")):
            return "glitch"
        if any(x in text for x in ("ловушк", "капкан", "захлоп", "силок")):
            return "trap"
        if any(x in text for x in ("шестер", "механизм", "вращающ", "вращается", "механическ")):
            return "mechanism"
        if any(x in text for x in ("типограф", "структуры ответа", "пункт структуры", "перечеркиваются слова", "последовательно появляются слова")):
            return "typography"
        if any(x in text for x in ("нейронн сет", "связи между узлами", "узлы подсвеч", "transformer", "attention")):
            return "network"
        if any(x in text for x in ("первоисточник", "проверка источника", "сверка документа", "проверить утверждение")):
            return "research"
        if any(x in text for x in ("человек", "специалист", "автор", "говорит", "объясняет")):
            return "human"
        if any(x in text for x in ("галлюцинац", "ложн", "неверн", "сомнен", "ошибка модели", "уверенный тон")):
            return "warning"
        return None

    selected = classify(description)
    if selected:
        return selected

    visual_type = str(beat.get("visual_type") or "").lower()
    if visual_type == "text":
        return "typography"
    if visual_type == "comparison":
        return "comparison"

    selected = classify(context)
    return selected or "abstract"

def _background(motif: str, phase: int) -> Image.Image:
    palettes = {
        "tokens": ((12, 19, 37), (31, 21, 61), PURPLE),
        "browser": ((8, 24, 39), (12, 48, 62), CYAN),
        "phone": ((22, 17, 36), (47, 22, 58), PURPLE),
        "archive": ((28, 21, 16), (54, 35, 20), ORANGE),
        "probability": ((8, 22, 34), (13, 44, 60), CYAN),
        "warning": ((25, 15, 23), (50, 20, 30), RED),
        "research": ((9, 21, 34), (17, 41, 57), BLUE),
        "network": ((9, 17, 32), (23, 26, 59), BLUE),
        "human": ((22, 22, 28), (49, 32, 29), ORANGE),
        "abstract": ((11, 17, 31), (26, 25, 52), PURPLE),
        "chat": ((8, 20, 34), (16, 43, 61), CYAN),
        "crystal": ((19, 16, 37), (55, 31, 69), ORANGE),
        "stamp": ((28, 18, 24), (57, 29, 35), RED),
        "glitch": ((12, 15, 31), (39, 20, 52), PURPLE),
        "trap": ((12, 24, 31), (28, 48, 47), GREEN),
        "mechanism": ((13, 22, 35), (39, 39, 54), ORANGE),
        "typography": ((13, 17, 32), (29, 25, 52), PURPLE),
        "comparison": ((9, 22, 35), (24, 34, 58), CYAN),
    }
    top, bottom, accent = palettes[motif]
    im = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(im)
    for y in range(H):
        t = y / (H - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line((0, y, W, y), fill=color)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx = 1450 if phase % 2 == 0 else 420
    cy = 280 + phase * 90
    gd.ellipse((cx - 390, cy - 390, cx + 390, cy + 390), fill=(*accent, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(115))
    im = Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(im)
    # Fine grain-like points and diagonal depth; no repeated card/grid motif.
    seed = int.from_bytes(hashlib.sha256(f"{motif}:{phase}".encode()).digest()[:4], "big")
    for i in range(95):
        x = (seed * (i + 17) + i * 7919) % W
        y = (seed // (i + 3) + i * 3571) % H
        r = 1 + (i % 3)
        draw.ellipse((x-r, y-r, x+r, y+r), fill=tuple(max(0, c // 2) for c in accent))
    return im


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int,
              start: int = 104, minimum: int = 38, bold: bool = True):
    size = start
    while size > minimum:
        font = _font(size, bold)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            return font
        size -= 4
    return _font(minimum, bold)


def _draw_glow_circle(im: Image.Image, cx: int, cy: int, radius: int,
                      color: tuple[int, int, int], alpha: int = 120) -> None:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=(*color, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(max(20, radius // 2)))
    im.alpha_composite(layer)


def _draw_title(draw: ImageDraw.ImageDraw, beat: dict[str, Any], phase: int) -> list[str]:
    labels = _clean_labels(beat)
    title = labels[min(phase, len(labels)-1)] if labels else ""
    if title:
        font = _fit_text(draw, title.upper(), 1450, start=66, minimum=36)
        draw.text((110, 92), title.upper(), font=font, fill=WHITE)
        draw.rounded_rectangle((110, 190, 110 + min(250, len(title)*11), 199),
                               radius=4, fill=[CYAN, PURPLE, ORANGE][phase % 3])
    return [title] if title else []


def _draw_browser(im: Image.Image, draw: ImageDraw.ImageDraw,
                  beat: dict[str, Any], phase: int) -> list[str]:
    """Draw a clearly labelled illustrative browser simulation, not a real website."""
    x0, y0, x1, y1 = 150, 280, 1770, 960
    draw.rounded_rectangle((x0, y0, x1, y1), radius=28, fill=(235, 241, 247), outline=(160, 185, 208), width=3)
    draw.rounded_rectangle((x0, y0, x1, y0+88), radius=26, fill=(35, 49, 67))
    for i, color in enumerate(((245, 98, 100), (245, 184, 84), (99, 205, 143))):
        cx = x0 + 38 + i*34
        draw.ellipse((cx-9, y0+34, cx+9, y0+52), fill=color)
    draw.rounded_rectangle((x0+175, y0+22, x1-55, y0+64), radius=18, fill=(15, 28, 43))
    draw.text((x0+200, y0+26), "УЧЕБНАЯ СИМУЛЯЦИЯ · ПОИСК", font=_font(22, True), fill=(200, 215, 230))
    source_text = str(beat.get("visual_description") or "").lower()
    failed_page = any(term in source_text for term in ("404", "не найден", "ошибка", "битая ссылк"))
    if phase == 0:
        draw.text((240, 430), "ПОИСК ПЕРВОИСТОЧНИКА", font=_font(31, True), fill=(41, 59, 79))
        draw.rounded_rectangle((240, 505, 1640, 635), radius=22, fill=(255,255,255), outline=(66,145,215), width=4)
        prompt = "Название документа или темы"
        draw.text((290, 545), prompt, font=_fit_text(draw, prompt, 1250, 42, 30), fill=(42,57,76))
        draw.ellipse((1535, 535, 1600, 600), outline=(56,157,216), width=7)
        draw.line((1580, 580, 1625, 625), fill=(56,157,216), width=9)
    elif phase == 1:
        draw.text((240, 415), "РЕЗУЛЬТАТЫ ПОИСКА", font=_font(30, True), fill=(41,59,79))
        for i in range(3):
            yy = 490 + i*125
            draw.text((260, yy), f"Материал {i+1}", font=_font(29, True), fill=(34,92,151))
            draw.rounded_rectangle((260, yy+48, 1430-i*90, yy+60), radius=6, fill=(126,151,172))
            draw.rounded_rectangle((260, yy+73, 1280-i*80, yy+84), radius=6, fill=(190,202,213))
    elif failed_page:
        draw.text((260, 420), "404", font=_font(205, True), fill=(205,57,72))
        draw.text((275, 665), "СТРАНИЦА НЕ НАЙДЕНА", font=_font(40, True), fill=(48,61,77))
        for i in range(4):
            draw.rounded_rectangle((1000, 500+i*65, 1510-i*75, 514+i*65), radius=7, fill=(180,195,207))
    else:
        draw.text((260, 420), "ПЕРВОИСТОЧНИК", font=_font(75, True), fill=(42,92,142))
        draw.text((260, 545), "АВТОР · ДОКУМЕНТ · ДАТА", font=_font(34, True), fill=(76,97,117))
        for i in range(4):
            draw.rounded_rectangle((260, 625+i*52, 1500-i*90, 638+i*52), radius=7, fill=(180,195,207))
    draw.rounded_rectangle((150, 985, 600, 1035), radius=18, fill=(14,29,46), outline=(79,112,142), width=2)
    draw.text((180, 995), "УСЛОВНАЯ ИЛЛЮСТРАЦИЯ", font=_font(17, True), fill=(191,207,220))
    return ["Учебная симуляция", "Поиск первоисточника"]

def _draw_tokens(draw: ImageDraw.ImageDraw, beat: dict[str, Any], phase: int) -> list[str]:
    # A deliberately conditional illustration, not a claim about a specific tokenizer.
    draw.text((120, 300), "КАК ТЕКСТ ПРЕВРАЩАЕТСЯ В ТОКЕНЫ", font=_font(31, True), fill=MUTED)
    word = "НЕЙРОСЕТЬ"
    if phase == 0:
        draw.text((190, 510), word, font=_font(150, True), fill=WHITE)
        draw.line((190, 700, 930, 700), fill=PURPLE, width=8)
        return ["Условный пример"]
    parts = [("НЕЙРО", PURPLE), ("СЕТЬ", CYAN)]
    positions = [(240, 475), (850, 475)]
    for index, (label, color) in enumerate(parts):
        x, y = positions[index]
        draw.rounded_rectangle((x, y, x+500, y+200), radius=34, fill=(30,35,65), outline=color, width=7)
        draw.text((x+45, y+48), label, font=_font(78, True), fill=WHITE)
        if phase == 2 and index == 1:
            draw.ellipse((x+420, y-30, x+540, y+90), fill=(*color,), outline=WHITE, width=5)
    if phase == 2:
        draw.text((260, 790), "ЧАСТИ ТЕКСТА → ПОСЛЕДОВАТЕЛЬНОСТЬ", font=_font(33, True), fill=CYAN)
    draw.text((260, 905), "УСЛОВНАЯ СХЕМА · ГРАНИЦЫ ЗАВИСЯТ ОТ ТОКЕНИЗАТОРА",
              font=_font(20, True), fill=MUTED)
    return ["Условный пример токенизации"]


def _draw_phone(draw: ImageDraw.ImageDraw, beat: dict[str, Any], phase: int) -> list[str]:
    """Illustrate predictive input without copying any words from the narration."""
    x0, y0, x1, y1 = 650, 230, 1270, 1000
    draw.rounded_rectangle((x0, y0, x1, y1), radius=85, fill=(7,12,23), outline=(145,118,232), width=8)
    draw.rounded_rectangle((x0+24, y0+34, x1-24, y1-40), radius=62, fill=(31,31,57))
    draw.rounded_rectangle((x0+225, y0+12, x0+395, y0+28), radius=8, fill=(78,82,104))
    draw.text((x0+80, y0+130), "ПОДСКАЗКИ ПРИ ВВОДЕ", font=_font(27, True), fill=MUTED)
    draw.rounded_rectangle((x0+70, y0+220, x0+545, y0+325), radius=18, fill=(48,51,78), outline=CYAN, width=3)
    draw.rounded_rectangle((x0+95, y0+262, x0+370, y0+275), radius=6, fill=WHITE)
    suggestions = ["ВАРИАНТ 1", "ВАРИАНТ 2", "ВАРИАНТ 3"]
    for i, label in enumerate(suggestions):
        bx = x0+55+i*165
        draw.rounded_rectangle((bx, y0+355, bx+150, y0+435), radius=20,
                               fill=(54,48,89), outline=[CYAN,PURPLE,ORANGE][i], width=3)
        draw.text((bx+13, y0+383), label, font=_font(20, True), fill=WHITE)
    for row in range(3):
        for col in range(3):
            bx = x0+74+col*145
            by = y0+510+row*112
            draw.rounded_rectangle((bx,by,bx+122,by+78), radius=16,
                                   fill=(60,64,94), outline=(126,133,169), width=2)
            draw.text((bx+49,by+20), "АБВ"[col], font=_font(25, True), fill=WHITE)
    return ["Предиктивный ввод"]

def _draw_archive(draw: ImageDraw.ImageDraw, beat: dict[str, Any], phase: int) -> list[str]:
    accent = ORANGE if phase < 2 else CYAN
    if phase < 2:
        # Perspective archive shelves with visible paper spines.
        for row in range(3):
            y = 410 + row*185
            draw.rectangle((160,y+125,1760,y+150), fill=(105,73,47))
            for col in range(12):
                x = 185+col*130
                height = 92 + ((col*43+row*17)%55)
                draw.rounded_rectangle((x,y+125-height,x+92,y+118), radius=5,
                                       fill=[(129,83,55),(159,111,72),(89,113,125)][(col+row)%3],
                                       outline=(221,185,134), width=2)
                draw.line((x+16,y+95-height,x+16,y+110-height), fill=(234,211,178), width=4)
        if phase == 1:
            draw.rounded_rectangle((700,330,1220,465),radius=24,fill=(22,31,46),outline=accent,width=4)
            draw.text((770,370),"ПОИСК В АРХИВЕ",font=_font(38,True),fill=WHITE)
    else:
        _draw_network_field(draw, phase)
    return ["Архив" if phase < 2 else "Модель как процесс"]


def _draw_network_field(draw: ImageDraw.ImageDraw, phase: int) -> list[str]:
    nodes = [(330,500),(600,340),(810,650),(1080,360),(1330,590),(1580,410),(1480,820),(850,890),(470,830)]
    edges = [(0,1),(0,2),(1,2),(1,3),(2,3),(2,4),(3,4),(3,5),(4,5),(4,6),(2,7),(0,8),(7,8),(6,7)]
    highlight = {phase % len(nodes), (phase+2) % len(nodes), (phase+4) % len(nodes)}
    for a,b in edges:
        color = CYAN if a in highlight and b in highlight else (73,103,144)
        draw.line((*nodes[a],*nodes[b]), fill=color, width=7 if color == CYAN else 3)
    for i,(x,y) in enumerate(nodes):
        radius = 32 if i in highlight else 20
        color = CYAN if i in highlight else (70,108,153)
        draw.ellipse((x-radius,y-radius,x+radius,y+radius), fill=color, outline=WHITE, width=3)
    return ["Сеть взаимосвязей"]


def _draw_probability(draw: ImageDraw.ImageDraw, beat: dict[str, Any], phase: int) -> list[str]:
    """Show competing continuations without inventing values or echoing narration."""
    labels = ["ВАРИАНТ А", "ВАРИАНТ Б", "ВАРИАНТ В", "ВАРИАНТ Г"]
    base_y = 470
    for i, label in enumerate(labels):
        x = 170+i*430
        height = [190,285,230,330][(i+phase)%4]
        color = [BLUE,CYAN,PURPLE,ORANGE][i]
        draw.rounded_rectangle((x,base_y-height,x+250,base_y),radius=24,fill=(29,37,61),outline=color,width=5)
        draw.text((x+18,base_y-height+32),label,font=_fit_text(draw,label,215,30,21),fill=WHITE)
        draw.rounded_rectangle((x+45,base_y+35,x+205,base_y+35+height//2),radius=14,fill=(42,49,74),outline=color,width=3)
        if i == phase % len(labels):
            draw.ellipse((x+90,base_y+70,x+160,base_y+140),fill=color)
    draw.text((150,900),"УСЛОВНАЯ СХЕМА · НЕ РЕАЛЬНЫЕ ВЕРОЯТНОСТИ",
              font=_font(20,True),fill=MUTED)
    return ["Схема вероятностного выбора"]

def _draw_warning(draw: ImageDraw.ImageDraw, beat: dict[str, Any], phase: int) -> list[str]:
    if phase == 0:
        draw.text((165,340),"УВЕРЕННЫЙ ТОН",font=_font(43,True),fill=MUTED)
        draw.text((165,455),"≠",font=_font(215,True),fill=RED)
        draw.text((590,505),"ПРОВЕРЕННЫЙ ФАКТ",font=_fit_text(draw,"ПРОВЕРЕННЫЙ ФАКТ",1080,74,44),fill=WHITE)
    elif phase == 1:
        # A large response glyph and confidence signal, not a miniature chat-window card.
        draw.rounded_rectangle((300,370,1620,710),radius=62,fill=(34,35,56),outline=RED,width=5)
        draw.text((390,455),"ОТВЕТ",font=_font(35,True),fill=MUTED)
        draw.text((390,535),"ЗВУЧИТ УБЕДИТЕЛЬНО",font=_fit_text(draw,"ЗВУЧИТ УБЕДИТЕЛЬНО",1100,82,48),fill=WHITE)
        draw.ellipse((1410,430,1540,560),outline=ORANGE,width=9)
        draw.text((1437,437),"!",font=_font(98,True),fill=ORANGE)
    else:
        _draw_network_field(draw, phase)
        draw.rounded_rectangle((555,120,1370,260),radius=32,fill=(22,30,48),outline=RED,width=4)
        draw.text((650,162),"НУЖНА ПРОВЕРКА",font=_font(45,True),fill=WHITE)
    return ["Тон не доказывает точность"]


def _draw_research(draw: ImageDraw.ImageDraw, beat: dict[str, Any], phase: int) -> list[str]:
    if phase == 0:
        draw.text((150,355),"УТВЕРЖДЕНИЕ",font=_font(37,True),fill=MUTED)
        draw.text((150,460),"НАЙТИ ПЕРВОИСТОЧНИК",font=_fit_text(draw,"НАЙТИ ПЕРВОИСТОЧНИК",1350,90,50),fill=WHITE)
        draw.ellipse((1450,360,1710,620),outline=CYAN,width=18)
        draw.line((1650,570,1775,695),fill=CYAN,width=26)
    else:
        for i in range(3):
            x=175+i*560
            draw.rounded_rectangle((x,370,x+440,790),radius=26,fill=(18,33,53),outline=[BLUE,CYAN,PURPLE][i],width=4)
            draw.text((x+34,420),["ЗАЯВЛЕНИЕ","ИСТОЧНИК","КОНТЕКСТ"][i],font=_font(27,True),fill=MUTED)
            for j in range(4):
                y=510+j*55
                draw.rounded_rectangle((x+35,y,x+350-(j%2)*55,y+11),radius=5,fill=(115,142,169))
            if i < 2:
                draw.line((x+450,590,x+530,590),fill=CYAN,width=8)
                draw.polygon([(x+530,590),(x+506,572),(x+506,608)],fill=CYAN)
    return ["Проверка первоисточника"]


def _draw_human(draw: ImageDraw.ImageDraw, beat: dict[str, Any], phase: int) -> list[str]:
    # Abstract editorial silhouette; not a fake photograph or identifiable person.
    cx, cy = (620 if phase % 2 == 0 else 1290), 620
    draw.ellipse((cx-150,cy-300,cx+150,cy),fill=(180,133,112))
    draw.rounded_rectangle((cx-245,cy-30,cx+245,cy+425),radius=110,fill=(45,78,112))
    draw.text((920,440),"ЧЕЛОВЕК",font=_font(55,True),fill=WHITE)
    draw.text((920,535),"ПРОВЕРЯЕТ",font=_font(55,True),fill=CYAN)
    return ["Иллюстративная фигура"]


def _draw_abstract(draw: ImageDraw.ImageDraw, beat: dict[str, Any], phase: int) -> list[str]:
    """Draw an explanatory abstract system; narration is never used as labels."""
    points = []
    for i in range(7):
        angle = math.radians(phase*12 + i*360/7)
        cx = int(960 + math.cos(angle)*430)
        cy = int(570 + math.sin(angle)*260)
        points.append((cx,cy))
    for i in range(len(points)):
        for j in range(i+1,len(points)):
            if (i+j+phase) % 3 == 0:
                draw.line((*points[i],*points[j]),fill=(65,101,145),width=4)
    for i,(cx,cy) in enumerate(points):
        color = [CYAN,BLUE,PURPLE,ORANGE][(i+phase)%4]
        radius = 48 + (i%3)*10
        draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),
                     fill=(24,35,61),outline=color,width=7)
    return ["Абстрактная схема связей"]

# ENGINE2 SEMANTIC MOTION UPGRADE 2.1.0
_ANIMATED_MOTIFS = {
    "chat", "crystal", "stamp", "glitch", "trap", "mechanism", "typography", "comparison"
}
_ANIMATION_WIDTH = 1280
_ANIMATION_HEIGHT = 720


def _draw_gear(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int,
               angle: float, color: tuple[int, int, int]) -> None:
    points = []
    teeth = 12
    for i in range(teeth * 4):
        a = angle + (math.pi * 2 * i / (teeth * 4))
        r = radius if i % 4 in (0, 1) else radius * 0.84
        points.append((int(cx + math.cos(a) * r), int(cy + math.sin(a) * r)))
    draw.polygon(points, fill=color, outline=PALE)
    inner = int(radius * 0.72)
    draw.ellipse((cx-inner, cy-inner, cx+inner, cy+inner), fill=(23, 34, 53), outline=PALE, width=7)
    hub = max(18, radius // 7)
    draw.ellipse((cx-hub, cy-hub, cx+hub, cy+hub), fill=ORANGE, outline=WHITE, width=4)
    for spoke in range(4):
        a = angle + spoke * math.pi / 2
        ex = int(cx + math.cos(a) * inner * 0.82)
        ey = int(cy + math.sin(a) * inner * 0.82)
        draw.line((cx, cy, ex, ey), fill=PALE, width=9)


def _semantic_motion_frame(motif: str, beat: dict[str, Any], progress: float,
                           background: Image.Image | None = None) -> Image.Image:
    """Draw one continuous animation frame for a concrete shot-level motif."""
    if motif not in _ANIMATED_MOTIFS:
        raise ValueError(f"Unsupported semantic animation motif: {motif}")
    t = max(0.0, min(1.0, float(progress)))
    image = (background.copy() if background is not None else _background(motif, 0)).convert("RGB")
    draw = ImageDraw.Draw(image)

    if motif == "chat":
        # Full-size training simulation: the query is typed, then a response is composed.
        x0, y0, x1, y1 = 220, 185, 1700, 930
        draw.rounded_rectangle((x0, y0, x1, y1), radius=42, fill=(13, 29, 45), outline=(83, 139, 170), width=5)
        draw.text((x0+55, y0+36), "УЧЕБНАЯ СИМУЛЯЦИЯ · ЧАТ", font=_font(27, True), fill=MUTED)
        draw.ellipse((x0+1370, y0+38, x0+1394, y0+62), fill=GREEN)
        # A neutral illustrative prompt, never a fragment of the narrator's speech.
        prompt = "Ваш запрос к модели"
        typed = max(1, min(len(prompt), int(len(prompt) * min(1.0, t * 1.9))))
        draw.rounded_rectangle((x0+90, y0+155, x1-110, y0+315), radius=28, fill=(29, 56, 76), outline=CYAN, width=3)
        draw.text((x0+130, y0+195), prompt[:typed], font=_fit_text(draw, prompt[:typed], 1190, 43, 28), fill=WHITE)
        cursor_x = min(x0+130+len(prompt[:typed])*22, x1-170)
        draw.rounded_rectangle((cursor_x, y0+188, cursor_x+5, y0+260), radius=2, fill=CYAN)
        if t > 0.42:
            reveal = min(1.0, (t-0.42)/0.42)
            bx, by = x0+420, y0+390
            draw.rounded_rectangle((bx, by, x1-100, by+260), radius=28, fill=(31, 39, 61), outline=PURPLE, width=3)
            draw.text((bx+38, by+35), "ОТВЕТ МОДЕЛИ", font=_font(25, True), fill=PURPLE)
            lines = 1 + int(reveal * 4)
            for i in range(lines):
                yy = by+100+i*34
                width = int((820 - (i % 2)*120) * min(1.0, max(0.15, reveal*1.7)))
                draw.rounded_rectangle((bx+40, yy, bx+40+width, yy+10), radius=5, fill=(177, 194, 210))

    elif motif == "crystal":
        # A faceted answer object grows out of a stream of data particles.
        cx, cy = 960, 545
        scale = 0.32 + 0.68 * (0.5 - 0.5 * math.cos(math.pi * t))
        radius = int(245 * scale)
        for i in range(28):
            a = i * math.tau / 28 + t * 1.4
            orbit = 350 + 35 * math.sin(t * math.tau + i)
            px, py = int(cx + math.cos(a)*orbit), int(cy + math.sin(a)*orbit*0.62)
            pr = 4 + (i % 4)
            draw.ellipse((px-pr, py-pr, px+pr, py+pr), fill=[CYAN, BLUE, ORANGE][i % 3])
        pts = [(cx, cy-radius), (cx+int(radius*.72), cy-int(radius*.18)),
               (cx+int(radius*.52), cy+int(radius*.74)), (cx, cy+radius),
               (cx-int(radius*.52), cy+int(radius*.74)), (cx-int(radius*.72), cy-int(radius*.18))]
        draw.polygon(pts, fill=(85, 91, 144), outline=(255, 218, 155), width=8)
        draw.polygon([pts[0], pts[1], (cx, cy+int(radius*.12))], fill=(155, 191, 235))
        draw.polygon([pts[0], pts[5], (cx, cy+int(radius*.12))], fill=(101, 131, 203))
        draw.polygon([(cx, cy+int(radius*.12)), pts[1], pts[2], pts[3]], fill=(74, 74, 128))
        draw.polygon([(cx, cy+int(radius*.12)), pts[5], pts[4], pts[3]], fill=(111, 76, 153))
        draw.line((cx, cy-radius, cx, cy+radius), fill=(255, 236, 196), width=5)
        if t > 0.72:
            halo = 5 + int(7 * (0.5 + 0.5 * math.sin(t * math.tau * 2)))
            draw.ellipse((cx-radius-32, cy-radius-32, cx+radius+32, cy+radius+32), outline=ORANGE, width=halo)

    elif motif == "stamp":
        # A robotic stamping arm descends; the confident mark is then questioned.
        draw.rounded_rectangle((355, 205, 1565, 955), radius=18, fill=(226, 231, 235), outline=(154, 174, 188), width=5)
        draw.text((455, 285), "ОТВЕТ МОДЕЛИ", font=_font(34, True), fill=(46, 63, 80))
        for i in range(5):
            yy = 375 + i*72
            draw.rounded_rectangle((460, yy, 1360-(i%2)*140, yy+12), radius=5, fill=(150, 166, 178))
        elbow = (1450, 185)
        wrist = (1190, 350 + int(135*math.sin(t*math.pi)))
        head_y = 350 + int(300*math.sin(t*math.pi))
        draw.line((1580, 110, elbow[0], elbow[1], wrist[0], wrist[1]), fill=(116, 139, 161), width=48, joint="curve")
        draw.ellipse((elbow[0]-48, elbow[1]-48, elbow[0]+48, elbow[1]+48), fill=BLUE, outline=WHITE, width=7)
        draw.ellipse((wrist[0]-42, wrist[1]-42, wrist[0]+42, wrist[1]+42), fill=CYAN, outline=WHITE, width=7)
        draw.line((wrist[0], wrist[1], 960, head_y), fill=(158, 174, 189), width=34)
        draw.rounded_rectangle((820, head_y-8, 1100, head_y+112), radius=18, fill=(45, 52, 72), outline=RED, width=7)
        draw.rectangle((850, head_y+82, 1070, head_y+128), fill=(185, 53, 67), outline=(255, 140, 143), width=5)
        if t > 0.48:
            alpha = int(100 + 155*min(1.0, (t-.48)/.25))
            draw.rounded_rectangle((650, 625, 1260, 790), radius=16, outline=(210, 48, 63), width=18)
            draw.text((720, 665), "ВЕРНО", font=_font(104, True), fill=(195, 45, 59))
            if t > 0.78:
                draw.line((670, 620, 1250, 805), fill=(35, 37, 47), width=15)
                draw.text((670, 830), "ПЕЧАТЬ НЕ ЗАМЕНЯЕТ ПРОВЕРКУ", font=_font(25, True), fill=(63, 69, 78))

    elif motif == "glitch":
        # Binary/data field bends; a document-like signal breaks into offset fragments.
        for row in range(12):
            y = 170 + row*68
            shift = int(math.sin(t*math.tau*1.4 + row*.83)*95)
            text = "01010110 10100101 01101001 11001010"
            x = 80 + shift
            color = (70, 116, 160) if row % 3 else (111, 78, 164)
            draw.text((x, y), text, font=_font(31, True), fill=color)
        label = "ОТВЕТ"
        base_x, base_y = 570, 450
        jitter = int((1.0-t)*18*math.sin(t*math.tau*5))
        draw.text((base_x+jitter-8, base_y), label, font=_font(118, True), fill=(90, 210, 220))
        draw.text((base_x-jitter+8, base_y+8), label, font=_font(118, True), fill=(220, 80, 120))
        draw.text((base_x, base_y+4), label, font=_font(118, True), fill=WHITE)
        for band in range(5):
            y = 405 + band*76 + int(math.sin(t*math.tau*2+band)*28)
            x = int(180 + ((t*900 + band*310) % 1400))
            width = 120 + (band%3)*95
            draw.rectangle((x, y, min(W-90, x+width), y+9+(band%2)*8), fill=[CYAN, PURPLE, RED][band%3])
        if t > .62:
            draw.text((545, 690), "СИГНАЛ ИСКАЖЁН", font=_font(35, True), fill=ORANGE)

    elif motif == "trap":
        # The data particle approaches a trap whose jaws close and reopen.
        hinge_y = 715
        close = 0.5 - 0.5*math.cos(math.pi*min(1.0, t*1.5))
        spread = 250*(1.0-close) + 42
        apex_y = 390 + int(close*180)
        left = (960-int(spread), apex_y)
        right = (960+int(spread), apex_y)
        draw.line((560, hinge_y, 1360, hinge_y), fill=(162, 177, 188), width=28)
        draw.line((560, hinge_y, 960, 820), fill=GREEN, width=17)
        draw.line((1360, hinge_y, 960, 820), fill=GREEN, width=17)
        draw.polygon([(560, hinge_y), left, (960, 820)], fill=(45, 92, 84), outline=PALE)
        draw.polygon([(1360, hinge_y), right, (960, 820)], fill=(45, 92, 84), outline=PALE)
        for i in range(7):
            xx = 610+i*115
            draw.polygon([(xx, hinge_y), (xx+48, hinge_y-68), (xx+82, hinge_y)], fill=(177, 199, 190))
        particle_x = int(180 + min(1.0, t*1.3)*690)
        particle_y = 465 + int(math.sin(t*math.tau*2)*34)
        draw.ellipse((particle_x-28, particle_y-28, particle_x+28, particle_y+28), fill=CYAN, outline=WHITE, width=5)
        for i in range(5):
            px = particle_x-110-i*36
            draw.ellipse((px-5, particle_y-5, px+5, particle_y+5), fill=BLUE)
        if t > .72:
            draw.text((760, 250), "ЛОВУШКА", font=_font(43, True), fill=ORANGE)

    elif motif == "mechanism":
        angle = t*math.tau*1.4
        _draw_gear(draw, 650, 565, 190, angle, (63, 113, 158))
        _draw_gear(draw, 1035, 565, 145, -angle*190/145, (105, 88, 150))
        _draw_gear(draw, 1370, 565, 112, angle*190/112, (156, 104, 57))
        draw.line((250, 850, 1670, 850), fill=(81, 112, 145), width=5)
        for i in range(9):
            x = int(280+i*170 + (t*500 % 170))
            draw.ellipse((x-12, 825, x+12, 849), fill=[CYAN, ORANGE, PURPLE][i%3])
        draw.text((600, 895), "СВЯЗАННЫЕ ЭТАПЫ РАБОТЫ", font=_font(33, True), fill=PALE)

    elif motif == "typography":
        labels = _clean_labels(beat)
        if labels:
            # Render the director's actual label instead of substituting generic warning copy.
            word = labels[0].upper()
            font = _fit_text(draw, word, 1450, start=132, minimum=54)
            box = draw.textbbox((0, 0), word, font=font)
            x = (W-(box[2]-box[0]))//2
            y = 455
            draw.text((x, y), word, font=font, fill=WHITE)
            reveal = max(0.0, min(1.0, t*1.25))
            draw.line((x, y+box[3]+28, int(x+(box[2]-box[0])*reveal), y+box[3]+28), fill=CYAN, width=14)
            # Small moving signal under the underline makes the label visibly animate.
            marker_x = int(x+(box[2]-box[0])*reveal)
            draw.ellipse((marker_x-13, y+box[3]+10, marker_x+13, y+box[3]+46), fill=ORANGE)
        else:
            words = [("КАЖЕТСЯ", 300), ("ВОЗМОЖНО", 470), ("ФАКТ", 675)]
            for index, (word, y) in enumerate(words):
                font = _font(94 if index < 2 else 128, True)
                box = draw.textbbox((0, 0), word, font=font)
                x = (W-(box[2]-box[0]))//2
                draw.text((x, y), word, font=font, fill=WHITE if index < 2 else CYAN)
                if index < 2:
                    amount = max(0.0, min(1.0, (t-index*.12)*1.55))
                    x2 = int(x+(box[2]-box[0])*amount)
                    draw.line((x, y+112, x2, y+112), fill=RED, width=12)
                else:
                    pulse = 4 + int(8*(0.5+0.5*math.sin(t*math.tau*2)))
                    draw.rounded_rectangle((x-28, y-20, x+box[2]+28, y+148), radius=20, outline=CYAN, width=pulse)

    elif motif == "comparison":
        # Contrast a static archive with a connected, changing network.
        draw.text((280, 225), "АРХИВ", font=_font(42, True), fill=ORANGE)
        draw.text((1190, 225), "СЕТЬ СВЯЗЕЙ", font=_font(42, True), fill=CYAN)
        for row in range(3):
            for col in range(4):
                x, y = 245+col*145, 370+row*150
                draw.rectangle((x, y, x+108, y+112), fill=(114, 79, 54), outline=(221, 185, 134), width=3)
                draw.line((x+18, y+28, x+88, y+28), fill=(232, 207, 174), width=5)
        nodes = [(1190,390),(1430,365),(1290,570),(1545,610),(1160,770),(1450,820)]
        edges = [(0,1),(0,2),(1,2),(1,3),(2,3),(2,4),(3,5),(4,5)]
        pulse = int(80+120*(0.5+0.5*math.sin(t*math.tau*2)))
        for a,b in edges:
            draw.line((*nodes[a], *nodes[b]), fill=(55, 120, pulse), width=7)
        for i,(x,y) in enumerate(nodes):
            r = 27 + int(8*(0.5+0.5*math.sin(t*math.tau*2+i)))
            draw.ellipse((x-r,y-r,x+r,y+r), fill=CYAN if i%2==0 else BLUE, outline=WHITE, width=3)
        arrow_x = int(800 + 250*t)
        draw.line((760, 590, arrow_x, 590), fill=PALE, width=10)
        draw.polygon([(arrow_x+28,590),(arrow_x-8,567),(arrow_x-8,613)], fill=PALE)

    return image


def _render_object_animation(ffmpeg: str, output_path: Path, duration: float,
                              motif: str, beat: dict[str, Any], fps: int) -> Path:
    """Stream procedurally moving Pillow frames to FFmpeg without storing a frame sequence."""
    anim_fps = min(20, fps)
    anim_frames = max(1, int(round(float(duration)*anim_fps)))
    output_frames = max(1, int(round(float(duration)*fps)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(output_path.stem + ".semantic.tmp" + output_path.suffix)
    temp_output.unlink(missing_ok=True)
    background = _background(motif, 0).convert("RGB")
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", f"{_ANIMATION_WIDTH}x{_ANIMATION_HEIGHT}",
        "-framerate", str(anim_fps), "-i", "pipe:0",
        "-an", "-vf", f"scale={W}:{H}:flags=lanczos,fps={fps},format=yuv420p",
        "-frames:v", str(output_frames), "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(temp_output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE)
    write_error: Exception | None = None
    try:
        assert process.stdin is not None
        for index in range(anim_frames):
            progress = 0.0 if anim_frames == 1 else index/(anim_frames-1)
            frame = _semantic_motion_frame(motif, beat, progress, background)
            frame = frame.resize((_ANIMATION_WIDTH, _ANIMATION_HEIGHT), Image.Resampling.LANCZOS)
            process.stdin.write(frame.tobytes())
        process.stdin.close()
    except Exception as exc:
        write_error = exc
        if process.stdin and not process.stdin.closed:
            try:
                process.stdin.close()
            except OSError:
                pass
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    return_code = process.wait()
    if write_error or return_code != 0 or not temp_output.is_file() or temp_output.stat().st_size < 1024:
        temp_output.unlink(missing_ok=True)
        reason = str(write_error) if write_error else (stderr[-5000:] or f"FFmpeg exit code {return_code}")
        raise RuntimeError("Semantic motion animation failed: " + reason)
    temp_output.replace(output_path)

    labels = _clean_labels(beat)
    metadata = {
        "render_version": "2.1.0",
        "template_id": f"motion_{motif}",
        "visual_family": motif,
        "source": "AI Video Factory original motion graphics",
        "animation_mode": "procedural_object_motion",
        "animation_fps": anim_fps,
        "motion_frame_count": anim_frames,
        "keyframe_count": 1,
        "frame_count": output_frames,
        "transition": "continuous_object_motion",
        "duration_seconds": round(output_frames/fps, 4),
        "requested_duration_seconds": round(float(duration), 4),
        "fps": fps,
        "dimensions": [W, H],
        "visible_text": labels,
        "description_rendered": False,
        "visual_description_used": True,
        "motif_routing": "shot_visual_description_first",
        "semantic_frame_to_speech": "human_review_required",
    }
    output_path.with_suffix(output_path.suffix + ".meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


_DRAWERS = {
    "browser": _draw_browser,
    "tokens": _draw_tokens,
    "phone": _draw_phone,
    "archive": _draw_archive,
    "probability": _draw_probability,
    "warning": _draw_warning,
    "research": _draw_research,
    "network": _draw_network_field,
    "human": _draw_human,
    "abstract": _draw_abstract,
}


def _make_keyframe(scene: dict[str, Any], beat: dict[str, Any],
                   motif: str, phase: int, count: int) -> tuple[Image.Image, list[str]]:
    image = _background(motif, phase).convert("RGBA")
    draw = ImageDraw.Draw(image)
    title_visible = _draw_title(draw, beat, phase)
    drawer = _DRAWERS[motif]
    if motif in ("browser",):
        content_visible = drawer(image, draw, beat, phase)
    else:
        # Some drawers only need a drawing context; background is shared and text remains private.
        if motif == "network":
            content_visible = drawer(draw, phase)
        elif motif in ("tokens","phone","archive","probability","warning","research","human","abstract"):
            content_visible = drawer(draw, beat, phase)
        else:
            content_visible = drawer(draw, beat, phase)
    # Editorial marker is deliberately small and unobtrusive, not a repeated giant card heading.
    return image.convert("RGB"), [x for x in title_visible + content_visible if x]


def render_motion_graphic(settings: Any, scene: dict[str, Any], beat: dict[str, Any],
                          output_path: Path, duration: float) -> Path:
    """Render a semantic animated clip from 1–3 designed keyframes.

    Each keyframe becomes a short CFR H.264 shot with its own camera movement.
    The shots are then concatenated losslessly. Hard cuts are intentional editorial
    changes; no crossfade filter is used because some FFmpeg builds report an
    unspecified frame rate for image-loop/zoompan inputs to xfade.
    """
    if duration <= 0.4:
        raise ValueError(f"Motion graphic duration is too short: {duration}")
    ffmpeg = str(getattr(settings, "ffmpeg", "ffmpeg"))
    fps = int(getattr(settings, "fps", FPS) or FPS)
    if fps < 12 or fps > 60:
        raise ValueError(f"Unsupported motion graphics FPS: {fps}")

    motif = _motif(scene, beat)
    if motif in _ANIMATED_MOTIFS:
        return _render_object_animation(ffmpeg, output_path, duration, motif, beat, fps)
    count = 3 if duration >= 4.2 else (2 if duration >= 1.8 else 1)
    scratch = output_path.parent / (output_path.stem + "_keyframes")
    scratch.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    visible_text: list[str] = []
    for phase in range(count):
        frame, visible = _make_keyframe(scene, beat, motif, phase, count)
        frame_path = scratch / f"keyframe_{phase+1:02d}.png"
        frame.save(frame_path, format="PNG", optimize=True)
        frame_paths.append(frame_path)
        for value in visible:
            if value and value not in visible_text:
                visible_text.append(value)

    # Slightly vary the camera direction per keyframe to avoid the same zoom on
    # every illustration while keeping the text and central subject readable.
    # Allocate a single integer frame budget across all keyframes. Rendering
    # each segment from an independently rounded decimal duration can add up
    # to several extra frames (e.g. 3 x 1.68 s for a 5 s clip at 25 fps).
    total_frames = max(count, int(round(float(duration) * fps)))
    base_frames, extra_frames = divmod(total_frames, count)
    frame_counts = [base_frames + (1 if i < extra_frames else 0) for i in range(count)]
    segment_paths: list[Path] = []
    for index, frame_path in enumerate(frame_paths):
        segment_frames = frame_counts[index]
        segment_duration = segment_frames / fps
        segment = scratch / f"motion_{index+1:02d}.mp4"
        if index % 3 == 0:
            x_expr = "iw/2-(iw/zoom/2)+sin(on/41)*13"
            zoom_expr = "min(zoom+0.00038,1.055)"
        elif index % 3 == 1:
            x_expr = "iw/2-(iw/zoom/2)-on*0.18"
            zoom_expr = "min(zoom+0.00028,1.045)"
        else:
            x_expr = "iw/2-(iw/zoom/2)"
            zoom_expr = "max(1.0,1.055-on*0.00032)"
        vf = (
            "scale=2200:1238:force_original_aspect_ratio=increase,crop=2200:1238,"
            f"zoompan=z='{zoom_expr}':x='{x_expr}':"
            f"y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps},"
            f"setsar=1,format=yuv420p"
        )
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-framerate", str(fps),
            "-i", str(frame_path), "-an", "-vf", vf,
            "-frames:v", str(segment_frames), "-r", str(fps),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(segment),
        ]
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if result.returncode != 0 or not segment.is_file() or segment.stat().st_size < 1024:
            raise RuntimeError(
                "FFmpeg motion keyframe render failed: " +
                (result.stderr[-5000:] or "empty output")
            )
        segment_paths.append(segment)

    concat_path = scratch / "motion.ffconcat"
    concat_lines = ["ffconcat version 1.0"]
    for segment in segment_paths:
        safe = str(segment.resolve()).replace("\\", "/").replace("'", "'\\''")
        concat_lines.append(f"file '{safe}'")
    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(output_path.stem + ".tmp" + output_path.suffix)
    concat_command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat_path),
        "-an", "-c", "copy", "-frames:v", str(total_frames),
        "-movflags", "+faststart", str(temp_output),
    ]
    result = subprocess.run(concat_command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0 or not temp_output.is_file() or temp_output.stat().st_size < 1024:
        temp_output.unlink(missing_ok=True)
        raise RuntimeError(
            "FFmpeg motion clip assembly failed: " +
            (result.stderr[-5000:] or "empty output")
        )
    temp_output.replace(output_path)

    metadata = {
        "render_version": "2.0.0",
        "template_id": f"motion_{motif}",
        "visual_family": motif,
        "source": "AI Video Factory original motion graphics",
        "keyframe_count": count,
        "frame_count": total_frames,
        "transition": "editorial_cut",
        "duration_seconds": round(total_frames / fps, 4),
        "requested_duration_seconds": round(float(duration), 4),
        "fps": fps,
        "dimensions": [W, H],
        "visible_text": visible_text,
        "description_rendered": False,
        "semantic_frame_to_speech": "human_review_required",
    }
    output_path.with_suffix(output_path.suffix + ".meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path
