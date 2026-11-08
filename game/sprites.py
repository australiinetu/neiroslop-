# -*- coding: utf-8 -*-
"""Спрайты зверей и людей (вид сверху), нарисованные кодом. Базовый спрайт смотрит вправо (на восток),
при отрисовке поворачивается в сторону движения. Кадры 0..3 — шаги (лапы/ноги двигаются)."""
import math

import pygame

OUT = (28, 22, 18)
_base = {}
_avatar = {}

SIZES = {"rabbit": 44, "fox": 60, "deer": 84, "boar": 66, "bear": 100, "wolf": 76, "alpha": 92, "moose": 110,
         "snake": 64, "human": 52, "dog": 68}


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _e(s, col, cx, cy, w, h, width=0):
    pygame.draw.ellipse(s, col, pygame.Rect(round(cx - w / 2), round(cy - h / 2), round(w), round(h)), width)


def _eo(s, col, cx, cy, w, h):
    """Эллипс с контуром."""
    _e(s, col, cx, cy, w, h)
    _e(s, OUT, cx, cy, w, h, 2)


def _legs(s, cx, cy, half_len, half_w, col, f, foot, stride):
    """Четыре лапы: диагональные пары шагают вместе."""
    d = math.sin(f * math.pi / 2) * stride
    for lx, ly, sign in ((1, -1, 1), (1, 1, -1), (-1, -1, -1), (-1, 1, 1)):
        x = cx + lx * half_len + sign * d
        y = cy + ly * half_w
        _eo(s, col, x, y, foot * 1.5, foot)


def _rabbit(s, c, f, col):
    _legs(s, c, c, 6, 6, shade(col, 0.8), f, 5, 2.5)
    _eo(s, (245, 245, 245), c - 11, c, 8, 8)                       # белый хвостик
    _eo(s, col, c - 1, c, 22, 15)
    _eo(s, shade(col, 1.08), c + 10, c, 12, 11)                     # голова
    for sg in (-1, 1):                                              # длинные уши назад
        _eo(s, shade(col, 0.95), c + 2, c + sg * 4, 15, 5)
        _e(s, (235, 175, 175), c + 3, c + sg * 4, 9, 2)
        pygame.draw.circle(s, (20, 20, 20), (c + 13, c + sg * 3), 2)
    pygame.draw.circle(s, (230, 140, 150), (c + 16, c), 2)


def _canine(s, c, f, col, k, tail_tip=None, legs=None, scar=False):
    L, W = 17 * k, 7 * k
    _legs(s, c, c, L * 0.55, W * 1.05, legs or shade(col, 0.72), f, 5.5 * k, 3.2 * k)
    wag = math.sin(f * math.pi / 2 + 1) * 3 * k
    _eo(s, shade(col, 0.92), c - L - 7 * k, c + wag, 20 * k, 8 * k)    # пушистый хвост
    if tail_tip:
        _e(s, tail_tip, c - L - 14 * k, c + wag, 7 * k, 6 * k)
    _eo(s, col, c, c, 2 * L + 4, 2 * W + 5)
    _e(s, shade(col, 0.78), c - 2, c, 2 * L - 8, W * 0.9)               # тёмная полоса по спине
    hx = c + L + 2 * k
    head = [(hx - 6 * k, c - 7 * k), (hx + 5 * k, c - 5 * k), (hx + 13 * k, c), (hx + 5 * k, c + 5 * k), (hx - 6 * k, c + 7 * k)]
    pygame.draw.polygon(s, shade(col, 1.05), head)
    pygame.draw.polygon(s, OUT, head, 2)
    _e(s, shade(col, 1.35), hx + 8 * k, c, 9 * k, 6 * k)                # светлая морда
    pygame.draw.circle(s, (15, 15, 15), (round(hx + 13 * k), c), max(2, round(2 * k)))
    for sg in (-1, 1):
        ear = [(hx - 5 * k, c + sg * 4 * k), (hx - 10 * k, c + sg * 11 * k), (hx, c + sg * 6 * k)]
        pygame.draw.polygon(s, shade(col, 0.8), ear)
        pygame.draw.polygon(s, OUT, ear, 1)
        pygame.draw.circle(s, (240, 210, 70), (round(hx + 4 * k), round(c + sg * 3 * k)), max(1, round(1.6 * k)))
    if scar:
        pygame.draw.line(s, (170, 40, 40), (hx - 2 * k, c - 5 * k), (hx + 6 * k, c + 2 * k), 3)


