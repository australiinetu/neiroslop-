# -*- coding: utf-8 -*-
"""Генерация и состояние мира: биомы, объекты, постройки, крыши, фракции, огонь."""
import math
import random

import pygame

from .config import (TILE, GRASS, WATER, SAND, FLOOR, DITCH, SNOW, SWAMP, STEPPE, ROCKY, MEADOW, LAND, WORLD_SIZES,
                     DENSITIES, FACTION_AMOUNTS, CHEST_TOOLS, GARDEN_TIME, MAX_BURNING, TREE_SLOW, DITCH_SLOW,
                     BIOME_IDS)
from .data import ITEMS, LOOT, FACTION_TYPES, BLOCKING, DOORS, HITBOX, FLAMMABLE, LAIRS, NOTES
from .util import clamp, first_free, smooth_noise

CAMP_SIZE = {"village": (17, 17), "fort": (11, 11), "post": (9, 9), "shrine": (9, 9)}
BUILD_GROUND = {GRASS, STEPPE, SNOW, SWAMP, MEADOW}  # где можно ставить лагеря и дома
RESPAWN_GROUND = {"tuft": {GRASS, STEPPE}, "pebble": {GRASS, SAND, STEPPE, ROCKY}, "reed": {SWAMP},
                  "mushroom": {SWAMP, GRASS}, "toadstool": {SWAMP}, "dry_bush": {STEPPE}, "flower": {MEADOW}}
LAIR_SIZE = 9


