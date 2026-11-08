# -*- coding: utf-8 -*-
"""Рисование мира: земля и биомы, объекты, крыши и входы, вышки, существа, огонь, освещение, погода."""
import math
import random

import pygame

from .config import (SCREEN_W, SCREEN_H, TILE, REACH, DARK_RGB, FOG_RGB, GROUND_COL, GRASS, WATER, SAND, FLOOR,
                     DITCH, SNOW, SWAMP, STEPPE, ROCKY, MEADOW, GARDEN_TIME, FPS, DECK_H, SETTLE_RADIUS, tile_hash)
from .data import ANIMALS, ROLES, FACTION_TYPES, BREAKABLE, BUILD_BY_ID, BENCH_TIER, LIGHT_OBJ, TURRETS, PITS, DOORS
from .icons import draw_item_icon
from .util import clamp
from . import sprites

FAC_CLOTHES = {"tribe": (120, 90, 60), "bandits": (52, 52, 62), "traders": (130, 96, 60), "cult": (96, 96, 100),
               "survivors": (210, 110, 40)}
FAC_EXTRA = {"tribe": "band", "bandits": "bandana", "traders": "hat", "cult": "hood", "survivors": None}
FLOWER_COLS = [(250, 230, 90), (245, 245, 250), (230, 110, 170), (170, 120, 240), (250, 150, 60), (110, 170, 250)]