def _deer(s, c, f, col):
    _legs(s, c, c, 12, 8, (70, 50, 35), f, 4.5, 4)
    _eo(s, col, c - 3, c, 38, 19)
    _e(s, (240, 235, 225), c - 20, c, 8, 10)                            # белое пятно сзади
    for ox, oy in ((-8, -3), (-2, 3), (4, -2), (-12, 2)):
        pygame.draw.circle(s, shade(col, 1.3), (c + ox, c + oy), 2)
    _eo(s, col, c + 17, c, 15, 9)                                       # шея
    _eo(s, shade(col, 1.08), c + 26, c, 14, 11)                         # голова
    pygame.draw.circle(s, (30, 25, 20), (c + 33, c), 2)
    for sg in (-1, 1):
        _eo(s, shade(col, 0.95), c + 22, c + sg * 7, 8, 5)              # уши
        ant = (225, 205, 160)
        base = (c + 23, c + sg * 3)
        tip = (c + 12, c + sg * 16)
        pygame.draw.line(s, ant, base, tip, 3)                          # рога
        pygame.draw.line(s, ant, (c + 18, c + sg * 9), (c + 22, c + sg * 17), 2)
        pygame.draw.line(s, ant, (c + 14, c + sg * 13), (c + 9, c + sg * 11), 2)


def _boar(s, c, f, col):
    _legs(s, c, c, 9, 9, (55, 40, 32), f, 5, 3)
    pygame.draw.line(s, shade(col, 0.7), (c - 16, c), (c - 21, c + 3), 2)  # хвостик
    _eo(s, col, c - 2, c, 34, 24)
    for i in range(-12, 10, 3):                                         # щетина по хребту
        pygame.draw.line(s, shade(col, 0.6), (c + i, c - 3), (c + i + 2, c + 3), 2)
    head = [(c + 10, c - 10), (c + 22, c - 7), (c + 27, c), (c + 22, c + 7), (c + 10, c + 10)]
    pygame.draw.polygon(s, shade(col, 1.1), head)
    pygame.draw.polygon(s, OUT, head, 2)
    _eo(s, (215, 150, 140), c + 27, c, 7, 9)                            # пятачок
    for sg in (-1, 1):
        pygame.draw.circle(s, (90, 50, 50), (c + 28, c + sg * 2), 1)
        pygame.draw.line(s, (245, 240, 220), (c + 22, c + sg * 5), (c + 28, c + sg * 10), 3)   # клыки
        ear = [(c + 11, c + sg * 6), (c + 7, c + sg * 13), (c + 15, c + sg * 9)]
        pygame.draw.polygon(s, shade(col, 0.8), ear)
        pygame.draw.circle(s, (20, 20, 20), (c + 19, c + sg * 4), 2)


