# -*- coding: utf-8 -*-
"""Интерфейс: HUD, инвентарь, сундуки, крафт и изучение, стройка, диалоги, журнал, меню и экраны."""
import math

import pygame

from .config import (SCREEN_W, SCREEN_H, TILE, VERSION, GROUND_COL, GRASS, WATER, SAND, FLOOR, DITCH, SNOW, SWAMP,
                     STEPPE, ROCKY, MEADOW, CHEST_TOOLS, BAG_SIZES, WORLD_SIZES, DIFFICULTIES, DENSITIES,
                     FACTION_AMOUNTS, BIOME_NAMES, SETTLE_RADIUS, DECK_H, SEASON_DAYS, SKILLS, SKILL_MAX)
from .data import (RES_INFO, USABLE, ITEMS, CRAFTS, CRAFT_BY_ID, BUILDS, BUILD_BY_ID, BUILD_CATS, ROLES,
                   FACTION_TYPES, DIALOG, BENCH_TIER, ANIMALS, BREAKABLE, CONDITIONS, SPOIL, QUEST_RES, NOTES,
                   LAIRS, ENDINGS)

SKILL_INFO = {"chop": "сильнее рубишь деревья; с 5 ур. +1 дерево",
              "mine": "быстрее добываешь камень и руду; с 5 ур. +1 добыча",
              "hunt": "сильнее бьёшь зверей; с 4 ур. +1 мясо, с 8 ур. +1 шкура",
              "combat": "сильнее бьёшь врагов в ближнем бою",
              "archery": "стрелы, болты и пули наносят больше урона",
              "medicine": "бинты, мази и аптечки лечат больше",
              "craft": "всё крафтится быстрее (до −50% времени)",
              "fishing": "рыба клюёт быстрее и реже срывается"}
from .icons import draw_item_icon, draw_res_icon
from . import saves

SLOT_NAMES = ["Руки", "Пояс", "Спина"]
SLOT_HINT = ["любой предмет", "малые предметы", "большие предметы"]
CRAFT_TABS = [("Руки", lambda c: c["tier"] == 0 and not c.get("station")),
              ("Костёр", lambda c: c.get("station") == "fire"),
              ("Печь", lambda c: c.get("station") == "furnace"),
              ("Коптильня", lambda c: c.get("station") == "smokehouse"),
              ("Верстак I", lambda c: c["tier"] == 1),
              ("Верстак II", lambda c: c["tier"] == 2),
              ("Верстак III", lambda c: c["tier"] == 3)]
ATT_COL = {"friend": (140, 255, 140), "truce": (140, 220, 255), "neutral": (255, 230, 140), "hostile": (255, 110, 100)}
ATT_NAME = {"friend": "Друзья", "truce": "Перемирие", "neutral": "Настороженно", "hostile": "Вражда"}


