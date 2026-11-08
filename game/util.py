# -*- coding: utf-8 -*-
import math
import random

import pygame


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def first_free(lst):
    for i, v in enumerate(lst):
        if v is None:
            return i
    return -1


def smooth_noise(w, h, scale, rng):
    """Простой value-noise: случайная сетка + плавная интерполяция."""
    gw, gh = int(w / scale) + 2, int(h / scale) + 2
    grid = [[rng.random() for _ in range(gw)] for _ in range(gh)]
    out = []
    for y in range(h):
        fy = y / scale
        y0 = int(fy)
        ty = fy - y0
        ty = ty * ty * (3 - 2 * ty)
        g0, g1 = grid[y0], grid[y0 + 1]
        row = []
        for x in range(w):
            fx = x / scale
            x0 = int(fx)
            tx = fx - x0
            tx = tx * tx * (3 - 2 * tx)
            top = g0[x0] + (g0[x0 + 1] - g0[x0]) * tx
            bot = g1[x0] + (g1[x0 + 1] - g1[x0]) * tx
            row.append(top + (bot - top) * ty)
        out.append(row)
    return out


def make_font(size, bold=False):
    return pygame.font.SysFont("segoeui,arial,dejavusans", size, bold=bold)


def gen_name(syllables, rng=random):
    return "".join(rng.choice(syllables) for _ in range(rng.randint(2, 3))).capitalize()


def direction(dx, dy, names):
    return names[round(math.atan2(dy, dx) / (math.pi / 4)) % 8]