class RenderMixin:
    # ------------------------------------------------------------ примитивы
    def render_cached(self, font, txt, color):
        """Готовые надписи кэшируются — рендер шрифта самая дорогая часть кадра."""
        cache = self.__dict__.setdefault("text_cache", {})
        key = (id(font), txt, color)
        img = cache.get(key)
        if img is None:
            if len(cache) > 2000:
                cache.clear()
            img = cache[key] = font.render(txt, True, color)
        return img

    def text(self, txt, font, color, pos, center=False, right=False, shadow=True):
        color = tuple(color)
        img = self.render_cached(font, txt, color)
        r = img.get_rect()
        if center:
            r.center = pos
        elif right:
            r.topright = pos
        else:
            r.topleft = pos
        if shadow:
            self.screen.blit(self.render_cached(font, txt, (0, 0, 0)), (r.x + 1, r.y + 1))
        self.screen.blit(img, r)
        return r

    @staticmethod
    def wrap(text, font, width):
        lines, cur = [], ""
        for word in text.split():
            t = (cur + " " + word).strip()
            if font.size(t)[0] <= width:
                cur = t
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def panel(self, rect, alpha=180, color=(18, 20, 28), border=(95, 100, 118)):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill((*color, alpha))
        self.screen.blit(s, rect.topleft)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=6)

    def get_light(self, r, rgb=DARK_RGB):
        key = (r, rgb)
        if key not in self.light_cache:
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            s.fill((*rgb, 255))
            for rr in range(r, 0, -2):
                a = int(255 * (rr / r) ** 1.7)
                pygame.draw.circle(s, (*rgb, a), (r, r), rr)
            self.light_cache[key] = s
        return self.light_cache[key]

    def get_glow(self, r):
        if r not in self.glow_cache:
            s = pygame.Surface((r * 2, r * 2))
            s.fill((0, 0, 0))
            for rr in range(r, 0, -3):
                f = (1 - rr / r) ** 1.5
                pygame.draw.circle(s, (int(52 * f), int(27 * f), int(6 * f)), (r, r), rr)
            self.glow_cache[r] = s
        return self.glow_cache[r]

    def item_sprite(self, item_id):
        if item_id not in self.icon_cache:
            s = pygame.Surface((36, 36), pygame.SRCALPHA)
            draw_item_icon(s, item_id, (0, 0, 36, 36))
            self.icon_cache[item_id] = s
        return self.icon_cache[item_id]

    def fac_color(self, fi):
        return tuple(self.world.factions[fi]["color"]) if fi is not None and 0 <= fi < len(self.world.factions) \
            else (200, 200, 200)

    def bar(self, x, y, w, k, h=4):
        k = max(0.0, min(1.0, k))
        col = (90, 210, 90) if k > 0.5 else (230, 180, 60) if k > 0.25 else (230, 60, 50)
        pygame.draw.rect(self.screen, (25, 20, 20), (x - 1, y - 1, w + 2, h + 2))
        pygame.draw.rect(self.screen, col, (x, y, int(w * k), h))

    # ------------------------------------------------------------ спрайты существ
    def human_spec(self, a):
        ftype = self.world.factions[a.faction]["type"] if a.faction >= 0 else "tribe"
        tcol = self.fac_color(a.faction)
        spec = {"clothes": (255, 120, 120) if a.hurt > 0 else FAC_CLOTHES.get(ftype, (120, 90, 60)),
                "skin": (160, 108, 72) if ftype == "tribe" else (214, 172, 138),
                "hair": (35, 25, 20) if ftype in ("tribe", "bandits") else (110, 75, 40),
                "extra": FAC_EXTRA.get(ftype), "accent": tcol}
        if a.role in ("chief", "boss", "priest"):
            spec["feathers"] = (240, 240, 230) if a.role == "chief" else tcol
        if ftype == "survivors":
            spec["stripe"] = (235, 235, 110)
        key = (ftype, tcol, a.role, a.hurt > 0)
        return key, spec

    def player_spec(self):
        p = self.player
        clothes = ((64, 98, 176), (130, 92, 58), (150, 156, 168))[p.armor]
        if p.hurt > 0:
            clothes = (220, 90, 90)
        elif p.wet > 30 and not self.player_in_water():
            clothes = tuple(int(c * 0.75) for c in clothes)
        spec = {"clothes": clothes, "skin": (226, 184, 150), "hair": (92, 62, 36), "pack": True,
                "extra": "helmet" if p.armor == 2 else None}
        return ("player", clothes, p.armor), spec

    def creature_base(self, a, frame=0):
        if a.human:
            key, spec = self.human_spec(a)
            return sprites.human_base(key, frame, spec), ("h",) + key
        if a.kind in ("shadow", "barrow_lord"):
            return None, None
        return sprites.creature_base(a.kind, frame, a.color), (a.kind, tuple(a.color))

    def creature_avatar(self, a, size=36):
        if a.human:
            key, spec = self.human_spec(a)
            return sprites.face(key, spec, size)
        base, key = self.creature_base(a, 0)
        if base is None:
            s = pygame.Surface((size, size), pygame.SRCALPHA)
            c, lord = size // 2, a.kind == "barrow_lord"
            pygame.draw.circle(s, (70, 30, 120, 230) if lord else (90, 50, 130, 220), (c, c + (2 if lord else 0)),
                               c - 2)
            eye = (255, 120, 255) if lord else (230, 210, 255)
            pygame.draw.circle(s, eye, (c - 5, c - 1), 3)
            pygame.draw.circle(s, eye, (c + 5, c - 1), 3)
            if lord:                                               # корона Владыки
                k = size / 36
                pts = [(c - 11 * k, c - 8 * k), (c - 11 * k, c - 16 * k), (c - 6 * k, c - 11 * k), (c, c - 18 * k),
                       (c + 6 * k, c - 11 * k), (c + 11 * k, c - 16 * k), (c + 11 * k, c - 8 * k)]
                pygame.draw.polygon(s, (230, 190, 70), pts)
            return s
        return sprites.avatar(key, base, size)

    def player_avatar(self, size=36):
        key, spec = self.player_spec()
        return sprites.face(key, spec, size)

    # ------------------------------------------------------------ объекты
    def draw_tree(self, sx, sy, o):
        scr = self.screen
        cx = sx + TILE // 2
        if self.clock_t - o["hit_t"] < 0.15:
            cx += int(math.sin(self.clock_t * 80) * 3)
        base = sy + TILE - 6
        k = o["size"]
        kind = o["kind"]
        season = self.world.season if self.world else "summer"
        if season == "winter" and kind == "pine":
            kind = "snowpine"                                     # зимой сосны в снегу
        pygame.draw.ellipse(scr, (40, 80, 36) if kind != "snowpine" else (170, 180, 195), (cx - 18, base - 8, 36, 14))
        if kind == "dead":
            col = (110, 100, 90)
            pygame.draw.line(scr, col, (cx, base), (cx, base - 46 * k), 6)
            for i, (dx, dy) in enumerate(((-14, -30), (12, -36), (-9, -44), (10, -22))):
                y0 = base - (20 + i * 7) * k
                pygame.draw.line(scr, col, (cx, y0), (cx + dx * k, y0 + (dy + 20) * k), 3)
            return
        pygame.draw.rect(scr, (98, 66, 38), (cx - 4, base - 18, 8, 18))
        if kind in ("pine", "snowpine"):
            for i, (w, h, yo) in enumerate(((22, 26, 14), (18, 24, 30), (12, 22, 44))):
                w, h, yo = w * k, h * k, yo * k
                col = (30 + i * 8, 92 + i * 12, 46 + i * 6) if kind == "pine" else (34 + i * 6, 80 + i * 8, 62 + i * 6)
                tri = [(cx, base - yo - h), (cx - w, base - yo), (cx + w, base - yo)]
                pygame.draw.polygon(scr, col, tri)
                if kind == "snowpine":
                    pygame.draw.polygon(scr, (235, 240, 248), [(cx, base - yo - h), (cx - w * 0.55, base - yo - h * 0.45),
                                                               (cx + w * 0.55, base - yo - h * 0.45)])
        else:
            r = int(20 * k)
            cy = base - int(36 * k)
            pal = {"autumn": ((176, 92, 34), (212, 128, 44), (240, 178, 70)),
                   "winter": ((150, 150, 156), (205, 212, 222), (240, 244, 250)),
                   "spring": ((52, 120, 48), (70, 146, 60), (110, 180, 90))}.get(
                season, ((38, 96, 40), (48, 114, 46), (62, 132, 54)))
            pygame.draw.circle(scr, pal[0], (cx, cy), r)
            pygame.draw.circle(scr, pal[1], (cx - r // 3, cy - r // 4), int(r * 0.7))
            pygame.draw.circle(scr, pal[2], (cx - r // 3, cy - r // 3), int(r * 0.35))
            wx, wy = int(sx + getattr(self, "cam_x", 0)) // TILE, int(sy + getattr(self, "cam_y", 0)) // TILE
            if season == "spring" and tile_hash(wx, wy, 5) % 3 == 0:
                for ox, oy in ((-8, -6), (6, 4), (2, -12)):
                    pygame.draw.circle(scr, (250, 220, 235), (cx + ox, cy + oy), 2)

    def draw_wall_block(self, sx, sy, col, hit, lines=True):
        scr = self.screen
        pygame.draw.rect(scr, col, (sx, sy, TILE, TILE))
        if lines:
            for i in range(1, 4):
                pygame.draw.line(scr, tuple(max(0, c - 25) for c in col), (sx, sy + i * 10), (sx + TILE, sy + i * 10), 1)
        pygame.draw.rect(scr, tuple(min(255, c + 25) for c in col), (sx, sy, TILE, 5))
        pygame.draw.rect(scr, (230, 230, 230) if hit else tuple(max(0, c - 50) for c in col), (sx, sy, TILE, TILE), 1)

    def door_is_open(self, sx, sy, o):
        if o.get("open"):
            return True
        cx, cy = sx + self.cam_x + 20, sy + self.cam_y + 20
        p = self.player
        if math.hypot(p.x - cx, p.y - cy) < 36:
            return True
        return any(a.ally and math.hypot(a.x - cx, a.y - cy) < 36 for a in self.animals
                   if abs(a.x - cx) < 40 and abs(a.y - cy) < 40)

    def draw_rockish(self, cx, cy, hit, base=(118, 118, 124), light=(150, 150, 158), dots=None):
        scr = self.screen
        pts = [(cx - 16, cy + 12), (cx - 18, cy - 2), (cx - 8, cy - 14), (cx + 10, cy - 13),
               (cx + 18, cy), (cx + 14, cy + 13)]
        pygame.draw.polygon(scr, base, pts)
        pygame.draw.polygon(scr, light, [(cx - 12, cy - 2), (cx - 6, cy - 10), (cx + 6, cy - 9), (cx, cy)])
        if dots:
            for ox, oy in ((-8, 4), (4, -4), (8, 6), (-2, 8), (10, -8)):
                pygame.draw.circle(scr, dots, (cx + ox, cy + oy), 3)
        pygame.draw.polygon(scr, (230, 230, 230) if hit else (80, 80, 86), pts, 2)

    def draw_flat(self, sx, sy, o):
        scr = self.screen
        cx, cy = sx + TILE // 2, sy + TILE // 2
        t = o["t"]
        hit = self.clock_t - o.get("hit_t", -9) < 0.15
        if t == "rock":
            self.draw_rockish(cx, cy, hit)
        elif t == "ore":
            self.draw_rockish(cx, cy, hit, (110, 100, 96), (140, 128, 120), dots=(200, 120, 70))
        elif t == "coal_node":
            self.draw_rockish(cx, cy, hit, (96, 96, 100), (126, 126, 130), dots=(30, 30, 34))
        elif t in ("wall", "wall_old", "tower_wall"):
            col = {"wall": (150, 108, 64), "wall_old": (88, 64, 44), "tower_wall": (110, 80, 50)}[t]
            self.draw_wall_block(sx, sy, col, hit)
        elif t == "hut_wall":
            pygame.draw.rect(scr, (170, 138, 80), (sx, sy, TILE, TILE))
            for i in range(0, TILE, 6):
                pygame.draw.line(scr, (140, 110, 60), (sx + i, sy), (sx + i + 4, sy + TILE), 2)
            pygame.draw.rect(scr, (230, 230, 230) if hit else self.fac_color(o.get("fac")), (sx, sy, TILE, TILE), 2)
        elif t == "palisade":
            for i in range(5):
                x = sx + 2 + i * 8
                pygame.draw.rect(scr, (120, 84, 48), (x, sy + 2, 7, TILE - 4), border_radius=2)
                pygame.draw.polygon(scr, (150, 110, 70), [(x, sy + 4), (x + 3, sy - 4), (x + 7, sy + 4)])
            pygame.draw.line(scr, (80, 56, 32), (sx, cy), (sx + TILE, cy), 3)
            if hit:
                pygame.draw.rect(scr, (230, 230, 230), (sx, sy, TILE, TILE), 1)
        elif t == "barricade":
            pygame.draw.line(scr, (130, 92, 52), (sx + 4, sy + 6), (sx + 36, sy + 34), 6)
            pygame.draw.line(scr, (130, 92, 52), (sx + 36, sy + 6), (sx + 4, sy + 34), 6)
            pygame.draw.line(scr, (150, 150, 155), (sx + 2, cy), (sx + 38, cy), 4)
        elif t == "spikes":
            for i in range(3):
                for j in range(3):
                    x, y = sx + 8 + i * 12, sy + 10 + j * 11
                    pygame.draw.polygon(scr, (150, 112, 66), [(x - 4, y + 4), (x, y - 7), (x + 4, y + 4)])
                    pygame.draw.circle(scr, (200, 190, 170), (x, y - 6), 1)
        elif t in PITS:
            if o.get("hidden"):                                  # замаскированная яма: только кучка листьев
                for ox, oy, c in ((-8, -6, (90, 120, 50)), (6, -4, (110, 130, 60)), (-3, 6, (100, 115, 50)),
                                  (9, 7, (85, 110, 45)), (0, 0, (120, 140, 70))):
                    pygame.draw.ellipse(scr, c, (cx + ox - 6, cy + oy - 3, 12, 6))
                if o.get("own"):
                    for i in range(0, 32, 6):
                        pygame.draw.line(scr, (240, 230, 160), (sx + 4 + i, sy + 4), (sx + 7 + i, sy + 4), 1)
                        pygame.draw.line(scr, (240, 230, 160), (sx + 4 + i, sy + 36), (sx + 7 + i, sy + 36), 1)
            else:
                pygame.draw.ellipse(scr, (40, 28, 18), (sx + 4, sy + 5, 32, 30))
                pygame.draw.ellipse(scr, (20, 14, 10), (sx + 9, sy + 10, 22, 20))
                if t == "spiked_pit":
                    for ox, oy in ((-6, -4), (5, -5), (0, 4), (-7, 5), (7, 4)):
                        pygame.draw.polygon(scr, (170, 130, 80), [(cx + ox - 2, cy + oy + 3), (cx + ox, cy + oy - 5),
                                                                  (cx + ox + 2, cy + oy + 3)])
        elif t in ("stone_wall", "metal_wall", "pillar"):
            base, brick = ((120, 120, 126), (150, 150, 156)) if t != "metal_wall" else ((90, 96, 106), (140, 148, 160))
            if t == "pillar":
                pygame.draw.circle(scr, base, (cx, cy), 12)
                pygame.draw.circle(scr, brick, (cx - 3, cy - 3), 6)
                pygame.draw.circle(scr, self.fac_color(o.get("fac")), (cx, cy), 12, 2)
                return
            pygame.draw.rect(scr, base, (sx, sy, TILE, TILE))
            for row in range(4):
                y = sy + row * 10
                off = 10 if row % 2 else 0
                for bx in range(-10 + off, TILE, 20):
                    pygame.draw.rect(scr, brick, (sx + max(0, bx) + 1, y + 1, min(18, TILE - max(0, bx) - 2), 8))
            pygame.draw.rect(scr, (230, 230, 230) if hit else (70, 70, 76), (sx, sy, TILE, TILE), 1)
        elif t in DOORS:
            frame, leaf = ((80, 56, 34), (170, 125, 75)) if t == "door" else ((70, 74, 82), (140, 146, 158))
            pygame.draw.rect(scr, frame, (sx, sy, TILE, TILE))
            pygame.draw.rect(scr, (60, 46, 34), (sx + 4, sy + 4, TILE - 8, TILE - 8))
            if self.door_is_open(sx, sy, o):                     # створка откинута в сторону
                pygame.draw.rect(scr, leaf, (sx + 2, sy + 3, 8, TILE - 6), border_radius=2)
                pygame.draw.rect(scr, (30, 24, 18), (sx + 2, sy + 3, 8, TILE - 6), 1, border_radius=2)
                if o.get("open"):
                    pygame.draw.circle(scr, (120, 230, 120), (sx + TILE - 7, sy + 7), 3)
            else:
                pygame.draw.rect(scr, leaf, (sx + 5, sy + 3, TILE - 10, TILE - 6), border_radius=3)
                pygame.draw.line(scr, tuple(c - 40 for c in leaf), (cx, sy + 5), (cx, sy + TILE - 5), 2)
                pygame.draw.circle(scr, (230, 200, 90), (sx + TILE - 12, cy), 3)
            if hit:
                pygame.draw.rect(scr, (230, 230, 230), (sx, sy, TILE, TILE), 1)
        elif t == "bush":
            for ox, oy, r in ((-7, 3, 10), (7, 3, 10), (0, -5, 11)):
                pygame.draw.circle(scr, (40, 104, 44), (cx + ox, cy + oy), r)
            pygame.draw.circle(scr, (56, 124, 54), (cx - 3, cy - 7), 5)
            if o["berries"]:
                for ox, oy in ((-8, 0), (6, -6), (2, 6), (9, 4), (-3, -2)):
                    pygame.draw.circle(scr, (210, 30, 70), (cx + ox, cy + oy), 3)
        elif t == "tuft":
            for i in range(-3, 4):
                pygame.draw.line(scr, (150, 192, 72), (cx + i * 2, cy + 10), (cx + i * 4, cy - 8 + abs(i) * 2), 2)
        elif t == "reed":
            for i in range(-3, 4):
                x = cx + i * 4
                pygame.draw.line(scr, (110, 140, 70), (x, cy + 14), (x + i, cy - 12 + abs(i) * 2), 2)
                pygame.draw.ellipse(scr, (120, 80, 45), (x + i - 2, cy - 16 + abs(i) * 2, 4, 9))
        elif t in ("mushroom", "toadstool"):
            cap = (175, 120, 75) if t == "mushroom" else (210, 40, 35)
            for ox, oy, r in ((-6, 4, 6), (5, -2, 7), (2, 8, 4)):
                pygame.draw.rect(scr, (235, 225, 205), (cx + ox - 2, cy + oy, 4, 6))
                pygame.draw.ellipse(scr, cap, (cx + ox - r, cy + oy - r // 2, r * 2, r))
                if t == "toadstool":
                    pygame.draw.circle(scr, (250, 250, 250), (cx + ox - 2, cy + oy - 1), 1)
                    pygame.draw.circle(scr, (250, 250, 250), (cx + ox + 2, cy + oy), 1)
        elif t == "dry_bush":
            for a in range(7):
                ang = a / 7 * math.pi + math.pi
                pygame.draw.line(scr, (140, 105, 60), (cx, cy + 8), (cx + math.cos(ang) * 14, cy + 8 + math.sin(ang) * 16), 2)
        elif t == "pebble":
            pygame.draw.ellipse(scr, (130, 130, 136), (cx - 9, cy - 2, 11, 8))
            pygame.draw.ellipse(scr, (155, 155, 160), (cx + 1, cy + 2, 8, 6))
        elif t in ("stump", "charred"):
            col = (98, 66, 38) if t == "stump" else (40, 36, 34)
            pygame.draw.circle(scr, col, (cx, cy + 6), 9)
            pygame.draw.circle(scr, (170, 130, 85) if t == "stump" else (70, 64, 60), (cx, cy + 6), 6)
            if t == "charred":
                pygame.draw.line(scr, (30, 28, 26), (cx - 2, cy + 6), (cx - 6, cy - 12), 3)
                pygame.draw.line(scr, (30, 28, 26), (cx + 2, cy + 6), (cx + 7, cy - 8), 2)
        elif t in ("bed", "mat"):
            pygame.draw.rect(scr, (110, 75, 45), (sx + 4, sy + 6, 32, 28), border_radius=4)
            pygame.draw.rect(scr, (90, 140, 60) if t == "bed" else (172, 132, 92), (sx + 7, sy + 9, 26, 22), border_radius=3)
            pygame.draw.rect(scr, (200, 190, 160), (sx + 8, sy + 10, 10, 8), border_radius=2)
        elif t in ("bigbed", "bed_old"):
            frame, blanket = ((140, 95, 55), (170, 50, 55)) if t == "bigbed" else ((95, 75, 58), (110, 90, 80))
            pygame.draw.rect(scr, frame, (sx + 3, sy + 2, 34, 36), border_radius=3)
            pygame.draw.rect(scr, blanket, (sx + 6, sy + 14, 28, 22), border_radius=3)
            pygame.draw.rect(scr, (235, 230, 220) if t == "bigbed" else (170, 165, 150), (sx + 8, sy + 5, 24, 8),
                             border_radius=3)
        elif t in ("tent", "tent_old"):
            col = (84, 124, 74) if t == "tent" else (128, 120, 104)
            pygame.draw.polygon(scr, col, [(sx + 2, sy + 36), (cx, sy + 2), (sx + 38, sy + 36)])
            pygame.draw.polygon(scr, tuple(c - 30 for c in col), [(cx - 6, sy + 36), (cx, sy + 14), (cx + 6, sy + 36)])
            pygame.draw.line(scr, (60, 45, 30), (cx, sy + 2), (cx, sy - 3), 2)
        elif t == "ladder":
            pygame.draw.line(scr, (150, 110, 65), (sx + 12, sy + 2), (sx + 12, sy + 38), 3)
            pygame.draw.line(scr, (150, 110, 65), (sx + 28, sy + 2), (sx + 28, sy + 38), 3)
            for i in range(5):
                pygame.draw.line(scr, (170, 130, 80), (sx + 12, sy + 5 + i * 8), (sx + 28, sy + 5 + i * 8), 2)
        elif t == "totem":
            col = self.fac_color(o.get("fac"))
            pygame.draw.rect(scr, (110, 76, 46), (cx - 7, sy - 18, 14, 54), border_radius=3)
            for i, y in enumerate((sy - 14, sy + 4, sy + 20)):
                pygame.draw.rect(scr, col if i % 2 == 0 else (230, 220, 190), (cx - 8, y, 16, 10), border_radius=2)
                pygame.draw.circle(scr, (20, 20, 20), (cx - 3, y + 4), 2)
                pygame.draw.circle(scr, (20, 20, 20), (cx + 3, y + 4), 2)
            pygame.draw.line(scr, (110, 76, 46), (cx - 16, sy - 6), (cx + 16, sy - 6), 4)
            if hit:
                pygame.draw.rect(scr, (230, 230, 230), (cx - 9, sy - 20, 18, 58), 1)
        elif t in ("camp_banner", "flag"):
            col = self.fac_color(o.get("fac")) if t == "camp_banner" else (60, 140, 230)
            pygame.draw.circle(scr, (110, 110, 115), (cx - 6, sy + 34), 4)
            pygame.draw.circle(scr, (110, 110, 115), (cx + 4, sy + 35), 4)
            pygame.draw.line(scr, (90, 64, 40), (cx, sy + 36), (cx, sy - 16), 3)
            wave = math.sin(self.clock_t * 4 + sx) * 3
            cloth = [(cx, sy - 16), (cx + 22, sy - 12 + wave), (cx + 20, sy - 2 + wave), (cx, sy - 2)]
            pygame.draw.polygon(scr, col, cloth)
            pygame.draw.polygon(scr, (30, 24, 18), cloth, 1)
            if t == "flag":
                pygame.draw.circle(scr, (250, 230, 120), (round(cx + 10), round(sy - 9 + wave / 2)), 3)
            if hit:
                pygame.draw.rect(scr, (230, 230, 230), (cx - 2, sy - 18, 26, 56), 1)
        elif t == "altar":
            pygame.draw.rect(scr, (100, 100, 108), (sx + 4, sy + 10, 32, 22), border_radius=3)
            pygame.draw.rect(scr, (60, 60, 66), (sx + 4, sy + 10, 32, 22), 2, border_radius=3)
            pygame.draw.circle(scr, (150, 90, 220), (cx, sy + 14), 5)
            pygame.draw.circle(scr, (220, 200, 255), (cx, sy + 14), 2)
        elif t == "rack":
            pygame.draw.line(scr, (100, 70, 40), (sx + 6, sy + 34), (sx + 6, sy + 8), 3)
            pygame.draw.line(scr, (100, 70, 40), (sx + 34, sy + 34), (sx + 34, sy + 8), 3)
            pygame.draw.line(scr, (100, 70, 40), (sx + 4, sy + 10), (sx + 36, sy + 10), 3)
            pygame.draw.rect(scr, (172, 132, 92), (sx + 10, sy + 12, 9, 16))
            pygame.draw.rect(scr, (200, 110, 90), (sx + 22, sy + 12, 8, 12))
        elif t == "chest":
            special = o.get("loot") in ("airdrop", "wreck")
            pygame.draw.rect(scr, (90, 100, 70) if special else (130, 85, 45), (sx + 6, sy + 10, 28, 22), border_radius=3)
            pygame.draw.rect(scr, (70, 80, 50) if special else (100, 64, 34), (sx + 6, sy + 10, 28, 8), border_radius=3)
            pygame.draw.line(scr, (90, 90, 95), (sx + 6, sy + 18), (sx + 34, sy + 18), 2)
            pygame.draw.rect(scr, (230, 190, 70), (cx - 3, sy + 16, 6, 6))
            if (any(o["res"].values()) or any(o["tools"])) and int(self.clock_t * 2 + sx) % 3 == 0:
                pygame.draw.circle(scr, (255, 240, 160), (sx + 30, sy + 10), 2)
        elif t == "drop":
            pygame.draw.ellipse(scr, (40, 80, 36), (cx - 11, cy + 6, 22, 8))
            pygame.draw.circle(scr, (150, 115, 70), (cx, cy + 3), 9)
            pygame.draw.polygon(scr, (130, 98, 58), [(cx - 5, cy - 6), (cx + 5, cy - 6), (cx, cy)])
            if int(self.clock_t * 3) % 2 == 0:
                pygame.draw.circle(scr, (255, 240, 160), (cx + 8, cy - 6), 2)
        elif t in BENCH_TIER:
            tier = BENCH_TIER[t]
            top = [(150, 105, 60), (130, 120, 110), (110, 120, 140)][tier - 1]
            pygame.draw.rect(scr, top, (sx + 2, sy + 10, 36, 18), border_radius=2)
            pygame.draw.rect(scr, (100, 70, 40), (sx + 4, sy + 28, 5, 8))
            pygame.draw.rect(scr, (100, 70, 40), (sx + 31, sy + 28, 5, 8))
            pygame.draw.polygon(scr, (190, 190, 200), [(sx + 8, sy + 14), (sx + 24, sy + 14), (sx + 24, sy + 20)])
            self.text("I" * tier, self.font_s, (255, 214, 90), (sx + 31, sy + 12), center=True)
        elif t == "smokehouse":
            pygame.draw.rect(scr, (110, 78, 46), (sx + 6, sy + 10, 28, 26), border_radius=3)
            pygame.draw.polygon(scr, (80, 56, 34), [(sx + 2, sy + 12), (cx, sy - 2), (sx + 38, sy + 12)])
            pygame.draw.rect(scr, (40, 30, 22), (cx - 5, sy + 22, 10, 14))
            for i in range(3):                                     # дымок
                k = (self.clock_t * 0.6 + i / 3) % 1
                pygame.draw.circle(scr, (170, 170, 175), (int(cx + 6 + math.sin(k * 6) * 3), int(sy - 4 - k * 26)),
                                   int(3 + k * 4), 1)
        elif t == "cellar":
            pygame.draw.rect(scr, (110, 110, 116), (sx + 4, sy + 6, 32, 30), border_radius=6)
            pygame.draw.rect(scr, (130, 92, 54), (sx + 9, sy + 11, 22, 20), border_radius=2)
            pygame.draw.line(scr, (90, 62, 36), (sx + 20, sy + 11), (sx + 20, sy + 31), 2)
            pygame.draw.circle(scr, (200, 200, 205), (sx + 26, sy + 21), 2)
        elif t == "furnace":
            pygame.draw.rect(scr, (110, 106, 100), (sx + 4, sy + 4, 32, 32), border_radius=6)
            pygame.draw.rect(scr, (70, 66, 62), (sx + 4, sy + 4, 32, 32), 2, border_radius=6)
            glow = 180 + int(math.sin(self.clock_t * 6 + sx) * 40)
            pygame.draw.rect(scr, (glow, 90, 30), (sx + 12, sy + 20, 16, 10), border_radius=3)
            pygame.draw.rect(scr, (60, 56, 52), (sx + 15, sy, 10, 8))
        elif t in TURRETS:
            pygame.draw.rect(scr, (90, 90, 96) if t == "gun_turret" else (120, 86, 52), (sx + 4, sy + 4, 32, 32),
                             border_radius=5)
            pygame.draw.rect(scr, (40, 40, 44), (sx + 4, sy + 4, 32, 32), 2, border_radius=5)
            ang = o.get("ang", 0)
            fx, fy = math.cos(ang), math.sin(ang)
            pygame.draw.circle(scr, (150, 150, 158), (cx, cy), 10)
            if t == "turret":
                pygame.draw.line(scr, (110, 76, 44), (cx, cy), (cx + fx * 18, cy + fy * 18), 5)
                pygame.draw.line(scr, (80, 80, 86), (cx + fx * 12 - fy * 12, cy + fy * 12 + fx * 12),
                                 (cx + fx * 12 + fy * 12, cy + fy * 12 - fx * 12), 3)
            else:
                for s in (-3, 3):
                    pygame.draw.line(scr, (50, 50, 56), (cx - fy * s, cy + fx * s), (cx + fx * 20 - fy * s, cy + fy * 20 + fx * s), 3)
            if self.clock_t - o.get("flash", -9) < 0.08:
                pygame.draw.circle(scr, (255, 230, 120), (round(cx + fx * 22), round(cy + fy * 22)), 5)
            self.bar(sx + 6, sy + 36, 28, o.get("ammo", 0) / 40, 3)
        elif t == "wreck_part":
            dx, dy = o.get("dir", [1, 0])
            metal, dark = (176, 180, 188), (90, 92, 98)
            part = o.get("part")
            if part == "wing":
                rect = (sx + 2, sy + 12, 36, 16) if dy else (sx + 12, sy + 2, 16, 36)
                pygame.draw.rect(scr, metal, rect, border_radius=3)
                pygame.draw.rect(scr, dark, rect, 2, border_radius=3)
            else:
                rect = (sx, sy + 6, 40, 28) if dx else (sx + 6, sy, 28, 40)
                pygame.draw.rect(scr, metal, rect, border_radius=10 if part in ("nose", "tail") else 2)
                pygame.draw.rect(scr, dark, rect, 2, border_radius=10 if part in ("nose", "tail") else 2)
                for i in (-1, 1):
                    wx, wy = (cx + i * 9, cy - 6) if dx else (cx - 6, cy + i * 9)
                    pygame.draw.circle(scr, (90, 140, 190), (wx, wy), 3)
                if part == "tail":
                    pygame.draw.polygon(scr, (200, 70, 50), [(cx - 4, cy - 4), (cx + 4, cy - 4), (cx, cy - 18)])
            pygame.draw.circle(scr, (50, 46, 44), (cx + 8, cy + 8), 5)          # копоть
        elif t == "table":
            pygame.draw.rect(scr, (115, 82, 50), (sx + 6, sy + 6, 28, 28), border_radius=3)
            pygame.draw.rect(scr, (230, 230, 230) if hit else (80, 56, 34), (sx + 6, sy + 6, 28, 28), 2, border_radius=3)
        elif t == "flower":
            season = self.world.season
            wx, wy = int((sx + self.cam_x) // TILE), int((sy + self.cam_y) // TILE)
            col = FLOWER_COLS[o.get("c", tile_hash(wx, wy, 3) % len(FLOWER_COLS))]
            if season == "winter":
                col = (150, 130, 100)
            elif season == "autumn":
                col = tuple((c + 140) // 2 for c in col)
            for i, (ox, oy) in enumerate(((-7, 2), (6, -3), (0, 8))):
                fx, fy = cx + ox, cy + oy - 6
                pygame.draw.line(scr, (50, 110, 44), (fx, fy), (fx + (i - 1), cy + oy + 6), 2)
                if season != "winter":
                    for a in range(5):
                        ang = a / 5 * math.tau + i
                        pygame.draw.circle(scr, col, (int(fx + math.cos(ang) * 3), int(fy + math.sin(ang) * 3)), 3)
                    pygame.draw.circle(scr, (255, 230, 120), (fx, fy), 2)
        elif t == "hive":
            pygame.draw.line(scr, (90, 64, 40), (cx, sy + 38), (cx, sy + 22), 4)
            pygame.draw.ellipse(scr, (196, 150, 70), (cx - 12, sy + 4, 24, 24))
            for i in range(3):
                pygame.draw.line(scr, (150, 106, 46), (cx - 11, sy + 10 + i * 6), (cx + 11, sy + 10 + i * 6), 2)
            pygame.draw.circle(scr, (40, 30, 20), (cx, sy + 22), 3)
            if o.get("honey"):
                pygame.draw.circle(scr, (240, 190, 60), (cx + 8, sy + 24), 3)
            if self.world.season != "winter":                       # пчёлы кружат
                for i in range(4):
                    ang = self.clock_t * (3 + i) + i * 1.7
                    bx, by = cx + math.cos(ang) * (14 + i * 2), sy + 14 + math.sin(ang * 1.3) * 10
                    pygame.draw.circle(scr, (250, 210, 40), (int(bx), int(by)), 2)
                    pygame.draw.circle(scr, (30, 30, 30), (int(bx) + 1, int(by)), 1)
        elif t in ("bones", "bone_pile"):
            bone = (226, 220, 200)
            pygame.draw.line(scr, bone, (sx + 8, sy + 30), (sx + 26, sy + 24), 3)
            pygame.draw.line(scr, bone, (sx + 14, sy + 34), (sx + 30, sy + 32), 3)
            if t == "bones":
                pygame.draw.circle(scr, bone, (sx + 14, sy + 16), 7)                 # череп
                pygame.draw.circle(scr, (40, 34, 30), (sx + 11, sy + 15), 2)
                pygame.draw.circle(scr, (40, 34, 30), (sx + 17, sy + 15), 2)
                for i in range(3):                                                  # рёбра
                    pygame.draw.arc(scr, bone, (sx + 18, sy + 18 + i * 4, 14, 8), 0, math.pi, 2)
                if o.get("notes"):                                                  # записка рядом
                    pygame.draw.rect(scr, (240, 232, 205), (sx + 24, sy + 6, 12, 14))
                    pygame.draw.rect(scr, (150, 130, 100), (sx + 24, sy + 6, 12, 14), 1)
                    for i in range(3):
                        pygame.draw.line(scr, (120, 110, 100), (sx + 26, sy + 10 + i * 3), (sx + 33, sy + 10 + i * 3), 1)
                    if int(self.clock_t * 2 + sx) % 3 == 0:
                        pygame.draw.circle(scr, (255, 250, 200), (sx + 35, sy + 6), 2)
        elif t == "den":                                                            # вход в берлогу
            pygame.draw.polygon(scr, (104, 100, 96), [(sx - 4, sy + 38), (sx + 2, sy + 6), (cx, sy - 4),
                                                      (sx + 38, sy + 6), (sx + 44, sy + 38)])
            pygame.draw.ellipse(scr, (18, 14, 12), (sx + 6, sy + 12, 28, 26))
            pygame.draw.polygon(scr, (136, 132, 126), [(sx + 2, sy + 6), (cx, sy - 4), (sx + 38, sy + 6), (cx, sy + 4)])
            for ox in (8, 20, 30):
                pygame.draw.line(scr, (226, 220, 200), (sx + ox, sy + 38), (sx + ox + 4, sy + 34), 2)
        elif t == "nest":
            pygame.draw.ellipse(scr, (96, 76, 44), (sx + 2, sy + 8, 36, 28))
            pygame.draw.ellipse(scr, (60, 46, 26), (sx + 8, sy + 13, 24, 18))
            for ox, oy in ((14, 18), (22, 17), (18, 24), (26, 24)):
                pygame.draw.ellipse(scr, (196, 214, 170), (sx + ox - 4, sy + oy - 3, 9, 7))
                pygame.draw.circle(scr, (120, 150, 90), (sx + ox, sy + oy), 1)
        elif t == "ice_spike":
            pts = [(cx - 9, sy + 36), (cx - 4, sy + 2), (cx + 2, sy + 14), (cx + 7, sy - 2), (cx + 11, sy + 36)]
            pygame.draw.polygon(scr, (190, 225, 250), pts)
            pygame.draw.polygon(scr, (240, 250, 255), [(cx - 4, sy + 6), (cx - 1, sy + 30), (cx - 6, sy + 30)])
            pygame.draw.polygon(scr, (120, 170, 210), pts, 2)
        elif t == "menhir":
            pts = [(cx - 9, sy + 36), (cx - 10, sy + 4), (cx - 3, sy - 6), (cx + 7, sy - 2), (cx + 10, sy + 36)]
            pygame.draw.polygon(scr, (110, 108, 116), pts)
            pygame.draw.polygon(scr, (70, 68, 76), pts, 2)
            glow = 150 + int(math.sin(self.clock_t * 2 + sx) * 60)
            for i in range(3):                                      # светящиеся руны
                pygame.draw.line(scr, (glow, 90, 230), (cx - 3, sy + 6 + i * 9), (cx + 3, sy + 10 + i * 9), 2)
        elif t == "mound":
            pygame.draw.ellipse(scr, (112, 96, 70), (sx - 2, sy + 6, 44, 32))
            pygame.draw.ellipse(scr, (134, 116, 84), (sx + 6, sy + 10, 28, 18))
        elif t == "dark_heart":
            beat = 1 + 0.12 * max(0.0, math.sin(self.clock_t * 5))
            glow = pygame.Surface((80, 80), pygame.SRCALPHA)
            pygame.draw.circle(glow, (150, 60, 220, 70), (40, 40), int(30 * beat))
            scr.blit(glow, (cx - 40, cy - 40))
            r = int(9 * beat)
            col = (230, 230, 230) if hit else (34, 14, 44)
            pygame.draw.circle(scr, col, (cx - r // 2 - 1, cy - 3), r)
            pygame.draw.circle(scr, col, (cx + r // 2 + 1, cy - 3), r)
            pygame.draw.polygon(scr, col, [(cx - r * 1.5, cy), (cx + r * 1.5, cy), (cx, cy + r * 1.8)])
            pygame.draw.line(scr, (170, 80, 240), (cx - 4, cy - 6), (cx + 2, cy + 6), 2)       # трещины-жилы
            pygame.draw.line(scr, (170, 80, 240), (cx + 5, cy - 8), (cx + 1, cy), 2)
        elif t == "radio":
            pygame.draw.rect(scr, (115, 82, 50), (sx + 3, sy + 14, 34, 22), border_radius=3)      # стол
            pygame.draw.rect(scr, (70, 74, 70), (sx + 7, sy + 4, 26, 18), border_radius=3)        # корпус рации
            pygame.draw.rect(scr, (30, 34, 32), (sx + 9, sy + 6, 12, 8))
            n = len(self.story["installed"]) if hasattr(self, "story") else 0
            for i in range(3):                                       # три лампочки — три детали
                on = i < n
                pygame.draw.circle(scr, (120, 255, 140) if on else (90, 40, 40), (sx + 25 + (i % 2) * 5, sy + 8 + i * 4), 2)
            pygame.draw.circle(scr, (200, 200, 205), (sx + 15, sy + 18), 2)
            pygame.draw.line(scr, (180, 180, 186), (sx + 30, sy + 4), (sx + 36, sy - 8), 2)       # антенна
        elif t == "pad":
            pygame.draw.rect(scr, (120, 122, 128), (sx, sy, TILE, TILE))
            pygame.draw.rect(scr, (98, 100, 106), (sx, sy, TILE, TILE), 1)
            i = o.get("i", 4)
            if i == 4:                                              # центр — буква H
                for x in (cx - 8, cx + 6):
                    pygame.draw.line(scr, (240, 220, 80), (x, cy - 11), (x, cy + 11), 4)
                pygame.draw.line(scr, (240, 220, 80), (cx - 8, cy), (cx + 6, cy), 4)
            else:                                                   # жёлтая окантовка площадки
                if i < 3:
                    pygame.draw.line(scr, (230, 200, 60), (sx, sy + 3), (sx + TILE, sy + 3), 3)
                if i > 5:
                    pygame.draw.line(scr, (230, 200, 60), (sx, sy + TILE - 4), (sx + TILE, sy + TILE - 4), 3)
                if i % 3 == 0:
                    pygame.draw.line(scr, (230, 200, 60), (sx + 3, sy), (sx + 3, sy + TILE), 3)
                if i % 3 == 2:
                    pygame.draw.line(scr, (230, 200, 60), (sx + TILE - 4, sy), (sx + TILE - 4, sy + TILE), 3)
        elif t == "radio_mast":                                    # антенная мачта (высокая)
            top = sy - 96
            pygame.draw.line(scr, (150, 150, 158), (cx - 9, sy + 34), (cx, top), 3)
            pygame.draw.line(scr, (150, 150, 158), (cx + 9, sy + 34), (cx, top), 3)
            for i in range(1, 9):
                y = sy + 34 - i * 14
                k = 1 - i / 10
                pygame.draw.line(scr, (120, 120, 128), (cx - 9 * k, y), (cx + 9 * k, y - 7), 1)
            if int(self.clock_t * 1.5) % 2 == 0:
                pygame.draw.circle(scr, (255, 60, 50), (cx, top), 4)
        elif t == "heli":                                          # вертолёт на площадке (3×3 клетки)
            body = pygame.Rect(cx - 34, cy - 18, 68, 36)
            pygame.draw.ellipse(scr, (40, 60, 40), (cx - 40, cy + 8, 90, 22))                     # тень
            pygame.draw.rect(scr, (60, 64, 72), (cx + 28, cy - 4, 46, 8), border_radius=3)        # хвост
            pygame.draw.rect(scr, (210, 60, 50), (cx + 66, cy - 12, 8, 24), border_radius=2)
            pygame.draw.ellipse(scr, (220, 222, 228), body)
            pygame.draw.ellipse(scr, (200, 60, 50), (cx - 30, cy - 4, 56, 10))
            pygame.draw.ellipse(scr, (120, 180, 230), (cx - 32, cy - 12, 22, 22))                 # кабина
            pygame.draw.ellipse(scr, (60, 60, 66), body, 2)
            ang = self.clock_t * 9                                   # винт крутится
            for k in range(2):
                a = ang + k * math.pi / 2
                pygame.draw.line(scr, (50, 50, 56), (cx - math.cos(a) * 54, cy - math.sin(a) * 54),
                                 (cx + math.cos(a) * 54, cy + math.sin(a) * 54), 4)
            pygame.draw.circle(scr, (40, 40, 44), (cx, cy), 6)
        elif t == "garden":
            pygame.draw.rect(scr, (96, 66, 42), (sx + 3, sy + 3, 34, 34), border_radius=3)
            for i in range(3):
                pygame.draw.line(scr, (76, 52, 34), (sx + 6, sy + 10 + i * 10), (sx + 34, sy + 10 + i * 10), 2)
            if o.get("planted"):
                k = o["grow"] / GARDEN_TIME
                for gx in (sx + 12, sx + 28):
                    for gy in (sy + 12, sy + 28):
                        pygame.draw.circle(scr, (60, 140, 60), (gx, gy), int(2 + 5 * k))
                        if k >= 1:
                            pygame.draw.circle(scr, (210, 30, 70), (gx + 2, gy - 2), 2)
        elif t == "trap":
            pygame.draw.circle(scr, (90, 90, 96), (cx, cy), 11, 3)
            for i in range(8):
                a = i / 8 * math.tau
                r1, r2 = (11, 5) if o["armed"] else (11, 9)
                pygame.draw.line(scr, (170, 170, 176), (cx + math.cos(a) * r1, cy + math.sin(a) * r1),
                                 (cx + math.cos(a) * r2, cy + math.sin(a) * r2), 2)
        elif t == "torch_post":
            pygame.draw.line(scr, (100, 70, 40), (cx, sy + 36), (cx, sy + 2), 4)
            fl = math.sin(self.clock_t * 15 + sx) * 1.5
            pygame.draw.circle(scr, (240, 120, 30), (cx, sy + 2), int(6 + fl))
            pygame.draw.circle(scr, (255, 220, 90), (cx, sy + 1), 3)
        elif t == "fire":
            for i in range(7):
                a = i / 7 * math.tau
                pygame.draw.circle(scr, (110, 110, 115), (int(cx + math.cos(a) * 13), int(cy + math.sin(a) * 11)), 4)
            pygame.draw.line(scr, (90, 60, 35), (cx - 8, cy + 5), (cx + 8, cy - 4), 4)
            pygame.draw.line(scr, (90, 60, 35), (cx - 8, cy - 4), (cx + 8, cy + 5), 4)
            if o["fuel"] > 0:
                fl = math.sin(self.clock_t * 17 + cx) * 2 + random.uniform(-1, 1)
                pygame.draw.circle(scr, (230, 90, 20), (cx, cy - 3), int(9 + fl))
                pygame.draw.circle(scr, (255, 170, 40), (cx, cy - 4), int(6 + fl * 0.6))
                pygame.draw.circle(scr, (255, 240, 150), (cx, cy - 5), 3)
            else:
                pygame.draw.circle(scr, (40, 40, 44) if o.get("coal") else (70, 70, 70), (cx, cy), 6)

    def draw_flames(self, sx, sy, seed):
        scr = self.screen
        t = self.clock_t * 9 + seed
        for i in range(3):
            fx = sx + 10 + i * 10 + math.sin(t + i) * 3
            h = 14 + math.sin(t * 1.3 + i * 2) * 5
            pygame.draw.polygon(scr, (240, 110, 30), [(fx - 7, sy + 34), (fx, sy + 30 - h * 1.6), (fx + 7, sy + 34)])
            pygame.draw.polygon(scr, (255, 210, 80), [(fx - 3, sy + 34), (fx, sy + 32 - h), (fx + 3, sy + 34)])

    # ------------------------------------------------------------ крыши, вышки и входы
    def player_inside(self, r):
        p = self.player
        x, y, w, h = r["rect"]
        return not p.on_tower and x <= int(p.x // TILE) < x + w and y <= int(p.y // TILE) < y + h

    def draw_roofs(self):
        scr = self.screen
        p = self.player
        w = self.world
        for ri, r in enumerate(w.roofs):
            if r["ruined"]:
                continue
            x, y, rw, rh = r["rect"]
            sx, sy = x * TILE - self.cam_x, y * TILE - self.cam_y
            W, H = rw * TILE, rh * TILE
            if sx > SCREEN_W or sy > SCREEN_H + 60 or sx + W < 0 or sy + H < -60:
                continue
            if self.player_inside(r):
                pygame.draw.rect(scr, (255, 255, 255), (sx, sy, W, H), 1)       # ты внутри — крыша скрыта
                continue
            if r["kind"] == "house":
                rect = pygame.Rect(sx - 4, sy - 8, W + 8, H + 8)
                pygame.draw.rect(scr, (104, 56, 44), rect, border_radius=4)
                for yy in range(rect.y + 8, rect.bottom, 10):
                    pygame.draw.line(scr, (84, 44, 34), (rect.x + 2, yy), (rect.right - 3, yy), 1)
                pygame.draw.line(scr, (140, 76, 58), (rect.x + 4, rect.centery), (rect.right - 5, rect.centery), 4)
                pygame.draw.rect(scr, (60, 30, 24), rect, 2, border_radius=4)
            elif r["kind"] == "hut":
                rect = pygame.Rect(sx - 6, sy - 10, W + 12, H + 12)
                pygame.draw.ellipse(scr, (176, 146, 82), rect)
                c = rect.center
                for i in range(12):
                    a = i / 12 * math.tau
                    pygame.draw.line(scr, (146, 116, 62), c, (c[0] + math.cos(a) * W * 0.55, c[1] + math.sin(a) * H * 0.55), 2)
                pygame.draw.ellipse(scr, self.fac_color(r["fac"]), rect, 3)
                pygame.draw.circle(scr, (200, 172, 100), c, 9)
                pygame.draw.circle(scr, (120, 90, 50), c, 9, 2)
            else:
                self.draw_tower(ri, r, sx, sy, W, H)
            self.draw_entrance(r, sx, sy)

    def draw_tower(self, ri, r, sx, sy, W, H):
        """Смотровая вышка: столбы, раскосы, площадка с перилами, люк с лестницей, постройки на площадке."""
        scr = self.screen
        w = self.world
        sh = pygame.Surface((W, H), pygame.SRCALPHA)
        sh.fill((0, 0, 0, 55))
        scr.blit(sh, (sx + 10, sy + 6))
        dark, mid = (66, 44, 26), (96, 66, 38)
        corners = ((sx + 5, sy + 6), (sx + W - 5, sy + 6), (sx + 5, sy + H - 4), (sx + W - 5, sy + H - 4))
        for px_, py_ in corners:                                   # столбы до земли
            pygame.draw.line(scr, dark, (px_, py_), (px_, py_ - DECK_H), 8)
            pygame.draw.circle(scr, (50, 34, 20), (px_, py_), 5)
        bl, br = corners[2], corners[3]
        pygame.draw.line(scr, mid, bl, (br[0], br[1] - DECK_H + 6), 4)    # раскосы спереди
        pygame.draw.line(scr, mid, br, (bl[0], bl[1] - DECK_H + 6), 4)
        plat = pygame.Rect(sx - 6, sy - DECK_H - 6, W + 12, H + 12)
        pygame.draw.rect(scr, (132, 94, 56), plat)
        for xx in range(plat.x + 6, plat.right, 10):
            pygame.draw.line(scr, (108, 76, 44), (xx, plat.y + 4), (xx, plat.bottom - 4), 1)
        pygame.draw.rect(scr, (80, 54, 32), plat, 6)                     # перила
        for xx in range(plat.x, plat.right + 1, 40):
            for yy in (plat.y, plat.bottom - 7):
                pygame.draw.rect(scr, (60, 40, 22), (min(xx, plat.right - 7), yy, 7, 7))
        for yy in range(plat.y, plat.bottom + 1, 40):
            for xx in (plat.x, plat.right - 7):
                pygame.draw.rect(scr, (60, 40, 22), (xx, min(yy, plat.bottom - 7), 7, 7))
        if r.get("ladder"):                                        # люк
            lx, ly = r["ladder"]
            hx, hy = lx * TILE - self.cam_x + 6, ly * TILE - self.cam_y - DECK_H + 6
            pygame.draw.rect(scr, (40, 28, 16), (hx, hy, 28, 28))
            for i in range(4):
                pygame.draw.line(scr, (150, 110, 65), (hx + 6, hy + 4 + i * 7), (hx + 22, hy + 4 + i * 7), 2)
        pole = (plat.right - 10, plat.y + 6)                       # флажок вышки
        pygame.draw.line(scr, (60, 40, 22), pole, (pole[0], pole[1] - 30), 3)
        wave = math.sin(self.clock_t * 5 + ri) * 3
        pygame.draw.polygon(scr, (200, 60, 50), [(pole[0], pole[1] - 30), (pole[0] - 16, pole[1] - 25 + wave),
                                                 (pole[0], pole[1] - 20)])
        x, y, rw, rh = r["rect"]
        for (tx, ty), o in w.deck.items():
            if x <= tx < x + rw and y <= ty < y + rh:
                self.draw_flat(tx * TILE - self.cam_x, ty * TILE - self.cam_y - DECK_H, o)

    def draw_entrance(self, r, sx, sy):
        """Где вход: тёмный проём на краю крыши и мигающие стрелки снаружи."""
        if not r.get("door"):
            return
        scr = self.screen
        p = self.player
        x, y, rw, rh = r["rect"]
        dx, dy = r["door"]
        out = (-1, 0) if dx == x else (1, 0) if dx == x + rw - 1 else (0, -1) if dy == y else (0, 1)
        dsx, dsy = dx * TILE - self.cam_x, dy * TILE - self.cam_y
        lift = DECK_H if r["kind"] == "tower" and out[1] == -1 else 0
        if r["kind"] != "tower":
            pygame.draw.rect(scr, (34, 24, 16), (dsx + 6, dsy + 6, TILE - 12, TILE - 12), border_radius=4)
            pygame.draw.rect(scr, (220, 190, 110), (dsx + 6, dsy + 6, TILE - 12, TILE - 12), 2, border_radius=4)
        dist = math.hypot(p.x - (dx + 0.5) * TILE, p.y - (dy + 0.5) * TILE)
        if dist > 11 * TILE:
            return
        cx, cy = dsx + 20 + out[0] * 34, dsy + 20 + out[1] * (34 + lift)
        pulse = (math.sin(self.clock_t * 5) + 1) / 2
        col = (255, int(200 + 40 * pulse), 90)
        for i in range(2):
            ox, oy = cx + out[0] * (i * 10 - pulse * 4), cy + out[1] * (i * 10 - pulse * 4)
            ix, iy = -out[0], -out[1]                    # стрелка смотрит внутрь, к двери
            px_, py_ = -iy, ix
            tip = (ox + ix * 7, oy + iy * 7)
            pygame.draw.lines(scr, col, False, [(ox - ix * 3 + px_ * 8, oy - iy * 3 + py_ * 8), tip,
                                                (ox - ix * 3 - px_ * 8, oy - iy * 3 - py_ * 8)], 3)
        if dist < 8 * TILE:
            self.text("ВХОД", self.font_s, col, (round(cx + out[0] * 26), round(cy + out[1] * 26)), center=True)

    # ------------------------------------------------------------ существа
    def draw_creature(self, a):
        scr = self.screen
        sx, sy = int(a.x - self.cam_x), int(a.y - self.cam_y)
        frame = int(a.anim_t) % 4 if a.walking else 0
        if a.beh == "boss":                                       # аура босса — видно издалека, что это не простой зверь
            pulse = int(math.sin(self.clock_t * 4) * 4)
            aura = pygame.Surface((a.r * 4, a.r * 4), pygame.SRCALPHA)
            pygame.draw.circle(aura, (170, 70, 230, 60), (a.r * 2, a.r * 2), a.r + 12 + pulse)
            pygame.draw.circle(aura, (200, 120, 255, 150), (a.r * 2, a.r * 2), a.r + 12 + pulse, 2)
            scr.blit(aura, (sx - a.r * 2, sy - a.r * 2))
        if a.kind in ("shadow", "barrow_lord"):
            col = (255, 120, 120) if a.hurt > 0 else tuple(a.color)
            fx, fy = math.cos(a.face), math.sin(a.face)
            s = pygame.Surface((a.r * 6, a.r * 6), pygame.SRCALPHA)
            c = a.r * 3
            wob = math.sin(self.clock_t * 6 + id(a) % 9)
            for i in range(4):
                pygame.draw.circle(s, (*col, 70), (int(c - fx * (i + 1) * 8 - fy * wob * 4),
                                                   int(c - fy * (i + 1) * 8 + fx * wob * 4)), a.r - i * 2)
            pygame.draw.circle(s, (*col, 170), (c, c), a.r)
            pygame.draw.circle(s, (30, 10, 50, 200), (c, c), a.r - 4)
            if a.kind == "barrow_lord":                          # Владыка: горящие глаза и золотая корона
                for sg in (-1, 1):
                    ex, ey = c + fx * 8 - fy * sg * 7, c + fy * 8 + fx * sg * 7
                    pygame.draw.circle(s, (255, 120, 255, 255), (int(ex), int(ey)), 4)
                crown = [(c - 14, c - a.r + 2), (c - 14, c - a.r - 10), (c - 7, c - a.r - 3), (c, c - a.r - 14),
                         (c + 7, c - a.r - 3), (c + 14, c - a.r - 10), (c + 14, c - a.r + 2)]
                pygame.draw.polygon(s, (230, 190, 70, 255), crown)
                pygame.draw.polygon(s, (120, 90, 30, 255), crown, 2)
            scr.blit(s, (sx - c, sy - c))
        else:
            base, _ = self.creature_base(a, frame)
            if not a.human:
                pygame.draw.ellipse(scr, (30, 50, 30), (sx - a.r, sy + a.r - 8, a.r * 2, 10))
            if a.hurt > 0 and not a.human:
                base = base.copy()
                base.fill((255, 90, 90, 0), special_flags=pygame.BLEND_RGBA_MAX)
            spr = sprites.rotated(base, a.face)
            scr.blit(spr, spr.get_rect(center=(sx, sy)))
            if a.human:
                self.draw_human_weapon(a, sx, sy)
        if a.stun_t > 0:
            for i in range(3):
                ang = self.clock_t * 5 + i * 2.1
                pygame.draw.circle(scr, (255, 240, 150), (int(sx + math.cos(ang) * 10), int(sy - a.r - 8 + math.sin(ang) * 3)), 2)
        if a.sleeping:                                            # медведь в спячке
            for i in range(3):
                bob = (self.clock_t * 12 + i * 5) % 14
                self.text("z", self.font_s if i < 2 else self.font, (225, 230, 255),
                          (sx + 12 + i * 7, int(sy - a.r - 6 - i * 9 - bob)), center=True)
        if a.kind == "dog" and (a.ally or a.trust):
            if a.ally:
                pygame.draw.circle(scr, (110, 230, 110), (sx, sy), a.r + 5, 2)
            tag = f"{a.name} (твой пёс)" if a.ally else f"Пёс · доверие {a.trust}/3"
            img = self.font_s.render(tag, True, (160, 255, 160) if a.ally else (255, 210, 220))
            scr.blit(img, img.get_rect(center=(sx, sy - a.r - 24)))
        if a.burn_t > 0:
            self.draw_flames(sx - 20, sy - 30, id(a) % 10)
        threat = self.is_threat(a)
        p = self.player
        near = abs(a.x - p.x) < 11 * TILE and abs(a.y - p.y) < 8 * TILE
        if a.hp < a.max_hp or (threat and near):
            w = max(26, a.r * 2 + 6)
            self.bar(sx - w // 2, sy - a.r - 14, w, a.hp / a.max_hp)
        if a.beh == "boss" and near:
            self.text(ANIMALS[a.kind]["name"], self.font_s, (230, 190, 255),
                      (sx, sy - a.r - (44 if a.chasing else 30)), center=True)
        if a.chasing:                                             # «!» — атакует тебя
            bob = math.sin(self.clock_t * 8) * 2
            cy = int(sy - a.r - 26 + bob)
            pygame.draw.circle(scr, (220, 40, 30), (sx, cy), 8)
            pygame.draw.circle(scr, (255, 230, 220), (sx, cy), 8, 2)
            pygame.draw.line(scr, (255, 255, 255), (sx, cy - 4), (sx, cy + 1), 2)
            pygame.draw.circle(scr, (255, 255, 255), (sx, cy + 4), 1)
        if a.human and math.hypot(a.x - p.x, a.y - p.y) < 7 * TILE:
            if a.ally:
                ncol, tag = (140, 255, 140), f"{a.name} ({'житель' if a.settler else 'спутник'})"
            else:
                f = self.world.factions[a.faction]
                att = "hostile" if self.fac_hostile(a.faction) else self.attitude(f)
                ncol = {"friend": (140, 255, 140), "truce": (140, 220, 255), "neutral": (255, 230, 140),
                        "hostile": (255, 110, 100)}[att]
                tag = f"{ROLES[a.role]['name']} {a.name}" + (" (в походе)" if a.war_target >= 0 else "")
            img = self.font_s.render(tag, True, ncol)
            scr.blit(img, img.get_rect(center=(sx, sy - a.r - (40 if a.chasing else 26))))

    def draw_human_weapon(self, a, sx, sy):
        fx, fy = math.cos(a.face), math.sin(a.face)
        px, py = -fy, fx
        prog = 1 - a.swing / 0.3 if a.swing > 0 else 0
        push = math.sin(prog * math.pi) * 14 if a.swing > 0 else 0
        weapon = ROLES[a.role]["weapon"] if a.role else "spear"
        spr = pygame.transform.rotate(self.item_sprite(weapon), -math.degrees(a.face) - 45)
        hx, hy = sx + px * 9 + fx * (12 + push), sy + py * 9 + fy * (12 + push)
        self.screen.blit(spr, spr.get_rect(center=(int(hx), int(hy))))
        skin = (160, 108, 72) if a.faction >= 0 and self.world.factions[a.faction]["type"] == "tribe" else (214, 172, 138)
        pygame.draw.circle(self.screen, skin, (int(sx + px * 9 + fx * (6 + push)), int(sy + py * 9 + fy * (6 + push))), 4)
        pygame.draw.circle(self.screen, skin, (int(sx - px * 9 + fx * 6), int(sy - py * 9 + fy * 6)), 4)

    def draw_player(self):
        p = self.player
        scr = self.screen
        sx, sy = int(p.x - self.cam_x), int(p.y - self.cam_y)
        if p.on_tower:
            sy -= DECK_H
        in_water = self.player_in_water()
        if not p.on_tower and not in_water:
            pygame.draw.ellipse(scr, (30, 60, 30), (sx - 13, sy + 8, 26, 10))
        prog = 1 - p.swing / 0.3 if p.swing > 0 else 0
        k = math.sin(prog * math.pi) if p.swing > 0 else 0
        push = 0
        if p.anim == "thrust":                       # укол: оружие уходит вперёд
            ang, push = p.angle, k * 20
        elif p.anim == "wide":                       # широкий взмах
            ang = p.angle + 1.0 - prog * 2.0 if p.swing > 0 else p.angle
        elif p.anim in ("bow", "gun"):               # отдача
            ang, push = p.angle, -k * 6
        else:
            ang = p.angle - k * 0.9
        if p.cloak:
            pygame.draw.circle(scr, (120, 88, 60), (sx, sy), 16)
        key, spec = self.player_spec()
        frame = int(p.walk_t) % 4 if p.moving else 0
        spr = sprites.rotated(sprites.human_base(key, frame, spec), p.angle)
        scr.blit(spr, spr.get_rect(center=(sx, sy)))
        skin = (226, 184, 150)
        fx, fy = math.cos(p.angle), math.sin(p.angle)
        thrust = p.anim in ("thrust", "bow", "gun") and p.held_id()
        for s in (-0.75, 0.75):
            a = (ang if s > 0 else p.angle) + (s * 0.5 if thrust else s)
            hx, hy = sx + math.cos(a) * 14 + fx * push, sy + math.sin(a) * 14 + fy * push
            pygame.draw.circle(scr, skin, (int(hx), int(hy)), 4)
            pygame.draw.circle(scr, (40, 30, 24), (int(hx), int(hy)), 4, 1)
        iid = p.held_id()
        if iid:
            a = ang + (0.35 if thrust else 0.75)
            hx, hy = sx + math.cos(a) * 14 + fx * push, sy + math.sin(a) * 14 + fy * push
            spr = pygame.transform.rotate(self.item_sprite(iid), -math.degrees(ang) - 45)
            reach = 16 if iid in ("spear", "iron_spear", "fishing_rod") else 10
            scr.blit(spr, spr.get_rect(center=(int(hx + math.cos(ang) * reach), int(hy + math.sin(ang) * reach))))
            if p.flash > 0:
                mx, my = hx + math.cos(ang) * 30, hy + math.sin(ang) * 30
                pygame.draw.circle(scr, (255, 230, 120), (int(mx), int(my)), 8)
                pygame.draw.circle(scr, (255, 255, 230), (int(mx), int(my)), 4)
        if p.fishing:
            fx_, fy_ = p.fishing[1] * TILE + 20 - self.cam_x, p.fishing[2] * TILE + 20 - self.cam_y
            pygame.draw.line(scr, (230, 230, 230), (sx + fx * 30, sy + fy * 30), (fx_, fy_), 1)
            bob = math.sin(self.clock_t * 6) * 2
            pygame.draw.circle(scr, (230, 60, 50), (int(fx_), int(fy_ + bob)), 4)
        if in_water:
            wave = math.sin(self.clock_t * 4) * 2
            pygame.draw.ellipse(scr, (52, 108, 178), (sx - 16, sy + 5 + wave, 32, 11))
            pygame.draw.ellipse(scr, (170, 210, 245), (sx - 20, sy - 4 + wave, 40, 22), 2)

    # ------------------------------------------------------------ мир целиком
    def draw_ground_tile(self, g, tx, ty, sx, sy, s):
        scr = self.screen
        season = self.world.season
        r, gg, b = GROUND_COL[g]
        hv = tile_hash(tx, ty)
        h = hv % 7
        if g == WATER and self.world.frozen:                  # лёд
            pygame.draw.rect(scr, (clamp(196 + s, 0, 255), clamp(222 + s, 0, 255), 238), (sx, sy, TILE, TILE))
            if h < 2:
                pygame.draw.line(scr, (240, 248, 255), (sx + 6, sy + 10 + h * 8), (sx + 30, sy + 20 + h * 5), 1)
            return
        if season == "winter" and g in (GRASS, STEPPE, SWAMP, SAND, ROCKY, MEADOW):
            r, gg, b = ((r + 3 * 226) // 4, (gg + 3 * 232) // 4, (b + 3 * 240) // 4)
            g = SNOW
        elif season == "autumn" and g in (GRASS, MEADOW):
            r, gg, b = (112, 122, 56) if g == GRASS else (124, 128, 62)
        if g == WATER:
            s += int(math.sin(self.clock_t * 1.5 + tx * 0.7 + ty * 0.4) * 6)
        elif g in (FLOOR, DITCH):
            s //= 2
        pygame.draw.rect(scr, (clamp(r + s, 0, 255), clamp(gg + s, 0, 255), clamp(b + s, 0, 255)), (sx, sy, TILE, TILE))
        if g == MEADOW:                                       # цветочная поляна: много цветов на каждой клетке
            n = (2 if season == "autumn" else 6) + (hv >> 5) % 3
            for i in range(n):
                v = tile_hash(tx, ty, i + 1)
                px, py = sx + 3 + v % 34, sy + 3 + (v >> 8) % 34
                col = FLOWER_COLS[(v >> 16) % len(FLOWER_COLS)] if season != "autumn" else (150, 120, 70)
                pygame.draw.line(scr, (52, 110, 44), (px, py + 2), (px, py + 5), 1)
                pygame.draw.circle(scr, col, (px, py), 2)
                if (v >> 20) % 3 == 0:
                    pygame.draw.circle(scr, (255, 240, 150), (px, py), 1)
        elif g == GRASS and season in ("spring", "summer") and hv % 100 < (5 if season == "spring" else 3):
            for i in range(1 + (hv >> 7) % 2):                # редкие одиночные цветочки в лесу
                v = tile_hash(tx, ty, i + 11)
                pygame.draw.circle(scr, FLOWER_COLS[(v >> 16) % len(FLOWER_COLS)],
                                   (sx + 5 + v % 30, sy + 5 + (v >> 8) % 30), 2)
        if g == FLOOR:
            for i in (13, 26):
                pygame.draw.line(scr, (96, 70, 46), (sx, sy + i), (sx + TILE, sy + i), 1)
        elif g == DITCH:
            pygame.draw.rect(scr, (46, 32, 22), (sx + 4, sy + 4, TILE - 8, TILE - 8))
            pygame.draw.rect(scr, (92, 68, 46), (sx, sy, TILE, TILE), 3)
        elif g == SNOW and h < 3:
            pygame.draw.circle(scr, (250, 252, 255), (sx + 8 + h * 9, sy + 12 + h * 5), 2)
            pygame.draw.circle(scr, (200, 210, 225), (sx + 30 - h * 4, sy + 30), 2)
        elif g == SWAMP and h < 3:
            pygame.draw.ellipse(scr, (52, 74, 66), (sx + 4 + h * 5, sy + 10 + h * 4, 22, 12))
            pygame.draw.ellipse(scr, (90, 120, 110), (sx + 9 + h * 5, sy + 13 + h * 4, 6, 3))
        elif g == STEPPE and h < 4:
            for i in range(3):
                x = sx + 6 + i * 12 + h
                pygame.draw.line(scr, (150, 140, 70), (x, sy + 30), (x + 3, sy + 20), 1)
        elif g == ROCKY and h < 3:
            pygame.draw.lines(scr, (98, 94, 90), False, [(sx + 6, sy + 10 + h * 5), (sx + 18, sy + 16 + h * 3),
                                                         (sx + 30, sy + 12 + h * 6)], 1)

    def draw_world(self):
        scr = self.screen
        w = self.world
        cam_x, cam_y = self.cam_x, self.cam_y
        tx0, ty0 = int(cam_x // TILE), int(cam_y // TILE)
        tx1, ty1 = tx0 + SCREEN_W // TILE + 2, ty0 + SCREEN_H // TILE + 2
        tall = []
        self.post_lights = []
        self.fire_lights = []
        for ty in range(ty0, ty1):
            for tx in range(tx0, tx1):
                sx, sy = tx * TILE - cam_x, ty * TILE - cam_y
                if not w.in_bounds(tx, ty):
                    pygame.draw.rect(scr, (30, 70, 130), (sx, sy, TILE, TILE))
                    continue
                self.draw_ground_tile(w.ground[ty][tx], tx, ty, sx, sy, w.shade[ty][tx])
        for bx, by, t in self.blood:                               # капли крови
            pygame.draw.circle(scr, (150, 20, 20) if t > 10 else (110, 30, 25), (int(bx - cam_x), int(by - cam_y)),
                               2 if t > 15 else 1)
        if self.flag and (self.build_mode or (self.hover and self.hover.get("obj", {}).get("t") == "flag")):
            fx, fy = (self.flag[0] + 0.5) * TILE - cam_x, (self.flag[1] + 0.5) * TILE - cam_y
            pygame.draw.circle(scr, (90, 170, 255), (int(fx), int(fy)), SETTLE_RADIUS * TILE, 2)
        for ty in range(ty0 - 1, ty1 + 3):
            for tx in range(tx0 - 1, tx1 + 1):
                o = w.objects.get((tx, ty))
                if not o:
                    continue
                sx, sy = tx * TILE - cam_x, ty * TILE - cam_y
                t = o["t"]
                if t == "tree":
                    tall.append(((ty + 1) * TILE - 6, 0, (sx, sy, o)))
                elif t in ("totem", "torch_post", "palisade", "camp_banner", "flag", "radio_mast", "heli", "menhir",
                           "ice_spike", "den"):
                    tall.append(((ty + 1) * TILE - 8 + (TILE if t == "heli" else 0), 4, (sx, sy, o)))
                    if t in LIGHT_OBJ:
                        self.post_lights.append((tx * TILE + 20, ty * TILE + 4, LIGHT_OBJ[t]))
                else:
                    self.draw_flat(sx, sy, o)
                    if t == "dark_heart":                          # Чёрное сердце светится лиловым и ночью
                        self.post_lights.append((tx * TILE + 20, ty * TILE + 20, 150))
                if t in BREAKABLE and o.get("hp", 1e9) < BREAKABLE[t][2] and t not in TURRETS:
                    self.bar(sx + 4, sy + TILE - 6, TILE - 8, o["hp"] / BREAKABLE[t][2], 3)

        p = self.player
        if self.build_mode and self.menu is None:
            self.draw_build_ghost(*self.mouse_tile())

        for a in self.animals:
            if -60 < a.x - cam_x < SCREEN_W + 60 and -60 < a.y - cam_y < SCREEN_H + 60:
                tall.append((a.y + a.r, 1, a))
        if not p.on_tower:
            tall.append((p.y + p.r, 2, None))
        tall.sort(key=lambda d: (d[0], d[1]))
        for _, kind, obj in tall:
            if kind == 0:
                self.draw_tree(*obj)
            elif kind == 1:
                self.draw_creature(obj)
            elif kind == 2:
                self.draw_player()
            else:
                self.draw_flat(*obj)

        self.draw_roofs()
        if p.on_tower:
            if self.build_mode and self.menu is None:
                self.draw_build_ghost(*self.mouse_tile())
            self.draw_player()
        for (tx, ty) in w.burning:
            sx, sy = tx * TILE - cam_x, ty * TILE - cam_y
            if -TILE < sx < SCREEN_W and -TILE < sy < SCREEN_H:
                self.draw_flames(sx, sy, tx * 7 + ty)
                if len(self.fire_lights) < 30:
                    self.fire_lights.append((tx * TILE + 20, ty * TILE + 20))

        for pr in self.projectiles:
            x, y = pr["x"] - cam_x, pr["y"] - cam_y
            ln = math.hypot(pr["vx"], pr["vy"]) or 1
            kind = pr["kind"]
            if kind == "stone":
                pygame.draw.circle(scr, (150, 150, 155), (int(x), int(y)), 3)
            elif kind == "bomb":
                lift = math.sin(min(1.0, pr["life"] * 2) * math.pi) * 10
                pygame.draw.circle(scr, (200, 100, 40), (int(x), int(y - lift)), 5)
                pygame.draw.circle(scr, (255, 220, 120), (int(x + 3), int(y - lift - 4)), 2)
            elif kind == "spit":                                   # плевок ядом
                pygame.draw.circle(scr, (90, 170, 50), (int(x), int(y)), 6)
                pygame.draw.circle(scr, (170, 255, 110), (int(x - 1), int(y - 1)), 3)
                pygame.draw.circle(scr, (120, 200, 70), (int(x - pr["vx"] / ln * 8), int(y - pr["vy"] / ln * 8)), 3)
            elif pr.get("freeze"):                                 # ледяная стрела
                pygame.draw.line(scr, (190, 230, 255), (x, y), (x - pr["vx"] / ln * 18, y - pr["vy"] / ln * 18), 3)
                pygame.draw.circle(scr, (240, 250, 255), (int(x), int(y)), 3)
            else:
                col, length = {"bullet": ((255, 240, 170), 26), "pellet": ((255, 220, 150), 12),
                               "bolt": ((200, 200, 210), 20)}.get(kind, ((220, 210, 170), 16))
                if pr.get("fire"):
                    col = (255, 150, 50)
                pygame.draw.line(scr, col, (x, y), (x - pr["vx"] / ln * length, y - pr["vy"] / ln * length), 2)
                if pr.get("fire"):
                    pygame.draw.circle(scr, (255, 200, 80), (int(x), int(y)), 3)
        for ex, ey, t in self.explosions:
            k = 1 - t / 0.5
            pygame.draw.circle(scr, (255, int(200 - 120 * k), 60), (int(ex - cam_x), int(ey - cam_y)), int(10 + 50 * k),
                               max(1, int(8 * (1 - k))))

        for bx, by, t in self.breath:                              # пар изо рта
            s = pygame.Surface((16, 16), pygame.SRCALPHA)
            pygame.draw.circle(s, (240, 245, 255, int(120 * t / 1.2)), (8, 8), int(3 + (1.2 - t) * 5))
            scr.blit(s, (bx - cam_x - 8, by - cam_y - 8))
        self.draw_hover_tag()
        cache = self.__dict__.setdefault("popup_cache", {})
        if len(cache) > 80:
            cache.clear()
        for x, y, txt, col, t in self.popups:
            key = (txt, tuple(col))
            if key not in cache:
                cache[key] = self.font.render(txt, True, col)
            img = cache[key]
            img.set_alpha(int(255 * min(1, t)))
            scr.blit(img, img.get_rect(center=(int(x - cam_x), int(y - cam_y))))

    def draw_hover_tag(self):
        """Подсказка [E] прямо у предмета под курсором."""
        h = self.hover
        if not h or self.menu is not None:
            return
        scr = self.screen
        label = self.hover_label(h)
        if not label:
            return
        if h["kind"] == "npc":
            a = h["npc"]
            ax, ay = a.x - self.cam_x, a.y - self.cam_y - a.r - 56
            pygame.draw.circle(scr, (255, 220, 120) if not h["far"] else (150, 150, 150),
                               (int(a.x - self.cam_x), int(a.y - self.cam_y)), a.r + 6, 2)
        else:
            tx, ty = h["pos"]
            lift = DECK_H if h["kind"] in ("deck", "descend") else 0
            sx, sy = tx * TILE - self.cam_x, ty * TILE - self.cam_y - lift
            pygame.draw.rect(scr, (255, 220, 120) if not h["far"] else (150, 150, 150), (sx, sy, TILE, TILE), 2,
                             border_radius=4)
            ax, ay = sx + 20, sy - 22
        img = self.font_s.render(label, True, (255, 245, 220) if not h["far"] else (190, 190, 190))
        w = img.get_width() + 34
        box = pygame.Rect(0, 0, w, 24)
        box.center = (int(ax), int(ay))
        box.clamp_ip(pygame.Rect(4, 4, SCREEN_W - 8, SCREEN_H - 8))
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((15, 15, 20, 210))
        scr.blit(s, box.topleft)
        pygame.draw.rect(scr, (255, 214, 90) if not h["far"] else (110, 110, 120), box, 1, border_radius=5)
        key = pygame.Rect(box.x + 4, box.y + 3, 18, 18)
        pygame.draw.rect(scr, (255, 214, 90) if not h["far"] else (120, 120, 120), key, border_radius=4)
        self.text("E", self.font_s, (20, 20, 20), key.center, center=True, shadow=False)
        scr.blit(img, (box.x + 28, box.y + 3))

    def draw_build_ghost(self, tx, ty):
        scr = self.screen
        lift = DECK_H if self.player.on_tower else 0
        sx, sy = tx * TILE - self.cam_x, ty * TILE - self.cam_y - lift
        if self.demolish:
            store = self.world.deck if self.player.on_tower else self.world.objects
            o = store.get((tx, ty))
            ok = (o and o.get("own")) or (tx, ty) in self.world.own_floor
            pygame.draw.rect(scr, (255, 80, 60) if ok else (120, 120, 120), (sx, sy, TILE, TILE), 3)
            pygame.draw.line(scr, (255, 80, 60), (sx + 8, sy + 8), (sx + 32, sy + 32), 3)
            pygame.draw.line(scr, (255, 80, 60), (sx + 32, sy + 8), (sx + 8, sy + 32), 3)
            return
        b = BUILD_BY_ID[self.build_sel]
        bid = b["id"]
        err = self.build_check(bid, tx, ty)
        afford = all(self.player.res[k] >= v for k, v in b["cost"].items())
        if bid in ("floor", "ditch"):
            pygame.draw.rect(scr, GROUND_COL[FLOOR if bid == "floor" else DITCH], (sx, sy, TILE, TILE))
        else:
            self.draw_flat(sx, sy, self.preview_obj(bid))
        ok = not err and afford
        s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        s.fill((80, 255, 80, 70) if ok else (255, 60, 60, 90))
        scr.blit(s, (sx, sy))
        pygame.draw.rect(scr, (80, 255, 80) if ok else (255, 60, 60), (sx, sy, TILE, TILE), 2)
        if err:
            self.text(err, self.font_s, (255, 150, 140), (sx + 20, sy - 12), center=True)

    @staticmethod
    def preview_obj(bid):
        return {"t": bid, "fuel": 1, "hp": 10, "res": {}, "tools": [], "armed": True, "planted": False, "grow": 0,
                "ammo": 40, "ang": 0.0, "hidden": False}

    # ------------------------------------------------------------ свет и погода
    def draw_lighting(self):
        d = min(1.0, self.darkness() + (0.25 if self.weather == "rain" else 0.4 if self.weather == "storm" else 0))
        p = self.player
        if d > 0.01:
            dark = self.dark_surf
            dark.fill((*DARK_RGB, int(228 * d)))
            py = p.y - (DECK_H if p.on_tower else 0)
            lights = [(p.x, py, 380 if p.on_tower else 100, False)]
            if p.light():
                lights.append((p.x, py, p.light() + math.sin(self.clock_t * 9) * 6, p.held_id() == "torch"))
            for (tx, ty) in self.world.fires:
                o = self.world.objects.get((tx, ty))
                if o and o["t"] == "fire" and o["fuel"] > 0:
                    k = min(1.0, 0.5 + o["fuel"] / 120)
                    lights.append((tx * TILE + 20, ty * TILE + 20, (300 + math.sin(self.clock_t * 7 + tx) * 10) * k, True))
            for x, y, r in self.post_lights:
                lights.append((x, y, r + math.sin(self.clock_t * 8 + x) * 6, True))
            for x, y in self.fire_lights:
                lights.append((x, y, 180, True))
            for (tx, ty), o in self.world.deck.items():
                if o["t"] == "torch_post":
                    lights.append((tx * TILE + 20, ty * TILE + 4 - DECK_H, 260, True))
            glows = []
            for x, y, r, warm in lights:
                r = max(16, int(r) // 8 * 8)
                sx, sy = x - self.cam_x, y - self.cam_y
                if -r < sx < SCREEN_W + r and -r < sy < SCREEN_H + r:
                    dark.blit(self.get_light(r), (sx - r, sy - r), special_flags=pygame.BLEND_RGBA_MIN)
                    if warm:
                        glows.append((sx, sy, r))
            self.screen.blit(dark, (0, 0))
            if d > 0.3:
                for sx, sy, r in glows[:24]:
                    self.screen.blit(self.get_glow(r), (sx - r, sy - r), special_flags=pygame.BLEND_RGB_ADD)
            if d > 0.5:
                for a in self.animals:
                    if a.beh in ("hunter", "shadow") or (a.chasing and a.human):
                        sx, sy = a.x - self.cam_x, a.y - self.cam_y
                        fx, fy = math.cos(a.face), math.sin(a.face)
                        col = (255, 60, 40) if a.beh == "hunter" else (225, 200, 255) if a.ghost else (255, 220, 120)
                        for s in (-1, 1):
                            pygame.draw.circle(self.screen, col, (int(sx + fx * (a.r + 3) - fy * 3 * s),
                                                                  int(sy + fy * (a.r + 3) + fx * 3 * s)), 2)
            if "blood_moon" in self.events and self.is_night():
                s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                s.fill((120, 0, 0, 55))
                self.screen.blit(s, (0, 0))
        if "fog" in self.events:
            fog = self.fog_surf
            fog.fill((*FOG_RGB, 215))
            r = 200
            fog.blit(self.get_light(r, FOG_RGB), (p.x - self.cam_x - r, p.y - self.cam_y - r),
                     special_flags=pygame.BLEND_RGBA_MIN)
            self.screen.blit(fog, (0, 0))

    def draw_weather(self):
        winter = self.world.season == "winter"
        blizzard = "blizzard" in self.events
        if winter and (self.raining() or blizzard):           # снегопад / метель
            n = len(self.rain_drops) if blizzard else 110
            wind = 420 if blizzard else 50
            for i in range(n):
                x, y = self.rain_drops[i]
                y = (y + (260 if blizzard else 70) / FPS) % SCREEN_H
                x = (x - (wind + math.sin(self.clock_t + i) * 30) / FPS) % SCREEN_W
                self.rain_drops[i] = (x, y)
                pygame.draw.circle(self.screen, (245, 248, 255), (int(x), int(y)), 2 if i % 3 else 1)
            if blizzard:
                p = self.player
                fog = self.fog_surf
                fog.fill((235, 240, 248, 170))
                r = 240
                fog.blit(self.get_light(r, (235, 240, 248)), (p.x - self.cam_x - r, p.y - self.cam_y - r),
                         special_flags=pygame.BLEND_RGBA_MIN)
                self.screen.blit(fog, (0, 0))
        elif self.raining():
            storm = self.weather == "storm"
            n = len(self.rain_drops) if storm else 140
            for i in range(n):
                x, y = self.rain_drops[i]
                y = (y + (1300 if storm else 900) / FPS) % SCREEN_H
                x = (x - (320 if storm else 160) / FPS) % SCREEN_W
                self.rain_drops[i] = (x, y)
                pygame.draw.line(self.screen, (160, 180, 220), (x, y), (x - (7 if storm else 4), y + 16), 1)
        if self.flash_t > 0:
            s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            s.fill((255, 255, 255, int(170 * self.flash_t / 0.15)))
            self.screen.blit(s, (0, 0))