class UIMixin:
    # ------------------------------------------------------------ HUD
    def draw_bars(self):
        p = self.player
        bars = [("Здоровье", p.hp, (205, 52, 52), False), ("Сытость", p.hunger, (212, 142, 50), False),
                ("Вода", p.thirst, (62, 142, 222), False), ("Тепло", p.warmth, (232, 200, 82), False),
                ("Выносливость", p.stamina, (92, 200, 92), False), ("Влажность", p.wet, (110, 200, 230), True)]
        self.panel(pygame.Rect(8, 8, 262, 14 + len(bars) * 26))
        blink = int(self.clock_t * 3) % 2 == 0
        for i, (name, val, col, inverse) in enumerate(bars):
            y = 16 + i * 26
            bad = val > 60 if inverse else val < 25
            self.text(name, self.font_s, (255, 90, 90) if bad and blink else (230, 230, 230), (18, y))
            r = pygame.Rect(124, y + 3, 110, 14)
            pygame.draw.rect(self.screen, (40, 40, 46), r, border_radius=3)
            pygame.draw.rect(self.screen, col, (r.x, r.y, int(r.w * val / 100), r.h), border_radius=3)
            self.text(str(int(val)), self.font_s, (230, 230, 230), (240, y))
        status = [BIOME_NAMES.get(self.world.ground_at(p.x, p.y), "")]
        if p.on_tower:
            status.append("На вышке")
        if self.player_in_water():
            status.append("Плывёшь")
        elif p.wet > 5:
            status.append("Мокрый")
        if self.sheltered():
            status.append("Под крышей")
        if self.near_fire(3.5 * TILE):
            status.append("У огня")
        if p.armor:
            status.append(("", "Кож. броня", "Жел. броня")[p.armor])
        if self.followers_count():
            status.append(f"Спутников: {self.followers_count()}")
        y = 22 + len(bars) * 26
        self.text(" · ".join(s for s in status if s), self.font_s, (200, 220, 255), (16, y))
        y += 20
        blink = int(self.clock_t * 3) % 2
        for c in self.active_conditions():                   # раны и болезни — что и чем лечить
            name, col, cure = CONDITIONS[c]
            left = p.poison if c == "poison" else p.cond.get(c, 0)
            txt = f"{name} ({int(left)}с) — {cure} [H]"
            pygame.draw.rect(self.screen, (20, 18, 22), (10, y - 1, self.font_s.size(txt)[0] + 12, 19), border_radius=4)
            self.text(txt, self.font_s, col if blink or c != "bleed" else (255, 255, 255), (16, y))
            y += 20
        self.draw_threats(y + 2)

    def draw_threats(self, y0):
        """Список тех, кто нападает на тебя, с мини-портретами и здоровьем."""
        p = self.player
        threats = [a for a in self.animals if (a.chasing or (a.human and self.is_threat(a)))
                   and abs(a.x - p.x) < 16 * TILE and abs(a.y - p.y) < 16 * TILE]
        if not threats:
            return
        threats.sort(key=lambda a: math.hypot(a.x - p.x, a.y - p.y))
        box = pygame.Rect(8, y0, 262, 22 + 40 * min(5, len(threats)))
        self.panel(box, alpha=170, border=(150, 60, 50))
        self.text("Угрозы рядом", self.font_s, (255, 140, 120), (box.x + 10, box.y + 3))
        for i, a in enumerate(threats[:5]):
            y = box.y + 22 + i * 40
            self.screen.blit(self.creature_avatar(a, 34), (box.x + 6, y))
            name = (f"{ROLES[a.role]['name']} {a.name}" if a.human else ANIMALS[a.kind]["name"])
            dist = int(math.hypot(a.x - p.x, a.y - p.y) / TILE)
            self.text(name, self.font_s, (240, 220, 210), (box.x + 46, y))
            self.text(f"{dist} м", self.font_s, (190, 190, 200), (box.right - 8, y), right=True)
            self.bar(box.x + 46, y + 22, 150, a.hp / a.max_hp, 6)
            self.text(f"{max(0, int(a.hp))}/{int(a.max_hp)}", self.font_s, (220, 220, 220), (box.x + 202, y + 17))

    def inspect_target(self):
        """Что под курсором для карточки с HP: существо или постройка."""
        mx, my = pygame.mouse.get_pos()
        wx, wy = mx + self.cam_x, my + self.cam_y
        for a in self.animals:
            if not a.dead and math.hypot(a.x - wx, a.y - wy) < a.r + 8:
                return ("creature", a)
        tx, ty = int(wx // TILE), int(wy // TILE)
        o = self.world.objects.get((tx, ty))
        if o and o["t"] in BREAKABLE:
            return ("building", o)
        return None

    def draw_inspect(self):
        if self.menu is not None or self.build_mode:
            return
        t = self.inspect_target()
        if not t:
            return
        r = pygame.Rect(0, 0, 300, 58)
        r.midtop = (SCREEN_W // 2, 8)
        if self.banner:
            return
        self.panel(r, alpha=200)
        if t[0] == "creature":
            a = t[1]
            self.screen.blit(self.creature_avatar(a, 48), (r.x + 5, r.y + 5))
            if a.human:
                name = f"{ROLES[a.role]['name']} {a.name}"
                if a.ally:
                    state, col = ("житель поселения" if a.settler else "твой спутник"), (140, 255, 140)
                else:
                    f = self.world.factions[a.faction]
                    state = f["name"] + (" — ВРАГ" if self.fac_hostile(a.faction) else "")
                    col = (255, 120, 110) if self.fac_hostile(a.faction) else (230, 220, 180)
            else:
                name = ANIMALS[a.kind]["name"]
                state, col = (("атакует тебя!", (255, 110, 100)) if a.chasing else
                              ("босс — хозяин логова", (220, 160, 255)) if a.beh == "boss" else
                              ("опасен, если подойти", (255, 190, 120)) if a.beh in ("territorial", "hunter") else
                              ("нападёт, если ударить", (230, 220, 150)) if a.beh == "neutral" else
                              ("пугливый", (180, 230, 180)))
            hp, mhp = a.hp, a.max_hp
        else:
            o = t[1]
            bid = o["t"]
            self.screen.blit(self.building_icon(bid), (r.x + 9, r.y + 9))
            name = BUILD_BY_ID[bid]["name"] if bid in BUILD_BY_ID else {
                "wall_old": "Старая стена", "hut_wall": "Стена хижины", "tower_wall": "Стена вышки", "table": "Стол",
                "totem": "Тотем племени", "rack": "Сушилка", "pillar": "Колонна", "altar": "Алтарь культа",
                "camp_banner": "Знамя лагеря", "wreck_part": "Обломок самолёта",
                "dark_heart": "Чёрное сердце (разбей его!)"}.get(bid, bid)
            if "fac" in o and 0 <= o["fac"] < len(self.world.factions):
                state, col = self.world.factions[o["fac"]]["name"], (230, 200, 160)
            else:
                state, col = ("твоя постройка" if o.get("own") else "ничья"), (190, 210, 230)
            mhp = BREAKABLE[bid][2]
            hp = o.get("hp", mhp)
        self.text(name, self.font_s, (255, 240, 200), (r.x + 60, r.y + 4))
        self.text(state, self.font_s, col, (r.x + 60, r.y + 20))
        self.bar(r.x + 60, r.y + 40, 170, hp / mhp, 8)
        self.text(f"{max(0, int(hp))}/{int(mhp)}", self.font_s, (230, 230, 230), (r.x + 236, r.y + 36))

    def building_icon(self, bid):
        key = ("bicon", bid)
        if key not in self.icon_cache:
            icon = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            old, self.screen = self.screen, icon
            self.draw_flat(0, 0, dict(self.preview_obj(bid), fac=-1))
            self.screen = old
            self.icon_cache[key] = icon
        return self.icon_cache[key]

    def draw_clock(self):
        r = pygame.Rect(SCREEN_W - 210, 8, 202, 84)
        self.panel(r)
        h = int(self.time * 24)
        m = int((self.time * 24 - h) * 60)
        d = self.darkness()
        phase = "День" if d == 0 else "Ночь" if d >= 1 else ("Закат" if self.time > 0.5 else "Рассвет")
        winter = self.season() == "winter"
        extra = {"rain": ", снег" if winter else ", дождь", "storm": ", ЛИВЕНЬ"}.get(self.weather, "")
        if "fog" in self.events:
            extra += ", туман"
        if "drought" in self.events:
            extra += ", засуха"
        if "blizzard" in self.events:
            extra += ", МЕТЕЛЬ"
        self.text(f"День {self.day}", self.font_b, (255, 230, 150), (r.x + 12, r.y + 4))
        self.text(f"{h:02d}:{m:02d}  {phase}{extra}", self.font_s, (220, 220, 230), (r.x + 14, r.y + 40))
        scol = {"spring": (150, 230, 140), "summer": (255, 220, 110), "autumn": (240, 160, 70),
                "winter": (190, 220, 255)}[self.season()]
        self.text(f"{self.season_name()}, день {self.season_day()}/{SEASON_DAYS}", self.font_s, scol,
                  (r.x + 14, r.y + 60))
        cx, cy = r.right - 30, r.y + 26
        if self.raining():
            pygame.draw.circle(self.screen, (150, 155, 170), (cx - 4, cy - 2), 9)
            pygame.draw.circle(self.screen, (150, 155, 170), (cx + 6, cy), 8)
        elif d < 0.5:
            pygame.draw.circle(self.screen, (255, 210, 80), (cx, cy), 13)
        else:
            col = (230, 90, 80) if "blood_moon" in self.events else (220, 220, 240)
            pygame.draw.circle(self.screen, col, (cx, cy), 12)
            pygame.draw.circle(self.screen, (18, 20, 28), (cx + 5, cy - 4), 10)

    def hotbar_rects(self):
        size, gap = 70, 16
        x0 = (SCREEN_W - (3 * size + 2 * gap)) // 2
        return [pygame.Rect(x0 + i * (size + gap), SCREEN_H - size - 18, size, size) for i in range(3)]

    def draw_hotbar(self):
        p = self.player
        rects = self.hotbar_rects()
        for i, r in enumerate(rects):
            self.draw_slot(r, p.slots[i], i == p.sel, i)
            self.text(SLOT_NAMES[i], self.font_s, (220, 220, 220) if i == p.sel else (160, 160, 170),
                      (r.centerx, r.y - 11), center=True)
        it = p.held()
        name = ITEMS[it["id"]]["name"] if it else ("Голые руки" if p.sel == 0 else "пусто (бьёшь руками)")
        ranged = ITEMS[it["id"]].get("ranged") if it else None
        if ranged:
            name += f"  ({RES_INFO[ranged['ammo']][0]}: {p.res[ranged['ammo']]})"
            if ranged.get("misfire"):
                name += ", осечки"
            if ranged["ammo"] == "arrows":
                name += f" · R: {'ОГНЕННЫЕ (' + str(p.res['fire_arrows']) + ')' if p.fire_mode else 'обычные'} стрелы"
        if p.res["firebomb"]:
            name += f"   ·   T — бросить бомбу ({p.res['firebomb']})"
        y0 = rects[0].y
        self.text(f"{SLOT_NAMES[p.sel]}: {name}", self.font, (255, 240, 200), (SCREEN_W // 2, y0 - 36), center=True)
        if self.hint:
            self.text(self.hint, self.font, (180, 255, 180), (SCREEN_W // 2, y0 - 64), center=True)

    def draw_slot(self, r, it, selected, slot_idx=None, ref=None):
        if self.drag and ref == self.drag["ref"]:
            it = None
        self.panel(r, alpha=220, color=(28, 30, 40) if not selected else (55, 52, 36),
                   border=(255, 214, 90) if selected else (95, 100, 118))
        if selected:
            pygame.draw.rect(self.screen, (255, 214, 90), r, 3, border_radius=6)
        pad = max(6, r.w // 5)
        if it:
            draw_item_icon(self.screen, it["id"], r.inflate(-pad, -pad))
            k = max(0, it["dur"] / ITEMS[it["id"]]["dur"])
            col = (90, 210, 90) if k > 0.5 else (230, 200, 60) if k > 0.2 else (230, 70, 60)
            pygame.draw.rect(self.screen, (30, 30, 30), (r.x + 5, r.bottom - 7, r.w - 10, 3))
            pygame.draw.rect(self.screen, col, (r.x + 5, r.bottom - 7, int((r.w - 10) * k), 3))
        elif slot_idx == 0:
            s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            draw_item_icon(s, "hands", (pad // 2 + 4, pad // 2 + 4, r.w - pad - 8, r.h - pad - 8))
            s.set_alpha(110)
            self.screen.blit(s, r.topleft)
        if slot_idx is not None:
            self.text(str(slot_idx + 1), self.font_s, (200, 200, 200), (r.x + 5, r.y + 2))

    def queue_rects(self):
        x0 = self.hotbar_rects()[2].right + 30
        return [pygame.Rect(x0 + i * 46, SCREEN_H - 60, 42, 42) for i in range(len(self.craft_queue))]

    def over_queue(self, pos):
        return any(r.collidepoint(pos) for r in self.queue_rects())

    def draw_queue(self):
        if not self.craft_queue:
            return
        rects = self.queue_rects()
        self.text("Крафт (ПКМ — отмена):", self.font_s, (200, 200, 210), (rects[0].x, rects[0].y - 20))
        for i, (q, r) in enumerate(zip(self.craft_queue, rects)):
            self.panel(r, alpha=220)
            rec = CRAFT_BY_ID[q["id"]]
            if rec["kind"] == "tool":
                draw_item_icon(self.screen, rec["id"], r.inflate(-10, -10))
            elif rec.get("result", rec["id"]) in RES_INFO:
                draw_res_icon(self.screen, rec.get("result", rec["id"]), r.centerx, r.centery, 9)
            else:
                draw_res_icon(self.screen, "hide", r.centerx, r.centery, 9)
            k = 1 - q["t"] / q["total"] if i == 0 else 0
            pygame.draw.rect(self.screen, (30, 30, 30), (r.x + 3, r.bottom - 6, r.w - 6, 4))
            pygame.draw.rect(self.screen, (120, 200, 255), (r.x + 3, r.bottom - 6, int((r.w - 6) * k), 4))
            if i == 0:
                self.text(f"{max(0, q['t']):.0f}с", self.font_s, (230, 230, 240), (r.right - 3, r.y + 1), right=True)

    def draw_drag(self):
        if not self.drag:
            return
        item = self.slot_get(self.drag["ref"])
        if item:
            mx, my = pygame.mouse.get_pos()
            draw_item_icon(self.screen, item["id"], pygame.Rect(mx - 22, my - 22, 44, 44))

    def draw_messages(self):
        y = SCREEN_H - 28
        cache = self.__dict__.setdefault("msg_cache", {})
        if len(cache) > 80:
            cache.clear()
        for txt, col, t in reversed(self.messages):
            key = (txt, tuple(col))
            if key not in cache:                                 # шрифт рисуем один раз, а не каждый кадр
                cache[key] = (self.font_s.render(txt, True, col), self.font_s.render(txt, True, (0, 0, 0)))
            img, sh = cache[key]
            img.set_alpha(int(255 * min(1, t)))
            sh.set_alpha(int(200 * min(1, t)))
            self.screen.blit(sh, (17, y + 1))
            self.screen.blit(img, (16, y))
            y -= 20

    def draw_banner(self):
        if not self.banner:
            return
        title, text, t = self.banner
        lines = self.wrap(text, self.font, 620)
        r = pygame.Rect(0, 0, 670, 50 + 24 * len(lines))
        r.midtop = (SCREEN_W // 2, 124 if self.fighting_boss() else 90)     # не загораживаем полосу босса
        s = pygame.Surface(r.size, pygame.SRCALPHA)
        s.fill((30, 20, 14, int(220 * min(1, t))))
        self.screen.blit(s, r.topleft)
        pygame.draw.rect(self.screen, (230, 170, 80), r, 2, border_radius=6)
        self.text(title, self.font_b, (255, 210, 120), (r.centerx, r.y + 20), center=True)
        for i, line in enumerate(lines):
            self.text(line, self.font, (240, 230, 210), (r.centerx, r.y + 50 + i * 24), center=True)

    def draw_minimap(self):
        w = self.world
        p = self.player
        if self.map_surf is None or self.map_timer <= 0:
            self.map_timer = 2.0
            s = pygame.Surface((w.w, w.h))
            cols = {GRASS: (70, 130, 60), WATER: (40, 90, 160), SAND: (200, 186, 125), FLOOR: (140, 100, 65),
                    DITCH: (60, 42, 28), SNOW: (225, 230, 238), SWAMP: (78, 100, 66), STEPPE: (182, 172, 100),
                    ROCKY: (128, 124, 118), MEADOW: (150, 190, 90)}
            for y in range(w.h):
                row = w.ground[y]
                for x in range(w.w):
                    s.set_at((x, y), cols[row[x]])
            for (x, y), o in w.objects.items():
                t = o["t"]
                if t == "tree":
                    s.set_at((x, y), (30, 80, 34))
                elif t == "rock":
                    s.set_at((x, y), (120, 120, 125))
                elif t in ("wall", "wall_old", "stone_wall", "metal_wall", "door", "hut_wall", "tower_wall", "palisade"):
                    s.set_at((x, y), (60, 40, 25))
            for (x, y) in w.burning:
                s.set_at((x, y), (255, 120, 30))
            self.map_surf = pygame.transform.scale(s, (220, 220))
        r = pygame.Rect(SCREEN_W - 230, 100, 222, 222)
        pygame.draw.rect(self.screen, (95, 100, 118), r, 2)
        self.screen.blit(self.map_surf, (r.x + 1, r.y + 1))
        k = 220 / (w.w * TILE)

        def dot(x, y, col, rad=2):
            pygame.draw.circle(self.screen, col, (r.x + 1 + int(x * k), r.y + 1 + int(y * k)), rad)

        for i, (kind, rect, fi) in enumerate(w.structs):
            cx, cy = (rect.centerx + 0.5) * TILE, (rect.centery + 0.5) * TILE
            if kind == "tower":
                pygame.draw.rect(self.screen, (255, 220, 90), (r.x + int(cx * k) - 1, r.y + int(cy * k) - 1, 4, 4))
            elif i in w.seen:
                if fi >= 0:
                    dot(cx, cy, self.fac_color(fi), 5)
                    pygame.draw.circle(self.screen, (255, 255, 255), (r.x + 1 + int(cx * k), r.y + 1 + int(cy * k)), 5, 1)
                elif kind == "airdrop":
                    dot(cx, cy, (120, 255, 120), 4)
                elif kind == "crash":
                    dot(cx, cy, (255, 90, 40), 5)
                    pygame.draw.circle(self.screen, (255, 255, 255), (r.x + 1 + int(cx * k), r.y + 1 + int(cy * k)),
                                       6 + int(self.clock_t * 4) % 4, 1)
                elif kind == "radio":                                  # станция: голубой квадрат с антенной
                    px, py = r.x + 1 + int(cx * k), r.y + 1 + int(cy * k)
                    pygame.draw.rect(self.screen, (90, 200, 255), (px - 4, py - 4, 9, 9))
                    pygame.draw.line(self.screen, (255, 255, 255), (px, py - 4), (px, py - 11), 2)
                    if self.story["heli"] or self.story["rescue_t"] > 0:
                        pygame.draw.circle(self.screen, (90, 200, 255), (px, py), 8 + int(self.clock_t * 4) % 4, 1)
                elif kind.startswith("lair_"):                         # логово: красный череп / серый крест
                    lair = next((l for l in w.lairs if l["struct"] == i), None)
                    px, py = r.x + 1 + int(cx * k), r.y + 1 + int(cy * k)
                    if lair and lair["alive"]:
                        pygame.draw.circle(self.screen, (200, 40, 50), (px, py), 6)
                        pygame.draw.circle(self.screen, (255, 230, 220), (px, py), 6, 1)
                        pygame.draw.circle(self.screen, (20, 10, 10), (px - 2, py - 1), 1)
                        pygame.draw.circle(self.screen, (20, 10, 10), (px + 2, py - 1), 1)
                    else:
                        pygame.draw.line(self.screen, (150, 150, 150), (px - 4, py - 4), (px + 4, py + 4), 2)
                        pygame.draw.line(self.screen, (150, 150, 150), (px + 4, py - 4), (px - 4, py + 4), 2)
                else:
                    dot(cx, cy, (230, 150, 70) if kind == "camp" else (200, 140, 90), 3)
        if p.on_tower:
            for (tx, ty), o in w.objects.items():
                if o["t"] == "chest" and (any(o["res"].values()) or any(o["tools"])):
                    dot(tx * TILE, ty * TILE, (255, 230, 80), 2)
            for a in self.animals:
                hostile = (a.human and self.fac_hostile(a.faction)) or (not a.human and a.beh in ("hunter", "shadow", "territorial"))
                dot(a.x, a.y, (230, 40, 40) if hostile else (240, 240, 240), 2)
        else:
            for a in self.animals:
                if (a.beh in ("hunter", "shadow") or (a.human and a.raid)) and math.hypot(a.x - p.x, a.y - p.y) < 25 * TILE:
                    dot(a.x, a.y, (230, 40, 40))
                elif a.ally:
                    dot(a.x, a.y, (110, 240, 110))
        if self.flag:
            fx, fy = (self.flag[0] + 0.5) * TILE, (self.flag[1] + 0.5) * TILE
            pygame.draw.circle(self.screen, (90, 170, 255), (r.x + 1 + int(fx * k), r.y + 1 + int(fy * k)),
                               max(3, int(SETTLE_RADIUS * TILE * k)), 1)
            dot(fx, fy, (60, 140, 230), 4)
        dot(p.x, p.y, (255, 255, 255), 3)
        if p.on_tower:
            self.text("Обзор с вышки: жёлтые точки — сундуки с добычей", self.font_s, (255, 230, 150),
                      (r.right, r.bottom + 4), right=True)

    # ------------------------------------------------------------ стройка
    def build_tab_rects(self):
        return [pygame.Rect(SCREEN_W - 316 + i * 77, 136, 73, 28) for i in range(len(BUILD_CATS))]

    def build_list(self):
        if self.player.on_tower:
            return [b for b in BUILDS if b.get("deck")]
        return [b for b in BUILDS if b["cat"] == self.build_cat]

    def build_rows(self):
        return [pygame.Rect(SCREEN_W - 316, 174 + i * 38, 308, 34) for i in range(len(self.build_list()))]

    def over_palette(self, pos):
        rows = self.build_rows()
        return pygame.Rect(SCREEN_W - 324, 98, 324, rows[-1].bottom - 98 + 60).collidepoint(pos)

    def draw_build_palette(self):
        p = self.player
        rows = self.build_rows()
        box = pygame.Rect(SCREEN_W - 324, 100, 320, rows[-1].bottom - 100 + 56)
        self.panel(box, alpha=225)
        self.text("Стройка" + ("  —  РЕЖИМ СНОСА" if self.demolish else ""), self.font,
                  (255, 120, 100) if self.demolish else (255, 230, 150), (box.x + 12, box.y + 6))
        for (cat, label), r in zip(BUILD_CATS, self.build_tab_rects()):
            sel = cat == self.build_cat
            pygame.draw.rect(self.screen, (80, 74, 44) if sel else (44, 46, 58), r, border_radius=5)
            self.text(label, self.font_s, (255, 230, 150) if sel else (200, 200, 210), r.center, center=True)
        mouse = pygame.mouse.get_pos()
        built = self.bench_tier_built()
        for r, b in zip(rows, self.build_list()):
            locked = built < b["tier"]
            ok = all(p.res[k] >= v for k, v in b["cost"].items()) and not locked
            selected = b["id"] == self.build_sel and not self.demolish
            bg = (70, 66, 40) if selected else (64, 70, 60) if ok else (44, 44, 52)
            if r.collidepoint(mouse):
                bg = tuple(min(255, c + 20) for c in bg)
            pygame.draw.rect(self.screen, bg, r, border_radius=5)
            if selected:
                pygame.draw.rect(self.screen, (255, 214, 90), r, 2, border_radius=5)
            if b["id"] in ("floor", "ditch"):
                pygame.draw.rect(self.screen, GROUND_COL[FLOOR if b["id"] == "floor" else DITCH], (r.x + 6, r.y + 5, 24, 24))
            else:
                self.screen.blit(pygame.transform.smoothscale(self.building_icon(b["id"]), (30, 30)), (r.x + 3, r.y + 2))
            self.text(b["name"], self.font_s, (240, 240, 240) if ok else (165, 165, 172), (r.x + 38, r.y + 1))
            if locked:
                ctext, ccol = f"нужен верстак {'I' * b['tier']}", (255, 170, 110)
            elif not b["cost"]:
                ctext, ccol = "бесплатно, нужна лопата", (170, 200, 230)
            else:
                ctext = "  ".join(f"{RES_INFO[k][0]} {p.res[k]}/{v}" for k, v in b["cost"].items())
                ccol = (140, 230, 140) if ok else (235, 120, 110)
            self.text(ctext, self.font_s, ccol, (r.x + 38, r.y + 16))
        for i, line in enumerate(["ЛКМ — строить (можно вести) · колесо — выбор",
                                  "X — снос своих построек · B / ПКМ — выйти"]):
            self.text(line, self.font_s, (180, 180, 195), (box.x + 12, rows[-1].bottom + 8 + i * 18))

    # ------------------------------------------------------------ инвентарь и сундуки
    def bp_layout(self, x0, y0, width):
        n = len(self.player.backpack)
        cols = {6: 3, 10: 5, 14: 7}.get(n, 7)
        step = min(86, width // cols)
        size = step - 8
        return [pygame.Rect(x0 + (i % cols) * step, y0 + (i // cols) * step, size, size) for i in range(n)]

    @staticmethod
    def res_grid(res, x0, y0, col_w, height, max_step, cols=3):
        """Только ненулевые ресурсы, по колонкам сверху вниз — сколько бы ресурсов ни добавилось в игру."""
        ids = [rid for rid in RES_INFO if res.get(rid, 0) > 0]
        per_col = max(10, math.ceil(len(ids) / cols))
        step = max(18, min(max_step, height // per_col))
        per_col = max(per_col, 1)
        return [(rid, pygame.Rect(x0 + (i // per_col) * col_w, y0 + (i % per_col) * step, col_w - 4, step - 2))
                for i, rid in enumerate(ids) if i // per_col < cols]

    def inv_layout(self):
        panel = pygame.Rect(0, 0, 860, 560)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        rows = self.res_grid(self.player.res, panel.x + 14, panel.y + 62, 154, 280, 28)
        x0 = panel.x + 488
        bp = self.bp_layout(x0, panel.y + 92, 360)
        hb = [pygame.Rect(x0 + i * 116, panel.y + 310, 74, 74) for i in range(3)]
        return panel, rows, bp, hb

    def chest_layout(self):
        panel = pygame.Rect(0, 0, 1000, 520)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        o = self.chest_obj() or {"res": {}}
        left = self.res_grid(self.player.res, panel.x + 16, panel.y + 60, 156, 240, 24)
        right = self.res_grid(o["res"], panel.x + 516, panel.y + 60, 156, 240, 24)
        ty = panel.y + 60 + 10 * 24 + 36
        n = 3 + len(self.player.backpack)
        mine = [pygame.Rect(panel.x + 20 + (i % 9) * 50, ty + (i // 9) * 50, 46, 46) for i in range(n)]
        chest = [pygame.Rect(panel.x + 520 + i * 50, ty, 46, 46) for i in range(CHEST_TOOLS)]
        return panel, left, right, mine, chest

    def menu_panel(self):
        return self.inv_layout()[0] if self.menu == "inv" else self.chest_layout()[0]

    def slot_at(self, pos):
        if self.menu == "inv":
            _, _, bp, hb = self.inv_layout()
            for i, r in enumerate(hb):
                if r.collidepoint(pos):
                    return ("hot", i)
            for i, r in enumerate(bp):
                if r.collidepoint(pos):
                    return ("bp", i)
        elif self.menu == "chest":
            _, _, _, mine, chest = self.chest_layout()
            for i, r in enumerate(mine):
                if r.collidepoint(pos):
                    return ("hot", i) if i < 3 else ("bp", i - 3)
            for i, r in enumerate(chest):
                if r.collidepoint(pos):
                    return ("chest", i)
        return None

    def slot_click(self, ref):
        if ref[0] == "hot":
            self.player.sel = ref[1]
        elif ref[0] == "bp":
            self.equip_from_backpack(ref[1])

    def quick_move(self, ref):
        item = self.slot_get(ref)
        if item is None:
            return
        p = self.player
        if self.menu == "chest":
            c = self.chest_obj()
            if ref[0] == "chest":
                if self.give_tool(item, quiet=True):
                    c["tools"][ref[1]] = None
            else:
                i = next((j for j, v in enumerate(c["tools"]) if v is None), -1)
                if i < 0:
                    self.msg("Сундук полон", (255, 160, 120))
                    return
                c["tools"][i] = item
                self.slot_set(ref, None)
        elif ref[0] == "hot":
            p.sel = ref[1]
            self.stow_held()
        else:
            i = self.free_slot_for(item["id"])
            if i is None:
                self.equip_from_backpack(ref[1])
            else:
                p.slots[i], p.backpack[ref[1]] = item, None

    def inv_click(self, pos, button):
        _, rows, _, _ = self.inv_layout()
        for rid, r in rows:
            if r.collidepoint(pos) and button == 1 and rid in USABLE:
                self.use_resource(rid)
                return

    def chest_res_click(self, pos, button):
        p = self.player
        o = self.chest_obj()
        if not o:
            self.menu = None
            return
        every = button == 3 or pygame.key.get_mods() & pygame.KMOD_SHIFT
        _, left, right, _, _ = self.chest_layout()
        for rid, r in left:
            if r.collidepoint(pos) and p.res[rid] > 0:
                n = p.res[rid] if every else 1
                p.res[rid] -= n
                o["res"][rid] = o["res"].get(rid, 0) + n
                return
        for rid, r in right:
            have = o["res"].get(rid, 0)
            if r.collidepoint(pos) and have > 0:
                n = have if every else 1
                o["res"][rid] = have - n
                p.res[rid] += n
                return

    def draw_inventory(self):
        p = self.player
        panel, rows, bp, hb = self.inv_layout()
        self.panel(panel, alpha=232)
        self.text("Инвентарь", self.font_b, (255, 230, 150), (panel.x + 24, panel.y + 16))
        mouse = pygame.mouse.get_pos()
        if not rows:
            self.text("Ресурсов пока нет — руби деревья, собирай траву и камешки", self.font_s, (150, 150, 160),
                      (panel.x + 24, panel.y + 66))
        for rid, r in rows:
            n = p.res[rid]
            if r.collidepoint(mouse) and rid in USABLE:
                pygame.draw.rect(self.screen, (60, 64, 80), r, border_radius=4)
            draw_res_icon(self.screen, rid, r.x + 11, r.centery, 8)
            ncol = (245, 195, 140) if rid in SPOIL else (160, 230, 255) if rid in QUEST_RES else (225, 225, 225)
            ty = r.centery - 9
            self.text(RES_INFO[rid][0], self.font_s, ncol, (r.x + 24, ty))
            self.text(str(n), self.font_s, (255, 240, 200), (r.right - 4, ty), right=True)
        armor = ("нет", "кожаная (−15% урона)", "железная (−35% урона)")[p.armor]
        self.text(f"Накидка: {'надета' if p.cloak else 'нет'}  ·  Броня: {armor}  ·  Сумка: {BAG_SIZES[p.bag]} мест",
                  self.font_s, (200, 230, 200), (panel.x + 20, panel.y + 350))
        self.text("Клик по еде или лекарству — использовать · оранжевая еда портится (храни в погребе)",
                  self.font_s, (160, 160, 175), (panel.x + 20, panel.y + 370))
        conds = self.active_conditions()
        if conds:
            self.text("Состояние: " + ", ".join(CONDITIONS[c][0] for c in conds), self.font_s, (255, 160, 140),
                      (panel.x + 96, panel.y + 400))
        self.screen.blit(self.player_avatar(64), (panel.x + 20, panel.y + 392))
        free = sum(1 for b in p.backpack if b is None)
        self.text(f"Рюкзак (свободно {free}/{len(p.backpack)})", self.font, (255, 230, 150), (bp[0].x, panel.y + 62))
        for i, r in enumerate(bp):
            self.draw_slot(r, p.backpack[i], r.collidepoint(mouse) and p.backpack[i] is not None, ref=("bp", i))
        self.text("Снаряжение", self.font, (255, 230, 150), (hb[0].x, panel.y + 280))
        for i, r in enumerate(hb):
            self.draw_slot(r, p.slots[i], i == p.sel, i, ref=("hot", i))
            self.text(SLOT_NAMES[i], self.font_s, (230, 230, 230), (r.centerx, r.bottom + 12), center=True)
            self.text(SLOT_HINT[i], self.font_s, (150, 150, 160), (r.centerx, r.bottom + 30), center=True)
        lines = ["Перетаскивай предметы мышью между руками, поясом, спиной и рюкзаком",
                 "ПКМ — быстро переложить · Перетащи за край окна — выбросить · Z в игре — перевесить",
                 "Пояс: топоры, нож, мачете, дубина, молоток, факел, фонарь, праща, пистолет · Спина: всё большое"]
        for i, line in enumerate(lines):
            self.text(line, self.font_s, (180, 180, 195), (panel.centerx, panel.bottom - 66 + i * 20), center=True)
        self.draw_drag()

    def draw_chest(self):
        p = self.player
        o = self.chest_obj()
        if not o:
            self.menu = None
            return
        panel, left, right, mine, chest = self.chest_layout()
        self.panel(panel, alpha=232)
        self.text("Ты", self.font_b, (255, 230, 150), (panel.x + 16, panel.y + 16))
        title = {"house": "Сундук в доме", "camp": "Сундук в лагере", "tower": "Ящик в вышке", "village": "Сундук племени",
                 "fort": "Ящик бандитов", "post": "Тюк торговцев", "shrine": "Ларец культа",
                 "airdrop": "Груз с неба", "wreck": "Ящик с самолёта"}.get(o.get("loot"), "Сундук")
        if o["t"] == "flag":
            title = "Склад поселения"
        elif o["t"] == "cellar":
            title = "Погреб (еда не портится)"
        self.text(title, self.font_b, (255, 230, 150), (panel.x + 516, panel.y + 16))
        mouse = pygame.mouse.get_pos()
        for rows, src, x0 in ((left, p.res, panel.x + 16), (right, o["res"], panel.x + 516)):
            if not rows:
                self.text("пусто", self.font_s, (130, 130, 140), (x0 + 6, panel.y + 62))
            for rid, r in rows:
                n = src.get(rid, 0)
                if r.collidepoint(mouse):
                    pygame.draw.rect(self.screen, (60, 64, 80), r, border_radius=4)
                draw_res_icon(self.screen, rid, r.x + 10, r.centery, 7)
                ty = r.centery - 9
                self.text(RES_INFO[rid][0], self.font_s, (160, 230, 255) if rid in QUEST_RES else (225, 225, 225),
                          (r.x + 22, ty))
                self.text(str(n), self.font_s, (255, 240, 200), (r.right - 4, ty), right=True)
        ty = mine[0].y
        self.text("Руки · Пояс · Спина | Рюкзак", self.font_s, (200, 200, 210), (mine[0].x, ty - 20))
        self.text("Инструменты в сундуке", self.font_s, (200, 200, 210), (chest[0].x, ty - 20))
        for i, r in enumerate(mine):
            ref = ("hot", i) if i < 3 else ("bp", i - 3)
            it = self.slot_get(ref)
            self.draw_slot(r, it, r.collidepoint(mouse) and it is not None, ref=ref)
        for i, r in enumerate(chest):
            it = o["tools"][i]
            self.draw_slot(r, it, r.collidepoint(mouse) and it is not None, ref=("chest", i))
        for i, line in enumerate(["Ресурсы: ЛКМ — 1 шт., ПКМ или Shift+ЛКМ — всё",
                                  "Инструменты: клик — переложить, или перетащи мышью в нужный слот · E / Esc — закрыть"]):
            self.text(line, self.font_s, (180, 180, 195), (panel.centerx, panel.bottom - 44 + i * 20), center=True)
        self.draw_drag()

    # ------------------------------------------------------------ крафт
    def craft_panel(self):
        panel = pygame.Rect(0, 0, 1240, 480)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        return panel

    def craft_tab_rects(self):
        panel = self.craft_panel()
        return [pygame.Rect(panel.x + 20 + i * 140, panel.y + 54, 132, 30) for i in range(len(CRAFT_TABS))]

    def craft_list(self):
        return [c for c in CRAFTS if CRAFT_TABS[self.craft_tab][1](c)]

    def craft_rows(self):
        panel = self.craft_panel()
        items = self.craft_list()
        half = max(1, (len(items) + 1) // 2)
        cw = (panel.w - 60) // 2
        return [pygame.Rect(panel.x + 20 + (i // half) * (cw + 20), panel.y + 96 + (i % half) * 41, cw, 38)
                for i in range(len(items))]

    def draw_craft(self):
        p = self.player
        panel = self.craft_panel()
        self.panel(panel, alpha=235)
        self.text("Крафт и изучение", self.font_b, (255, 230, 150), (panel.x + 24, panel.y + 12))
        tier = self.bench_tier_near()
        self.text(f"Рядом: {'верстак ' + 'I' * tier if tier else 'верстака нет'} · костёр: {'да' if self.near_fire() else 'нет'}"
                  f" · печь: {'да' if self.near_obj(('furnace',)) else 'нет'}"
                  f" · металлолом: {p.res['scrap']} · очередь: {len(self.craft_queue)}/8",
                  self.font_s, (190, 200, 220), (panel.right - 24, panel.y + 22), right=True)
        mouse = pygame.mouse.get_pos()
        for i, ((label, _), r) in enumerate(zip(CRAFT_TABS, self.craft_tab_rects())):
            sel = i == self.craft_tab
            pygame.draw.rect(self.screen, (80, 74, 44) if sel else (44, 46, 58), r, border_radius=5)
            self.text(label, self.font, (255, 230, 150) if sel else (200, 200, 210), r.center, center=True)
        for r, rec in zip(self.craft_rows(), self.craft_list()):
            known = rec["id"] in p.known
            ok, why = self.recipe_state(rec)
            bg = (64, 70, 60) if ok else (44, 44, 52) if known else (46, 40, 60)
            if r.collidepoint(mouse):
                bg = tuple(min(255, c + 22) for c in bg)
            pygame.draw.rect(self.screen, bg, r, border_radius=5)
            if rec["kind"] == "tool":
                draw_item_icon(self.screen, rec["id"], pygame.Rect(r.x + 6, r.y + 4, 32, 32))
            elif rec.get("result", rec["id"]) in RES_INFO:
                draw_res_icon(self.screen, rec.get("result", rec["id"]), r.x + 22, r.centery)
            else:
                draw_res_icon(self.screen, "hide", r.x + 22, r.centery)
            self.text(rec["name"], self.font, (240, 240, 240) if ok else (175, 175, 180), (r.x + 46, r.y + 2))
            if not known:
                need = max(1, rec["tier"])
                self.text(f"ЗАКРЫТО · изучить у верстака {'I' * need}: {rec.get('research', 0)} металлолома (клик)",
                          self.font_s, (200, 170, 255), (r.x + 46, r.y + 22))
                continue
            x = r.x + 46
            for k, v in rec["cost"].items():
                col = (140, 230, 140) if p.res[k] >= v else (235, 110, 100)
                x = self.text(f"{RES_INFO[k][0]} {p.res[k]}/{v}", self.font_s, col, (x, r.y + 22)).right + 10
            self.text(f"{rec['time']}с" + (f" · {why}" if why and why != "не хватает ресурсов" else ""), self.font_s,
                      (255, 190, 110) if why else (170, 180, 200), (r.right - 10, r.y + 12), right=True)
        self.text("Клик — в очередь крафта (идёт, пока ты занят делами) · закрытые рецепты изучаются за металлолом · "
                  "C / Esc — закрыть", self.font_s, (180, 180, 195), (panel.centerx, panel.bottom - 22), center=True)

    # ------------------------------------------------------------ диалог
    def dialog_panel(self):
        panel = pygame.Rect(0, 0, 900, 640)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        return panel

    def dialog_rows(self):
        panel = self.dialog_panel()
        return [pygame.Rect(panel.x + 30, panel.y + 226 + i * 32, panel.w - 60, 29) for i in range(12)]

    def draw_dialog(self):
        dg = self.dialog
        if not dg or dg["npc"].dead:
            self.menu, self.dialog = None, None
            return
        a = dg["npc"]
        scr = self.screen
        panel = self.dialog_panel()
        self.panel(panel, alpha=250)
        f = self.world.factions[a.faction]
        tcol = tuple(f["color"])
        ftype = f["type"]
        px, py = panel.x + 90, panel.y + 100
        pygame.draw.circle(scr, (40, 36, 30), (px, py), 64)
        pygame.draw.circle(scr, tcol, (px, py), 64, 3)
        av = self.creature_avatar(a, 110)
        scr.blit(av, av.get_rect(center=(px, py)))
        self.bar(px - 50, py + 70, 100, a.hp / a.max_hp, 6)
        x0 = panel.x + 178
        self.text(a.name, self.font_b, (255, 230, 150), (x0, panel.y + 20))
        if a.ally:
            sub = f"{'Житель поселения' if a.settler else 'Твой спутник'} ({f['name']})"
            att_text, att_col = "Верен тебе", (140, 255, 140)
        else:
            att = self.attitude(f)
            sub = f"{ROLES[a.role]['name']} · {f['name']}"
            att_text = ATT_NAME[att] + (f" (до конца дня {f['truce']})" if att == "truce" else "")
            att_col = ATT_COL[att]
            wars = [self.world.factions[t]["name"] for t in f["wars"]]
            if wars:
                att_text += "   ·   воюют с: " + ", ".join(wars)
        self.text(sub, self.font, (220, 220, 230), (x0, panel.y + 56))
        self.text(att_text, self.font_s if len(att_text) > 50 else self.font, att_col, (x0, panel.y + 84))
        if not a.ally:
            bar = pygame.Rect(x0, panel.y + 114, 300, 12)
            pygame.draw.rect(scr, (40, 40, 46), bar, border_radius=3)
            mid = bar.x + bar.w // 2
            val = f["rel"] / 100 * bar.w / 2
            pygame.draw.rect(scr, (110, 220, 110) if val >= 0 else (220, 90, 80),
                             (min(mid, mid + val), bar.y, abs(val), bar.h), border_radius=3)
            pygame.draw.line(scr, (200, 200, 200), (mid, bar.y - 2), (mid, bar.bottom + 2), 1)
            self.text(f"Отношение: {f['rel']}   ·   дары до перемирия: {f['gift']}/10", self.font_s,
                      (190, 190, 200), (bar.right + 14, bar.y - 3))
        for i, line in enumerate(self.wrap(f"«{dg['line']}»", self.font, panel.w - 210)[:3]):
            self.text(line, self.font, (245, 240, 225), (x0, panel.y + 140 + i * 24))
        mouse = pygame.mouse.get_pos()
        for i, ((label, act), r) in enumerate(zip(self.dialog_options(), self.dialog_rows())):
            hover = r.collidepoint(mouse)
            tough = act in ("threaten", "shoo", "declare", "tough")
            pygame.draw.rect(scr, (70, 72, 90) if hover else ((64, 36, 36) if tough else (40, 42, 54)), r, border_radius=5)
            num = f"{i + 1}. " if i < 9 else "    "
            self.text(num + label, self.font, (255, 240, 200) if hover else (225, 225, 230), (r.x + 12, r.y + 3))
        self.text("Цифры или клик — ответить · Esc — уйти", self.font_s, (170, 170, 185),
                  (panel.centerx, panel.bottom - 20), center=True)

    # ------------------------------------------------------------ навыки
    def draw_skills(self):
        p = self.player
        panel = pygame.Rect(0, 0, 820, 520)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        self.panel(panel, alpha=240)
        self.text("Навыки", self.font_b, (255, 230, 150), (panel.x + 24, panel.y + 14))
        self.text("Навыки растут сами, когда ты делаешь дело: рубишь, охотишься, лечишься, крафтишь...",
                  self.font_s, (190, 200, 220), (panel.x + 24, panel.y + 52))
        for i, (sid, name) in enumerate(SKILLS):
            y = panel.y + 84 + i * 50
            lvl = self.skill_lvl(sid)
            xp = p.skills.get(sid, 0)
            cur, nxt = 20 * lvl * lvl, 20 * (lvl + 1) ** 2
            self.text(f"{name}", self.font, (255, 240, 200), (panel.x + 24, y))
            self.text(f"ур. {lvl}" + (" (макс.)" if lvl >= SKILL_MAX else ""), self.font, (160, 220, 255),
                      (panel.x + 190, y))
            k = 1.0 if lvl >= SKILL_MAX else (xp - cur) / max(1, nxt - cur)
            pygame.draw.rect(self.screen, (40, 40, 46), (panel.x + 290, y + 6, 200, 12), border_radius=3)
            pygame.draw.rect(self.screen, (110, 180, 250), (panel.x + 290, y + 6, int(200 * k), 12), border_radius=3)
            self.text(SKILL_INFO[sid], self.font_s, (190, 190, 200), (panel.x + 504, y + 3))
        self.text("K / Esc — закрыть", self.font_s, (170, 170, 185), (panel.centerx, panel.bottom - 22), center=True)

    # ------------------------------------------------------------ поселение
    def settlement_panel(self):
        panel = pygame.Rect(0, 0, 860, 560)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        return panel

    def settlement_rows(self):
        panel = self.settlement_panel()
        rows = []
        for i, a in enumerate(self.settlers()[:8]):
            y = panel.y + 120 + i * 46
            rows.append((a, pygame.Rect(panel.x + 410, y, 190, 36), pygame.Rect(panel.x + 612, y, 210, 36)))
        return rows

    def settlement_stash_button(self):
        panel = self.settlement_panel()
        return pygame.Rect(panel.x + 24, panel.bottom - 64, 260, 42)

    def draw_settlement(self):
        from .core import JOB_BY_ID
        panel = self.settlement_panel()
        self.panel(panel, alpha=240)
        settlers = self.settlers()
        cap = self.settle_capacity()
        self.text("Поселение", self.font_b, (255, 230, 150), (panel.x + 24, panel.y + 14))
        self.text(f"Жителей: {len(settlers)} / мест для сна: {cap}  (кровати, лежанки и палатки в радиусе "
                  f"{SETTLE_RADIUS} клеток от флага + 1)", self.font_s, (200, 210, 230), (panel.x + 24, panel.y + 52))
        self.text("Каждое утро жители приносят на склад то, что добыли на своей работе. Охрана защищает поселение.",
                  self.font_s, (180, 200, 180), (panel.x + 24, panel.y + 72))
        if not settlers:
            self.text("Пока никто не живёт здесь. Поговори с человеком, у которого отношение 50+, и выбери",
                      self.font, (220, 220, 220), (panel.x + 24, panel.y + 130))
            self.text("«Пригласить жить в моё поселение». Спасённые выжившие с крушений тоже приходят сюда.",
                      self.font, (220, 220, 220), (panel.x + 24, panel.y + 156))
        mouse = pygame.mouse.get_pos()
        for a, jr, fr in self.settlement_rows():
            y = jr.y
            self.screen.blit(self.creature_avatar(a, 36), (panel.x + 24, y))
            f = self.world.factions[a.faction] if a.faction >= 0 else None
            self.text(a.name, self.font, (255, 240, 200), (panel.x + 68, y - 2))
            self.text(f["name"] if f else "", self.font_s, (170, 180, 200), (panel.x + 68, y + 20))
            self.bar(panel.x + 260, y + 14, 130, a.hp / a.max_hp, 8)
            for r, label in ((jr, "Работа: " + JOB_BY_ID.get(a.job, ("", "Охрана"))[1]),
                             (fr, "Живёт у флага" if a.stay else "Ходит за тобой")):
                pygame.draw.rect(self.screen, (70, 72, 90) if r.collidepoint(mouse) else (44, 46, 58), r, border_radius=6)
                self.text(label, self.font_s, (240, 240, 240), r.center, center=True)
        b = self.settlement_stash_button()
        pygame.draw.rect(self.screen, (80, 74, 44) if b.collidepoint(mouse) else (54, 50, 36), b, border_radius=8)
        pygame.draw.rect(self.screen, (255, 214, 90), b, 2, border_radius=8)
        self.text("Открыть склад поселения", self.font, (255, 240, 200), b.center, center=True)
        self.text("Клик по работе — сменить · клик справа — за тобой / у флага · Esc — закрыть", self.font_s,
                  (180, 180, 195), (panel.right - 24, panel.bottom - 50), right=True)

    # ------------------------------------------------------------ журнал
    def journal_panel(self):
        panel = pygame.Rect(0, 0, 1180, 620)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        return panel

    def journal_tab_rects(self):
        panel = self.journal_panel()
        return [pygame.Rect(panel.x + 200 + i * 170, panel.y + 14, 160, 32) for i in range(3)]

    def note_list_rects(self):
        panel = self.journal_panel()
        return [(nid, pygame.Rect(panel.x + 20, panel.y + 90 + i * 30, 360, 28))
                for i, nid in enumerate(self.story["notes"][:16])]

    def draw_check(self, x, y, done):
        pygame.draw.rect(self.screen, (40, 44, 56), (x, y, 16, 16), border_radius=3)
        pygame.draw.rect(self.screen, (130, 220, 130) if done else (120, 125, 140), (x, y, 16, 16), 2, border_radius=3)
        if done:
            pygame.draw.lines(self.screen, (140, 255, 140), False, [(x + 3, y + 8), (x + 7, y + 12), (x + 13, y + 3)], 3)

    def draw_journal(self):
        panel = self.journal_panel()
        self.panel(panel, alpha=240)
        self.text("Журнал", self.font_b, (255, 230, 150), (panel.x + 24, panel.y + 14))
        mouse = pygame.mouse.get_pos()
        for i, (r, label) in enumerate(zip(self.journal_tab_rects(), ("1  Сюжет", "2  Записки", "3  Фракции"))):
            sel = i == self.journal_tab
            pygame.draw.rect(self.screen, (70, 64, 40) if sel else (50, 54, 66) if r.collidepoint(mouse) else (34, 38, 48),
                             r, border_radius=6)
            pygame.draw.rect(self.screen, (255, 214, 90) if sel else (95, 100, 118), r, 2, border_radius=6)
            self.text(label, self.font, (255, 240, 200), r.center, center=True)
        footer = (f"Мир: {self.settings['name']} · зерно {self.world.seed} · {WORLD_SIZES[self.settings['size']][0]} · "
                  f"{DIFFICULTIES[self.settings['diff']][0]} · побеждено врагов: {self.kills}   ·   1/2/3 — вкладки · "
                  f"J / Esc — закрыть")
        self.text(footer, self.font_s, (170, 170, 185), (panel.centerx, panel.bottom - 22), center=True)
        if self.journal_tab == 0:
            self.draw_journal_story(panel)
        elif self.journal_tab == 1:
            self.draw_journal_notes(panel)
        else:
            self.draw_journal_factions(panel)

    def draw_journal_story(self, panel):
        st = self.story
        self.text("Как выбраться с острова", self.font, (255, 230, 150), (panel.x + 24, panel.y + 62))
        y = panel.y + 94
        goal = self.current_goal()
        for text, done in self.objectives():
            self.draw_check(panel.x + 26, y + 2, done)
            col = (150, 210, 150) if done else (255, 240, 200) if text == goal else (205, 205, 215)
            self.text(text, self.font_s if done else self.font, col, (panel.x + 52, y))
            y += 30
        x0 = panel.x + 740
        self.text("Хозяева острова", self.font, (255, 230, 150), (x0, panel.y + 62))
        y = panel.y + 94
        w = self.world
        for lair in w.lairs:
            boss = LAIRS[lair["kind"]]["boss"]
            known = lair["struct"] in w.seen
            fake = type("A", (), {"kind": boss, "color": ANIMALS[boss]["color"], "human": False})()
            self.screen.blit(self.creature_avatar(fake, 44), (x0, y))
            self.text(ANIMALS[boss]["name"], self.font, (240, 220, 210) if lair["alive"] else (150, 150, 150), (x0 + 54, y))
            state = ("повержен" if not lair["alive"] else "логово отмечено на карте" if known else "логово не найдено")
            self.text(state, self.font_s, (150, 230, 150) if not lair["alive"] else (255, 200, 140) if known else
                      (160, 160, 170), (x0 + 54, y + 22))
            y += 56
        y += 10
        found = len(st["notes"])
        self.text(f"Найдено записок: {found} из {len(NOTES)} (вкладка «Записки»)", self.font_s, (200, 210, 230), (x0, y))
        lines = self.wrap("Записки лежат в сундуках домов, вышек, лагерей, деревень и рядом с останками. Они рассказывают, "
                          "что случилось с экспедицией «Маяк-7», и отмечают на карте логова Хозяев.", self.font_s, 400)
        for i, line in enumerate(lines):
            self.text(line, self.font_s, (160, 165, 180), (x0, y + 24 + i * 18))

    def draw_journal_notes(self, panel):
        st = self.story
        mouse = pygame.mouse.get_pos()
        self.text(f"Записки ({len(st['notes'])} из {len(NOTES)})", self.font, (255, 230, 150), (panel.x + 24, panel.y + 60))
        if not st["notes"]:
            self.text("Пока ни одной. Осмотри останки рядом с местом, где ты очнулся.", self.font_s, (170, 170, 185),
                      (panel.x + 24, panel.y + 96))
            return
        if self.note_sel not in st["notes"]:
            self.note_sel = st["notes"][-1]
        for nid, r in self.note_list_rects():
            sel = nid == self.note_sel
            if sel or r.collidepoint(mouse):
                pygame.draw.rect(self.screen, (70, 64, 40) if sel else (50, 54, 66), r, border_radius=5)
            self.text(NOTES[nid]["title"], self.font_s, (255, 240, 200) if sel else (215, 215, 225), (r.x + 10, r.y + 5))
        page = pygame.Rect(panel.x + 410, panel.y + 60, 740, 500)
        self.draw_paper(page, self.note_sel)

    def draw_paper(self, page, nid):
        """Лист бумаги с текстом записки."""
        pygame.draw.rect(self.screen, (226, 214, 180), page, border_radius=6)
        pygame.draw.rect(self.screen, (150, 124, 84), page, 3, border_radius=6)
        for i in range(page.y + 70, page.bottom - 20, 28):
            pygame.draw.line(self.screen, (204, 190, 152), (page.x + 20, i), (page.right - 20, i), 1)
        self.text(NOTES[nid]["title"], self.font_b, (70, 46, 26), (page.centerx, page.y + 30), center=True, shadow=False)
        for i, line in enumerate(self.wrap(self.note_text(nid), self.font, page.w - 60)):
            self.text(line, self.font, (52, 40, 30), (page.x + 30, page.y + 72 + i * 28), shadow=False)

    def draw_note(self):
        if not self.note_queue:
            self.menu = None
            return
        self.draw_overlay(150)
        page = pygame.Rect(0, 0, 760, 500)
        page.center = (SCREEN_W // 2, SCREEN_H // 2 - 10)
        self.draw_paper(page, self.note_queue[0])
        more = len(self.note_queue) > 1
        self.text(("Тут ещё записка — " if more else "") + "E / Enter / клик — " + ("дальше" if more else "закрыть") +
                  "   ·   все записки — в журнале (J)", self.font_s, (240, 240, 240), (SCREEN_W // 2, page.bottom + 18),
                  center=True)

    def draw_radio(self):
        st = self.story
        p = self.player
        self.draw_overlay(150)
        panel = pygame.Rect(0, 0, 680, 470)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2 + 10)
        self.panel(panel, alpha=245, border=(90, 200, 255))
        self.text("Передатчик «Маяк-7»", self.font_b, (160, 225, 255), (panel.centerx, panel.y + 26), center=True)
        y = panel.y + 66
        from .story import PARTS
        for part, kind in PARTS:
            installed = part in st["installed"]
            have = p.res.get(part, 0) > 0
            draw_res_icon(self.screen, part, panel.x + 44, y + 14, 12)
            self.text(RES_INFO[part][0], self.font, (255, 240, 200), (panel.x + 70, y + 2))
            if installed:
                state, col = "установлена", (140, 255, 140)
            elif have:
                state, col = "есть у тебя — нажми «Установить»", (255, 230, 140)
            else:
                lair = self.lair_by_kind(kind)
                where = "логово на карте" if lair and lair["struct"] in self.world.seen else "логово не найдено"
                state, col = f"у {ANIMALS[LAIRS[kind]['boss']]['cause']} ({where})", (255, 160, 140)
            self.text(state, self.font_s, col, (panel.x + 230, y + 5))
            y += 40
        if st["heli"]:
            status = "Вертолёт приземлился на площадке «H» — садись в него (E)!"
        elif st["rescue_t"] > 0:
            status = f"Сигнал отправлен. Вертолёт прилетит через {int(st['rescue_t'])} с. Держись у станции!"
        elif len(st["installed"]) == 3:
            status = "Передатчик собран. Подай сигнал SOS — и продержись сутки до прилёта."
        elif all(part in st["installed"] or p.res.get(part, 0) > 0 for part, _ in PARTS):
            status = "Все детали у тебя! Нажми «Установить детали», а потом подай сигнал SOS."
        else:
            status = "Не хватает деталей. Их охраняют Хозяева острова — читай записки, чтобы найти логова."
        for i, line in enumerate(self.wrap(status, self.font, panel.w - 60)):
            self.text(line, self.font, (210, 230, 255), (panel.centerx, panel.y + 200 + i * 24), center=True)
        self.draw_buttons(self.radio_buttons())

    def draw_ending(self):
        kind = self.ending_kind or "rescue"
        e = ENDINGS[kind]
        self.draw_overlay(215)
        self.text(e["title"], self.font_xl, (255, 230, 150), (SCREEN_W // 2, 110), center=True)
        for i, line in enumerate(self.wrap(e["text"], self.font, 760)):
            self.text(line, self.font, (235, 235, 240), (SCREEN_W // 2, 190 + i * 28), center=True)
        bosses = sum(1 for l in self.world.lairs if not l["alive"])
        stats = [f"Прожито дней: {self.day}", f"Побеждено врагов: {self.kills}",
                 f"Хозяев острова повержено: {bosses} из {len(self.world.lairs)}",
                 f"Найдено записок: {len(self.story['notes'])} из {len(NOTES)}"]
        for i, line in enumerate(stats):
            self.text(line, self.font, (255, 214, 120), (SCREEN_W // 2, 340 + i * 30), center=True)
        self.draw_buttons(self.ending_buttons())

    def fighting_boss(self):
        p = self.player
        return next((a for a in self.animals if a.beh == "boss" and not a.dead and a.aggro_t > 0
                     and abs(a.x - p.x) < 20 * TILE and abs(a.y - p.y) < 20 * TILE), None)

    def draw_boss_bar(self):
        """Большая полоса здоровья босса вверху экрана, пока он сражается с тобой."""
        boss = self.fighting_boss()
        if not boss or self.menu is not None:
            return
        r = pygame.Rect(0, 0, 560, 44)
        r.midtop = (SCREEN_W // 2, 72)
        self.panel(r, alpha=210, border=(170, 80, 220))
        name = ANIMALS[boss.kind]["name"]
        if boss.hp < boss.max_hp * 0.4:
            name += " — В ЯРОСТИ"
        self.text(name, self.font, (235, 200, 255), (r.centerx, r.y + 14), center=True)
        bar = pygame.Rect(r.x + 14, r.y + 28, r.w - 28, 10)
        pygame.draw.rect(self.screen, (40, 20, 30), bar)
        pygame.draw.rect(self.screen, (200, 50, 70), (bar.x, bar.y, int(bar.w * max(0, boss.hp) / boss.max_hp), bar.h))
        pygame.draw.rect(self.screen, (255, 220, 230), bar, 1)

    def draw_goal(self, y):
        goal = self.current_goal()
        if not goal:
            return
        lines = self.wrap("Цель: " + goal, self.font_s, 270)[:3]
        r = pygame.Rect(SCREEN_W - 298, y, 290, 10 + 18 * len(lines))
        self.panel(r, alpha=160, border=(120, 110, 70))
        for i, line in enumerate(lines):
            self.text(line, self.font_s, (255, 235, 170), (r.x + 10, r.y + 5 + i * 18))

    def draw_journal_factions(self, panel):
        self.text("Фракции острова", self.font, (255, 230, 150), (panel.x + 24, panel.y + 56))
        y = panel.y + 86
        for fi, f in enumerate(self.world.factions):
            known = any(s[2] == fi and i in self.world.seen for i, s in enumerate(self.world.structs))
            att = self.attitude(f)
            pygame.draw.circle(self.screen, tuple(f["color"]), (panel.x + 34, y + 11), 7)
            name = f["name"] if known else f"{FACTION_TYPES[f['type']]['label']} (лагерь не найден)"
            if not f["alive"]:
                name += " — исчезли"
            self.text(name, self.font, (230, 230, 230) if f["alive"] else (130, 130, 130), (panel.x + 50, y))
            self.text(f"{ATT_NAME[att]} ({f['rel']})", self.font_s, ATT_COL[att], (panel.x + 380, y + 3))
            wars = ", ".join(self.world.factions[t]["short"] for t in f["wars"])
            while wars and self.font_s.size("война: " + wars)[0] > 200:
                wars = wars[:-4] + "…"
            if wars:
                self.text("война: " + wars, self.font_s, (255, 150, 130), (panel.x + 500, y + 3))
            if f["quest"]:
                self.text("задание: " + f["quest"]["text"], self.font_s, (190, 200, 255), (panel.x + 50, y + 22))
                y += 18
            y += 30
        self.text("События", self.font, (255, 230, 150), (panel.x + 720, panel.y + 56))
        lines = []
        for e in reversed(self.journal[-30:]):
            lines += self.wrap(e, self.font_s, 430)
        for i, line in enumerate(lines[:24]):
            self.text(line, self.font_s, (210, 210, 220), (panel.x + 720, panel.y + 86 + i * 20))

    # ------------------------------------------------------------ справка, пауза, смерть
    def draw_help(self):
        panel = pygame.Rect(0, 0, 1020, 700)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        self.panel(panel, alpha=245)
        self.text(f"NeTheForest  v{VERSION}", self.font_b, (255, 230, 150), (panel.centerx, panel.y + 24), center=True)
        lines = [
            ("WASD / Shift", "ходить / бег. Сквозь чащу, болото и ров — медленно; можно плавать"),
            ("ЛКМ (зажать)", "рубить, бить, стрелять, рыбачить; молотком — чинить свои постройки"),
            ("1 / 2 / 3, колесо", "хотбар: Руки · Пояс · Спина"),
            ("Z / Q / G", "перевесить (руки ↔ пояс/спина) / в рюкзак / выбросить"),
            ("E", "НАВЕДИ МЫШЬ на предмет или человека — появится подсказка [E]"),
            ("Tab  /  C", "инвентарь  /  крафт и изучение"),
            ("B  /  X", "стройка (стены, ловушки, турели, флаг, верстаки...) / снос"),
            ("V  /  T  /  R", "поджечь факелом или огнивом / бросить огненную бомбу / огненные стрелы"),
            ("F  /  H", "съесть еду  /  лечиться (H сам выберет лекарство под рану или болезнь)"),
            ("M / J / K", "мини-карта  /  журнал: сюжет, записки, фракции  /  навыки"),
            ("F5 / F9", "сохранить / загрузить этот мир (есть автосохранение на рассвете)"),
            ("Esc / F1", "меню паузы / эта справка"),
        ]
        y = panel.y + 54
        for k, v in lines:
            self.text(k, self.font, (255, 214, 90), (panel.x + 34, y))
            self.text(v, self.font, (225, 225, 230), (panel.x + 220, y))
            y += 26
        tips = [
            "Красный «!» над зверем или человеком — он атакует тебя. Слева — список угроз с их здоровьем.",
            "Наведи мышь на кого угодно — сверху появится карточка с портретом и HP. Жёлтые стрелки «ВХОД» — двери зданий.",
            "Дверь: ты и твои люди проходите сами, враги и звери — нет. E по двери — распахнуть настежь для всех.",
            "Флаг поселения (B → Основа) + кровати рядом = жители. Приглашай людей с отношением 50+, давай им работу.",
            "Времена года по 4 дня: зимой мороз, лёд на озёрах, спят медведи и голодные волки охотятся даже днём.",
            "Раны кровоточат (запах крови манит волков), грязные раны гноятся. Сырая вода — дизентерия: кипяти её.",
            "Мясо и рыба портятся: копти их в коптильне или храни в погребе. Гнилью удобряют грядки.",
            "СЮЖЕТ: читай записки, найди радиостанцию «Маяк-7», отбери 3 детали рации у боссов и вызови вертолёт.",
            "Боссы живут в логовах (красный череп на карте). Сундук логова открывается после победы над хозяином.",
            "Цветочные поляны: цветы → отвар и мазь, ульи → мёд. С горящим факелом в руках пчёлы не жалят.",
        ]
        y += 6
        for t in tips:
            self.text(t, self.font_s, (180, 205, 180), (panel.x + 34, y))
            y += 20
        self.text("Нажми Enter, чтобы продолжить", self.font, (255, 255, 255), (panel.centerx, panel.bottom - 22), center=True)

    def pause_buttons(self):
        snd = getattr(self, "sound", None)
        sound_label = "Звук: " + ("нет устройства" if not (snd and snd.ok) else "вкл" if snd.enabled else "выкл")
        labels = [("resume", "Продолжить"), ("save", "Сохранить"), ("save_new", "Сохранить как новый слот"),
                  ("load", "Загрузить игру..."), ("sound", sound_label), ("help", "Управление"),
                  ("main", "Главное меню"), ("quit", "Выход")]
        return [(act, label, pygame.Rect(SCREEN_W // 2 - 170, 180 + i * 50, 340, 42)) for i, (act, label) in enumerate(labels)]

    def draw_overlay(self, alpha=170):
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        self.screen.blit(s, (0, 0))

    def draw_buttons(self, buttons):
        mouse = pygame.mouse.get_pos()
        for act, label, r in buttons:
            hover = r.collidepoint(mouse)
            pygame.draw.rect(self.screen, (80, 74, 44) if hover else (40, 44, 56), r, border_radius=8)
            pygame.draw.rect(self.screen, (255, 214, 90) if hover else (95, 100, 118), r, 2, border_radius=8)
            self.text(label, self.font, (255, 240, 200), r.center, center=True)

    def draw_pause(self):
        self.draw_overlay()
        self.text("Пауза", self.font_xl, (255, 230, 150), (SCREEN_W // 2, 120), center=True)
        self.text(f"Мир «{self.settings['name']}» · слот «{self.slot}»", self.font_s, (200, 200, 210),
                  (SCREEN_W // 2, 162), center=True)
        self.draw_buttons(self.pause_buttons())

    def draw_dead(self):
        p = self.player
        self.draw_overlay()
        self.text("Ты погиб", self.font_xl, (255, 230, 150), (SCREEN_W // 2, SCREEN_H // 2 - 100), center=True)
        for i, line in enumerate([f"Причина: смерть от {p.cause or 'ран'}",
                                  f"Прожито дней: {self.day}   ·   Побеждено врагов: {self.kills}",
                                  "R — новая игра с теми же настройками  ·  F9 — загрузить сохранение  ·  Esc — главное меню"]):
            self.text(line, self.font, (230, 230, 230), (SCREEN_W // 2, SCREEN_H // 2 - 20 + i * 32), center=True)

    # ------------------------------------------------------------ главное меню и экраны мира
    def draw_menu_background(self):
        self.screen.fill((20, 36, 24))
        for i in range(26):
            x = (i * 137) % (SCREEN_W + 80) - 40
            y = 380 + (i * 53) % 340
            self.draw_tree(x, y, {"kind": "pine" if i % 3 else "oak", "size": 1.0 + (i % 4) * 0.15, "hit_t": -9})
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((6, 8, 20, 120))
        self.screen.blit(s, (0, 0))

    def main_buttons(self):
        items = []
        if self.continue_slot():
            items.append(("continue", "Продолжить"))
        items += [("new", "Новый мир"), ("load", "Загрузить мир"), ("help", "Управление"), ("quit", "Выход")]
        return [(act, label, pygame.Rect(SCREEN_W // 2 - 170, 250 + i * 58, 340, 48)) for i, (act, label) in enumerate(items)]

    def continue_slot(self):
        slot = saves.load_settings().get("last_slot")
        return slot if slot and any(m["slot"] == slot for m in self.slot_list) else None

    def draw_main_menu(self):
        self.draw_menu_background()
        self.text("NeTheForest", self.font_xl, (255, 230, 150), (SCREEN_W // 2, 130), center=True)
        self.text(f"версия {VERSION} · выживание, стройка, племена и фракции", self.font, (210, 220, 200),
                  (SCREEN_W // 2, 186), center=True)
        self.draw_buttons(self.main_buttons())
        if self.scene_help:
            self.draw_help()

    def newgame_rows(self):
        x, w = SCREEN_W // 2 - 300, 600
        return {key: pygame.Rect(x, 170 + i * 58, w, 46) for i, key in
                enumerate(("name", "seed", "size", "diff", "dens", "facs"))}

    def newgame_buttons(self):
        return [("random_seed", "Случайное зерно", pygame.Rect(SCREEN_W // 2 + 320, 228, 180, 46)),
                ("create", "Создать мир", pygame.Rect(SCREEN_W // 2 - 300, 540, 290, 52)),
                ("back", "Назад", pygame.Rect(SCREEN_W // 2 + 10, 540, 290, 52))]

    NG_OPTIONS = {"size": WORLD_SIZES, "diff": DIFFICULTIES, "dens": DENSITIES, "facs": FACTION_AMOUNTS}
    NG_LABELS = {"name": "Название мира", "seed": "Зерно генерации", "size": "Размер острова", "diff": "Сложность",
                 "dens": "Лес", "facs": "Фракций"}

    def draw_newgame(self):
        self.draw_menu_background()
        self.text("Новый мир", self.font_xl, (255, 230, 150), (SCREEN_W // 2, 96), center=True)
        ng = self.ng
        mouse = pygame.mouse.get_pos()
        for key, r in self.newgame_rows().items():
            focus = ng["focus"] == key
            pygame.draw.rect(self.screen, (54, 56, 70) if r.collidepoint(mouse) or focus else (36, 38, 50), r, border_radius=8)
            pygame.draw.rect(self.screen, (255, 214, 90) if focus else (95, 100, 118), r, 2, border_radius=8)
            self.text(self.NG_LABELS[key], self.font, (200, 200, 210), (r.x + 16, r.y + 11))
            if key in ("name", "seed"):
                val = ng[key] + ("|" if focus and int(self.clock_t * 2) % 2 == 0 else "")
                if key == "seed" and not ng[key] and not focus:
                    val = "(случайное)"
            else:
                val = "<   " + self.NG_OPTIONS[key][ng[key]][0] + "   >"
            self.text(val, self.font, (255, 240, 200), (r.right - 16, r.y + 11), right=True)
        self.draw_buttons(self.newgame_buttons())
        self.text("Клик по полю — ввести текст или переключить вариант · одинаковое зерно = одинаковый остров",
                  self.font_s, (190, 200, 190), (SCREEN_W // 2, 520), center=True)

    def load_rows(self):
        return [pygame.Rect(SCREEN_W // 2 - 420, 150 + i * 56, 700, 48) for i in range(min(8, len(self.slot_list)))]

    def draw_load(self):
        self.draw_menu_background()
        self.text("Загрузить мир", self.font_xl, (255, 230, 150), (SCREEN_W // 2, 90), center=True)
        mouse = pygame.mouse.get_pos()
        if not self.slot_list:
            self.text("Сохранений пока нет", self.font, (220, 220, 220), (SCREEN_W // 2, 300), center=True)
        for meta, r in zip(self.slot_list, self.load_rows()):
            hover = r.collidepoint(mouse)
            pygame.draw.rect(self.screen, (60, 62, 78) if hover else (36, 38, 50), r, border_radius=8)
            pygame.draw.rect(self.screen, (95, 100, 118), r, 2, border_radius=8)
            size = WORLD_SIZES.get(meta.get("size"), ("?",))[0]
            diff = DIFFICULTIES.get(meta.get("diff"), ("?",))[0]
            self.text(f"{meta.get('name', meta['slot'])}  —  день {meta.get('day', '?')}", self.font, (255, 240, 200),
                      (r.x + 14, r.y + 4))
            self.text(f"{size} · {diff} · зерно {meta.get('seed')} · слот {meta['slot']} · {meta.get('saved', '')}",
                      self.font_s, (180, 185, 200), (r.x + 14, r.y + 27))
            d = pygame.Rect(r.right + 10, r.y, 120, 48)
            confirm = self.delete_confirm == meta["slot"]
            pygame.draw.rect(self.screen, (150, 50, 40) if confirm else (70, 40, 40), d, border_radius=8)
            self.text("Точно?" if confirm else "Удалить", self.font, (255, 220, 210), d.center, center=True)
        self.draw_buttons([("back", "Назад", pygame.Rect(SCREEN_W // 2 - 150, 630, 300, 48))])
