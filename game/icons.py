# -*- coding: utf-8 -*-
"""Иконки предметов и ресурсов (рисуются кодом, без картинок)."""
import math

import pygame

from .data import RES_INFO

WOOD, STONE, DARK, STEEL = (139, 94, 52), (160, 160, 165), (70, 70, 75), (205, 210, 220)


def draw_item_icon(surf, item_id, rect):
    x, y, w, h = rect

    def P(a, b):
        return (x + w * a, y + h * b)

    t = max(3, int(w * 0.1))
    if item_id in ("axe", "iron_axe", "battle_axe"):
        head_col = STONE if item_id == "axe" else STEEL
        pygame.draw.line(surf, WOOD, P(0.2, 0.88), P(0.68, 0.26), t)
        head = [P(0.52, 0.1), P(0.9, 0.2), P(0.86, 0.48), P(0.62, 0.36)]
        pygame.draw.polygon(surf, head_col, head)
        pygame.draw.polygon(surf, DARK, head, 2)
        if item_id == "battle_axe":
            back = [P(0.5, 0.2), P(0.3, 0.12), P(0.36, 0.42)]
            pygame.draw.polygon(surf, head_col, back)
            pygame.draw.polygon(surf, DARK, back, 2)
    elif item_id == "pickaxe":
        pygame.draw.line(surf, WOOD, P(0.18, 0.9), P(0.62, 0.3), t)
        pygame.draw.lines(surf, STONE, False, [P(0.25, 0.32), P(0.48, 0.14), P(0.75, 0.14), P(0.92, 0.4)],
                          max(3, int(w * 0.12)))
    elif item_id == "shovel":
        pygame.draw.line(surf, WOOD, P(0.14, 0.12), P(0.62, 0.62), t)
        pygame.draw.polygon(surf, STEEL, [P(0.56, 0.56), P(0.84, 0.6), P(0.92, 0.92), P(0.6, 0.84)])
        pygame.draw.line(surf, WOOD, P(0.06, 0.2), P(0.22, 0.04), t)
    elif item_id == "hammer":
        pygame.draw.line(surf, WOOD, P(0.2, 0.9), P(0.6, 0.36), t)
        pygame.draw.polygon(surf, STEEL, [P(0.42, 0.22), P(0.66, 0.06), P(0.84, 0.3), P(0.6, 0.46)])
    elif item_id == "knife":
        pygame.draw.line(surf, WOOD, P(0.2, 0.85), P(0.42, 0.58), max(4, int(w * 0.14)))
        pygame.draw.polygon(surf, STONE, [P(0.34, 0.55), P(0.86, 0.12), P(0.5, 0.66)])
        pygame.draw.polygon(surf, DARK, [P(0.34, 0.55), P(0.86, 0.12), P(0.5, 0.66)], 1)
    elif item_id == "machete":
        pygame.draw.line(surf, (40, 40, 44), P(0.14, 0.88), P(0.32, 0.7), max(4, int(w * 0.13)))
        pygame.draw.polygon(surf, STEEL, [P(0.3, 0.66), P(0.84, 0.08), P(0.94, 0.16), P(0.4, 0.76)])
    elif item_id == "club":
        pygame.draw.line(surf, WOOD, P(0.18, 0.88), P(0.62, 0.36), max(4, int(w * 0.12)))
        pygame.draw.circle(surf, (120, 80, 45), P(0.68, 0.28), max(4, int(w * 0.18)))
        for a in (0.2, 2.2, 4.2):
            pygame.draw.circle(surf, STONE, (P(0.68, 0.28)[0] + math.cos(a) * w * 0.16,
                                             P(0.68, 0.28)[1] + math.sin(a) * h * 0.16), 2)
    elif item_id in ("spear", "iron_spear"):
        pygame.draw.line(surf, WOOD, P(0.08, 0.95), P(0.74, 0.27), max(3, int(w * 0.08)))
        tip = STEEL if item_id == "iron_spear" else STONE
        pygame.draw.polygon(surf, tip, [P(0.66, 0.24), P(0.94, 0.05), P(0.77, 0.35)])
        pygame.draw.circle(surf, (170, 200, 90), P(0.7, 0.3), max(2, int(w * 0.06)))
    elif item_id == "sword":
        pygame.draw.line(surf, STEEL, P(0.32, 0.68), P(0.88, 0.12), max(4, int(w * 0.12)))
        pygame.draw.line(surf, (120, 120, 130), P(0.2, 0.52), P(0.48, 0.8), max(3, int(w * 0.08)))
        pygame.draw.line(surf, WOOD, P(0.14, 0.86), P(0.32, 0.68), max(4, int(w * 0.11)))
    elif item_id == "bow":
        pygame.draw.arc(surf, WOOD, pygame.Rect(P(0.05, 0.05), (w * 0.9, h * 0.9)), -0.6, 2.2, max(3, int(w * 0.09)))
        pygame.draw.line(surf, (230, 230, 220), P(0.87, 0.3), P(0.3, 0.87), 1)
    elif item_id == "crossbow":
        pygame.draw.line(surf, WOOD, P(0.18, 0.82), P(0.72, 0.28), max(4, int(w * 0.12)))
        pygame.draw.arc(surf, (90, 90, 96), pygame.Rect(P(0.42, 0.0), (w * 0.56, h * 0.56)), 2.3, 5.4, 3)
        pygame.draw.line(surf, (230, 230, 220), P(0.46, 0.12), P(0.86, 0.52), 1)
    elif item_id == "sling":
        pygame.draw.line(surf, (196, 170, 110), P(0.15, 0.85), P(0.55, 0.4), 2)
        pygame.draw.line(surf, (196, 170, 110), P(0.25, 0.9), P(0.6, 0.5), 2)
        pygame.draw.ellipse(surf, (172, 132, 92), pygame.Rect(P(0.5, 0.25), (w * 0.3, h * 0.3)))
        pygame.draw.circle(surf, STONE, P(0.65, 0.4), max(2, int(w * 0.08)))
    elif item_id in ("rifle", "shotgun"):
        barrel = (60, 60, 66) if item_id == "rifle" else (80, 80, 86)
        pygame.draw.line(surf, barrel, P(0.4, 0.6), P(0.94, 0.06), max(3, int(w * (0.09 if item_id == "rifle" else 0.13))))
        pygame.draw.polygon(surf, (120, 76, 40), [P(0.06, 0.86), P(0.24, 0.94), P(0.5, 0.62), P(0.38, 0.52)])
        pygame.draw.line(surf, (40, 40, 44), P(0.44, 0.62), P(0.5, 0.72), 2)
    elif item_id == "pistol":
        pygame.draw.rect(surf, (60, 60, 66), pygame.Rect(P(0.2, 0.3), (w * 0.62, h * 0.18)))
        pygame.draw.polygon(surf, (110, 72, 40), [P(0.24, 0.46), P(0.42, 0.46), P(0.36, 0.86), P(0.16, 0.86)])
    elif item_id == "torch":
        pygame.draw.line(surf, WOOD, P(0.22, 0.9), P(0.6, 0.38), max(4, int(w * 0.13)))
        pygame.draw.circle(surf, (240, 120, 30), P(0.65, 0.3), max(3, int(w * 0.17)))
        pygame.draw.circle(surf, (255, 220, 90), P(0.66, 0.29), max(2, int(w * 0.09)))
    elif item_id == "lantern":
        pygame.draw.line(surf, DARK, P(0.5, 0.08), P(0.5, 0.22), 2)
        pygame.draw.rect(surf, (90, 90, 96), pygame.Rect(P(0.28, 0.22), (w * 0.44, h * 0.6)), border_radius=3)
        pygame.draw.rect(surf, (255, 225, 120), pygame.Rect(P(0.35, 0.3), (w * 0.3, h * 0.44)), border_radius=2)
        pygame.draw.circle(surf, (200, 150, 255), P(0.5, 0.52), max(2, int(w * 0.07)))
    elif item_id == "hands":
        skin = (226, 184, 150)
        pygame.draw.circle(surf, skin, P(0.5, 0.58), int(w * 0.24))
        for i, fx in enumerate((0.32, 0.44, 0.56, 0.68)):
            pygame.draw.circle(surf, skin, P(fx, 0.3 + (0.04 if i in (0, 3) else 0)), int(w * 0.08))
        pygame.draw.circle(surf, skin, P(0.22, 0.55), int(w * 0.08))
    elif item_id == "fishing_rod":
        pygame.draw.line(surf, WOOD, P(0.12, 0.92), P(0.82, 0.1), max(2, int(w * 0.07)))
        pygame.draw.line(surf, (230, 230, 230), P(0.82, 0.1), P(0.9, 0.6), 1)
        pygame.draw.circle(surf, (220, 60, 50), P(0.9, 0.62), max(2, int(w * 0.06)))
        pygame.draw.circle(surf, (90, 90, 96), P(0.3, 0.72), max(2, int(w * 0.08)), 2)
    elif item_id == "flint":
        pygame.draw.polygon(surf, (90, 90, 100), [P(0.15, 0.6), P(0.4, 0.35), P(0.55, 0.55), P(0.3, 0.8)])
        pygame.draw.rect(surf, STEEL, pygame.Rect(P(0.5, 0.25), (w * 0.35, h * 0.14)), border_radius=2)
        for a, b in ((0.55, 0.2), (0.65, 0.12), (0.47, 0.12)):
            pygame.draw.circle(surf, (255, 200, 80), P(a, b), max(1, int(w * 0.04)))
    # ---- легендарное оружие из логов боссов
    elif item_id == "king_axe":
        pygame.draw.line(surf, (90, 60, 40), P(0.14, 0.92), P(0.66, 0.26), max(4, int(w * 0.11)))
        blade = [P(0.42, 0.08), P(0.94, 0.14), P(0.9, 0.56), P(0.58, 0.42)]
        pygame.draw.polygon(surf, (190, 196, 210), blade)
        pygame.draw.polygon(surf, (110, 60, 40), blade, 2)
        for a, b in ((0.7, 0.2), (0.8, 0.32), (0.72, 0.42)):                  # когти Хозяина на обухе
            pygame.draw.circle(surf, (240, 230, 210), P(a, b), max(1, int(w * 0.04)))
    elif item_id == "venom_blade":
        pygame.draw.line(surf, (40, 60, 40), P(0.14, 0.88), P(0.34, 0.68), max(4, int(w * 0.13)))
        blade = [P(0.3, 0.64), P(0.9, 0.08), P(0.44, 0.74)]
        pygame.draw.polygon(surf, (150, 220, 110), blade)
        pygame.draw.polygon(surf, (40, 90, 40), blade, 2)
        pygame.draw.circle(surf, (120, 255, 90), P(0.62, 0.38), max(2, int(w * 0.05)))
    elif item_id == "frost_bow":
        pygame.draw.arc(surf, (190, 225, 255), pygame.Rect(P(0.05, 0.05), (w * 0.9, h * 0.9)), -0.6, 2.2,
                        max(3, int(w * 0.1)))
        pygame.draw.line(surf, (240, 250, 255), P(0.87, 0.3), P(0.3, 0.87), 1)
        for a, b in ((0.8, 0.14), (0.12, 0.8)):
            pygame.draw.circle(surf, (240, 250, 255), P(a, b), max(2, int(w * 0.05)))
    elif item_id == "dawn_blade":
        pygame.draw.line(surf, (255, 230, 150), P(0.3, 0.7), P(0.9, 0.1), max(5, int(w * 0.14)))
        pygame.draw.line(surf, (255, 255, 230), P(0.36, 0.64), P(0.86, 0.14), max(2, int(w * 0.05)))
        pygame.draw.line(surf, (200, 160, 70), P(0.18, 0.54), P(0.46, 0.82), max(3, int(w * 0.08)))
        pygame.draw.line(surf, (120, 80, 50), P(0.12, 0.88), P(0.3, 0.7), max(4, int(w * 0.11)))