def _bear(s, c, f, col):
    paws = shade(col, 0.7)
    d = math.sin(f * math.pi / 2) * 4
    for lx, ly, sign in ((1, -1, 1), (1, 1, -1), (-1, -1, -1), (-1, 1, 1)):
        x, y = c + lx * 15 + sign * d, c + ly * 15
        _eo(s, paws, x, y, 15, 11)
        for i in (-1, 0, 1):                                            # когти
            pygame.draw.circle(s, (235, 230, 215), (round(x + 7 * (1 if lx > 0 else -1)), round(y + i * 3)), 1)
    _eo(s, col, c - 5, c, 48, 36)
    _e(s, shade(col, 1.14), c + 4, c, 22, 28)                           # загривок
    _eo(s, shade(col, 1.05), c + 22, c, 23, 23)                         # большая круглая голова
    for sg in (-1, 1):
        _eo(s, shade(col, 0.9), c + 17, c + sg * 10, 10, 10)            # круглые уши
        _e(s, (150, 110, 80), c + 17, c + sg * 10, 5, 5)
        pygame.draw.circle(s, (15, 10, 8), (c + 26, c + sg * 5), 2)
    _eo(s, (165, 125, 90), c + 32, c, 13, 11)                           # светлая морда
    pygame.draw.circle(s, (15, 10, 8), (c + 37, c), 3)


def _moose(s, c, f, col):
    _legs(s, c, c, 14, 10, (55, 40, 30), f, 6, 4)
    _eo(s, col, c - 5, c, 54, 26)
    _e(s, shade(col, 1.12), c + 6, c, 22, 22)                           # горб
    _eo(s, shade(col, 0.9), c + 28, c, 26, 12)                          # длинная морда
    _eo(s, shade(col, 0.75), c + 40, c, 8, 10)
    for sg in (-1, 1):
        ant = (210, 190, 145)
        _eo(s, ant, c + 20, c + sg * 17, 22, 12)                        # широкие лопатообразные рога
        for i in range(4):
            pygame.draw.circle(s, ant, (c + 12 + i * 5, c + sg * 24), 3)
        pygame.draw.circle(s, (20, 15, 10), (c + 31, c + sg * 4), 2)


def _snake(s, c, f, col):
    pts = []
    for i in range(11):
        x = c - 24 + i * 4.6
        y = c + math.sin(i * 0.9 + f * math.pi / 2) * 5 * (0.4 + i / 14)
        pts.append((x, y))
    for i, (x, y) in enumerate(pts):
        r = 2.2 + i * 0.25
        pygame.draw.circle(s, OUT, (round(x), round(y)), round(r + 1.5))
    for i, (x, y) in enumerate(pts):
        r = 2.2 + i * 0.25
        pygame.draw.circle(s, shade(col, 0.6) if i % 3 == 0 else col, (round(x), round(y)), round(r))
    hx, hy = pts[-1][0] + 5, pts[-1][1]
    _eo(s, shade(col, 1.1), hx, hy, 11, 8)
    pygame.draw.circle(s, (230, 200, 40), (round(hx + 2), round(hy - 2)), 1)
    pygame.draw.circle(s, (230, 200, 40), (round(hx + 2), round(hy + 2)), 1)
    if f % 2:
        pygame.draw.lines(s, (210, 40, 40), False, [(hx + 5, hy), (hx + 10, hy), (hx + 12, hy - 2)], 1)


