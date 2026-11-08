# -*- coding: utf-8 -*-
"""Сюжет (v1.6): боссы и их логова, записки прошлой экспедиции, радиостанция, спасение и концовки."""
import math
import random

import pygame

from .config import TILE, LAIR_RADIUS, LAIR_LEASH, RESCUE_TIME, SCREEN_W, SCREEN_H
from .data import ANIMALS, LAIRS, NOTES, ENDINGS, RES_INFO, DIALOG
from .entities import Creature
from .util import direction
from .world import move_entity

PARTS = [("radio_tube", "bear"), ("radio_coil", "snake"), ("battery", "frost")]   # деталь -> чьё логово
STORY_DEFAULT = {"notes": [], "where": {}, "installed": [], "sos": False, "rescue_t": -1.0, "heli": False,
                 "endings": [], "heart": False, "intro": [], "radio_visited": False}


class StoryMixin:
    # ------------------------------------------------------------ состояние
    def new_story(self):
        self.story = {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in STORY_DEFAULT.items()}

    def fix_story(self):
        st = getattr(self, "story", None) or {}
        for k, v in STORY_DEFAULT.items():
            st.setdefault(k, v.copy() if isinstance(v, (list, dict)) else v)
        self.story = st

    def reset_story_ui(self):
        self.note_queue = []
        self.note_then = None
        self.ending_kind = None
        self.journal_tab = 0
        self.note_sel = None
        self.boss_check_t = 0.0
        self.wave_t = 30.0

    def lair_by_kind(self, kind):
        return next((l for l in self.world.lairs if l["kind"] == kind), None)

    def lair_center(self, lair):
        return (lair["center"][0] + 0.5) * TILE, (lair["center"][1] + 0.5) * TILE

    # ------------------------------------------------------------ боссы
    def ensure_bosses(self):
        """У каждого живого логова должен быть свой хозяин (старые сохранения, потерянные боссы)."""
        alive = {a.lair for a in self.animals if a.beh == "boss" and not a.dead}
        for i, lair in enumerate(self.world.lairs):
            if lair["alive"] and i not in alive:
                self.spawn_boss(i)

    def spawn_boss(self, i):
        lair = self.world.lairs[i]
        x, y = self.lair_center(lair)
        if lair["kind"] == "barrow":
            y += TILE * 1.6                                   # в центре кургана — Чёрное сердце
        a = Creature(lair["boss"], x, y)
        a.lair, a.home = i, [x, y]
        self.animals.append(a)
        return a

    def boss_intro(self, a):
        lair = self.world.lairs[a.lair] if 0 <= a.lair < len(self.world.lairs) else None
        name = ANIMALS[a.kind]["name"]
        if lair and lair["kind"] not in self.story["intro"]:
            self.story["intro"].append(lair["kind"])
            self.show_banner(name, LAIRS[lair["kind"]]["intro"])
        else:
            self.msg(f"{name} заметил тебя!", (255, 120, 100))
        self.sfx("howl" if a.kind == "frost_wolf" else "growl", a.x, a.y)

    def boss_summon(self, a, kind, n, text, color=(255, 140, 110)):
        for _ in range(n):
            m = self.spawn_animal(kind, around=(a.x, a.y))
            if m:
                m.aggro_t = 30
                m.life = 45.0
        self.msg(text, color)

    def boss_ai(self, a, dt):
        """Поведение босса: стережёт логово, замечает тебя рядом, у каждого — свой особый приём."""
        p = self.player
        w = self.world
        d = ANIMALS[a.kind]
        hx, hy = a.home
        dist = math.hypot(p.x - a.x, p.y - a.y)
        p_home = math.hypot(p.x - hx, p.y - hy)
        reachable = a.ghost or (not p.on_tower and not self.player_in_water())
        enraged = a.hp < a.max_hp * 0.4
        special = d.get("special")
        a.spec_cd -= dt
        if a.kind == "barrow_lord" and not self.story["heart"] and a.hurt < -2.8 and a.hp < a.max_hp:
            a.hp = min(a.max_hp, a.hp + 6 * dt)               # Чёрное сердце лечит Владыку
        if p_home < LAIR_RADIUS * TILE and not p.on_tower:
            if a.aggro_t <= 0:
                self.boss_intro(a)
            a.aggro_t = max(a.aggro_t, 3.0)
        leash = p_home > LAIR_LEASH * TILE
        if a.stun_t > 0:
            return
        speed, ang = 0.0, a.dir
        if a.aggro_t > 0 and not leash:
            a.chasing = True
            ang = math.atan2(p.y - a.y, p.x - a.x)
            speed = a.speed * (1.2 if enraged else 1.0)
            if special == "charge":                           # Хозяин чащи: разбег по прямой
                if a.spec_cd <= 0 and 2.5 * TILE < dist < 8 * TILE and reachable:
                    a.spec_cd = 5.0 if enraged else 7.0
                    a.lunge_t = 0.9
                    a.charge_ang = ang
                    self.msg(f"{d['name']} разбегается — отскочи в сторону!", (255, 160, 110))
                    self.sfx("growl", a.x, a.y)
                if a.lunge_t > 0:
                    ang, speed = a.charge_ang, a.speed * 3.0
            elif special == "spit":                           # Королева: плевки ядом веером
                if a.spec_cd <= 0 and dist < 9 * TILE and reachable:
                    a.spec_cd = 2.0 if enraged else 3.2
                    a.swing = 0.3
                    for k in ((-0.3, 0, 0.3) if enraged else (-0.2, 0.2)):
                        self.shoot(a.x, a.y, ang + k, {"dmg": 7, "speed": 430, "life": 1.4, "kind": "spit"}, "boss")
                if dist < 3 * TILE and not enraged:
                    speed *= 0.6
                if enraged and a.summoned < 1:
                    a.summoned = 1
                    self.boss_summon(a, "snake", 3, "Из трясины выползают змеёныши Королевы!", (180, 255, 120))
            elif special == "howl":                           # Ледяной Клык: рывки и вой стаи
                if (a.summoned < 1 and a.hp < a.max_hp * 0.7) or (a.summoned < 2 and a.hp < a.max_hp * 0.35):
                    a.summoned += 1
                    self.sfx("howl", a.x, a.y)
                    self.boss_summon(a, "wolf", 2 + a.summoned, "Ледяной Клык воет — на зов бежит стая!")
                if a.lunge_cd <= 0 and dist < 4 * TILE and reachable:
                    a.lunge_t, a.lunge_cd = 0.4, 2.2
                if a.lunge_t > 0:
                    speed *= 2.2
            elif special == "blink":                          # Владыка: исчезает и возникает за спиной
                if a.spec_cd <= 0 and dist < 12 * TILE:
                    a.spec_cd = 5.0 if enraged else 7.5
                    back = p.angle + math.pi
                    a.x, a.y = p.x + math.cos(back) * 2.5 * TILE, p.y + math.sin(back) * 2.5 * TILE
                    self.popup(a.x, a.y - 30, "Владыка за спиной!", (200, 150, 255))
                if (a.summoned < 1 and a.hp < a.max_hp * 0.66) or (a.summoned < 2 and a.hp < a.max_hp * 0.33):
                    a.summoned += 1
                    self.boss_summon(a, "shadow", 2, "Владыка призывает Теней!", (200, 150, 255))
                if p.light() and dist < 6 * TILE:
                    speed *= 0.5                              # свет сковывает
            if not reachable and dist < 3 * TILE:
                speed = 0
            if dist < a.r + p.r + 8:
                speed = 0
                if reachable and a.cd <= 0:
                    a.cd = 1.6 if a.kind == "bear_king" else 1.3
                    a.swing = 0.3
                    kind = {"bear_king": "claw", "barrow_lord": None}.get(a.kind, "bite")
                    self.hurt_player(random.randint(*a.dmg) * (1.15 if enraged else 1.0), d["cause"], kind)
                    if d.get("poison"):
                        p.poison = max(p.poison, d["poison"])
                        self.msg("Яд Королевы жжёт кровь! Нужен отвар или аптечка", (180, 255, 120))
                    if a.kind in ("frost_wolf", "barrow_lord"):
                        p.warmth = max(0, p.warmth - 14)
                    if a.kind == "bear_king":                 # удар лапой отбрасывает
                        move_entity(w, p, math.cos(ang) * 36, math.sin(ang) * 36, swim=True, doors=True)
        else:
            hd = math.hypot(hx - a.x, hy - a.y)
            if hd > TILE:
                ang, speed = math.atan2(hy - a.y, hx - a.x), d["walk"] * 1.6
            else:
                a.dir += dt * 0.3
            if a.aggro_t <= 0 and a.hp < a.max_hp:
                a.hp = min(a.max_hp, a.hp + a.max_hp * 0.03 * dt)       # отдыхает в логове
        if speed > 0:
            a.face = ang
            if a.walk(self, ang, speed, dt) and a.lunge_t > 0 and special == "charge":
                a.lunge_t = 0
                a.stun_t = 1.4
                self.shake = 0.25
                self.popup(a.x, a.y - 40, "Врезался!", (255, 230, 150))

    def on_boss_death(self, a):
        w = self.world
        p = self.player
        d = ANIMALS[a.kind]
        lair = w.lairs[a.lair] if 0 <= a.lair < len(w.lairs) else None
        self.kills += 1
        self.kill_counts[a.kind] = self.kill_counts.get(a.kind, 0) + 1
        gain = {"trophy": 1}
        for rid in ("meat", "hide", "fang", "essence"):
            if d.get(rid):
                gain[rid] = d[rid]
        text = f"{d['name']} больше не стережёт эти места."
        if lair:
            lair["alive"] = False
            spec = LAIRS[lair["kind"]]
            if spec["part"]:
                gain[spec["part"]] = 1
            chest = w.objects.get(tuple(lair["chest"]))
            if chest:
                chest["locked"] = False
            text = spec["death"]
        for k, v in gain.items():
            p.res[k] = p.res.get(k, 0) + v
        self.popup(a.x, a.y - 40, ", ".join(f"+{v} {RES_INFO[k][0]}" for k, v in gain.items()), (255, 220, 140))
        self.show_banner(f"{d['name']} повержен!", text)
        self.add_xp("combat", 60)
        self.sfx("levelup")
        for m in self.animals:                                # призванные слуги рассеиваются
            if m.life > 0:
                m.dead = True
        if w.lairs and not any(l["alive"] for l in w.lairs):
            for f in w.factions:
                if f["alive"] and f["type"] == "tribe":
                    self.change_rel(f, 15)
            self.msg("Все четыре Хозяина острова повержены! Племена будут петь о тебе песни.", (255, 230, 140))

    def heart_broken(self):
        """Чёрное сердце разбито: Тени уходят навсегда, культ в ярости."""
        st = self.story
        if st["heart"]:
            return
        st["heart"] = True
        for a in self.animals:
            if a.kind == "shadow":
                a.dead = True
                self.popup(a.x, a.y - 20, "Тень рассеялась", (190, 150, 255))
        for fi, f in enumerate(self.world.factions):
            if f["alive"] and f["type"] == "cult":
                self.change_rel(f, -40)
                f["anger"] = max(f["anger"], 90)
        lair = self.lair_by_kind("barrow")
        self.sfx("boom")
        if lair and lair["alive"]:
            self.show_banner("Чёрное сердце расколото!", "Тени больше не придут, а Владыка лишился силы — "
                             "раны у него теперь не затягиваются. Добей его!")
        self.log("Чёрное сердце разбито. Тени ушли.")

    # ------------------------------------------------------------ записки
    def note_text(self, nid):
        """Текст записки с направлениями от места, где она лежала, до нужных мест."""
        w = self.world
        text = NOTES[nid]["text"]
        where = self.story["where"].get(nid)
        if not where:
            where = [self.player.x / TILE, self.player.y / TILE]
        targets = {}
        if w.radio:
            targets["radio_dir"] = w.radio["center"]
        for lair in w.lairs:
            targets[f"lair_{lair['kind']}_dir"] = lair["center"]
        for key, (tx, ty) in targets.items():
            if "{" + key + "}" in text:
                text = text.replace("{" + key + "}", direction(tx - where[0], ty - where[1], DIALOG["directions"]))
        return text

    def read_notes(self, ids, pos, then=None):
        """Показать записки по очереди; then — что открыть после (например, сундук)."""
        ids = [n for n in ids if n in NOTES]
        if not ids:
            if then:
                then()
            return
        self.note_queue = list(ids)
        self.note_then = then
        self.menu = "note"
        self.sfx("pickup", vol=0.6)
        for nid in ids:
            if nid not in self.story["notes"]:
                self.story["notes"].append(nid)
                self.story["where"][nid] = [pos[0] + 0.5, pos[1] + 0.5]
                self.on_note_found(nid)

    def on_note_found(self, nid):
        w = self.world
        n = NOTES[nid]
        self.log(f"Найдена записка: «{n['title']}»")
        reveal = n.get("reveal")
        si = None
        if reveal == "radio" and w.radio:
            si = w.radio["struct"]
        elif reveal and reveal.startswith("lair:"):
            lair = self.lair_by_kind(reveal[5:])
            si = lair["struct"] if lair else None
        if si is not None and si not in w.seen:
            w.seen.add(si)
            self.map_timer = 0
            self.msg(f"На карте отмечено: {DIALOG['struct_names'][w.structs[si][0]]} (M — карта, J — журнал)",
                     (255, 230, 150))

    def close_note(self):
        if self.note_queue:
            self.note_queue.pop(0)
        if self.note_queue:
            return
        self.menu = None
        then, self.note_then = self.note_then, None
        if then:
            then()

    # ------------------------------------------------------------ радиостанция и спасение
    def radio_buttons(self):
        st = self.story
        p = self.player
        out = []
        y = SCREEN_H // 2 + 96
        if any(p.res.get(part, 0) > 0 and part not in st["installed"] for part, _ in PARTS):
            out.append(("install", "Установить детали"))
        if len(st["installed"]) == len(PARTS) and not st["sos"] and not st["heli"]:
            out.append(("sos", "Передать сигнал SOS"))
        out.append(("close", "Закрыть"))
        return [(act, label, pygame.Rect(SCREEN_W // 2 - 170, y + i * 50, 340, 42)) for i, (act, label) in enumerate(out)]

    def radio_action(self, act):
        st = self.story
        p = self.player
        if act == "install":
            for part, _ in PARTS:
                if p.res.get(part, 0) > 0 and part not in st["installed"]:
                    p.res[part] -= 1
                    st["installed"].append(part)
                    self.msg(f"Установлено в передатчик: {RES_INFO[part][0]}", (160, 230, 255))
            self.sfx("chime")
            if len(st["installed"]) == len(PARTS):
                self.msg("Передатчик собран! Можно подать сигнал SOS.", (140, 255, 140))
        elif act == "sos":
            st["sos"] = True
            st["rescue_t"] = RESCUE_TIME
            self.menu = None
            self.sfx("chime")
            self.show_banner("Сигнал SOS принят!", "База на материке ответила! Вертолёт прилетит через сутки и сядет "
                             "на площадку «H» у станции. Тени и звери почуяли сигнал — продержись!")
        else:
            self.menu = None

    def land_helicopter(self):
        w = self.world
        st = self.story
        st["rescue_t"] = -1.0
        st["heli"] = True
        if w.radio:
            pad = tuple(w.radio["pad"])
            w.objects[pad] = {"t": "heli"}
        self.map_timer = 0
        self.sfx("chime")
        self.show_banner("Вертолёт приземлился!", "Он ждёт на площадке у радиостанции. Подойди к нему и нажми E, "
                         "чтобы улететь домой.")

    def show_ending(self, kind):
        st = self.story
        if kind not in st["endings"]:
            st["endings"].append(kind)
        self.ending_kind = kind
        self.menu = "ending"
        self.banner = None
        self.log(f"Концовка: {ENDINGS[kind]['title']}")
        self.save_game(auto=True)

    def ending_buttons(self):
        if self.ending_kind == "rescue":
            items = [("leave", "Улететь домой (выйти в меню)"), ("stay", "Остаться на острове")]
        else:
            items = [("stay", "Продолжить игру")]
        return [(act, label, pygame.Rect(SCREEN_W // 2 - 190, 520 + i * 54, 380, 44)) for i, (act, label) in enumerate(items)]

    def ending_action(self, act):
        if act == "leave":
            self.save_game(auto=True)
            self.goto("menu")
            return
        if self.ending_kind == "rescue":                      # вертолёт улетает, вызвать можно снова
            st = self.story
            st["heli"], st["sos"] = False, False
            w = self.world
            if w.radio and w.objects.get(tuple(w.radio["pad"]), {}).get("t") == "heli":
                w.objects[tuple(w.radio["pad"])] = {"t": "pad", "i": 4}
            self.msg("Ты остался. Вертолёт улетел — рацией можно вызвать его снова.", (200, 230, 255))
        self.menu = None
        self.ending_kind = None

    # ------------------------------------------------------------ каждый кадр
    def update_story(self, dt):
        st = self.story
        p = self.player
        self.boss_check_t -= dt
        if self.boss_check_t <= 0:
            self.boss_check_t = 5.0
            self.ensure_bosses()
            r = self.world.radio
            if r and not st["radio_visited"] and \
                    math.hypot((r["center"][0] + 0.5) * TILE - p.x, (r["center"][1] + 0.5) * TILE - p.y) < 7 * TILE:
                st["radio_visited"] = True
                self.msg("Вот она, станция «Маяк-7»! Осмотри сундук и передатчик в домике.", (160, 225, 255))
        if st["rescue_t"] > 0:
            st["rescue_t"] -= dt
            self.wave_t -= dt
            if self.wave_t <= 0:                              # Тени и волки тянутся к сигналу
                self.wave_t = random.uniform(35, 55)
                kind = "shadow" if self.is_night() and not st["heart"] else "wolf"
                for _ in range(random.randint(2, 3)):
                    m = self.spawn_animal(kind, min_d=10, max_d=14)
                    if m:
                        m.aggro_t = 30
                self.msg("Сигнал рации манит хищников — они идут к тебе!", (255, 140, 110))
            if st["rescue_t"] <= 0:
                self.land_helicopter()
        lair = self.lair_by_kind("barrow")
        if st["heart"] and lair and not lair["alive"] and "keeper" not in st["endings"] and self.menu is None:
            self.show_ending("keeper")

    def objectives(self):
        """Список целей для журнала и строки «Цель» на экране: [(текст, выполнено)]."""
        st = self.story
        w = self.world
        p = self.player
        out = [("Осмотри останки неподалёку от места, где ты очнулся", "n_start" in st["notes"])]
        radio_known = bool(w.radio) and w.radio["struct"] in w.seen
        out.append(("Доберись до радиостанции «Маяк-7» (" + ("отмечена на карте — M" if radio_known else
                                                             "где она — узнай из записок") + ")",
                    st["radio_visited"] or bool(st["installed"])))
        for part, kind in PARTS:
            lair = self.lair_by_kind(kind)
            boss = ANIMALS[LAIRS[kind]["boss"]]["cause"]
            have = part in st["installed"] or p.res.get(part, 0) > 0
            hint = "логово на карте" if lair and lair["struct"] in w.seen else "где логово — ищи в записках"
            out.append((f"{RES_INFO[part][0]}: забери у {boss} ({hint})", have))
        out.append(("Установи три детали в передатчик на станции", len(st["installed"]) == len(PARTS)))
        out.append(("Подай сигнал SOS", st["sos"] or st["heli"] or "rescue" in st["endings"]))
        if st["rescue_t"] > 0:
            out.append((f"Продержись до прилёта вертолёта: ещё {int(st['rescue_t'])} с", False))
        if st["heli"]:
            out.append(("Вертолёт ждёт на площадке у станции — подойди и нажми E", False))
        lair = self.lair_by_kind("barrow")
        out.append(("Тайна Теней: одолей Курганного Владыку", bool(lair) and not lair["alive"]))
        out.append(("Тайна Теней: разбей Чёрное сердце в кургане", st["heart"]))
        return out

    def current_goal(self):
        for text, done in self.objectives():
            if not done:
                return text
        return None