def draw_res_icon(surf, rid, cx, cy, s=10):
    col = RES_INFO[rid][1]
    if rid in ("fish", "cooked_fish"):
        pygame.draw.ellipse(surf, col, (cx - s, cy - s * 0.45, s * 1.6, s * 0.9))
        pygame.draw.polygon(surf, col, [(cx + s * 0.5, cy), (cx + s, cy - s * 0.5), (cx + s, cy + s * 0.5)])
        pygame.draw.circle(surf, (20, 20, 20), (int(cx - s * 0.6), int(cy - 1)), 1)
        return
    if rid in ("mushroom", "toadstool"):
        pygame.draw.rect(surf, (235, 225, 205), (cx - 2, cy, 4, s * 0.8))
        pygame.draw.ellipse(surf, col, (cx - s * 0.8, cy - s * 0.6, s * 1.6, s * 0.9))
        if rid == "toadstool":
            pygame.draw.circle(surf, (255, 255, 255), (cx - 3, cy - 2), 1)
            pygame.draw.circle(surf, (255, 255, 255), (cx + 3, cy - 3), 1)
        return
    if rid == "boiled_water":
        pygame.draw.rect(surf, (150, 150, 160), (cx - s * 0.6, cy - s * 0.5, s * 1.2, s * 1.2), border_radius=3)
        pygame.draw.rect(surf, col, (cx - s * 0.45, cy - s * 0.3, s * 0.9, s * 0.8), border_radius=2)
        pygame.draw.line(surf, (230, 240, 255), (cx - 2, cy - s * 0.6), (cx, cy - s), 1)
        return
    if rid in ("salve",):
        pygame.draw.circle(surf, (190, 180, 160), (cx, cy), s * 0.8)
        pygame.draw.circle(surf, col, (cx, cy), s * 0.55)
        return
    if rid == "splint":
        for o in (-4, 0, 4):
            pygame.draw.line(surf, col, (cx + o, cy - s), (cx + o, cy + s), 3)
        pygame.draw.line(surf, (236, 236, 226), (cx - s, cy - 2), (cx + s, cy - 2), 3)
        return
    if rid in ("smoked_meat", "dried_fish"):
        for o in (-4, 0, 4):
            pygame.draw.line(surf, col, (cx - s * 0.8 + o, cy + s * 0.7), (cx + s * 0.4 + o, cy - s * 0.8), 4)
        return
    if rid == "rot":
        pygame.draw.circle(surf, col, (cx, cy + 2), s * 0.75)
        pygame.draw.circle(surf, (70, 80, 40), (cx + 3, cy), s * 0.35)
        pygame.draw.circle(surf, (130, 150, 70), (cx - 3, cy - 3), 2)
        return
    if rid == "herbal":
        pygame.draw.rect(surf, (200, 210, 220), (cx - s * 0.5, cy - s * 0.8, s, s * 1.6), border_radius=3)
        pygame.draw.rect(surf, col, (cx - s * 0.4, cy - s * 0.2, s * 0.8, s * 0.9), border_radius=2)
        return
    if rid == "ore":
        pygame.draw.circle(surf, (110, 100, 96), (cx, cy), s * 0.85)
        for ox, oy in ((-3, -2), (3, 2), (2, -4)):
            pygame.draw.circle(surf, (210, 130, 70), (cx + ox, cy + oy), 2)
        return
    if rid == "firebomb":
        pygame.draw.circle(surf, (120, 160, 100), (cx, cy + 2), s * 0.7)
        pygame.draw.rect(surf, (210, 200, 180), (cx - 2, cy - s, 4, s * 0.6))
        pygame.draw.circle(surf, (255, 150, 40), (cx, int(cy - s)), 3)
        return
    if rid == "fire_arrows":
        for o in (-4, 0, 4):
            pygame.draw.line(surf, (205, 195, 160), (cx - s + o, cy + s), (cx + s * 0.6 + o, cy - s * 0.6), 2)
            pygame.draw.circle(surf, (255, 140, 40), (int(cx + s * 0.6 + o), int(cy - s * 0.6)), 3)
        return
    if rid == "flowers":
        for i, c in enumerate(((235, 120, 180), (250, 230, 90), (170, 120, 240))):
            a = i * 2.1
            px, py = cx + math.cos(a) * s * 0.45, cy + math.sin(a) * s * 0.45 - 2
            pygame.draw.line(surf, (60, 130, 50), (px, py), (cx, cy + s), 1)
            pygame.draw.circle(surf, c, (int(px), int(py)), max(2, int(s * 0.35)))
        return
    if rid == "honey":
        pygame.draw.rect(surf, (200, 200, 210), (cx - s * 0.7, cy - s * 0.6, s * 1.4, s * 1.5), border_radius=4)
        pygame.draw.rect(surf, col, (cx - s * 0.55, cy - s * 0.2, s * 1.1, s * 0.95), border_radius=3)
        pygame.draw.rect(surf, (150, 100, 50), (cx - s * 0.6, cy - s * 0.9, s * 1.2, s * 0.35), border_radius=2)
        return
    if rid == "radio_tube":
        pygame.draw.ellipse(surf, (230, 235, 240), (cx - s * 0.5, cy - s, s, s * 1.5))
        pygame.draw.circle(surf, col, (cx, int(cy - s * 0.3)), max(2, int(s * 0.3)))
        pygame.draw.rect(surf, (90, 90, 96), (cx - s * 0.5, cy + s * 0.4, s, s * 0.5))
        return
    if rid == "radio_coil":
        pygame.draw.rect(surf, (90, 90, 96), (cx - s * 0.2, cy - s, s * 0.4, s * 2))
        for i in range(5):
            pygame.draw.ellipse(surf, col, (cx - s * 0.7, cy - s * 0.85 + i * s * 0.36, s * 1.4, s * 0.34), 2)
        return
    if rid == "battery":
        pygame.draw.rect(surf, (60, 60, 66), (cx - s, cy - s * 0.6, s * 2, s * 1.3), border_radius=3)
        pygame.draw.rect(surf, col, (cx - s * 0.8, cy - s * 0.35, s * 1.1, s * 0.8), border_radius=2)
        for o in (-0.6, 0.5):
            pygame.draw.rect(surf, (200, 200, 205), (cx + s * o, cy - s * 0.9, s * 0.3, s * 0.3))
        return
    if rid == "trophy":
        pygame.draw.circle(surf, (110, 70, 40), (cx, cy), s * 0.9)
        for o in (-0.45, 0, 0.45):
            pygame.draw.polygon(surf, col, [(cx + s * o - 2, cy - s * 0.2), (cx + s * o + 2, cy - s * 0.2),
                                            (cx + s * o, cy - s)])
        pygame.draw.circle(surf, (150, 90, 220), (cx, int(cy + s * 0.25)), max(2, int(s * 0.3)))
        return
    if rid == "wood":
        pygame.draw.rect(surf, col, (cx - s, cy - s * 0.45, s * 2, s * 0.9), border_radius=3)
        pygame.draw.circle(surf, (190, 140, 90), (cx + s - 2, cy), int(s * 0.42))
    elif rid in ("stone", "iron", "coal", "gunpowder"):
        pygame.draw.circle(surf, col, (cx, cy), s * 0.8)
        hi = {"stone": (185, 185, 190), "iron": (225, 230, 240), "coal": (90, 90, 96), "gunpowder": (140, 140, 150)}[rid]
        if rid == "iron":
            pygame.draw.rect(surf, col, (cx - s, cy - s * 0.4, s * 2, s * 0.8), border_radius=2)
        pygame.draw.circle(surf, hi, (cx - 2, cy - 3), s * 0.3)
        if rid == "gunpowder":
            pygame.draw.circle(surf, (200, 60, 40), (cx + 3, cy + 2), 2)
    elif rid == "fiber":
        for i in range(-2, 3):
            pygame.draw.line(surf, col, (cx + i * 2, cy + s), (cx + i * 4, cy - s), 2)
    elif rid == "rope":
        pygame.draw.circle(surf, col, (cx, cy), s * 0.8, 3)
        pygame.draw.circle(surf, col, (cx, cy), s * 0.4, 2)
    elif rid == "cloth":
        pygame.draw.rect(surf, col, (cx - s, cy - s * 0.6, s * 2, s * 1.2), border_radius=2)
        pygame.draw.line(surf, (170, 160, 140), (cx - s, cy), (cx + s, cy), 1)
    elif rid == "berries":
        for ox, oy in ((-4, 2), (4, 2), (0, -4)):
            pygame.draw.circle(surf, col, (cx + ox, cy + oy), s * 0.45)
    elif rid == "medkit":
        pygame.draw.rect(surf, (240, 240, 240), (cx - s, cy - s * 0.7, s * 2, s * 1.4), border_radius=3)
        pygame.draw.line(surf, col, (cx, cy - s * 0.5), (cx, cy + s * 0.5), 4)
        pygame.draw.line(surf, col, (cx - s * 0.5, cy), (cx + s * 0.5, cy), 4)
    elif rid == "bandage":
        pygame.draw.rect(surf, col, (cx - s, cy - s * 0.5, s * 2, s), border_radius=3)
        pygame.draw.line(surf, (200, 60, 60), (cx, cy - s * 0.4), (cx, cy + s * 0.4), 2)
        pygame.draw.line(surf, (200, 60, 60), (cx - s * 0.4, cy), (cx + s * 0.4, cy), 2)
    elif rid == "hide":
        pygame.draw.polygon(surf, col, [(cx - s, cy - s * 0.6), (cx + s, cy - s * 0.7), (cx + s * 0.8, cy + s * 0.7),
                                        (cx - s * 0.8, cy + s * 0.6)])
    elif rid == "scrap":
        pygame.draw.rect(surf, col, (cx - s, cy - s * 0.3, s * 1.4, s * 0.8), border_radius=2)
        pygame.draw.circle(surf, (110, 100, 95), (cx + s * 0.5, cy - s * 0.2), s * 0.5, 3)
    elif rid == "arrows":
        for o in (-4, 0, 4):
            pygame.draw.line(surf, col, (cx - s + o, cy + s), (cx + s * 0.6 + o, cy - s * 0.6), 2)
            pygame.draw.circle(surf, (160, 160, 165), (int(cx + s * 0.6 + o), int(cy - s * 0.6)), 2)
    elif rid == "ammo":
        for o in (-5, 0, 5):
            pygame.draw.rect(surf, col, (cx + o - 2, cy - s * 0.4, 4, s), border_radius=1)
            pygame.draw.rect(surf, (150, 150, 155), (cx + o - 2, cy - s * 0.7, 4, 4), border_radius=1)
    elif rid == "essence":
        pygame.draw.circle(surf, (80, 40, 130), (cx, cy), s * 0.9)
        pygame.draw.circle(surf, col, (cx, cy), s * 0.6)
        pygame.draw.circle(surf, (235, 215, 255), (cx - 2, cy - 2), s * 0.25)
    elif rid == "fang":
        pygame.draw.polygon(surf, col, [(cx - s * 0.5, cy - s * 0.7), (cx + s * 0.5, cy - s * 0.7), (cx, cy + s)])
    elif rid == "necklace":
        pygame.draw.arc(surf, (140, 100, 60), (cx - s, cy - s, s * 2, s * 2), math.pi, math.tau, 2)
        for o in (-6, 0, 6):
            pygame.draw.polygon(surf, (240, 235, 215), [(cx + o - 2, cy), (cx + o + 2, cy), (cx + o, cy + 6)])
    elif rid == "canned":
        pygame.draw.rect(surf, col, (cx - s * 0.7, cy - s * 0.8, s * 1.4, s * 1.6), border_radius=2)
        pygame.draw.rect(surf, (200, 70, 60), (cx - s * 0.7, cy - s * 0.3, s * 1.4, s * 0.6))
    elif rid == "stew":
        pygame.draw.ellipse(surf, (110, 80, 55), (cx - s, cy - s * 0.3, s * 2, s * 1.1))
        pygame.draw.ellipse(surf, col, (cx - s * 0.8, cy - s * 0.4, s * 1.6, s * 0.6))
    else:   # мясо
        pygame.draw.ellipse(surf, col, (cx - s, cy - s * 0.6, s * 1.6, s * 1.2))
        pygame.draw.line(surf, (235, 230, 215), (cx + s * 0.5, cy), (cx + s, cy), 3)