def _human(s, c, f, spec):
    """spec: clothes, skin, hair, pants, extra ('band'|'bandana'|'hat'|'hood'|'helmet'), accent, pack, feathers."""
    d = math.sin(f * math.pi / 2) * 6
    boots = spec.get("pants", (55, 45, 38))
    _eo(s, boots, c + d, c - 5, 10, 6)                                  # ноги шагают
    _eo(s, boots, c - d, c + 5, 10, 6)
    if spec.get("pack"):
        pygame.draw.rect(s, (110, 76, 44), (c - 14, c - 8, 9, 16), border_radius=3)
        pygame.draw.rect(s, OUT, (c - 14, c - 8, 9, 16), 2, border_radius=3)
    clothes = spec["clothes"]
    _eo(s, clothes, c - 1, c, 16, 27)                                   # плечи и торс
    if spec.get("stripe"):
        pygame.draw.line(s, spec["stripe"], (c - 1, c - 12), (c - 1, c + 12), 3)
    if spec.get("feathers"):
        for i in (-1, 0, 1):
            pygame.draw.line(s, spec["feathers"], (c - 3, c + i * 4), (c - 15, c + i * 7), 3)
    _e(s, spec.get("hair", (60, 40, 25)), c + 1, c, 13, 14)            # затылок (волосы)
    pygame.draw.circle(s, spec["skin"], (c + 3, c), 6)                  # лицо
    pygame.draw.circle(s, OUT, (c + 2, c), 7, 1)
    extra = spec.get("extra")
    acc = spec.get("accent", (200, 60, 50))
    if extra == "band":
        pygame.draw.line(s, acc, (c + 2, c - 7), (c + 2, c + 7), 3)
    elif extra == "bandana":
        pygame.draw.line(s, acc, (c + 4, c - 7), (c + 4, c + 7), 4)
    elif extra == "hat":
        pygame.draw.circle(s, (110, 80, 50), (c + 1, c), 11)
        pygame.draw.circle(s, (130, 96, 60), (c + 1, c), 7)
        pygame.draw.circle(s, OUT, (c + 1, c), 11, 1)
    elif extra == "hood":
        pygame.draw.circle(s, (64, 64, 70), (c + 1, c), 9)
        pygame.draw.circle(s, (225, 225, 225), (c + 5, c), 4)
    elif extra == "helmet":
        pygame.draw.circle(s, (150, 155, 165), (c + 1, c), 8)
        pygame.draw.circle(s, OUT, (c + 1, c), 8, 1)


DRAWERS = {"rabbit": _rabbit, "deer": _deer, "boar": _boar, "bear": _bear, "moose": _moose, "snake": _snake}
# боссы: обычный зверь, увеличенный в k раз, с горящими лиловыми глазами (координаты глаз — в масштабе обычного зверя)
BOSSES = {"bear_king": ("bear", 1.55, [(76, 45), (76, 55)]),
          "swamp_queen": ("snake", 2.7, [(58, 30), (58, 34)]),
          "frost_wolf": ("wolf", 1.55, [(61, 35), (61, 41)])}


def creature_base(kind, frame, color):
    """Базовый (неповёрнутый) спрайт зверя."""
    key = (kind, frame, tuple(color))
    if kind in BOSSES and key not in _base:
        base_kind, k, eyes = BOSSES[kind]
        small = creature_base(base_kind, frame, color)
        w, h = small.get_size()
        s = pygame.transform.smoothscale(small, (int(w * k), int(h * k)))
        for ex, ey in eyes:
            pygame.draw.circle(s, (190, 90, 255), (int(ex * k), int(ey * k)), max(3, int(2.4 * k)))
            pygame.draw.circle(s, (255, 220, 255), (int(ex * k), int(ey * k)), max(1, int(1.1 * k)))
        if kind == "swamp_queen":                                    # корона-гребень Королевы
            hx, hy = int(58 * k), int(32 * k)
            for i in (-1, 0, 1):
                pygame.draw.polygon(s, (220, 190, 60), [(hx - 6, hy + i * 6 - 3), (hx - 6, hy + i * 6 + 3),
                                                        (hx - 18, hy + i * 9)])
        _base[key] = s
    if key not in _base:
        size = SIZES.get(kind, 70)
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        if kind == "wolf":
            _canine(s, c, frame, color, 1.0)
        elif kind == "alpha":
            _canine(s, c, frame, color, 1.25, scar=True)
        elif kind == "fox":
            _canine(s, c, frame, color, 0.8, tail_tip=(245, 245, 240), legs=(40, 30, 25))
        elif kind == "dog":
            _canine(s, c, frame, color, 0.9, tail_tip=(235, 220, 190), legs=shade(color, 0.8))
            for sg in (-1, 1):                                   # висячие уши
                _eo(s, shade(color, 0.6), c + 15, c + sg * 6, 9, 6)
        else:
            DRAWERS[kind](s, c, frame, color)
        _base[key] = s
    return _base[key]