class World:
    def __init__(self, seed, size="medium", density="normal", factions="normal"):
        rng = random.Random(seed)
        self.rng = rng
        self.seed = seed
        self.w = self.h = WORLD_SIZES[size][1]
        dens = DENSITIES[density][1]
        W, H = self.w, self.h
        h1 = smooth_noise(W, H, 18, rng)
        h2 = smooth_noise(W, H, 6, rng)
        f1 = smooth_noise(W, H, 14, rng)
        f2 = smooth_noise(W, H, 5, rng)
        tn = smooth_noise(W, H, 34, rng)
        mn = smooth_noise(W, H, 22, rng)
        self.ground = [[GRASS] * W for _ in range(H)]
        self.shade = [[rng.randint(-7, 7) for _ in range(W)] for _ in range(H)]
        self.objects = {}       # (tx, ty) -> dict
        self.deck = {}          # объекты на площадках вышек: (tx, ty) -> dict
        self.timed = set()      # объекты с таймерами (пни, кусты, грядки)
        self.fires = set()      # костры
        self.burning = {}       # горящие клетки: (tx, ty) -> сколько ещё гореть
        self.structs = []       # [вид, Rect в тайлах, индекс фракции или -1]
        self.roofs = []         # крыши домов, хижин и вышек
        self.factions = []
        self.own_floor = set()  # пол и рвы, сделанные игроком
        self.seen = set()       # открытые на карте постройки
        self.grow_mult = 1.0
        self.frozen = False     # зимой вода замерзает — по льду можно ходить
        self.season = "spring"
        self.lairs = []         # логова боссов
        self.radio = None       # радиостанция «Маяк-7»
        # цветочные поляны — отдельный шум со своим зерном, чтобы старые зёрна давали тот же остров
        meadow = smooth_noise(W, H, 9, random.Random(f"{seed}:meadow"))
        cx, cy = W // 2, H // 2
        for y in range(H):
            for x in range(W):
                e = h1[y][x] * 0.7 + h2[y][x] * 0.3
                dc = math.hypot(x - cx, y - cy)
                e -= max(0.0, dc / (W / 2) - 0.7) * 1.6   # остров: края уходят в воду
                if dc < 6:
                    e = max(e, 0.5)
                temp = tn[y][x] * 0.55 + (y / H) * 0.45   # север холоднее
                moist = mn[y][x]
                if e < 0.33:
                    g = WATER
                elif e < 0.37:
                    g = SAND
                elif dc < 7:
                    g = GRASS
                elif e > 0.64:
                    g = ROCKY
                elif temp < 0.43:
                    g = SNOW
                elif moist > 0.6 and e < 0.52:
                    g = SWAMP
                elif moist < 0.37:
                    g = STEPPE
                else:
                    g = GRASS
                if g == GRASS and meadow[y][x] > 0.76 and dc > 9:
                    g = MEADOW
                self.ground[y][x] = g
                if dc < 4:
                    continue
                forest = f1[y][x] * 0.75 + f2[y][x] * 0.25
                obj = self.gen_object(rng, g, forest, dens)
                if obj:
                    self.objects[(x, y)] = obj
        self.place_structures(rng, FACTION_AMOUNTS[factions][1])
        self.add_story(random.Random(f"{seed}:story"))

    def gen_object(self, rng, g, forest, dens):
        r, r2 = rng.random(), rng.random()
        if g == MEADOW:                                   # поляна: цветы, редкие дубы, ульи диких пчёл
            if r < 0.015 * dens:
                return self.new_tree(rng, "oak")
            if r < 0.24:
                return {"t": "flower", "c": rng.randrange(6)}
            if r < 0.26:
                return {"t": "bush", "berries": True, "timer": 0}
            if r2 < 0.012:
                return {"t": "hive", "honey": True, "timer": 0}
            return None
        if g == GRASS:
            if (forest > 0.56 and r < 0.55 * dens) or (forest > 0.46 and r < 0.12 * dens):
                return self.new_tree(rng)
            if r2 < 0.04:
                return {"t": "tuft"}
            if r2 < 0.055:
                return {"t": "bush", "berries": True, "timer": 0}
            if r2 < 0.07:
                return {"t": "pebble"}
            if r2 < 0.078:
                return {"t": "rock", "hp": 12}
            if r2 < 0.085:
                return {"t": "mushroom"}
        elif g == SNOW:
            if (forest > 0.52 and r < 0.45 * dens) or r < 0.05 * dens:
                return self.new_tree(rng, "snowpine")
            if r2 < 0.02:
                return {"t": "rock", "hp": 12}
            if r2 < 0.035:
                return {"t": "pebble"}
            if r2 < 0.045:
                return {"t": "bush", "berries": True, "timer": 0}
        elif g == SWAMP:
            if r < 0.06 * dens:
                return self.new_tree(rng, "dead")
            if r < 0.18:
                return {"t": "reed"}
            if r < 0.22:
                return {"t": "mushroom"}
            if r < 0.24:
                return {"t": "toadstool"}
        elif g == STEPPE:
            if r < 0.02 * dens:
                return self.new_tree(rng, "oak")
            if r < 0.07:
                return {"t": "dry_bush"}
            if r < 0.13:
                return {"t": "tuft"}
            if r < 0.15:
                return {"t": "pebble"}
            if r < 0.16:
                return {"t": "rock", "hp": 12}
        elif g == ROCKY:
            if r < 0.18:
                return {"t": "rock", "hp": 12}
            if r < 0.225:
                return {"t": "ore", "hp": 16}
            if r < 0.255:
                return {"t": "coal_node", "hp": 12}
            if r < 0.3:
                return {"t": "pebble"}
        elif g == SAND and r < 0.06:
            return {"t": "pebble"}
        return None

    # ------------------------------------------------------------ постройки
    def place_structures(self, rng, fac_counts):
        k = (self.w / 160) ** 2
        plan = []
        for ftype, cnt in fac_counts.items():
            plan += ["fac:" + ftype] * cnt
        plan += ["house"] * max(3, round(7 * k)) + ["tower"] * max(2, round(5 * k)) + ["camp"] * max(2, round(5 * k))
        for kind in plan:
            for _ in range(1500):
                if kind.startswith("fac:"):
                    ftype = kind[4:]
                    w, h = CAMP_SIZE[FACTION_TYPES[ftype]["camp"]]
                elif kind == "house":
                    w, h = rng.randint(6, 8), rng.randint(5, 6)
                else:
                    w, h = {"tower": (4, 4), "camp": (4, 3)}[kind]
                x, y = rng.randint(3, self.w - w - 3), rng.randint(3, self.h - h - 3)
                if not self.area_ok(x, y, w, h, gap=14 if kind.startswith("fac:") else 8):
                    continue
                if kind.startswith("fac:"):
                    camp = FACTION_TYPES[ftype]["camp"]
                    getattr(self, "build_" + camp)(rng, x, y, ftype)
                else:
                    getattr(self, "build_" + kind)(rng, x, y, w, h)
                break
        # в мире обязательно должно быть хотя бы одно ружьё
        chests = [o for o in self.objects.values() if o["t"] == "chest" and o.get("loot") == "house"]
        if chests and not any(t and t["id"] == "rifle" for o in chests for t in o["tools"]):
            c = rng.choice(chests)
            c["tools"][first_free(c["tools"])] = {"id": "rifle", "dur": 60}
            c["res"]["ammo"] = c["res"].get("ammo", 0) + 5

    def area_ok(self, x0, y0, w, h, gap=8, ground=BUILD_GROUND):
        for y in range(y0 - 1, y0 + h + 1):
            for x in range(x0 - 1, x0 + w + 1):
                if not self.in_bounds(x, y) or self.ground[y][x] not in ground:
                    return False
        r = pygame.Rect(x0, y0, w, h)
        if r.inflate(28, 28).collidepoint(self.w // 2, self.h // 2):
            return False
        return not any(r.colliderect(s[1].inflate(gap, gap)) for s in self.structs)

    def clear_area(self, x0, y0, w, h):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                self.objects.pop((x, y), None)

    def add_faction(self, rng, ftype, center, radius):
        t = FACTION_TYPES[ftype]
        used = {f["short"] for f in self.factions}
        short = rng.choice([n for n in t["names"] if n not in used] or t["names"])
        self.factions.append({
            "type": ftype, "short": short, "name": f"{t['prefix']} {short}", "color": list(rng.choice(t["colors"])),
            "rel": t["base_rel"], "truce": 0, "gift": 0, "anger": 0.0, "intrude": 0.0, "center": list(center),
            "radius": radius, "quest": None, "greet_day": 0, "trades": [], "trade_day": 0, "raid_day": 0,
            "wars": [], "alive": True, "threat_day": 0, "help_day": 0, "war_day": 0, "heart_broken": False})
        return len(self.factions) - 1

    def add_roof(self, kind, x0, y0, w, h, fac=-1):
        self.roofs.append({"rect": [x0, y0, w, h], "kind": kind, "fac": fac, "walls": 0, "ruined": False,
                           "door": None, "ladder": None})
        return len(self.roofs) - 1

    def ring_building(self, rng, x0, y0, w, h, wall, hp, door, ri, fac=-1, round_corners=False, holes=0.0):
        """Стены по периметру с дверным проёмом; внутри пол."""
        n = 0
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                corner = x in (x0, x0 + w - 1) and y in (y0, y0 + h - 1)
                if round_corners and corner:
                    continue
                self.ground[y][x] = FLOOR
                edge = x in (x0, x0 + w - 1) or y in (y0, y0 + h - 1)
                if edge and (x, y) not in door and rng.random() >= holes:
                    o = {"t": wall, "hp": hp, "roof": ri}
                    if fac >= 0:
                        o["fac"] = fac
                    self.objects[(x, y)] = o
                    n += 1
        if ri >= 0:
            self.roofs[ri]["walls"] = n
            self.roofs[ri]["door"] = list(next(iter(door)))

    @staticmethod
    def door_toward(x0, y0, w, h, tx, ty):
        mx, my = x0 + w // 2, y0 + h // 2
        dx, dy = tx - mx, ty - my
        if abs(dx) > abs(dy):
            x = x0 + w - 1 if dx > 0 else x0
            return (x, my), (x - 1 if dx > 0 else x + 1, my)
        y = y0 + h - 1 if dy > 0 else y0
        return (mx, y), (mx, y - 1 if dy > 0 else y + 1)

    def build_house(self, rng, x0, y0, w, h):
        self.clear_area(x0 - 1, y0 - 1, w + 2, h + 2)
        door, inside = self.door_toward(x0, y0, w, h, x0 + rng.randint(-9, 9), y0 + rng.randint(-9, 9))
        ri = self.add_roof("house", x0, y0, w, h)
        self.ring_building(rng, x0, y0, w, h, "wall_old", 8, {door}, ri, holes=0.08)
        inner = [(x, y) for y in range(y0 + 1, y0 + h - 1) for x in range(x0 + 1, x0 + w - 1) if (x, y) != inside]
        rng.shuffle(inner)
        self.objects[inner.pop()] = self.loot_chest(rng, "house")
        if rng.random() < 0.75:
            self.objects[inner.pop()] = {"t": "bed_old"}
        if rng.random() < 0.6:
            self.objects[inner.pop()] = {"t": "table", "hp": 6}
        if rng.random() < 0.3:
            self.objects[inner.pop()] = self.loot_chest(rng, "house")
        self.structs.append(["house", pygame.Rect(x0, y0, w, h), -1])

    def build_tower(self, rng, x0, y0, w, h):
        self.clear_area(x0 - 1, y0 - 1, w + 2, h + 2)
        side = rng.choice(((x0 + 1, y0 + 3), (x0 + 2, y0), (x0, y0 + 1), (x0 + 3, y0 + 2)))
        ri = self.add_roof("tower", x0, y0, 4, 4)
        self.ring_building(rng, x0, y0, 4, 4, "tower_wall", 30, {side}, ri)
        inner = [(x0 + 1, y0 + 1), (x0 + 2, y0 + 1), (x0 + 1, y0 + 2), (x0 + 2, y0 + 2)]
        inside = min(inner, key=lambda p: abs(p[0] - side[0]) + abs(p[1] - side[1]))
        inner.remove(inside)                       # клетка у входа остаётся свободной
        rng.shuffle(inner)
        lad = inner.pop()
        self.objects[lad] = {"t": "ladder", "roof": ri}
        self.roofs[ri]["ladder"] = list(lad)
        if rng.random() < 0.8:
            self.objects[inner.pop()] = self.loot_chest(rng, "tower")
        self.structs.append(["tower", pygame.Rect(x0, y0, 4, 4), -1])

    def build_camp(self, rng, x0, y0, w, h):
        x, y = x0 + 1, y0 + 1
        self.clear_area(x - 1, y - 1, 4, 3)
        self.objects[(x, y)] = {"t": "tent_old"}
        self.objects[(x + 2, y)] = {"t": "fire", "fuel": 0.0}
        self.fires.add((x + 2, y))
        if rng.random() < 0.8:
            self.objects[(x + 1, y + 1)] = self.loot_chest(rng, "camp")
        self.structs.append(["camp", pygame.Rect(x - 1, y - 1, 4, 3), -1])

    def fac_chest(self, rng, loot, fac):
        c = self.loot_chest(rng, loot)
        c["fac"] = fac
        return c

    def place_free(self, positions, obj):
        for pos in positions:
            if pos not in self.objects and self.in_bounds(*pos) and self.ground[pos[1]][pos[0]] not in (WATER, DITCH):
                self.objects[pos] = obj
                return pos
        return None

    def build_village(self, rng, x0, y0, ftype):
        cx, cy = x0 + 8, y0 + 8
        fi = self.add_faction(rng, ftype, (cx, cy), 9)
        self.clear_area(x0, y0, 17, 17)
        self.objects[(cx, cy)] = {"t": "fire", "fuel": 999.0, "eternal": True}
        self.fires.add((cx, cy))
        self.objects[(cx, cy - 2)] = {"t": "totem", "fac": fi, "hp": 30}
        spots = [(-6, -6), (2, -6), (-6, 2), (2, 2)]
        rng.shuffle(spots)
        for ox, oy in spots[:rng.randint(3, 4)]:
            hx, hy = cx + ox, cy + oy
            door, inside = self.door_toward(hx, hy, 5, 5, cx, cy)
            ri = self.add_roof("hut", hx, hy, 5, 5, fi)
            self.ring_building(rng, hx, hy, 5, 5, "hut_wall", 15, {door}, ri, fac=fi, round_corners=True)
            inner = [(x, y) for y in range(hy + 1, hy + 4) for x in range(hx + 1, hx + 4) if (x, y) != inside]
            rng.shuffle(inner)
            self.objects[inner.pop()] = {"t": "mat"}
            self.objects[inner.pop()] = self.fac_chest(rng, "village", fi)
            if rng.random() < 0.5:
                self.objects[inner.pop()] = {"t": "rack", "hp": 5}
        for _ in range(3):
            self.place_free([(cx + rng.randint(-2, 2), cy + rng.randint(-1, 3))], {"t": "rack", "hp": 5})
        self.structs.append(["village", pygame.Rect(x0, y0, 17, 17), fi])

    def build_fort(self, rng, x0, y0, ftype):
        cx, cy = x0 + 5, y0 + 5
        fi = self.add_faction(rng, ftype, (cx, cy), 8)
        self.clear_area(x0 - 1, y0 - 1, 13, 13)
        gate = {(cx, y0 + 10), (cx + 1, y0 + 10)}
        for y in range(y0, y0 + 11):
            for x in range(x0, x0 + 11):
                if (x in (x0, x0 + 10) or y in (y0, y0 + 10)) and (x, y) not in gate:
                    self.objects[(x, y)] = {"t": "palisade", "hp": 60, "fac": fi}
        self.objects[(cx, cy)] = {"t": "fire", "fuel": 999.0, "eternal": True}
        self.fires.add((cx, cy))
        self.objects[(cx, cy - 2)] = {"t": "camp_banner", "fac": fi, "hp": 40}
        inner = [(x, y) for y in range(y0 + 1, y0 + 10) for x in range(x0 + 1, x0 + 10)
                 if abs(x - cx) + abs(y - cy) > 2 and (x, y + 1) not in gate and (x, y) not in self.objects]
        rng.shuffle(inner)
        for _ in range(2):
            self.objects[inner.pop()] = self.fac_chest(rng, "fort", fi)
        for t in ("bed_old", "bed_old", "tent_old", "rack", "table"):
            self.objects[inner.pop()] = {"t": t, "hp": 6}
        self.structs.append(["fort", pygame.Rect(x0, y0, 11, 11), fi])

    def build_post(self, rng, x0, y0, ftype):
        cx, cy = x0 + 4, y0 + 4
        fi = self.add_faction(rng, ftype, (cx, cy), 7)
        self.clear_area(x0, y0, 9, 9)
        self.objects[(cx, cy)] = {"t": "fire", "fuel": 999.0, "eternal": True}
        self.fires.add((cx, cy))
        self.objects[(cx - 2, cy - 2)] = {"t": "tent_old"}
        self.objects[(cx + 2, cy - 2)] = {"t": "tent_old"}
        self.objects[(cx - 2, cy + 2)] = self.fac_chest(rng, "post", fi)
        self.objects[(cx + 2, cy + 2)] = self.fac_chest(rng, "post", fi)
        self.objects[(cx, cy - 3)] = {"t": "table", "hp": 6}
        self.objects[(cx + 3, cy)] = {"t": "rack", "hp": 5}
        self.objects[(cx - 3, cy)] = {"t": "camp_banner", "fac": fi, "hp": 40}
        self.structs.append(["post", pygame.Rect(x0, y0, 9, 9), fi])

    def build_shrine(self, rng, x0, y0, ftype):
        cx, cy = x0 + 4, y0 + 4
        fi = self.add_faction(rng, ftype, (cx, cy), 7)
        self.clear_area(x0, y0, 9, 9)
        for i in range(8):
            a = i / 8 * math.tau
            self.objects[(cx + round(math.cos(a) * 3), cy + round(math.sin(a) * 3))] = {"t": "pillar", "hp": 60, "fac": fi}
        self.objects[(cx, cy)] = {"t": "altar", "fac": fi, "hp": 80}
        self.objects[(cx, cy + 2)] = {"t": "fire", "fuel": 999.0, "eternal": True}
        self.fires.add((cx, cy + 2))
        self.objects[(cx + 1, cy - 1)] = self.fac_chest(rng, "shrine", fi)
        self.structs.append(["shrine", pygame.Rect(x0, y0, 9, 9), fi])

    def find_crash_site(self, rng, near=None):
        """Случайное место для крушения: где угодно на суше острова."""
        for _ in range(800):
            x, y = rng.randint(6, self.w - 7), rng.randint(6, self.h - 7)
            if self.area_ok(x - 4, y - 4, 9, 9, gap=4, ground=LAND | {SAND}):
                return x, y
        return None

    def build_crash(self, rng, cx, cy, fi):
        """Обломки самолёта: фюзеляж, крылья, ящики с припасами, горящие обломки."""
        for y in range(cy - 4, cy + 5):
            for x in range(cx - 4, cx + 5):
                o = self.objects.get((x, y))
                if o and o["t"] not in ("rock", "ore", "coal_node"):
                    del self.objects[(x, y)]
        horizontal = rng.random() < 0.5
        dx, dy = (1, 0) if horizontal else (0, 1)
        for i in range(-2, 3):
            part = "nose" if i == 2 else "tail" if i == -2 else "body"
            self.objects[(cx + dx * i, cy + dy * i)] = {"t": "wreck_part", "hp": 40, "part": part, "dir": [dx, dy]}
        for s in (-1, 1):
            for j in (1, 2):
                pos = (cx + dy * s * j, cy + dx * s * j)
                self.objects[pos] = {"t": "wreck_part", "hp": 40, "part": "wing", "dir": [dx, dy]}
        free = [(cx + rng.randint(-4, 4), cy + rng.randint(-4, 4)) for _ in range(40)]
        crates = 0
        for pos in free:
            if pos not in self.objects and crates < 3:
                self.objects[pos] = self.loot_chest(rng, "wreck")
                crates += 1
        fires = 0
        for pos in free:
            if pos not in self.objects and fires < 2:
                self.objects[pos] = {"t": "fire", "fuel": 260.0}
                self.fires.add(pos)
                fires += 1
        self.structs.append(["crash", pygame.Rect(cx - 4, cy - 4, 9, 9), fi])
        return len(self.structs) - 1

    def build_survivor_camp(self, rng, cx, cy, fi):
        """Выжившие обустраиваются: палатки, костёр, ящик, флаг."""
        around = [(cx + ox, cy + oy) for ox in range(-4, 5) for oy in range(-4, 5) if abs(ox) + abs(oy) > 2]
        rng.shuffle(around)
        for t in ("tent_old", "tent_old", "bed_old"):
            self.place_free(around, {"t": t})
        self.place_free(around, self.fac_chest(rng, "camp", fi))
        pos = self.place_free(around, {"t": "fire", "fuel": 999.0, "eternal": True})
        if pos:
            self.fires.add(pos)
        self.place_free(around, {"t": "camp_banner", "fac": fi, "hp": 40})
        for s in self.structs:
            if s[2] == fi:
                s[0] = "survcamp"

    # ------------------------------------------------------------ сюжет: радиостанция, логова, записки
    def story_area_ok(self, x, y, w, h, gap, ground):
        if not self.area_ok(x, y, w, h, gap=gap, ground=ground):
            return False
        return not any(self.objects.get((xx, yy), {}).get("own")
                       for yy in range(y - 1, y + h + 1) for xx in range(x - 1, x + w + 1))

    def add_story(self, rng):
        """Радиостанция, четыре логова боссов, останки и записки. Для старых сохранений тоже вызывается."""
        self.lairs = []
        self.radio = None
        cx, cy = self.w // 2, self.h // 2
        far = self.w * 0.22
        for ground, gap, tries in ((BUILD_GROUND | {ROCKY, SAND}, 4, 3000), (LAND | {SAND}, 1, 3000)):
            for i in range(tries):
                x, y = rng.randint(4, self.w - 13), rng.randint(4, self.h - 13)
                if math.hypot(x + 4 - cx, y + 4 - cy) < far and i < tries * 0.8:
                    continue
                if self.story_area_ok(x, y, 9, 9, gap, ground):
                    self.build_radio(rng, x, y)
                    break
            if self.radio:
                break
        S = LAIR_SIZE
        for kind, spec in LAIRS.items():
            biome = {BIOME_IDS[g] for g in spec["ground"]}
            best, best_k = None, -1.0
            for gap, tries in ((4, 3000), (1, 3000)):          # ищем место, где больше всего «своего» биома
                for i in range(tries):
                    x, y = rng.randint(3, self.w - S - 3), rng.randint(3, self.h - S - 3)
                    if i < tries * 0.85 and math.hypot(x + 4 - cx, y + 4 - cy) < far * 0.8:
                        continue
                    others = [l["center"] for l in self.lairs] + ([self.radio["center"]] if self.radio else [])
                    if gap > 1 and any(math.hypot(x + 4 - ox, y + 4 - oy) < self.w * 0.15 for ox, oy in others):
                        continue                                # логова не жмутся друг к другу и к станции
                    if not self.story_area_ok(x, y, S, S, gap, LAND | {SAND}):
                        continue
                    k = sum(self.ground[yy][xx] in biome for yy in range(y, y + S) for xx in range(x, x + S)) / (S * S)
                    if k > best_k:
                        best, best_k = (x, y), k
                        if k > 0.75:
                            break
                if best:
                    break
            if best:
                self.build_lair(rng, kind, *best)
        self.place_notes(rng)

    def build_radio(self, rng, x0, y0):
        """Станция «Маяк-7»: домик с передатчиком, антенная мачта, вертолётная площадка."""
        self.clear_area(x0, y0, 9, 9)
        door = (x0 + 3, y0 + 4)
        ri = self.add_roof("house", x0 + 1, y0 + 1, 5, 4)
        self.ring_building(rng, x0 + 1, y0 + 1, 5, 4, "wall_old", 20, {door}, ri)
        self.objects[(x0 + 3, y0 + 2)] = {"t": "radio"}
        chest = (x0 + 2, y0 + 2)
        self.objects[chest] = dict(self.loot_chest(rng, "radio"), fireproof=True)
        self.objects[(x0 + 4, y0 + 2)] = {"t": "bed_old"}
        self.objects[(x0 + 7, y0 + 2)] = {"t": "radio_mast"}
        self.objects[(x0 + 1, y0 + 7)] = {"t": "torch_post"}
        for dy in range(3):
            for dx in range(3):
                self.objects[(x0 + 5 + dx, y0 + 5 + dy)] = {"t": "pad", "i": dy * 3 + dx}
        self.structs.append(["radio", pygame.Rect(x0, y0, 9, 9), -1])
        self.radio = {"center": [x0 + 4, y0 + 4], "struct": len(self.structs) - 1, "pos": [x0 + 3, y0 + 2],
                      "chest": list(chest), "pad": [x0 + 6, y0 + 6]}

    def build_lair(self, rng, kind, x0, y0):
        """Логово босса: у каждого своё убранство, в глубине — запертый сундук с легендарным оружием."""
        spec = LAIRS[kind]
        self.clear_area(x0, y0, LAIR_SIZE, LAIR_SIZE)
        cx, cy = x0 + 4, y0 + 4
        li = len(self.lairs)
        ring = []
        for i in range(16):
            if i in (3, 4, 5) or rng.random() < 0.2:                # проход с юга и пара случайных дыр
                continue
            a = i / 16 * math.tau
            ring.append((cx + round(math.cos(a) * 4), cy + round(math.sin(a) * 4)))
        inside = [(cx + dx, cy + dy) for dx in range(-3, 4) for dy in range(-3, 4) if dx * dx + dy * dy <= 10]
        theme = {"bear": GRASS, "snake": SWAMP, "frost": SNOW, "barrow": STEPPE}[kind]
        for dx in range(-4, 5):                                     # земля логова — «своего» биома
            for dy in range(-4, 5):
                if dx * dx + dy * dy <= 18 and not (theme == GRASS and self.ground[cy + dy][cx + dx] == MEADOW):
                    self.ground[cy + dy][cx + dx] = theme
        if kind == "bear":
            for pos in ring:
                self.objects[pos] = {"t": "rock", "hp": 12}
            self.objects[(cx, cy - 2)] = {"t": "den"}
        elif kind == "snake":
            for pos in inside:
                self.ground[pos[1]][pos[0]] = SWAMP
            for pos in ring:
                if rng.random() < 0.6:
                    self.objects[pos] = {"t": "reed"} if rng.random() < 0.7 else self.new_tree(rng, "dead")
            self.objects[(cx, cy - 1)] = {"t": "nest"}
        elif kind == "frost":
            for pos in inside:
                self.ground[pos[1]][pos[0]] = SNOW
            for pos in ring:
                self.objects[pos] = {"t": "ice_spike"}
        else:
            for pos in ring[::2]:
                self.objects[pos] = {"t": "menhir"}
            for dx, dy in ((-1, 0), (1, 0), (0, 1), (-1, 1), (1, 1)):
                self.objects[(cx + dx, cy + dy)] = {"t": "mound"}
            self.objects[(cx, cy)] = {"t": "dark_heart", "hp": 150}
        for _ in range(5):                                          # кости вокруг
            pos = rng.choice(inside)
            if pos not in self.objects and pos != (cx, cy):
                self.objects[pos] = {"t": "bone_pile"}
        chest = self.loot_chest(rng, "lair")
        chest["tools"][first_free(chest["tools"])] = {"id": spec["weapon"], "dur": ITEMS[spec["weapon"]]["dur"]}
        chest.update(lair=li, locked=True, fireproof=True)
        cpos = (cx, cy - 3)
        self.objects[cpos] = chest
        self.structs.append([spec["struct"], pygame.Rect(x0, y0, LAIR_SIZE, LAIR_SIZE), -1])
        self.lairs.append({"kind": kind, "boss": spec["boss"], "center": [cx, cy], "alive": True,
                           "chest": list(cpos), "struct": len(self.structs) - 1})

    def free_land(self, rng, ground, near=None, rmin=0, rmax=0, tries=600):
        for _ in range(tries):
            if near:
                a, d = rng.uniform(0, math.tau), rng.uniform(rmin, rmax)
                x, y = int(near[0] + math.cos(a) * d), int(near[1] + math.sin(a) * d)
            else:
                x, y = rng.randrange(self.w), rng.randrange(self.h)
            if self.in_bounds(x, y) and self.ground[y][x] in ground and (x, y) not in self.objects and \
                    not any(s[1].collidepoint(x, y) for s in self.structs):
                return x, y
        return None

    def place_notes(self, rng):
        chests = {}
        for pos, o in self.objects.items():
            if o["t"] == "chest" and o.get("loot") and not o.get("notes") and not o.get("own"):
                chests.setdefault(o["loot"], []).append(pos)
        for lst in chests.values():
            rng.shuffle(lst)
        center = (self.w // 2, self.h // 2)
        for nid, n in NOTES.items():
            place = n["place"]
            holder = None
            if place.startswith("lair:"):
                holder = next((tuple(l["chest"]) for l in self.lairs if l["kind"] == place[5:]), None)
            elif place == "radio" and self.radio:
                holder = tuple(self.radio["chest"])
            elif chests.get(place):
                holder = chests[place].pop()
            if holder and holder in self.objects:
                self.objects[holder].setdefault("notes", []).append(nid)
                continue
            if place == "start":
                pos = self.free_land(rng, LAND, center, 3, 6)
            elif place == "beach":
                pos = self.free_land(rng, {SAND})
            else:
                pos = None
            pos = pos or self.free_land(rng, LAND - {ROCKY})
            if pos:
                self.objects[pos] = {"t": "bones", "notes": [nid]}

    @staticmethod
    def loot_chest(rng, kind):
        table = LOOT[kind]
        kinds = rng.randint(*table["kinds"])
        res = {k: rng.randint(a, b) for k, a, b in rng.sample(table["res"], min(len(table["res"]), kinds))}
        tools = [None] * CHEST_TOOLS
        i = 0
        for iid, chance in table["tools"]:
            if rng.random() < chance:
                tools[i] = {"id": iid, "dur": int(ITEMS[iid]["dur"] * rng.uniform(0.4, 1.0))}
                i += 1
                if ITEMS[iid].get("ranged", {}).get("ammo") == "ammo":
                    res["ammo"] = res.get("ammo", 0) + rng.randint(3, 6)
        return {"t": "chest", "res": res, "tools": tools, "loot": kind}

    def fix_after_load(self):
        """Совместимость со старыми сохранениями."""
        for name, default in (("deck", {}), ("frozen", False), ("season", "spring")):
            if not hasattr(self, name):
                setattr(self, name, default)
        if not hasattr(self, "lairs"):                 # мир из версии до 1.6: достраиваем сюжетные места
            self.add_story(random.Random(f"{self.seed}:story"))
        for ri, r in enumerate(self.roofs):
            r.setdefault("ladder", None)
            if r.get("door") is None:
                x, y, w, h = r["rect"]
                for yy in range(y, y + h):
                    for xx in range(x, x + w):
                        edge = xx in (x, x + w - 1) or yy in (y, y + h - 1)
                        corner = xx in (x, x + w - 1) and yy in (y, y + h - 1)
                        if edge and not corner and (xx, yy) not in self.objects and self.ground[yy][xx] == FLOOR:
                            r["door"] = [xx, yy]
                    if r.get("door"):
                        break
            if r["kind"] == "tower" and not r["ladder"]:
                x, y, w, h = r["rect"]
                for yy in range(y, y + h):
                    for xx in range(x, x + w):
                        o = self.objects.get((xx, yy))
                        if o and o["t"] == "ladder":
                            r["ladder"] = [xx, yy]
        for f in self.factions:
            f.setdefault("heart_broken", False)

    # ------------------------------------------------------------ запросы
    @staticmethod
    def new_tree(rng, kind=None):
        return {"t": "tree", "hp": 10, "kind": kind or ("pine" if rng.random() < 0.55 else "oak"),
                "size": rng.uniform(0.85, 1.15), "hit_t": -9}

    def in_bounds(self, tx, ty):
        return 0 <= tx < self.w and 0 <= ty < self.h

    def ground_at(self, x, y):
        tx, ty = int(x // TILE), int(y // TILE)
        return self.ground[ty][tx] if self.in_bounds(tx, ty) else WATER

    def tile_blocked(self, tx, ty, swim=False, doors=False):
        """doors=True — игрок и дружелюбные люди: открывают двери и перелезают ров."""
        if not self.in_bounds(tx, ty):
            return True
        g = self.ground[ty][tx]
        if (g == WATER and not swim and not self.frozen) or (g == DITCH and not doors):
            return True
        o = self.objects.get((tx, ty))
        if o is None or o["t"] not in BLOCKING:
            return False
        if o["t"] in DOORS:
            return not (o.get("open") or doors)
        return True

    def circle_blocked(self, x, y, r, swim=False, doors=False):
        for ty in range(int((y - r) // TILE), int((y + r) // TILE) + 1):
            for tx in range(int((x - r) // TILE), int((x + r) // TILE) + 1):
                if not self.tile_blocked(tx, ty, swim, doors):
                    continue
                o = self.objects.get((tx, ty))
                if o is not None and o["t"] in BLOCKING:
                    hx, hy, hw, hh = HITBOX.get(o["t"], (0, 0, TILE, TILE))
                else:
                    hx, hy, hw, hh = 0, 0, TILE, TILE
                rx, ry = tx * TILE + hx, ty * TILE + hy
                nx = clamp(x, rx, rx + hw)
                ny = clamp(y, ry, ry + hh)
                if (x - nx) ** 2 + (y - ny) ** 2 < r * r:
                    return True
        return False

    def speed_mult(self, x, y):
        tx, ty = int(x // TILE), int(y // TILE)
        if not self.in_bounds(tx, ty):
            return 1.0
        g = self.ground[ty][tx]
        if g == DITCH:
            return DITCH_SLOW
        k = 0.75 if g == SWAMP else 0.88 if g == SNOW else 1.0
        o = self.objects.get((tx, ty))
        return k * (TREE_SLOW if o and o["t"] == "tree" else 1.0)

    def free_tile(self, tx, ty):
        return self.in_bounds(tx, ty) and self.ground[ty][tx] not in (WATER, DITCH) and (tx, ty) not in self.objects

    def find_near(self, x, y, types, radius):
        best, bd = None, radius
        tx0, ty0 = int(x // TILE), int(y // TILE)
        n = int(radius // TILE) + 1
        for ty in range(ty0 - n, ty0 + n + 1):
            for tx in range(tx0 - n, tx0 + n + 1):
                o = self.objects.get((tx, ty))
                if o and o["t"] in types:
                    d = math.hypot(tx * TILE + TILE / 2 - x, ty * TILE + TILE / 2 - y)
                    if d <= bd:
                        best, bd = (tx, ty), d
        return best

    def nearest_fire(self, x, y, radius):
        best, bd = None, radius
        for (tx, ty) in self.fires:
            o = self.objects.get((tx, ty))
            if not o or o["t"] != "fire" or o["fuel"] <= 0:
                continue
            fx, fy = tx * TILE + TILE / 2, ty * TILE + TILE / 2
            d = math.hypot(fx - x, fy - y)
            if d < bd:
                best, bd = (fx, fy), d
        return best

    def burning_near(self, x, y, n=2):
        tx0, ty0 = int(x // TILE), int(y // TILE)
        for ty in range(ty0 - n, ty0 + n + 1):
            for tx in range(tx0 - n, tx0 + n + 1):
                if (tx, ty) in self.burning:
                    return (tx * TILE + TILE / 2, ty * TILE + TILE / 2)
        return None

    def roof_at(self, tx, ty):
        for i, r in enumerate(self.roofs):
            x, y, w, h = r["rect"]
            if not r["ruined"] and x <= tx < x + w and y <= ty < y + h:
                return i
        return -1

    def respawn_random(self, kind, px, py):
        """Ресурсы (трава, камешки, тростник) появляются заново где-нибудь вдали от игрока."""
        ground = RESPAWN_GROUND.get(kind, {GRASS})
        for _ in range(60):
            tx, ty = self.rng.randrange(self.w), self.rng.randrange(self.h)
            if self.ground[ty][tx] in ground and (tx, ty) not in self.objects and \
                    math.hypot(tx * TILE - px, ty * TILE - py) > 10 * TILE:
                self.objects[(tx, ty)] = {"t": kind}
                return

    # ------------------------------------------------------------ огонь
    def ignite(self, pos):
        o = self.objects.get(pos)
        if pos in self.burning or len(self.burning) >= MAX_BURNING or not o or o["t"] not in FLAMMABLE or \
                o.get("fireproof"):
            return False
        self.burning[pos] = self.rng.uniform(5, 9) if o["t"] == "tree" else self.rng.uniform(4, 7)
        return True

    def update_fire(self, dt, spread=1.0, rain=False):
        """Возвращает список сгоревших объектов [(pos, obj)]."""
        burned = []
        for pos, t in list(self.burning.items()):
            t -= dt * (2.5 if rain else 1.0)
            if pos not in self.objects:
                del self.burning[pos]
                continue
            if t <= 0:
                del self.burning[pos]
                o = self.objects.pop(pos)
                if o["t"] == "tree":
                    self.objects[pos] = {"t": "charred"}
                burned.append((pos, o))
                continue
            self.burning[pos] = t
            if not rain and self.rng.random() < 0.45 * dt * spread:
                dx, dy = self.rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)))
                self.ignite((pos[0] + dx, pos[1] + dy))
        return burned

    def update(self, dt, fire_mult=1.0):
        for pos in list(self.timed):
            o = self.objects.get(pos)
            if o is None:
                self.timed.discard(pos)
                continue
            if o["t"] == "stump":
                o["timer"] -= dt
                if o["timer"] <= 0:
                    self.objects[pos] = self.new_tree(self.rng, o.get("kind"))
                    self.timed.discard(pos)
            elif o["t"] == "bush":
                if self.season == "winter":                 # зимой ягоды не растут
                    continue
                o["timer"] -= dt * (1.6 if self.season == "summer" else 0.6 if self.season == "autumn" else 1.0)
                if o["timer"] <= 0:
                    o["berries"] = True
                    self.timed.discard(pos)
            elif o["t"] == "hive":
                if self.season == "winter":                 # зимой пчёлы спят
                    continue
                o["timer"] -= dt
                if o["timer"] <= 0:
                    o["honey"] = True
                    self.timed.discard(pos)
            elif o["t"] == "garden" and o["planted"] and o["grow"] < GARDEN_TIME:
                o["grow"] = min(GARDEN_TIME, o["grow"] + dt * self.grow_mult)
            else:
                self.timed.discard(pos)
        for pos in self.fires:
            o = self.objects.get(pos)
            if o and o["t"] == "fire" and o["fuel"] > 0 and not o.get("eternal"):
                o["fuel"] = max(0.0, o["fuel"] - dt * fire_mult)
                if o["fuel"] <= 0:
                    o["coal"] = 1                    # прогоревший костёр оставляет уголь


def move_entity(world, ent, dx, dy, swim=False, doors=False):
    """Движение с коллизиями по осям отдельно (чтобы скользить вдоль стен)."""
    moved = 0.0
    if dx and not world.circle_blocked(ent.x + dx, ent.y, ent.r, swim, doors):
        ent.x += dx
        moved += abs(dx)
    if dy and not world.circle_blocked(ent.x, ent.y + dy, ent.r, swim, doors):
        ent.y += dy
        moved += abs(dy)
    return moved