def human_base(spec_key, frame, spec):
    key = ("human", spec_key, frame)
    if key not in _base:
        size = SIZES["human"]
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        _human(s, size // 2, frame, spec)
        _base[key] = s
    return _base[key]


def rotated(base, angle):
    return pygame.transform.rotate(base, -math.degrees(angle))


def face(key, spec, size):
    """Портрет человека анфас: лицо, причёска, головной убор, плечи в одежде фракции."""
    k = ("face", key, size)
    if k in _avatar:
        return _avatar[k]
    S = 100
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    clothes, skin, hair = spec["clothes"], spec["skin"], spec.get("hair", (60, 40, 25))
    acc = spec.get("accent", (200, 60, 50))
    _eo(s, clothes, 50, 100, 86, 50)                                    # плечи
    if spec.get("stripe"):
        pygame.draw.line(s, spec["stripe"], (30, 84), (70, 84), 4)
    pygame.draw.rect(s, shade(skin, 0.9), (43, 62, 14, 14))            # шея
    extra = spec.get("extra")
    if extra != "hood":
        _e(s, hair, 50, 38, 50, 46)                                     # волосы
    _eo(s, skin, 50, 46, 40, 46)                                        # лицо
    if extra != "hood":
        _e(s, hair, 50, 28, 40, 18)                                     # чёлка
    for x in (41, 59):
        pygame.draw.circle(s, (250, 250, 245), (x, 46), 5)
        pygame.draw.circle(s, (35, 25, 20), (x, 47), 2)
    pygame.draw.line(s, shade(skin, 0.75), (50, 48), (48, 56), 2)       # нос
    pygame.draw.arc(s, (110, 50, 40), (42, 54, 16, 10), math.pi + 0.4, math.tau - 0.4, 2)
    if extra == "band":
        pygame.draw.line(s, acc, (30, 34), (70, 34), 5)
        for x in (38, 50, 62):
            pygame.draw.line(s, acc, (x - 3, 46 + 8), (x + 3, 46 + 8), 2)
    elif extra == "bandana":
        pygame.draw.rect(s, acc, (28, 52, 44, 16), border_radius=6)
    elif extra == "hat":
        _eo(s, (110, 80, 50), 50, 26, 76, 16)
        pygame.draw.rect(s, (110, 80, 50), (34, 6, 32, 20), border_radius=6)
        pygame.draw.rect(s, OUT, (34, 6, 32, 20), 2, border_radius=6)
    elif extra == "hood":
        pygame.draw.circle(s, (64, 64, 70), (50, 44), 30, 10)
        pygame.draw.rect(s, (225, 225, 225), (34, 38, 32, 18), border_radius=6)
        for x in (42, 58):
            pygame.draw.circle(s, (20, 20, 20), (x, 46), 3)
    elif extra == "helmet":
        pygame.draw.arc(s, (150, 155, 165), (26, 14, 48, 44), 0, math.pi, 8)
    if spec.get("feathers"):
        for i, x in enumerate((36, 50, 64)):
            pygame.draw.line(s, spec["feathers"], (x, 22), (x + (i - 1) * 8, 0), 5)
    if spec.get("pack"):
        pygame.draw.line(s, (110, 76, 44), (24, 82), (34, 100), 5)
        pygame.draw.line(s, (110, 76, 44), (76, 82), (66, 100), 5)
    img = pygame.transform.smoothscale(s, (size, size))
    _avatar[k] = img
    return img


def avatar(key, base, size):
    """Мини-портрет зверя: спрайт целиком (мордой вправо), вписанный в квадрат."""
    k = (key, size)
    if k not in _avatar:
        img = base
        bw, bh = img.get_size()
        # обрезаем пустые поля
        rect = img.get_bounding_rect()
        if rect.w and rect.h:
            img = img.subsurface(rect).copy()
            bw, bh = img.get_size()
        scale = (size - 4) / max(bw, bh)
        img = pygame.transform.smoothscale(img, (max(1, int(bw * scale)), max(1, int(bh * scale))))
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        surf.blit(img, img.get_rect(center=(size // 2, size // 2)))
        _avatar[k] = surf
    return _avatar[k]
