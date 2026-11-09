# -*- coding: utf-8 -*-
"""Игровая логика: выживание, крафт и изучение, стройка, фракции и дипломатия, поселение, события, сохранения."""
import math
import random

import pygame

from .config import (TILE, REACH, BUILD_REACH, DAY_LENGTH, GARDEN_TIME, SWIM_SLOW, CHEST_TOOLS, BAG_SIZES,
                     CRAFT_QUEUE, GRASS, WATER, SAND, FLOOR, DITCH, SNOW, SWAMP, STEPPE, ROCKY, LAND, DIFFICULTIES,
                     VERSION, DECK_H, SETTLE_RADIUS, CRASH_TIME, SEASON_DAYS, SEASONS, SKILLS, SKILL_MAX)
from .data import (RES_INFO, FOOD, HEALS, CURES, SPOIL, CONDITIONS, GIFT_VALUE, ITEMS, CRAFTS, CRAFT_BY_ID, BUILDS,
                   BUILD_BY_ID, ANIMALS, FACTION_TYPES, ROLES, DIALOG, EVENTS, BENCH_TIER, BLOCKING, BREAKABLE,
                   FLAMMABLE, SLEEP, INTERACTIVE, LOOT, TURRETS, HEARTS, PITS, DOORS, GATHER, STORAGE)
from .util import clamp, first_free, gen_name, direction
from .world import World, move_entity
from .entities import Player, Creature
from . import saves

PASSIVE_CAP = {"rabbit": 14, "deer": 8, "boar": 6, "bear": 4, "fox": 5, "moose": 4, "snake": 6, "dog": 2}
SEASON_CAP = {"winter": {"rabbit": 0.5, "deer": 0.5, "snake": 0, "bear": 0, "boar": 0.6},
              "summer": {"snake": 1.5, "rabbit": 1.2}, "autumn": {"deer": 1.3}, "spring": {}}
SAVE_FIELDS = ("time", "day", "clock_t", "kills", "kill_counts", "weather", "weather_t", "events", "event_timer",
               "bench_counts", "wolf_timer", "shadow_timer", "raid_timer", "member_timer", "craft_queue",
               "journal", "settings", "slot", "lightning_t", "flag", "spoil_acc", "story")
SEASON_TEXT = {
    "spring": "Пришла весна. Медведи проснулись голодными — они злее обычного. Снег тает, ягоды снова растут.",
    "summer": "Наступило лето. Жарко: пить хочется чаще. Больше змей. Еда портится быстрее.",
    "autumn": "Пришла осень. Холодные ночи, частые дожди. Запасайся едой — скоро зима: коптильня и погреб помогут.",
    "winter": "Наступила зима! Мороз даже днём, озёра замёрзли (по льду можно ходить), ягоды не растут, "
              "медведи спят, а голодные волки охотятся и днём. Держись у огня и одевайся теплее.",
}
DOG_NAMES = ["Шарик", "Дружок", "Рекс", "Найда", "Пират", "Туман", "Уголёк", "Буран"]
WOUND_CHANCE = {"bite": 0.35, "claw": 0.4, "blade": 0.35, "arrow": 0.45, "bolt": 0.5, "bullet": 0.6, "pellet": 0.25}
TURRET_SPEC = {"turret": {"dmg": 18, "speed": 800, "kind": "bolt", "cd": 1.3},
               "gun_turret": {"dmg": 14, "speed": 1200, "kind": "bullet", "cd": 0.35}}
TURRET_CAP = 40
JOBS = [("guard", "Охрана", {}), ("wood", "Дрова", {"wood": 6}),
        ("gather", "Собирательство", {"berries": 4, "fiber": 3, "mushroom": 1}),
        ("hunt", "Охота", {"meat": 3, "hide": 1}), ("fish", "Рыбалка", {"fish": 3}),
        ("mine", "Камень и руда", {"stone": 4, "ore": 1})]
JOB_BY_ID = {j[0]: j for j in JOBS}
LEADERS = ("chief", "boss", "priest")


class GameLogic:
    # ------------------------------------------------------------ новая игра
    def new_game(self, settings):
        self.settings = dict(settings)
        self.world = World(settings["seed"], settings["size"], settings["dens"], settings["facs"])
        c = self.world.w // 2 * TILE + TILE / 2
        self.player = Player(c, c)
        self.animals = []
        self.time = 0.3
        self.day = 1
        self.clock_t = 0.0
        self.kills = 0
        self.kill_counts = {}
        self.weather = "clear"
        self.weather_t = random.uniform(150, 260)
        self.events = {}
        self.event_timer = random.uniform(100, 180)
        self.bench_counts = {"1": 0, "2": 0, "3": 0}
        self.wolf_timer = 5.0
        self.shadow_timer = 10.0
        self.raid_timer = 30.0
        self.member_timer = 45.0
        self.lightning_t = 5.0
        self.craft_queue = []
        self.journal = []
        self.flag = None
        self.spoil_acc = {}
        self.new_story()
        self.slot = saves.make_slot_id(settings["name"])
        self.reset_transient()
        k = (self.world.w / 160) ** 2
        for kind, n in PASSIVE_CAP.items():
            for _ in range(int(n * k) + 1):
                self.spawn_animal(kind, min_d=10)
        for fi, f in enumerate(self.world.factions):
            for role in FACTION_TYPES[f["type"]]["roles"]:
                self.spawn_member(fi, role)
        self.ensure_bosses()
        self.log(f"Ты очнулся на острове «{settings['name']}» (зерно мира {settings['seed']}).")
        self.msg("Ты очнулся посреди леса. На острове живут племена, бандиты, торговцы и культ...", (255, 230, 140))
        self.msg("Неподалёку белеют чьи-то кости. Осмотри их: наведи мышь и нажми E", (255, 230, 140))
        self.menu = "help"

    def reset_transient(self):
        self.projectiles = []
        self.popups = []
        self.messages = []
        self.explosions = []
        self.menu = None
        self.open_chest = None
        self.open_deck = False
        self.dialog = None
        self.drag = None
        self.build_mode = False
        self.build_cat = "base"
        self.build_sel = "fire"
        self.demolish = False
        self.build_cd = 0.0
        self.craft_tab = 0
        self.dead = False
        self.show_map = False
        self.map_surf = None
        self.map_timer = 0.0
        self.seen_timer = 0.0
        self.passive_timer = 0.0
        self.shake = 0.0
        self.flash_t = 0.0
        self.hint = ""
        self.hover = None
        self.banner = None
        self.post_lights = []
        self.fire_lights = []
        self.blood = []
        self.breath = []
        self.spoil_timer = 5.0
        self.cough_t = 6.0
        self.was_in_water = False
        self.rain_drops = [(random.uniform(0, 1280), random.uniform(0, 720)) for _ in range(220)]
        self.cam_x = self.cam_y = 0
        diff = DIFFICULTIES[self.settings["diff"]]
        self.dmg_mult, self.needs_mult = diff[1], diff[2]
        self.reset_story_ui()
        self.rebuild_turrets()

    def rebuild_turrets(self):
        self.turret_pos = set()
        w = getattr(self, "world", None)
        if not w:
            return
        for pos, o in w.objects.items():
            if o["t"] in TURRETS:
                self.turret_pos.add((pos[0], pos[1], False))
        for pos, o in w.deck.items():
            if o["t"] in TURRETS:
                self.turret_pos.add((pos[0], pos[1], True))

    # ------------------------------------------------------------ сообщения
    def msg(self, text, color=(235, 235, 235)):
        if any(m[0] == text and m[2] > 3 for m in self.messages):
            return
        self.messages.append([text, color, 5.0])
        self.messages = self.messages[-6:]

    def popup(self, x, y, text, color=(255, 255, 255)):
        self.popups.append([x, y, text, color, 1.3])

    def log(self, text):
        self.journal.append(f"День {self.day}: {text}")
        self.journal = self.journal[-40:]

    def show_banner(self, title, text):
        self.banner = [title, text, 8.0]
        self.log(title + ". " + text)

    def sfx(self, name, x=None, y=None, vol=1.0):
        """Звук; если указана точка — тише с расстоянием."""
        snd = getattr(self, "sound", None)
        if not snd:
            return
        if x is not None:
            d = math.hypot(x - self.player.x, y - self.player.y)
            vol *= max(0.0, 1 - d / (18 * TILE))
        snd.play(name, vol)

    # ------------------------------------------------------------ времена года
    def season(self):
        return SEASONS[((self.day - 1) // SEASON_DAYS) % 4][0]

    def season_name(self):
        return SEASONS[((self.day - 1) // SEASON_DAYS) % 4][1]

    def season_day(self):
        return (self.day - 1) % SEASON_DAYS + 1

    def check_season_change(self):
        if self.day > 1 and (self.day - 1) % SEASON_DAYS == 0:
            s = self.season()
            self.show_banner(self.season_name(), SEASON_TEXT[s])
            if s != "winter":
                self.events.pop("blizzard", None)

    # ------------------------------------------------------------ навыки
    def skill_lvl(self, sid):
        return min(SKILL_MAX, int(math.sqrt(self.player.skills.get(sid, 0) / 20)))

    def add_xp(self, sid, amount):
        p = self.player
        before = self.skill_lvl(sid)
        p.skills[sid] = p.skills.get(sid, 0) + amount
        after = self.skill_lvl(sid)
        if after > before:
            name = dict(SKILLS)[sid]
            self.msg(f"Навык «{name}» вырос до {after}!", (160, 220, 255))
            self.popup(p.x, p.y - 44, f"{name} {after}", (160, 220, 255))
            self.sfx("levelup")

    # ------------------------------------------------------------ состояние мира
    def darkness(self):
        t = self.time
        if 0.3 <= t <= 0.7:
            return 0.0
        if 0.7 < t < 0.8:
            return (t - 0.7) / 0.1
        if t >= 0.8 or t < 0.2:
            return 1.0
        return 1.0 - (t - 0.2) / 0.1

    def is_night(self):
        return self.darkness() > 0.5

    def raining(self):
        return self.weather in ("rain", "storm")

    def player_in_water(self):
        p = self.player
        return p.on_tower is None and not self.world.frozen and self.world.ground_at(p.x, p.y) == WATER

    def sheltered(self):
        p = self.player
        w = self.world
        if w.roof_at(int(p.x // TILE), int(p.y // TILE)) >= 0 or w.ground_at(p.x, p.y) == FLOOR:
            return True
        return w.find_near(p.x, p.y, ("tent", "tent_old"), 1.3 * TILE) is not None

    def near_fire(self, radius=2.5 * TILE):
        return self.world.nearest_fire(self.player.x, self.player.y, radius) is not None

    def near_obj(self, types, radius=2.5 * TILE):
        return self.world.find_near(self.player.x, self.player.y, types, radius) is not None

    def bench_tier_near(self):
        p = self.player
        best = 0
        pos = self.world.find_near(p.x, p.y, set(BENCH_TIER), 2.5 * TILE)
        if pos:
            tx0, ty0 = pos
            for (tx, ty) in ((tx0 + dx, ty0 + dy) for dx in range(-3, 4) for dy in range(-3, 4)):
                o = self.world.objects.get((tx, ty))
                if o and o["t"] in BENCH_TIER and math.hypot(tx * TILE + 20 - p.x, ty * TILE + 20 - p.y) < 2.5 * TILE:
                    best = max(best, BENCH_TIER[o["t"]])
        return best

    def bench_tier_built(self):
        return max([int(k) for k, v in self.bench_counts.items() if v > 0] or [0])

    def hurt_player(self, amount, cause, kind=None):
        """Урон по игроку; от укусов, когтей, клинков и пуль бывают кровотечения и переломы."""
        p = self.player
        amount *= self.dmg_mult * (1.0, 0.85, 0.65)[p.armor]
        p.damage(amount, cause)
        p.hurt = 0.3
        self.shake = 0.22
        self.sfx("hurt", vol=0.7)
        armor_k = (1.0, 0.7, 0.45)[p.armor]
        if kind in WOUND_CHANCE and random.random() < WOUND_CHANCE[kind] * armor_k:
            if p.cond.get("bleed", 0) <= 0:
                self.msg("Ты ранен и истекаешь кровью! Перевяжись бинтом [H]", (255, 110, 100))
            p.cond["bleed"] = min(120, p.cond.get("bleed", 0) + 35)
        if kind in ("claw", "blunt", "bite") and amount >= 14 and random.random() < 0.2 * armor_k:
            if p.cond.get("fracture", 0) <= 0:
                self.msg("Хруст... Перелом! Ты хромаешь. Нужна шина (2 дерева + верёвка)", (255, 200, 140))
            p.cond["fracture"] = 240
        if kind == "fire" and random.random() < 0.5:
            p.cond["burn"] = max(p.cond.get("burn", 0), 120)

    def is_threat(self, a):
        if a.dead or a.ally or a.fleeing:
            return False
        return self.fac_hostile(a.faction) if a.human else a.hostile()

    # ------------------------------------------------------------ существа
    def spawn_animal(self, kind, min_d=12, max_d=None, around=None):
        p = self.player
        w = self.world
        biomes = ANIMALS[kind]["biome_ids"] | ({WATER} if w.frozen and kind in ("wolf", "alpha") else set())
        for _ in range(80):
            if around:
                x, y = around[0] + random.uniform(-60, 60), around[1] + random.uniform(-60, 60)
            elif max_d:
                a = random.uniform(0, math.tau)
                d = random.uniform(min_d, max_d) * TILE
                x, y = p.x + math.cos(a) * d, p.y + math.sin(a) * d
            else:
                x, y = random.uniform(0, w.w * TILE), random.uniform(0, w.h * TILE)
            tx, ty = int(x // TILE), int(y // TILE)
            if not w.in_bounds(tx, ty):
                continue
            if kind != "shadow":
                g = w.ground[ty][tx]
                if (g not in biomes and not (max_d and g in LAND)) or w.circle_blocked(x, y, ANIMALS[kind]["r"]):
                    continue
            if not around and math.hypot(x - p.x, y - p.y) < min_d * TILE:
                continue
            a = Creature(kind, x, y, self.day - 1)
            if kind == "wolf" and w.ground[ty][tx] == SNOW:
                a.color = [218, 218, 226]                       # белые волки в тайге
            self.animals.append(a)
            return a
        return None

    def spawn_member(self, fi, role=None, near=None, raid=False, spread=3):
        f = self.world.factions[fi]
        hx, hy = (f["center"][0] + 0.5) * TILE, (f["center"][1] + 0.5) * TILE
        cx, cy = near or (hx, hy)
        roles = FACTION_TYPES[f["type"]]["roles"]
        role = role or random.choice(roles[1:] or roles)
        for _ in range(60):
            x, y = cx + random.uniform(-spread, spread) * TILE, cy + random.uniform(-spread, spread) * TILE
            if self.world.ground_at(x, y) != WATER and not self.world.circle_blocked(x, y, 13, doors=True):
                a = Creature("human", x, y)
                a.setup_role(role)
                a.faction, a.name, a.home, a.raid = fi, gen_name(DIALOG["syllables"]), [hx, hy], raid
                self.animals.append(a)
                return a
        return None

    # ------------------------------------------------------------ фракции
    def attitude(self, f):
        if f["rel"] >= 60:
            return "friend"
        if self.day <= f["truce"]:
            return "truce"
        if f["rel"] <= -20:
            return "hostile"
        return "neutral"

    def fac_hostile(self, fi):
        if fi < 0:
            return False
        f = self.world.factions[fi]
        return self.attitude(f) == "hostile" or f["anger"] > 0

    def fac_cause(self, fi):
        return FACTION_TYPES[self.world.factions[fi]["type"]]["cause"] if fi >= 0 else "людей"

    def ally_count(self):
        return sum(1 for a in self.animals if a.ally)

    def followers_count(self):
        return sum(1 for a in self.animals if a.ally and not a.settler and a.human)

    def change_rel(self, f, delta):
        was = self.attitude(f)
        f["rel"] = int(clamp(f["rel"] + delta, -100, 100))
        now = self.attitude(f)
        if now != was:
            text = {"friend": f"Ты стал другом: {f['name']}!",
                    "hostile": f"{f['name']} объявляет тебе войну!",
                    "neutral": f"{f['name']} больше не считает тебя врагом",
                    "truce": f"{f['name']}: перемирие"}[now]
            self.msg(text, (140, 255, 140) if now in ("friend", "truce") else (255, 120, 110))
            self.log(text)

    def provoke(self, fi, delta=-40, anger=90, witness=True):
        """Игрок напал на фракцию или её имущество."""
        f = self.world.factions[fi]
        if not f["alive"]:
            return
        if witness:
            p = self.player
            seen = any(a.faction == fi and not a.ally and math.hypot(a.x - p.x, a.y - p.y) < 14 * TILE
                       for a in self.animals)
            if not seen:
                return
        if f["anger"] <= 0:
            f["truce"] = 0
            self.change_rel(f, delta)
            if self.attitude(f) != "hostile":
                self.msg(f"{f['name']}: ты напал на нас! Они в ярости.", (255, 120, 110))
        f["anger"] = max(f["anger"], anger)

    def declare_war(self, a, b):
        fa, fb = self.world.factions[a], self.world.factions[b]
        if b not in fa["wars"]:
            fa["wars"].append(b)
        if a not in fb["wars"]:
            fb["wars"].append(a)
        fa["war_day"] = fb["war_day"] = self.day
        self.log(f"{fa['name']} и {fb['name']} начали войну")

    def is_enemy(self, me, other):
        if other.dead or other is me:
            return False
        if me.ally:
            if other.ally:
                return False
            return self.fac_hostile(other.faction) if other.human else other.hostile()
        if other.human:
            if other.ally:
                return self.fac_hostile(me.faction)
            return other.faction in self.world.factions[me.faction]["wars"]
        return other.hostile()

    def nearest_enemy(self, x, y, radius, me):
        best, bd = None, radius
        for a in self.animals:
            if abs(a.x - x) > radius or abs(a.y - y) > radius:
                continue
            if not self.is_enemy(me, a):
                continue
            d = math.hypot(a.x - x, a.y - y)
            if d < bd:
                best, bd = a, d
        return best

    def update_factions(self, dt):
        p = self.player
        w = self.world
        for fi, f in enumerate(w.factions):
            if not f["alive"]:
                continue
            f["anger"] = max(0.0, f["anger"] - dt)
            t = FACTION_TYPES[f["type"]]
            cx, cy = (f["center"][0] + 0.5) * TILE, (f["center"][1] + 0.5) * TILE
            inside = math.hypot(p.x - cx, p.y - cy) < f["radius"] * TILE and not p.on_tower
            if inside and t["intrude"] and self.attitude(f) == "neutral" and f["anger"] <= 0:
                if f["intrude"] <= 0:
                    who = next((a for a in self.animals if a.faction == fi and not a.ally), None)
                    name = f"{ROLES[who.role]['name']} {who.name}" if who else "Голос"
                    self.msg(f"{name}: " + DIALOG["warn"][f["type"]].format(name=f["name"]), (255, 200, 120))
                f["intrude"] += dt
                if f["intrude"] > t["intrude"]:
                    f["intrude"] = 0
                    f["anger"] = 25
                    self.change_rel(f, -5)
                    self.msg(f"{f['name']} прогоняет тебя силой!", (255, 120, 110))
            else:
                f["intrude"] = max(0.0, f["intrude"] - dt * 2)
        self.member_timer -= dt
        if self.member_timer <= 0:
            self.member_timer = 45
            for fi, f in enumerate(w.factions):
                if not f["alive"] or f["type"] == "survivors":
                    continue
                members = [a for a in self.animals if a.faction == fi and not a.raid and not a.ally and a.war_target < 0]
                huts = [r for r in w.roofs if r["fac"] == fi]
                if huts and all(r["ruined"] for r in huts):
                    if not members:
                        f["alive"] = False
                        self.show_banner("Фракция исчезла", f"{f['name']} покидает остров — их дома разрушены.")
                    continue
                if len(members) < len(FACTION_TYPES[f["type"]]["roles"]):
                    self.spawn_member(fi)

    def war_parties(self):
        """На рассвете враждующие фракции отправляют отряды друг на друга."""
        w = self.world
        for fi, f in enumerate(w.factions):
            if not f["alive"]:
                continue
            for ti in f["wars"]:
                if w.factions[ti]["alive"] and random.random() < 0.7:
                    for _ in range(random.randint(2, 3)):
                        a = self.spawn_member(fi)
                        if a:
                            a.war_target = ti
            f["wars"] = [ti for ti in f["wars"] if w.factions[ti]["alive"]]

    # уничтожение лагерей
    def heart_destroyed(self, fi, kind):
        f = self.world.factions[fi]
        if not f["alive"]:
            return
        f["heart_broken"] = True
        name = {"totem": "Тотем", "camp_banner": "Знамя", "altar": "Алтарь"}.get(kind, "Святыня")
        self.msg(f"{name} ({f['name']}) уничтожен!", (255, 170, 90))
        self.provoke(fi, delta=-30, anger=120, witness=False)
        self.check_camp(fi)

    def check_camp(self, fi):
        w = self.world
        f = w.factions[fi]
        if not f["alive"]:
            return
        huts = [r for r in w.roofs if r["fac"] == fi]
        need = math.ceil(len(huts) * 0.6)
        ruined = sum(1 for r in huts if r["ruined"])
        if f.get("heart_broken") and ruined >= need:
            self.disband(fi)
        elif f.get("heart_broken"):
            self.msg(f"Чтобы прогнать {f['name']}, разрушь ещё хижины: {ruined}/{need}", (255, 200, 140))

    def disband(self, fi):
        w = self.world
        f = w.factions[fi]
        f["alive"] = False
        for a in self.animals:
            if a.faction == fi and not a.ally:
                a.fleeing, a.raid, a.war_target = True, False, -1
        for other in w.factions:
            if fi in other["wars"]:
                other["wars"].remove(fi)
                if other["alive"]:
                    self.change_rel(other, 15)
        self.show_banner("Лагерь уничтожен", f"{f['name']} в страхе бегут с острова. Их сундуки теперь твои.")

    # ------------------------------------------------------------ поселение
    def settlers(self):
        return [a for a in self.animals if a.settler and a.ally and not a.dead]

    def settle_capacity(self):
        if not self.flag:
            return 0
        w = self.world
        fx, fy = self.flag
        n = 1
        for ty in range(fy - SETTLE_RADIUS, fy + SETTLE_RADIUS + 1):
            for tx in range(fx - SETTLE_RADIUS, fx + SETTLE_RADIUS + 1):
                o = w.objects.get((tx, ty))
                if o and o["t"] in SLEEP and o.get("own"):
                    n += 1
        return n

    def make_settler(self, a):
        a.ally, a.settler, a.stay = True, True, True
        a.ally_until, a.raid, a.war_target, a.visitor_t, a.fleeing = 0, False, -1, 0.0, False
        a.job = "guard"
        if self.flag:
            a.home = [(self.flag[0] + 0.5) * TILE, (self.flag[1] + 0.5) * TILE]

    def settlement_produce(self):
        if not self.flag:
            return
        o = self.world.objects.get(tuple(self.flag))
        if not o:
            return
        got = {}
        for a in self.settlers():
            for k, v in JOB_BY_ID.get(a.job, JOBS[0])[2].items():
                o["res"][k] = o["res"].get(k, 0) + v
                got[k] = got.get(k, 0) + v
        if got:
            text = ", ".join(f"{v} {RES_INFO[k][0]}" for k, v in got.items())
            self.msg(f"Жители принесли на склад поселения: {text}", (180, 255, 180))

    def cycle_job(self, a):
        ids = [j[0] for j in JOBS]
        a.job = ids[(ids.index(a.job) + 1) % len(ids)] if a.job in ids else ids[0]

    # ------------------------------------------------------------ предметы
    @staticmethod
    def fits(slot, item_id):
        rule = (None, "small", "large")[slot]
        return rule is None or rule == ITEMS[item_id]["size"]

    def free_slot_for(self, item_id):
        p = self.player
        for i in [p.sel] + [i for i in (1, 2, 0) if i != p.sel]:
            if p.slots[i] is None and self.fits(i, item_id):
                return i
        return None

    def give_tool(self, item, quiet=False):
        """Положить инструмент в подходящий слот или в рюкзак. False — некуда."""
        p = self.player
        i = self.free_slot_for(item["id"])
        if i is not None:
            p.slots[i] = item
            where = ("руки", "пояс", "спину")[i]
        elif first_free(p.backpack) >= 0:
            p.backpack[first_free(p.backpack)] = item
            where = "рюкзак"
        else:
            if not quiet:
                self.msg("Некуда положить: рюкзак полон", (255, 160, 120))
            return False
        if not quiet:
            self.msg(f"{ITEMS[item['id']]['name']} → {where}", (180, 230, 255))
        return True

    def give_reward(self, reward):
        if reward[0] == "tool":
            item = {"id": reward[1], "dur": ITEMS[reward[1]]["dur"]}
            if not self.give_tool(item, quiet=True):
                self.drop_at(self.player.x, self.player.y, [item], {})
            return ITEMS[reward[1]]["name"]
        self.player.res[reward[1]] += reward[2]
        return f"{reward[2]} {RES_INFO[reward[1]][0]}"

    def wear_held(self, amount=1):
        p = self.player
        it = p.held()
        if not it:
            return
        it["dur"] -= amount
        if it["dur"] <= 0:
            self.msg(f"{ITEMS[it['id']]['name']} сломался!", (255, 140, 120))
            p.slots[p.sel] = None

    def stow_held(self):
        p = self.player
        it = p.held()
        if not it:
            return
        i = first_free(p.backpack)
        if i < 0:
            self.msg("Рюкзак полон", (255, 160, 120))
            return
        p.backpack[i] = it
        p.slots[p.sel] = None
        self.msg(f"{ITEMS[it['id']]['name']} убран в рюкзак")

    def shift_held(self):
        """Перевесить предмет: из рук на пояс/спину и обратно."""
        p = self.player
        it = p.held()
        if not it:
            return
        target = (1 if ITEMS[it["id"]]["size"] == "small" else 2) if p.sel == 0 else 0
        if self.move_slots(("hot", p.sel), ("hot", target)):
            self.msg(f"{ITEMS[it['id']]['name']} → {('руки', 'пояс', 'спину')[target]}")
            p.sel = target

    def drop_held(self):
        p = self.player
        it = p.held()
        if it:
            p.slots[p.sel] = None
            self.drop_at(p.x, p.y, [it], {})
            self.msg(f"{ITEMS[it['id']]['name']} выброшен на землю (подобрать — E)")

    def equip_from_backpack(self, idx):
        p = self.player
        it = p.backpack[idx]
        if it is None:
            return
        if self.fits(p.sel, it["id"]):
            p.backpack[idx], p.slots[p.sel] = p.slots[p.sel], it
            return
        i = self.free_slot_for(it["id"])
        if i is not None:
            p.slots[i], p.backpack[idx] = it, None
        else:
            self.msg("Этот предмет не помещается в выбранный слот", (255, 170, 120))

    def drop_at(self, x, y, items, res):
        w = self.world
        tx0, ty0 = int(x // TILE), int(y // TILE)
        items = [i for i in items if i]
        if not items and not any(res.values()):
            return
        for r in range(0, 4):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    pos = (tx0 + dx, ty0 + dy)
                    o = w.objects.get(pos)
                    if (o and o["t"] == "drop") or w.free_tile(*pos):
                        if not o:
                            o = w.objects[pos] = {"t": "drop", "items": [], "res": {}}
                        o["items"].extend(items)
                        for k, v in res.items():
                            if v:
                                o["res"][k] = o["res"].get(k, 0) + v
                        return

    def set_bag(self, level):
        p = self.player
        p.bag = max(p.bag, level)
        p.backpack += [None] * (BAG_SIZES[p.bag] - len(p.backpack))

    # слоты для перетаскивания: ("hot", i), ("bp", i), ("chest", i)
    def chest_obj(self):
        store = self.world.deck if self.open_deck else self.world.objects
        o = store.get(self.open_chest) if self.open_chest else None
        return o if o and o["t"] in STORAGE else None

    def slot_get(self, ref):
        kind, i = ref
        if kind == "hot":
            return self.player.slots[i]
        if kind == "bp":
            return self.player.backpack[i] if i < len(self.player.backpack) else None
        c = self.chest_obj()
        return c["tools"][i] if c else None

    def slot_set(self, ref, item):
        kind, i = ref
        if kind == "hot":
            self.player.slots[i] = item
        elif kind == "bp":
            self.player.backpack[i] = item
        else:
            self.chest_obj()["tools"][i] = item

    def slot_accepts(self, ref, item):
        return item is None or ref[0] != "hot" or self.fits(ref[1], item["id"])

    def move_slots(self, src, dst):
        a, b = self.slot_get(src), self.slot_get(dst)
        if not self.slot_accepts(dst, a) or not self.slot_accepts(src, b):
            self.msg("Пояс — только малые предметы, спина — только большие", (255, 170, 120))
            return False
        self.slot_set(dst, a)
        self.slot_set(src, b)
        return True

    def active_conditions(self):
        p = self.player
        out = [k for k, v in p.cond.items() if v > 0]
        if p.poison > 0:
            out.append("poison")
        return out

    def cure(self, name):
        p = self.player
        if name == "poison":
            had, p.poison = p.poison > 0, 0
        else:
            had = p.cond.get(name, 0) > 0
            p.cond.pop(name, None)
            if name == "bleed":
                p.dirty = 0
        if had:
            self.msg(f"{CONDITIONS[name][0]}: вылечено", (160, 255, 160))
        return had

    def use_resource(self, rid):
        p = self.player
        if p.res.get(rid, 0) <= 0:
            return False
        cures = CURES.get(rid, set()) & set(self.active_conditions())
        if rid in FOOD:
            hun, thi, hp, warm = FOOD[rid]
            p.res[rid] -= 1
            p.hunger = min(100, p.hunger + hun)
            p.thirst = min(100, p.thirst + thi)
            p.hp = min(100, p.hp + hp)
            p.warmth = min(100, p.warmth + warm)
            self.popup(p.x, p.y - 30, f"+{hun} сытость" if hun else f"+{thi} вода", (255, 210, 120))
            self.sfx("eat", vol=0.6)
        elif rid == "meat":
            p.res[rid] -= 1
            p.hunger = min(100, p.hunger + 15)
            self.sfx("eat", vol=0.6)
            if random.random() < 0.4:
                p.damage(10, "отравления")
                p.hurt = 0.3
                p.cond["dysentery"] = max(p.cond.get("dysentery", 0), 90)
                self.msg("Сырое мясо... живот скрутило (−10 HP, дизентерия). Лучше пожарить на костре!", (255, 140, 120))
        elif rid in HEALS or rid in CURES:
            if p.hp >= 100 and not cures:
                self.msg("Тебе это сейчас не нужно")
                return False
            p.res[rid] -= 1
            heal = HEALS.get(rid, 0) * (1 + 0.08 * self.skill_lvl("medicine"))
            if heal:
                p.hp = min(100, p.hp + heal)
                self.popup(p.x, p.y - 30, f"+{int(heal)} HP", (140, 255, 140))
            self.add_xp("medicine", 5)
        else:
            return False
        for c in cures:
            self.cure(c)
        return True

    def eat(self):
        for rid in ("stew", "smoked_meat", "cooked", "dried_fish", "cooked_fish", "canned", "mushroom", "berries", "meat"):
            if self.player.res[rid] > 0:
                self.use_resource(rid)
                return
        self.msg("Нечего есть. Собирай ягоды и грибы, охоться, рыбачь или обыщи сундуки.", (255, 170, 120))

    def heal(self):
        """H: подобрать лекарство под самую опасную болячку, иначе — просто подлечиться."""
        p = self.player
        active = self.active_conditions()
        for cond in ("bleed", "infection", "poison", "fracture", "burn", "cold", "dysentery", "frostbite"):
            if cond in active:
                for rid in ("bandage", "splint", "herbal", "salve", "medkit"):
                    if cond in CURES.get(rid, ()) and p.res[rid] > 0:
                        self.use_resource(rid)
                        return
        order = ("bandage", "medkit") if p.hp > 50 else ("medkit", "bandage")
        for rid in order:
            if p.res[rid] > 0 and p.hp < 100:
                self.use_resource(rid)
                return
        if active:
            names = ", ".join(f"{CONDITIONS[c][0]} — {CONDITIONS[c][2]}" for c in active)
            self.msg(f"Нет подходящего лекарства. {names}", (255, 170, 120))
        else:
            self.msg("Нет бинтов и аптечек. Бинт делается из волокна [C]")

    def update_conditions(self, dt):
        """Раны и болезни: кровотечение, заражение, перелом, ожог, простуда, дизентерия, обморожение."""
        p = self.player
        c = p.cond
        if c.get("bleed", 0) > 0:
            p.damage(0.5 * dt * (1 + c["bleed"] / 60), "кровопотери")
            p.dirty += dt
            if random.random() < dt * 2:
                self.blood.append([p.x + random.uniform(-8, 8), p.y + random.uniform(4, 12), 30.0])
            if p.dirty > 30 and c.get("infection", 0) <= 0:
                p.dirty = 0
                if random.random() < 0.5:
                    c["infection"] = 400
                    self.msg("Рана загноилась — заражение! Нужна аптечка или мазь", (200, 210, 80))
        if c.get("infection", 0) > 0:
            p.damage(0.25 * dt, "заражения")
        if c.get("cold", 0) > 0:
            self.cough_t -= dt
            if self.cough_t <= 0:
                self.cough_t = random.uniform(6, 14)
                self.popup(p.x, p.y - 30, "Кхе-кхе!", (200, 220, 255))
                self.sfx("cough", vol=0.5)
        # простуда — от долгого холода и сырости
        if p.warmth < 25 or (p.wet > 60 and self.is_night()):
            p.chill += dt
            if p.chill > 45 and c.get("cold", 0) <= 0:
                p.chill = 0
                if random.random() < 0.6:
                    c["cold"] = 300
                    self.msg("Ты простудился: меньше сил, мёрзнешь сильнее. Помогут отвар и сон в кровати", (150, 200, 255))
        elif p.warmth > 55:
            p.chill = max(0.0, p.chill - dt)
        # обморожение — если тепло упало до нуля
        if p.warmth <= 0:
            p.frost_t += dt
            if p.frost_t > 15 and c.get("frostbite", 0) <= 0:
                c["frostbite"] = 240
                self.msg("Пальцы онемели — обморожение! Руки работают медленнее. Мазь или тепло помогут",
                         (180, 220, 255))
        else:
            p.frost_t = 0
            if p.warmth > 80 and c.get("frostbite", 0) > 0 and self.near_fire(3.5 * TILE):
                c["frostbite"] -= dt * 3                        # у огня отходит быстрее
        for k in list(c):
            if k == "bleed":
                c[k] -= dt * 0.6                                # кровь потихоньку сворачивается
            else:
                c[k] -= dt
            if c[k] <= 0:
                del c[k]
                if k != "bleed":
                    self.msg(f"{CONDITIONS[k][0]} прошло само", (180, 230, 180))

    # ------------------------------------------------------------ порча еды
    def spoil_store(self, res, k, key):
        lost = 0
        for rid, rate in SPOIL.items():
            n = res.get(rid, 0)
            if n <= 0:
                continue
            acc_key = f"{key}:{rid}"
            self.spoil_acc[acc_key] = self.spoil_acc.get(acc_key, 0.0) + n * rate * k
            whole = int(self.spoil_acc[acc_key])
            if whole > 0:
                whole = min(whole, n)
                self.spoil_acc[acc_key] -= whole
                res[rid] = n - whole
                res["rot"] = res.get("rot", 0) + whole
                lost += whole
        return lost

    def update_spoil(self, dt):
        self.spoil_timer -= dt
        if self.spoil_timer > 0:
            return
        period = 10.0
        self.spoil_timer = period
        season_k = {"winter": 0.3, "summer": 1.3, "autumn": 0.9, "spring": 1.0}[self.season()]
        k = period / 60 * season_k
        lost = self.spoil_store(self.player.res, k, "p")
        if lost:
            self.msg(f"Часть еды испортилась (+{lost} гнили). Храни еду в погребе или копти её", (190, 200, 120))
        for pos, o in self.world.objects.items():
            if o["t"] in ("chest", "flag") and o.get("own"):
                self.spoil_store(o["res"], k * 0.7, f"{pos[0]},{pos[1]}")

    # ------------------------------------------------------------ крафт и изучение
    def recipe_state(self, rec):
        """Возвращает (можно ли сейчас, причина)."""
        p = self.player
        if rec["id"] not in p.known:
            return False, "не изучено"
        if rec.get("station") == "fire" and not self.near_fire():
            return False, "нужен костёр рядом"
        if rec.get("station") == "furnace" and not self.near_obj(("furnace",)):
            return False, "нужна печь рядом"
        if rec.get("station") == "smokehouse" and not self.near_obj(("smokehouse",)):
            return False, "нужна коптильня рядом"
        if rec["tier"] > 0 and self.bench_tier_near() < rec["tier"]:
            return False, f"нужен верстак {'I' * rec['tier']} рядом"
        if any(p.res[k] < v for k, v in rec["cost"].items()):
            return False, "не хватает ресурсов"
        return True, ""

    def craft_click(self, rec):
        p = self.player
        if rec["id"] not in p.known:
            self.research(rec)
            return
        ok, why = self.recipe_state(rec)
        if not ok:
            self.msg(f"«{rec['name']}»: {why}", (255, 170, 120))
            return
        if len(self.craft_queue) >= CRAFT_QUEUE:
            self.msg("Очередь крафта заполнена", (255, 170, 120))
            return
        if rec["kind"] == "cloak" and (p.cloak or any(q["id"] == "cloak" for q in self.craft_queue)):
            self.msg("Накидка уже есть")
            return
        if rec["kind"] == "bag" and p.bag >= rec["bag"]:
            self.msg("У тебя уже есть сумка не хуже")
            return
        if rec["kind"] == "armor" and p.armor >= rec["armor"]:
            self.msg("У тебя уже есть броня не хуже")
            return
        for k, v in rec["cost"].items():
            p.res[k] -= v
        t = rec["time"] * (1 - 0.05 * self.skill_lvl("craft"))      # ремесло ускоряет крафт
        self.craft_queue.append({"id": rec["id"], "t": t, "total": t})

    def research(self, rec):
        p = self.player
        tier = max(1, rec["tier"])
        if self.bench_tier_near() < tier:
            self.msg(f"Изучать «{rec['name']}» можно у верстака {'I' * tier}", (255, 170, 120))
            return
        cost = rec.get("research", 0)
        if p.res["scrap"] < cost:
            self.msg(f"Для изучения нужно {cost} металлолома", (255, 170, 120))
            return
        p.res["scrap"] -= cost
        p.known.append(rec["id"])
        self.msg(f"Изучено: {rec['name']}!", (160, 220, 255))
        self.log(f"Изучен рецепт «{rec['name']}»")

    def cancel_craft(self, i):
        if i < len(self.craft_queue):
            q = self.craft_queue.pop(i)
            for k, v in CRAFT_BY_ID[q["id"]]["cost"].items():
                self.player.res[k] += v
            self.msg("Крафт отменён, ресурсы возвращены")

    def update_crafting(self, dt):
        if not self.craft_queue:
            return
        q = self.craft_queue[0]
        q["t"] -= dt
        if q["t"] > 0:
            return
        self.craft_queue.pop(0)
        rec = CRAFT_BY_ID[q["id"]]
        p = self.player
        kind = rec["kind"]
        self.add_xp("craft", rec["time"] * 2)
        self.sfx("chime", vol=0.5)
        if kind == "tool":
            item = {"id": rec["id"], "dur": ITEMS[rec["id"]]["dur"]}
            if not self.give_tool(item):
                self.drop_at(p.x, p.y, [item], {})
                self.msg(f"{rec['name']} упал на землю — нет места", (255, 200, 140))
        elif kind == "res":
            p.res[rec.get("result", rec["id"])] += rec.get("amount", 1)
            self.msg(f"Готово: {rec['name']}", (180, 255, 180))
        elif kind == "cloak":
            p.cloak = True
            self.msg("Ты надел меховую накидку — холод почти не страшен", (180, 255, 180))
        elif kind == "bag":
            self.set_bag(rec["bag"])
            self.msg(f"Теперь в рюкзаке {BAG_SIZES[p.bag]} мест!", (180, 255, 180))
        elif kind == "armor":
            p.armor = max(p.armor, rec["armor"])
            self.msg(f"Ты надел: {rec['name']} (урон по тебе −{(15, 35)[rec['armor'] - 1]}%)", (180, 255, 180))

    # ------------------------------------------------------------ стройка
    def mouse_tile(self):
        mx, my = pygame.mouse.get_pos()
        dy = DECK_H if self.player.on_tower else 0
        return int((mx + self.cam_x) // TILE), int((my + self.cam_y + dy) // TILE)

    def tower_rect(self):
        p = self.player
        if not p.on_tower or p.tower_roof < 0:
            return None
        return self.world.roofs[p.tower_roof]["rect"]

    def build_check(self, bid, tx, ty):
        p = self.player
        w = self.world
        b = BUILD_BY_ID[bid]
        if self.bench_tier_built() < b["tier"]:
            return f"Сначала построй верстак {'I' * b['tier']}"
        if p.on_tower:                                         # стройка на площадке вышки
            x, y, rw, rh = self.tower_rect()
            if not b.get("deck"):
                return "На вышке можно ставить только турели, сундуки, баррикады и факелы"
            if not (x <= tx < x + rw and y <= ty < y + rh):
                return "Только на площадке вышки"
            if [tx, ty] == w.roofs[p.tower_roof]["ladder"] or (tx, ty) in w.deck:
                return "Место занято"
            return ""
        if not w.in_bounds(tx, ty):
            return "За краем мира"
        if math.hypot(tx * TILE + TILE / 2 - p.x, ty * TILE + TILE / 2 - p.y) > BUILD_REACH:
            return "Слишком далеко"
        if b.get("tool") and not p.has_tool("dig"):
            return "Нужна лопата на поясе/спине/в руках"
        if bid == "flag" and self.flag:
            return "Флаг поселения уже стоит (снеси старый, чтобы перенести)"
        g = w.ground[ty][tx]
        if g == WATER:
            return "Нельзя строить на воде"
        o = w.objects.get((tx, ty))
        if bid in ("floor", "ditch"):
            if g == (FLOOR if bid == "floor" else DITCH):
                return "Здесь уже готово"
            if bid == "ditch" and g == FLOOR:
                return "Нельзя копать сквозь пол"
            if o and (o["t"] in BLOCKING or o["t"] == "tree" or bid == "ditch"):
                return "Мешает объект"
            if bid == "ditch" and pygame.Rect(tx * TILE, ty * TILE, TILE, TILE).collidepoint(p.x, p.y):
                return "Ты стоишь на этом месте"
            return ""
        if g == DITCH:
            return "Здесь ров"
        if bid in PITS and g == FLOOR:
            return "Нельзя копать сквозь пол"
        if o and o["t"] not in ("tuft", "pebble"):
            return "Место занято"
        if bid in BLOCKING and pygame.Rect(tx * TILE, ty * TILE, TILE, TILE).inflate(p.r * 2, p.r * 2).collidepoint(p.x, p.y):
            return "Ты стоишь на этом месте"
        return ""

    def new_build_obj(self, bid):
        obj = {"t": bid, "own": True}
        if bid == "fire":
            obj["fuel"] = 120.0
        elif bid in STORAGE:
            obj.update(res={}, tools=[None] * CHEST_TOOLS)
        elif bid == "garden":
            obj.update(planted=False, grow=0.0)
        elif bid == "trap":
            obj["armed"] = True
        elif bid in PITS:
            obj["hidden"] = False
        elif bid in TURRETS:
            obj.update(ammo=0, cd=0.0, ang=0.0)
        elif bid in DOORS:
            obj["open"] = False
        if bid in BREAKABLE:
            obj["hp"] = BREAKABLE[bid][2]
        return obj

    def try_build(self):
        if self.build_cd > 0:
            return
        p = self.player
        w = self.world
        tx, ty = self.mouse_tile()
        self.build_cd = 0.18
        if self.demolish:
            self.try_demolish(tx, ty)
            return
        b = BUILD_BY_ID[self.build_sel]
        bid = b["id"]
        err = self.build_check(bid, tx, ty)
        if err:
            self.msg(err, (255, 170, 120))
            return
        if any(p.res[k] < v for k, v in b["cost"].items()):
            self.msg(f"Не хватает ресурсов: {b['name']}", (255, 170, 120))
            return
        for k, v in b["cost"].items():
            p.res[k] -= v
        pos = (tx, ty)
        if p.on_tower:
            w.deck[pos] = self.new_build_obj(bid)
            if bid in TURRETS:
                self.turret_pos.add((tx, ty, True))
            self.popup(tx * TILE + 20, ty * TILE - DECK_H, b["name"], (180, 255, 180))
            return
        if bid == "floor":
            w.ground[ty][tx] = FLOOR
            w.own_floor.add(pos)
        elif bid == "ditch":
            w.ground[ty][tx] = DITCH
            w.own_floor.add(pos)
            self.build_cd = 0.6
            self.wear_tool("dig")
            if random.random() < 0.4:
                p.res["stone"] += 1
        else:
            obj = self.new_build_obj(bid)
            if bid == "fire":
                w.fires.add(pos)
            if bid in BENCH_TIER:
                self.bench_counts[str(BENCH_TIER[bid])] += 1
                self.msg(f"{b['name']} построен — открыты новые постройки и рецепты!", (180, 255, 180))
            if bid in TURRETS:
                self.turret_pos.add((tx, ty, False))
                self.msg("Турель построена. Зарядить: наведи мышь и нажми E (нужны стрелы/патроны)", (180, 255, 180))
            if bid in PITS:
                self.wear_tool("dig")
                self.build_cd = 0.6
                self.msg("Яма вырыта. Наведи на неё мышь и нажми E, чтобы замаскировать листьями", (180, 255, 180))
            if bid == "flag":
                self.flag = [tx, ty]
                self.show_banner("Поселение основано", "Флаг поднят! Ставь кровати и палатки рядом и приглашай людей "
                                 "с хорошим отношением — они будут жить здесь и работать.")
            w.objects[pos] = obj
        self.popup(tx * TILE + 20, ty * TILE, b["name"], (180, 255, 180))
        self.map_timer = 0

    def wear_tool(self, flag):
        p = self.player
        for i, s in enumerate(p.slots):
            if s and ITEMS[s["id"]].get(flag):
                s["dur"] -= 1
                if s["dur"] <= 0:
                    self.msg(f"{ITEMS[s['id']]['name']} сломался!", (255, 140, 120))
                    p.slots[i] = None
                return

    def try_demolish(self, tx, ty):
        w = self.world
        p = self.player
        pos = (tx, ty)
        if p.on_tower:
            o = w.deck.get(pos)
            if not o:
                return
            refund = BUILD_BY_ID[o["t"]]["cost"]
            del w.deck[pos]
            self.turret_pos.discard((tx, ty, True))
            if o["t"] == "chest":
                self.drop_at(p.x, p.y, o["tools"], o["res"])
        else:
            if math.hypot(tx * TILE + TILE / 2 - p.x, ty * TILE + TILE / 2 - p.y) > BUILD_REACH:
                return
            o = w.objects.get(pos)
            if o and o.get("own"):
                refund = BUILD_BY_ID[o["t"]]["cost"]
                self.remove_object(pos, drop=True)
            elif pos in w.own_floor:
                w.own_floor.discard(pos)
                refund = BUILD_BY_ID["ditch" if w.ground[ty][tx] == DITCH else "floor"]["cost"]
                w.ground[ty][tx] = GRASS
            else:
                self.msg("Сносить можно только свои постройки", (255, 170, 120))
                return
        for k, v in refund.items():
            p.res[k] += max(1, v // 2)
        self.popup(tx * TILE + 20, ty * TILE, "Снесено (+50% ресурсов)", (255, 220, 150))
        self.map_timer = 0

    def remove_object(self, pos, drop=True):
        """Единая точка удаления объектов (снос, поломка, огонь)."""
        o = self.world.objects.pop(pos, None)
        if o:
            self.on_removed(pos, o, drop)

    def on_removed(self, pos, o, drop):
        w = self.world
        t = o["t"]
        if t in BENCH_TIER and o.get("own"):
            self.bench_counts[str(BENCH_TIER[t])] -= 1
        w.fires.discard(pos)
        w.burning.pop(pos, None)
        self.turret_pos.discard((pos[0], pos[1], False))
        if drop and t in STORAGE:
            self.drop_at(pos[0] * TILE + 20, pos[1] * TILE + 20, o["tools"], o["res"])
        if t == "flag" and o.get("own"):
            self.flag = None
            for a in self.settlers():
                a.settler, a.stay = False, True
            self.msg("Флаг поселения уничтожен! Жители остались без дома.", (255, 120, 110))
        if t in HEARTS and "fac" in o:
            self.heart_destroyed(o["fac"], t)
        if t == "dark_heart":
            self.heart_broken()
        if "roof" in o:
            self.check_roof(o["roof"])
        self.map_timer = 0

    def check_roof(self, ri):
        w = self.world
        r = w.roofs[ri]
        if r["ruined"]:
            return
        x, y, rw, rh = r["rect"]
        left = 0
        for yy in range(y, y + rh):
            for xx in range(x, x + rw):
                o = w.objects.get((xx, yy))
                if o and o.get("roof") == ri and o["t"] in ("hut_wall", "wall_old", "tower_wall"):
                    left += 1
        if left < r["walls"] * 0.55:
            r["ruined"] = True
            if r["fac"] >= 0:
                f = w.factions[r["fac"]]
                self.change_rel(f, -25)
                f["anger"] = max(f["anger"], 60)
                self.msg(f"Хижина ({f['name']}) разрушена!", (255, 150, 110))
                self.log(f"Разрушена хижина: {f['name']}")
                self.check_camp(r["fac"])
            else:
                self.msg("Крыша обрушилась", (220, 200, 180))

    def damage_building(self, pos, dmg):
        o = self.world.objects.get(pos)
        if not o or o["t"] not in BREAKABLE:
            return
        o["hp"] = o.get("hp", BREAKABLE[o["t"]][2]) - dmg
        o["hit_t"] = self.clock_t
        if o["hp"] <= 0:
            if o.get("own"):
                self.msg(f"Враги сломали: {BUILD_BY_ID[o['t']]['name']}!", (255, 120, 110))
            self.remove_object(pos, drop=True)

    def after_burn(self, burned):
        for pos, o in burned:
            self.on_removed(pos, o, drop=False)
            if o.get("own"):
                self.msg(f"Сгорело: {BUILD_BY_ID[o['t']]['name']}", (255, 140, 90))

    # ------------------------------------------------------------ бой
    def shoot(self, x, y, ang, spec, owner, fac=-1, fire=False):
        for i in range(spec.get("pellets", 1)):
            a = ang + (random.uniform(-spec["spread"], spec["spread"]) if spec.get("spread") else 0)
            self.projectiles.append({"x": x, "y": y, "vx": math.cos(a) * spec["speed"], "vy": math.sin(a) * spec["speed"],
                                     "life": spec.get("life", 0.8), "dmg": spec["dmg"], "owner": owner, "fac": fac,
                                     "kind": spec.get("kind", "arrow"), "fire": fire, "freeze": spec.get("freeze", 0)})

    def throw_bomb(self):
        p = self.player
        if p.res["firebomb"] <= 0:
            self.msg("Нет огненных бомб. Их делают на верстаке I (ткань + уголь), сначала изучи", (255, 170, 120))
            return
        if p.cd > 0:
            return
        mx, my = pygame.mouse.get_pos()
        wx, wy = mx + self.cam_x, my + self.cam_y
        ang = math.atan2(wy - p.y, wx - p.x)
        dist = min(math.hypot(wx - p.x, wy - p.y), 7 * TILE)
        p.res["firebomb"] -= 1
        p.cd, p.swing, p.anim = 0.6, 0.3, "swing"
        self.projectiles.append({"x": p.x, "y": p.y, "vx": math.cos(ang) * 420, "vy": math.sin(ang) * 420,
                                 "life": max(0.1, dist / 420), "dmg": 20, "owner": "player", "fac": -1, "kind": "bomb",
                                 "fire": True})

    def explode(self, x, y):
        w = self.world
        p = self.player
        self.explosions.append([x, y, 0.5])
        self.shake = max(self.shake, 0.2)
        self.sfx("boom", x, y)
        tx0, ty0 = int(x // TILE), int(y // TILE)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                pos = (tx0 + dx, ty0 + dy)
                o = w.objects.get(pos)
                if o and w.ignite(pos) and "fac" in o:
                    self.provoke(o["fac"], delta=-25, anger=90)
        for a in self.animals:
            if not a.dead and not a.ally and math.hypot(a.x - x, a.y - y) < 1.7 * TILE:
                self.hit_creature(a, 20, ranged=True)
                a.burn_t = 4.0
        if math.hypot(p.x - x, p.y - y) < 1.2 * TILE and not p.on_tower:
            self.hurt_player(12, "собственной бомбы", "fire")

    def try_use(self):
        p = self.player
        if p.cd > 0:
            return
        st = p.stats()
        mx, my = pygame.mouse.get_pos()
        wx, wy = mx + self.cam_x, my + self.cam_y
        ang = math.atan2(wy - p.y, wx - p.x)
        ranged = st.get("ranged")
        if ranged:
            p.cd = ranged["cd"]
            ammo, fire = ranged["ammo"], False
            if ammo == "arrows" and p.fire_mode:
                if p.res["fire_arrows"] > 0:
                    ammo, fire = "fire_arrows", True
                else:
                    p.fire_mode = False
                    self.msg("Огненные стрелы кончились — стреляешь обычными", (255, 200, 140))
            if p.res[ammo] <= 0:
                self.msg(f"Нет боеприпасов: {RES_INFO[ammo][0]}", (255, 170, 120))
                return
            if random.random() < ranged.get("misfire", 0):     # старое ружьё стреляет через раз
                self.popup(p.x, p.y - 30, "Щёлк! Осечка", (220, 220, 220))
                return
            p.res[ammo] -= 1
            p.anim, p.swing = ("gun" if ammo == "ammo" else "bow"), 0.25
            if ammo == "ammo":
                p.flash = 0.08
                self.shake = 0.12
            self.sfx("gun" if ammo == "ammo" else "bow", vol=0.8)
            spec = dict(ranged, dmg=ranged["dmg"] * (1 + 0.05 * self.skill_lvl("archery")))
            self.shoot(p.x, p.y, ang, spec, "player", fire=fire)
            self.wear_held()
            return
        reach = REACH * st["reach"]
        slow = 1.4 if p.cond.get("frostbite", 0) > 0 else 1.0               # обмороженные руки медленнее
        for a in self.animals:
            if a.ally:
                continue
            if math.hypot(a.x - wx, a.y - wy) < a.r + 16 and math.hypot(a.x - p.x, a.y - p.y) < reach + a.r:
                p.cd, p.swing, p.anim = st["cd"] * slow, 0.3, st["anim"]
                self.sfx("hit", vol=0.7)
                self.hit_creature(a, st["dmg"])
                if st.get("stun") and random.random() < st["stun"]:
                    a.stun_t = 1.5
                    self.popup(a.x, a.y - 24, "Оглушён!", (255, 230, 150))
                if st.get("poison") and not a.dead:                 # ядовитый клинок
                    a.poison_t = max(a.poison_t, st["poison"])
                self.wear_held()
                return
        if p.on_tower:
            return
        tx, ty = int(wx // TILE), int(wy // TILE)
        w = self.world
        cx, cy = tx * TILE + TILE / 2, ty * TILE + TILE / 2
        if math.hypot(cx - p.x, cy - p.y) > REACH + 10:
            return
        if st.get("fish") and w.in_bounds(tx, ty) and w.ground[ty][tx] == WATER and not p.fishing:
            p.fishing = [random.uniform(2.5, 5.5) * (1 - 0.06 * self.skill_lvl("fishing")), tx, ty]
            p.cd = 0.5
            self.msg("Пробил лунку во льду и закинул удочку..." if w.frozen else
                     "Закинул удочку... не двигайся, пока не клюнет")
            return
        o = w.objects.get((tx, ty))
        if not o:
            return
        t = o["t"]
        res = p.res
        if st.get("repair") and o.get("own") and t in BREAKABLE:
            self.repair((tx, ty), o)
            return
        if o.get("locked"):
            p.cd = 0.5
            self.msg("Сундук окован железом — не взломать, пока жив хозяин логова", (255, 200, 140))
            return
        if t not in GATHER and t not in BREAKABLE:
            return
        p.cd, p.swing, p.anim = st["cd"] * slow, 0.3, st["anim"]
        if t == "tree":
            o["hp"] -= st["chop"] * (1 + 0.08 * self.skill_lvl("chop"))
            o["hit_t"] = self.clock_t
            self.sfx("chop", vol=0.6)
            self.add_xp("chop", 1)
            if p.held():
                self.wear_held()
            if o["hp"] <= 0:
                n = (2 if o["kind"] == "dead" else 4) + (1 if p.held_id() in ("axe", "iron_axe", "battle_axe") else 0)
                n += 1 if self.skill_lvl("chop") >= 5 else 0
                self.add_xp("chop", 5)
                res["wood"] += n
                self.popup(cx, cy - 30, f"+{n} Дерево", (230, 190, 130))
                if random.random() < 0.35:
                    res["fiber"] += 1
                w.objects[(tx, ty)] = {"t": "stump", "timer": random.uniform(160, 260), "kind": o["kind"]}
                w.timed.add((tx, ty))
            elif not p.held():
                self.msg("Голыми руками долго... Скрафти топор [C]")
        elif t == "charred":
            res["coal"] += 2
            self.popup(cx, cy - 20, "+2 Уголь", (180, 180, 190))
            w.objects[(tx, ty)] = {"t": "stump", "timer": random.uniform(160, 260)}
            w.timed.add((tx, ty))
        elif t in BREAKABLE:
            rid, n, hp = BREAKABLE[t]
            if "fac" in o:
                self.provoke(o["fac"], delta=-10, anger=60)
            o["hp"] = o.get("hp", hp) - max(1.0, st["chop"] if rid in ("wood", "fiber", "cloth") else st["mine"] + 1,
                                            st["dmg"] / 3)
            o["hit_t"] = self.clock_t
            if p.held():
                self.wear_held()
            if o["hp"] <= 0:
                res[rid] += n
                self.popup(cx, cy - 20, f"+{n} {RES_INFO[rid][0]}", (230, 190, 130))
                self.remove_object((tx, ty), drop=True)
        elif t in ("rock", "ore", "coal_node"):
            if st["mine"] <= 0:
                self.msg("Нужна кирка, чтобы разбить камень. Камешки можно собрать с земли.", (255, 200, 140))
                return
            o["hp"] -= st["mine"] * (1 + 0.08 * self.skill_lvl("mine"))
            o["hit_t"] = self.clock_t
            self.sfx("mine", vol=0.6)
            self.add_xp("mine", 1)
            self.wear_held()
            if o["hp"] <= 0:
                drop = {"rock": ("stone", 5), "ore": ("ore", 3), "coal_node": ("coal", 3)}[t]
                drop = (drop[0], drop[1] + (1 if self.skill_lvl("mine") >= 5 else 0))
                self.add_xp("mine", 6)
                res[drop[0]] += drop[1]
                if random.random() < (0.5 if t == "ore" else 0.25):
                    res["scrap"] += 1
                self.popup(cx, cy - 30, f"+{drop[1]} {RES_INFO[drop[0]][0]}", (200, 200, 210))
                del w.objects[(tx, ty)]
        elif t == "bush":
            if o["berries"]:
                res["berries"] += 3
                o["berries"] = False
                o["timer"] = random.uniform(80, 120)
                w.timed.add((tx, ty))
                self.popup(cx, cy - 20, "+3 Ягоды", (255, 120, 150))
            else:
                self.msg("Ягоды ещё не выросли")
        else:   # трава, камешки, тростник, грибы, сухие кусты
            loot = {"tuft": {"fiber": 2}, "pebble": {"stone": 1}, "reed": {"fiber": 3}, "mushroom": {"mushroom": 1},
                    "toadstool": {"toadstool": 1}, "dry_bush": {"wood": 1, "fiber": 1},
                    "flower": {"flowers": 2 if random.random() < 0.3 else 1}}[t]
            for k, v in loot.items():
                res[k] += v
            del w.objects[(tx, ty)]
            w.respawn_random(t, p.x, p.y)
            self.popup(cx, cy - 20, ", ".join(f"+{v} {RES_INFO[k][0]}" for k, v in loot.items()), (190, 230, 120))

    def repair(self, pos, o):
        p = self.player
        rid, _, maxhp = BREAKABLE[o["t"]]
        hp = o.get("hp", maxhp)
        p.cd, p.swing, p.anim = 0.5, 0.3, "swing"
        if hp >= maxhp:
            self.msg("Не нуждается в ремонте")
            return
        if p.res[rid] <= 0:
            self.msg(f"Для ремонта нужен ресурс: {RES_INFO[rid][0]}", (255, 170, 120))
            return
        p.res[rid] -= 1
        o["hp"] = min(maxhp, hp + maxhp * 0.25)
        self.wear_held()
        self.popup(pos[0] * TILE + 20, pos[1] * TILE, f"Ремонт {int(o['hp'])}/{maxhp}", (160, 230, 255))

    def ignite_target(self):
        p = self.player
        if not ITEMS.get(p.held_id() or "", {}).get("ignite"):
            self.msg("Чтобы поджечь, возьми в руки факел или огниво (или кинь огненную бомбу — T)", (255, 170, 120))
            return
        tx, ty = self.mouse_tile()
        o = self.world.objects.get((tx, ty))
        if math.hypot(tx * TILE + 20 - p.x, ty * TILE + 20 - p.y) > REACH + 10 or not o:
            return
        if o["t"] not in FLAMMABLE:
            self.msg("Это не горит")
            return
        if self.raining():
            self.msg("Под дождём не поджечь", (200, 220, 255))
            return
        if self.world.ignite((tx, ty)):
            self.msg("Огонь разгорается...", (255, 170, 90))
            if p.held_id() == "flint":
                self.wear_held()
            if "fac" in o:
                self.provoke(o["fac"], delta=-25, anger=90)

    def hit_creature(self, a, dmg, ranged=False):
        p = self.player
        if a.ally:
            return
        if (a.beh == "shadow" or a.kind == "barrow_lord") and p.light():
            dmg *= 2                                    # Тень боится света
        if not ranged:
            sk = "combat" if a.human or a.hostile() else "hunt"
            dmg *= 1 + 0.05 * self.skill_lvl(sk)
            self.add_xp(sk, 2)
        if a.sleeping:
            a.sleeping = False
            self.msg("Ты разбудил медведя!", (255, 120, 100))
        ang = math.atan2(a.y - p.y, a.x - p.x)
        if not a.ghost and a.beh != "boss":            # боссов не отбросить
            move_entity(self.world, a, math.cos(ang) * 14, math.sin(ang) * 14, doors=a.human)
        if a.beh in ("flee", "dog"):
            a.flee_t = 5.0
            a.trust = 0
        elif a.human:
            self.provoke(a.faction, witness=False)
        else:
            if a.aggro_t <= 0 and a.beh in ("neutral", "territorial"):
                self.msg(f"{ANIMALS[a.kind]['name']} в ярости!", (255, 140, 110))
            a.aggro_t = 30 if a.beh == "hunter" else 20
            if a.beh == "hunter" and not ranged:
                a.flee_t = 0.3
        self.damage_creature(a, dmg, by_player=True)

    def damage_creature(self, a, dmg, by_player):
        if a.dead:
            return
        a.hp -= dmg
        a.hurt = 0.2
        if a.hp > 0:
            return
        a.dead = True
        if a.ally:
            who = "Твой пёс" if not a.human else "Житель" if a.settler else "Спутник"
            self.msg(f"{who} {a.name} погиб...", (255, 120, 110))
            self.log(f"Погиб {a.name}")
            return
        if a.beh == "boss":
            self.on_boss_death(a)
            return
        if a.human:
            items = []
            if random.random() < 0.4:
                wid = ROLES[a.role]["weapon"]
                items.append({"id": wid, "dur": int(ITEMS[wid]["dur"] * random.uniform(0.2, 0.6))})
            res = {"hide": 1 if random.random() < 0.5 else 0, "arrows": 3 if a.role == "archer" else 0,
                   "ammo": random.randint(1, 4) if a.role in ("gunner", "boss") else 0,
                   "scrap": 1 if FACTION_TYPES[self.world.factions[a.faction]["type"]]["camp"] == "fort" else 0}
            self.drop_at(a.x, a.y, items, res)
            if by_player:
                self.kills += 1
                self.change_rel(self.world.factions[a.faction], -20)
                self.popup(a.x, a.y - 30, "Выпали вещи [E]", (255, 220, 150))
            return
        if not by_player:
            return
        p = self.player
        self.kill_counts[a.kind] = self.kill_counts.get(a.kind, 0) + 1
        if a.beh != "flee":
            self.kills += 1
        d = ANIMALS[a.kind]
        hunt = self.skill_lvl("hunt")
        self.add_xp("hunt", 4 + d["hp"] // 3)
        parts = []
        if d["meat"]:
            meat = d["meat"] + ITEMS.get(p.held_id() or "", {}).get("butcher", 0) + (1 if hunt >= 4 else 0)
            p.res["meat"] += meat
            parts.append(f"+{meat} Мясо")
        for rid in ("hide", "fang", "essence"):
            if d.get(rid):
                n = d[rid] + (1 if rid == "hide" and hunt >= 8 else 0)
                p.res[rid] += n
                parts.append(f"+{n} {RES_INFO[rid][0]}")
        if parts:
            self.popup(a.x, a.y - 30, ", ".join(parts), (255, 170, 160))

    def projectile_hits(self, pr, a):
        """Может ли снаряд задеть это существо."""
        owner = pr["owner"]
        if owner == "player":
            return not a.ally
        if owner in ("ally", "turret"):
            return self.is_threat(a)
        if owner == "boss":                             # плевки Королевы задевают только твоих
            return a.ally
        f = self.world.factions[pr["fac"]]
        if a.human and not a.ally:
            return a.faction != pr["fac"] and a.faction in f["wars"]
        if a.ally:
            return self.fac_hostile(pr["fac"])
        return a.hostile()

    def update_projectiles(self, dt):
        w = self.world
        p = self.player
        for pr in self.projectiles:
            hit_pos, hit_a = None, None
            for _ in range(4):
                pr["x"] += pr["vx"] * dt / 4
                pr["y"] += pr["vy"] * dt / 4
                tx, ty = int(pr["x"] // TILE), int(pr["y"] // TILE)
                if not w.in_bounds(tx, ty) or (w.ground[ty][tx] != DITCH and w.tile_blocked(tx, ty, swim=True)):
                    o = w.objects.get((tx, ty))
                    if o and o.get("own") and pr["owner"] == "npc":
                        self.damage_building((tx, ty), pr["dmg"] * 0.3)
                    hit_pos = (tx, ty)
                    break
                if pr["owner"] == "npc" and self.fac_hostile(pr["fac"]) and not p.on_tower and \
                        math.hypot(p.x - pr["x"], p.y - pr["y"]) < p.r + 4:
                    self.hurt_player(pr["dmg"], self.fac_cause(pr["fac"]), pr["kind"])
                    hit_pos = (tx, ty)
                    break
                if pr["owner"] == "boss" and not p.on_tower and math.hypot(p.x - pr["x"], p.y - pr["y"]) < p.r + 6:
                    self.hurt_player(pr["dmg"], "яда Болотной Королевы")
                    p.poison = max(p.poison, 8)
                    self.popup(p.x, p.y - 30, "Яд!", (160, 255, 110))
                    hit_pos = (tx, ty)
                    break
                for a in self.animals:
                    if a.dead or abs(a.x - pr["x"]) > 40 or abs(a.y - pr["y"]) > 40:
                        continue
                    if math.hypot(a.x - pr["x"], a.y - pr["y"]) < a.r + 4 and self.projectile_hits(pr, a):
                        hit_a = a
                        break
                if hit_a:
                    break
            if hit_a:
                if pr["kind"] != "bomb":
                    if pr["owner"] == "player":
                        self.add_xp("archery", 3)
                        self.hit_creature(hit_a, pr["dmg"], ranged=True)
                    else:
                        self.damage_creature(hit_a, pr["dmg"], by_player=pr["owner"] == "turret")
                    if pr.get("fire"):
                        hit_a.burn_t = 4.0
                    if pr.get("freeze") and not hit_a.dead:      # ледяные стрелы сковывают (боссов — чуть-чуть)
                        hit_a.stun_t = max(hit_a.stun_t, 0.25 if hit_a.beh == "boss" else pr["freeze"])
                        self.popup(hit_a.x, hit_a.y - 26, "Лёд!", (190, 230, 255))
                pr["life"] = 0
            elif hit_pos:
                if pr.get("fire") and pr["kind"] != "bomb":
                    o = w.objects.get(hit_pos)
                    if o and w.ignite(hit_pos) and "fac" in o and pr["owner"] == "player":
                        self.provoke(o["fac"], delta=-25, anger=90)
                pr["life"] = 0
            else:
                pr["life"] -= dt
            if pr["life"] <= 0 and pr["kind"] == "bomb" and not pr.get("boom"):
                pr["boom"] = True
                self.explode(pr["x"], pr["y"])
        self.projectiles = [pr for pr in self.projectiles if pr["life"] > 0]

    def update_turrets(self, dt):
        w = self.world
        for tx, ty, deck in list(self.turret_pos):
            store = w.deck if deck else w.objects
            o = store.get((tx, ty))
            if not o or o["t"] not in TURRETS:
                self.turret_pos.discard((tx, ty, deck))
                continue
            o["cd"] = o.get("cd", 0) - dt
            if o["cd"] > 0 or o.get("ammo", 0) <= 0:
                continue
            spec = TURRET_SPEC[o["t"]]
            cx, cy = tx * TILE + 20, ty * TILE + 20
            rng = (8 + (3 if deck else 0)) * TILE
            best, bd = None, rng
            for a in self.animals:
                if abs(a.x - cx) > rng or abs(a.y - cy) > rng or not self.is_threat(a):
                    continue
                d = math.hypot(a.x - cx, a.y - cy)
                if d < bd:
                    best, bd = a, d
            if not best:
                o["cd"] = 0.3
                continue
            o["ang"] = math.atan2(best.y - cy, best.x - cx)
            o["ammo"] -= 1
            o["cd"] = spec["cd"]
            o["flash"] = self.clock_t
            self.sfx("gun" if o["t"] == "gun_turret" else "bow", cx, cy, 0.5)
            self.shoot(cx + math.cos(o["ang"]) * 18, cy + math.sin(o["ang"]) * 18, o["ang"], dict(spec, life=0.9),
                       "turret")

    # ------------------------------------------------------------ наведение мыши и взаимодействие
    def compute_hover(self):
        """Что под курсором: человек, предмет, вода или объект на вышке. far=True — далеко для E."""
        p = self.player
        w = self.world
        mx, my = pygame.mouse.get_pos()
        wx, wy = mx + self.cam_x, my + self.cam_y
        if p.on_tower:
            tx, ty = int(wx // TILE), int((wy + DECK_H) // TILE)
            x, y, rw, rh = self.tower_rect()
            if not (x <= tx < x + rw and y <= ty < y + rh):
                return None
            far = math.hypot(tx * TILE + 20 - p.x, ty * TILE + 20 - p.y) > REACH + 12
            o = w.deck.get((tx, ty))
            if o and o["t"] in ("chest",) + tuple(TURRETS):
                return {"kind": "deck", "pos": (tx, ty), "obj": o, "far": far}
            if w.roofs[p.tower_roof]["ladder"] == [tx, ty]:
                return {"kind": "descend", "pos": (tx, ty), "far": False}
            return None
        for a in self.animals:
            if (a.human or a.kind == "dog") and not a.dead and math.hypot(a.x - wx, a.y - wy) < a.r + 10:
                return {"kind": "npc" if a.human else "dog", "npc": a,
                        "far": math.hypot(a.x - p.x, a.y - p.y) > REACH * 1.5}
        tx, ty = int(wx // TILE), int(wy // TILE)
        if not w.in_bounds(tx, ty):
            return None
        far = math.hypot(tx * TILE + 20 - p.x, ty * TILE + 20 - p.y) > REACH + 12
        o = w.objects.get((tx, ty))
        if o and o["t"] in INTERACTIVE and not (o["t"] == "fire" and o.get("eternal")):
            return {"kind": "obj", "pos": (tx, ty), "obj": o, "far": far}
        g = w.ground[ty][tx]
        if g in (WATER, SWAMP) and not o:
            return {"kind": "water", "pos": (tx, ty), "swamp": g == SWAMP, "far": far}
        return None

    def hover_label(self, h):
        p = self.player
        if not h:
            return ""
        k = h["kind"]
        if k == "npc":
            a = h["npc"]
            text = f"Поговорить: {a.name}"
        elif k == "dog":
            a = h["npc"]
            if a.ally:
                text = f"{a.name}: {'идти за мной' if a.stay else 'ждать здесь'}" + \
                       (" · покормить" if a.hp < a.max_hp else "")
            else:
                text = f"Подманить мясом (доверие {a.trust}/3)"
        elif k == "water":
            if self.world.frozen:
                text = "Растопить лёд и попить"
            else:
                text = "Попить болотной воды (яд и дизентерия!)" if h["swamp"] else "Попить сырой воды (риск дизентерии)"
        elif k == "descend":
            text = "Спуститься по лестнице"
        else:
            o = h["obj"]
            t = o["t"]
            if t == "fire":
                text = "Забрать уголь" if o.get("coal") else "Подбросить дрова (1 дерево)"
            elif t in SLEEP:
                text = "Лечь спать" if self.is_night() else "Спать можно только ночью"
            elif t == "garden":
                if self.season() == "winter":
                    text = "Зимой ничего не растёт"
                elif not o["planted"]:
                    text = "Посадить ягоды (2 шт.)"
                elif o["grow"] >= GARDEN_TIME:
                    text = "Собрать урожай"
                else:
                    text = f"Растёт: {int(o['grow'] / GARDEN_TIME * 100)}%" + \
                           (" · удобрить гнилью" if p.res.get("rot", 0) else "")
            elif t == "trap":
                text = "Капкан взведён" if o["armed"] else "Взвести капкан"
            elif t in BENCH_TIER:
                text = f"{BUILD_BY_ID[t]['name']}: крафт и изучение"
            elif t in DOORS:
                text = "Закрыть дверь" if o.get("open") else "Открыть дверь настежь"
            elif t in TURRETS:
                text = f"Зарядить турель ({o.get('ammo', 0)}/{TURRET_CAP} {RES_INFO[TURRETS[t]][0].lower()})"
            elif t in PITS:
                text = "Яма замаскирована" if o.get("hidden") else "Замаскировать листьями (3 волокна)"
            elif t == "chest" and o.get("locked"):
                text = "Сундук окован — сначала одолей хозяина логова"
            elif t == "chest" and o.get("notes"):
                text = "Открыть сундук (внутри какие-то бумаги)"
            elif t == "bones":
                text = "Осмотреть останки (тут записка)" if o.get("notes") else "Старые кости — здесь пусто"
            elif t == "hive":
                text = ("Забрать мёд" + (" (дым факела усыпит пчёл)" if p.held_id() != "torch" else " — пчёлы спят от дыма")
                        if o.get("honey") else "Мёда пока нет — пчёлы работают")
            elif t == "radio":
                st = self.story
                text = "Передатчик «Маяк-7»: " + ("вертолёт уже здесь" if st["heli"] else
                                                   "ждём вертолёт" if st["rescue_t"] > 0 else
                                                   f"деталей {len(st['installed'])}/3")
            elif t == "heli":
                text = "Сесть в вертолёт и улететь домой"
            else:
                text = {"chest": "Открыть сундук", "drop": "Подобрать вещи", "ladder": "Залезть на вышку",
                        "charred": "Собрать уголь", "altar": "Возложить эссенцию на алтарь", "flag": "Поселение",
                        "furnace": "Печь: выплавка", "smokehouse": "Коптильня: копчёное мясо и вяленая рыба",
                        "cellar": "Открыть погреб (еда тут не портится)", "flower": "Сорвать цветы"}.get(t, "")
        if text and h["far"]:
            text += " — подойди ближе"
        return text

    def interact(self):
        p = self.player
        h = self.hover
        if p.on_tower:
            if h and h["kind"] == "deck" and not h["far"]:
                self.interact_object(h["pos"], h["obj"], deck=True)
            else:
                self.descend()
            return
        if not h:
            self.msg("Наведи мышь на предмет или человека — появится подсказка [E]", (200, 200, 210))
            return
        if h["far"]:
            self.msg("Подойди ближе", (255, 200, 140))
            return
        if h["kind"] == "npc":
            self.open_dialog(h["npc"])
        elif h["kind"] == "dog":
            self.interact_dog(h["npc"])
        elif h["kind"] == "water":
            p.thirst = min(100, p.thirst + 30)
            self.popup(p.x, p.y - 30, "+30 вода", (120, 190, 255))
            self.sfx("splash", vol=0.3)
            if self.world.frozen:
                p.warmth = max(0, p.warmth - 5)
                return
            if h["swamp"] and random.random() < 0.35:
                p.poison = max(p.poison, 8)
                self.msg("Болотная вода оказалась гнилой — ты отравлен!", (180, 255, 120))
            sick = (0.3 if h["swamp"] else 0.12) * (1.6 if self.season() == "summer" else 1.0)
            if random.random() < sick and p.cond.get("dysentery", 0) <= 0:
                p.cond["dysentery"] = 200
                self.msg("Живот крутит — дизентерия! Голод и жажда растут вдвое быстрее. Кипяти воду у костра",
                         (200, 170, 100))
        else:
            self.interact_object(h["pos"], h["obj"])

    def interact_dog(self, a):
        p = self.player
        if a.ally:
            for rid in ("meat", "cooked", "smoked_meat"):
                if a.hp < a.max_hp and p.res.get(rid, 0) > 0:
                    p.res[rid] -= 1
                    a.hp = min(a.max_hp, a.hp + 15)
                    self.popup(a.x, a.y - 24, "+15 HP", (140, 255, 140))
                    return
            a.stay = not a.stay
            a.home = [a.x, a.y]
            self.msg(f"{a.name}: {'жду здесь' if a.stay else 'иду за тобой'}", (200, 230, 255))
            self.sfx("bark", a.x, a.y, 0.5)
            return
        rid = next((r for r in ("meat", "cooked", "smoked_meat") if p.res.get(r, 0) > 0), None)
        if not rid:
            self.msg("Пёс голодный, но у тебя нет мяса", (255, 200, 140))
            return
        p.res[rid] -= 1
        a.trust += 1
        a.flee_t = 0
        self.popup(a.x, a.y - 24, f"Доверие {a.trust}/3", (255, 120, 140))
        if a.trust >= 3:
            if any(o.ally and not o.human for o in self.animals if o is not a):
                self.msg("У тебя уже есть пёс — второй не пойдёт", (255, 200, 140))
                return
            a.ally, a.stay, a.trust = True, False, 3
            a.name = random.choice(DOG_NAMES)
            a.home = [a.x, a.y]
            self.sfx("bark", a.x, a.y)
            self.show_banner("Новый друг", f"Пёс доверяет тебе! Теперь его зовут {a.name}. Он ходит за тобой, "
                             "рычит, когда рядом враги, и кусает их. Наведи на него мышь и нажми E: ждать / за мной.")
        else:
            self.msg(f"Пёс съел мясо и подошёл ближе (доверие {a.trust}/3)", (255, 200, 200))

    def descend(self):
        p = self.player
        lad = self.world.roofs[p.tower_roof]["ladder"] if p.tower_roof >= 0 else None
        if lad:
            p.x, p.y = lad[0] * TILE + TILE / 2, lad[1] * TILE + TILE / 2
        else:
            p.x, p.y = p.tower_ret
        p.on_tower = None
        p.tower_roof = -1
        self.msg("Ты спустился с вышки")

    def interact_object(self, pos, o, deck=False):
        p = self.player
        w = self.world
        t = o["t"]
        if t == "fire":
            if o.get("coal"):
                o["coal"] = 0
                p.res["coal"] += 1
                self.popup(pos[0] * TILE + 20, pos[1] * TILE, "+1 Уголь", (180, 180, 190))
                return
            if p.res["wood"] <= 0:
                self.msg("Нет дров для костра", (255, 170, 120))
                return
            p.res["wood"] -= 1
            o["fuel"] = min(300.0, o["fuel"] + 60)
            self.popup(pos[0] * TILE + 20, pos[1] * TILE, "+60 сек огня", (255, 190, 90))
        elif t in SLEEP:
            self.sleep(SLEEP[t])
        elif t == "cellar":
            self.open_chest, self.open_deck = pos, False
            self.menu = "chest"
        elif t == "smokehouse":
            self.menu = "craft"
            self.craft_tab = 3
        elif t == "chest":
            if o.get("locked"):
                self.msg("Сундук окован железом. Пока жив хозяин логова, его не открыть.", (255, 200, 140))
                return

            def open_it():
                self.open_chest, self.open_deck = pos, deck
                self.menu = "chest"
            if "fac" in o:
                f = w.factions[o["fac"]]
                if f["alive"] and self.attitude(f) != "friend" and any(
                        a.faction == o["fac"] and not a.ally and math.hypot(a.x - p.x, a.y - p.y) < 10 * TILE
                        for a in self.animals):
                    self.change_rel(f, -15)
                    f["anger"] = max(f["anger"], 25)
                    self.msg(f"Вор! {f['name']} заметили, что ты роешься в их сундуке!", (255, 120, 110))
            if o.get("notes"):                                   # сначала записки, потом сам сундук
                self.read_notes(o.pop("notes"), pos, then=open_it)
            else:
                open_it()
        elif t == "bones":
            if o.get("notes"):
                self.read_notes(o.pop("notes"), pos)
                if random.random() < 0.6:
                    found = random.choice([("bandage", 1), ("arrows", 4), ("canned", 1), ("cloth", 1), ("rope", 1)])
                    p.res[found[0]] += found[1]
                    self.popup(pos[0] * TILE + 20, pos[1] * TILE, f"+{found[1]} {RES_INFO[found[0]][0]}", (230, 220, 180))
            else:
                self.msg("Старые кости. Больше здесь ничего нет.")
        elif t == "flower":
            n = 2 if random.random() < 0.3 else 1
            p.res["flowers"] += n
            del w.objects[pos]
            w.respawn_random("flower", p.x, p.y)
            self.popup(pos[0] * TILE + 20, pos[1] * TILE, f"+{n} Цветы", (255, 150, 200))
        elif t == "hive":
            if not o.get("honey"):
                self.msg("Пчёлы ещё не наделали мёда — загляни позже", (230, 210, 140))
                return
            n = random.randint(2, 3)
            p.res["honey"] += n
            o["honey"], o["timer"] = False, random.uniform(180, 260)
            w.timed.add(pos)
            self.popup(pos[0] * TILE + 20, pos[1] * TILE, f"+{n} Мёд", (255, 200, 80))
            if p.held_id() == "torch":
                self.msg("Дым факела усыпил пчёл — мёд твой, никто не ужалил", (200, 230, 160))
            else:
                self.hurt_player(5, "пчёл")
                p.poison = max(p.poison, 4)
                self.msg("Пчёлы жалят! В следующий раз держи в руках горящий факел — дым их усыпит", (255, 200, 120))
        elif t == "radio":
            self.story["radio_visited"] = True
            self.menu = "radio"
        elif t == "heli":
            self.show_ending("rescue")
        elif t == "flag":
            self.menu = "settlement"
        elif t in BENCH_TIER:
            self.menu = "craft"
            self.craft_tab = BENCH_TIER[t] + 3
        elif t == "furnace":
            self.menu = "craft"
            self.craft_tab = 2
        elif t in DOORS:
            o["open"] = not o.get("open")
            self.sfx("door", vol=0.6)
            self.msg("Дверь распахнута: теперь проходят все, даже звери и враги" if o["open"] else
                     "Дверь закрыта: проходишь только ты, твои жители и друзья", (200, 230, 255))
        elif t in TURRETS:
            res = TURRETS[t]
            need = TURRET_CAP - o.get("ammo", 0)
            n = min(need, p.res[res])
            if n <= 0:
                self.msg(f"Турель полна или нет боеприпасов ({RES_INFO[res][0]})", (255, 200, 140))
                return
            p.res[res] -= n
            o["ammo"] = o.get("ammo", 0) + n
            self.msg(f"Турель заряжена: {o['ammo']}/{TURRET_CAP}", (180, 255, 180))
        elif t in PITS:
            if o.get("hidden"):
                self.msg("Яма уже замаскирована — враги её не видят")
            elif p.res["fiber"] < 3:
                self.msg("Нужно 3 волокна (траву/листья), чтобы замаскировать яму", (255, 170, 120))
            else:
                p.res["fiber"] -= 3
                o["hidden"] = True
                self.msg("Яма прикрыта листьями. Враг, который на неё наступит, провалится!", (180, 255, 180))
        elif t == "charred":
            p.res["coal"] += 2
            self.popup(pos[0] * TILE + 20, pos[1] * TILE, "+2 Уголь", (180, 180, 190))
            w.objects[pos] = {"t": "stump", "timer": random.uniform(160, 260)}
            w.timed.add(pos)
        elif t == "altar":
            f = w.factions[o["fac"]]
            if p.res["essence"] <= 0:
                self.msg("Алтарь ждёт эссенцию тьмы...", (200, 160, 255))
                return
            p.res["essence"] -= 1
            self.change_rel(f, 12)
            f["anger"] = 0
            self.msg(f"Ты возложил эссенцию на алтарь. {f['name']}: +12 к отношению", (200, 160, 255))
        elif t == "drop":
            left = []
            for it in o["items"]:
                if not self.give_tool(it, quiet=True):
                    left.append(it)
            for k, v in o["res"].items():
                p.res[k] += v
            o["res"] = {}
            o["items"] = left
            if not left:
                del w.objects[pos]
            self.sfx("pickup", vol=0.5)
            self.msg("Подобрал вещи" + (" (что-то не влезло)" if left else ""))
        elif t == "garden":
            if self.season() == "winter":
                self.msg("Зимой на грядке ничего не растёт — жди весны", (200, 220, 255))
            elif o["planted"] and o["grow"] < GARDEN_TIME and p.res.get("rot", 0) > 0:
                p.res["rot"] -= 1
                o["grow"] = min(GARDEN_TIME, o["grow"] + GARDEN_TIME * 0.4)
                self.msg("Удобрил грядку гнилью — растёт быстрее", (170, 220, 120))
            elif not o["planted"]:
                if p.res["berries"] < 2:
                    self.msg("Для посадки нужно 2 ягоды")
                    return
                p.res["berries"] -= 2
                o["planted"], o["grow"] = True, 0.0
                w.timed.add(pos)
                self.msg("Посадил ягодный куст. Дождь ускоряет рост.")
            elif o["grow"] >= GARDEN_TIME:
                p.res["berries"] += 6
                p.res["fiber"] += 1
                o["planted"], o["grow"] = False, 0.0
                self.popup(pos[0] * TILE + 20, pos[1] * TILE, "+6 Ягоды, +1 Волокно", (255, 120, 150))
            else:
                self.msg(f"Растёт... {int(o['grow'] / GARDEN_TIME * 100)}%")
        elif t == "trap":
            if not o["armed"]:
                o["armed"] = True
                self.msg("Капкан взведён")
        elif t == "ladder":
            ri = o.get("roof", w.roof_at(*pos))
            if ri < 0 or w.roofs[ri]["ruined"]:
                self.msg("Вышка разрушена — наверх не залезть")
                return
            p.tower_ret = (p.x, p.y)
            p.on_tower = list(pos)
            p.tower_roof = ri
            p.x, p.y = pos[0] * TILE + TILE / 2, pos[1] * TILE + TILE / 2
            self.map_timer = 0
            self.msg("Ты на вышке: ходи по площадке (WASD), строй турели (B), стреляй сверху. E — спуститься.",
                     (255, 230, 140))

    def sleep(self, heal):
        p = self.player
        if not self.is_night():
            self.msg("Спать можно только ночью")
            return
        for a in self.animals:
            d = math.hypot(a.x - p.x, a.y - p.y)
            danger = (not a.human and (a.hostile() or a.kind == "bear" or a.beh == "boss")) or \
                (a.human and not a.ally and self.fac_hostile(a.faction))
            if danger and d < 10 * TILE:
                self.msg("Рядом опасно — не уснуть!", (255, 140, 120))
                return
        k = 1 - heal / 120                              # чем лучше постель, тем меньше тратишь сил
        self.time = 0.26
        self.day += 1
        p.hunger = max(0, p.hunger - 30 * k)
        p.thirst = max(0, p.thirst - 35 * k)
        p.hp = min(100, p.hp + heal)
        p.warmth = 100
        p.wet = 0
        p.stamina = 100
        if heal >= 25 and p.cond.pop("cold", None):
            self.msg("Сон в тепле прогнал простуду", (160, 255, 160))
        for k in ("fracture", "burn", "frostbite", "dysentery"):
            if k in p.cond:
                p.cond[k] = max(1.0, p.cond[k] - 150)
        self.events.pop("blood_moon", None)
        self.animals = [a for a in self.animals if a.beh not in ("hunter", "shadow") and not a.raid]
        self.msg(f"Ты выспался (+{heal} HP). Наступил день {self.day}. Хищники стали сильнее...", (255, 230, 140))
        self.on_dawn()

    def interaction_hint(self):
        p = self.player
        if self.build_mode:
            if p.on_tower:
                return "СТРОЙКА НА ВЫШКЕ: турели, сундук, баррикада, факел · ЛКМ — поставить · X — снос"
            return ("СНОС: ЛКМ по своей постройке — разобрать (+50%)" if self.demolish
                    else "СТРОЙКА: ЛКМ — поставить · X — снос · B / ПКМ — выйти")
        if p.on_tower:
            return "На вышке: WASD — ходить по площадке · B — строить турели · E — спуститься"
        if p.fishing:
            return "Рыбалка... не двигайся"
        if self.player_in_water():
            return "Ты плывёшь: тратится выносливость, одежда промокает!"
        if p.held_id() in ("torch", "flint"):
            tx, ty = self.mouse_tile()
            o = self.world.objects.get((tx, ty))
            if o and o["t"] in FLAMMABLE and math.hypot(tx * TILE + 20 - p.x, ty * TILE + 20 - p.y) <= REACH + 10:
                return "[V] Поджечь"
        return ""

    # ------------------------------------------------------------ диалоги
    def open_dialog(self, a):
        if a.ally:
            self.dialog = {"npc": a, "page": "ally", "line": random.choice(
                ["Я рядом. Что прикажешь?", "Лес шумит тревожно. Я начеку.", "Скажи — и я пойду."])}
        else:
            f = self.world.factions[a.faction]
            if self.fac_hostile(a.faction):
                self.msg(f"{a.name} не станет говорить — он хочет твоей крови!", (255, 120, 110))
                return
            self.dialog = {"npc": a, "page": "main",
                           "line": random.choice(DIALOG["greetings"][f["type"]][self.attitude(f)])}
        self.menu = "dialog"

    def quest_progress(self, q):
        if q["type"] == "kill":
            return sum(self.kill_counts.get(k, 0) for k in q["kinds"]) - q["start"]
        return self.player.res[q["res"]]

    def player_power(self):
        p = self.player
        best = max([ITEMS[s["id"]]["dmg"] + ITEMS[s["id"]].get("ranged", {}).get("dmg", 0) for s in p.slots if s] or [1])
        return best + 12 * self.followers_count() + p.hp / 10 + 8 * p.armor

    def dialog_options(self):
        dg = self.dialog
        a = dg["npc"]
        p = self.player
        if dg["page"] == "ally":
            opts = [("Следуй за мной", "follow"), ("Охраняй это место", "stay")]
            if self.flag:
                opts.append(("Живи в поселении (у флага)" if not a.settler else "Возвращайся в поселение", "settle"))
            opts += [("Возвращайся домой (уйти от меня)", "dismiss"), ("Уйти", "bye")]
            return opts
        f = self.world.factions[a.faction]
        att = self.attitude(f)
        opts = []
        page = dg["page"]
        if page == "main":
            if f["type"] == "survivors" and not f.get("resolved", True):
                opts.append(("Я помогу! Идёмте в моё поселение", "rescue"))
                opts.append(("Держитесь, вот припасы… (подарить)", "gift_page"))
                opts.append(("Уйти", "bye"))
                return opts
            if f["greet_day"] != self.day:
                opts.append(("Поприветствовать", "greet"))
            opts.append(("Сделать подношение…", "gift_page"))
            if att in ("truce", "friend") or f["type"] in ("traders", "survivors"):
                opts.append(("Обменяться…", "trade_page"))
            q = f["quest"]
            if q is None:
                opts.append(("Чем я могу помочь?", "quest_new"))
            elif self.quest_progress(q) >= q["need"]:
                opts.append(("Задание выполнено!", "quest_done"))
            else:
                opts.append(("Напомни, что нужно сделать", "quest_info"))
            opts.append(("Расскажи об этих местах", "lore"))
            opts.append(("Поговорим о других людях…", "politics"))
            if a.role not in LEADERS and f["rel"] >= 50:
                opts.append(("Пригласить жить в моё поселение", "invite"))
            if att == "friend" and f["rel"] >= 80 and self.followers_count() < 3 and a.role not in LEADERS:
                opts.append(("Пойдёшь со мной в поход?", "recruit"))
            opts.append(("Говорить жёстко…", "tough"))
            opts.append(("Уйти", "bye"))
        elif page == "gift":
            likes = FACTION_TYPES[f["type"]].get("likes", {})
            for rid, v in GIFT_VALUE.items():
                if p.res[rid] > 0:
                    val = round(v * likes.get(rid, 1))
                    opts.append((f"Подарить: {RES_INFO[rid][0]}  (у тебя {p.res[rid]}, ценность {val})", "gift:" + rid))
            opts = opts[:11]
            opts.append(("Назад", "back"))
        elif page == "trade":
            trades = DIALOG["trades"][f["type"]]
            if f["trade_day"] != self.day or not f["trades"]:
                f["trade_day"] = self.day
                f["trades"] = random.sample(range(len(trades)), min(4, len(trades)))
            for i in f["trades"]:
                give, get = trades[i]
                gtxt = ", ".join(f"{v} {RES_INFO[k][0]}" for k, v in give.items())
                rtxt = ITEMS[get[1]]["name"] if get[0] == "tool" else f"{get[2]} {RES_INFO[get[1]][0]}"
                opts.append((f"Отдать {gtxt}  →  получить {rtxt}", f"trade:{i}"))
            opts.append(("Назад", "back"))
        elif page == "politics":
            for ti, other in enumerate(self.world.factions):
                if ti == a.faction or not other["alive"] or other["type"] == "survivors":
                    continue
                state = "уже воюем" if ti in f["wars"] else "давайте нападём вместе"
                opts.append((f"{other['name']}: {state}", f"war:{ti}"))
            opts = opts[:9]
            if f["help_day"] < self.day and self.followers_count() < 3:
                opts.append(("Дайте мне воинов в помощь (нужно отношение 70+)", "help"))
            opts.append(("Назад", "back"))
        elif page == "tough":
            opts.append(("Угрожать: «Отдавайте припасы, или пожалеете!»", "threaten"))
            opts.append(("«Убирайтесь с моего пути!»", "shoo"))
            opts.append(("«Я объявляю вам войну!»", "declare"))
            opts.append(("Назад", "back"))
        return opts

    def dialog_action(self, act):
        dg = self.dialog
        a = dg["npc"]
        p = self.player
        if act == "bye":
            self.menu, self.dialog = None, None
            return
        if a.ally:
            if act == "follow":
                a.stay, a.settler = False, False
                dg["line"] = "Иду за тобой."
            elif act == "stay":
                a.stay, a.settler = True, False
                dg["line"] = "Буду стоять здесь и защищать это место."
            elif act == "settle":
                if not self.flag:
                    return
                if not a.settler and len(self.settlers()) >= self.settle_capacity():
                    dg["line"] = DIALOG["invite_full"]
                    return
                self.make_settler(a)
                dg["line"] = "Иду к флагу. Найди мне работу в меню поселения."
            elif act == "dismiss":
                a.ally, a.stay, a.settler = False, False, False
                self.menu = None
                self.msg(f"{a.name} возвращается домой")
            return
        f = self.world.factions[a.faction]
        if act == "greet":
            f["greet_day"] = self.day
            self.change_rel(f, 3)
            dg["line"] = random.choice(DIALOG["greet_replies"])
        elif act in ("gift_page", "trade_page", "politics", "tough"):
            dg["page"] = act.replace("_page", "")
            dg["line"] = {"gift_page": "Что ты принёс? Дары не забываются.", "trade_page": "Сегодня можем дать вот это.",
                          "politics": "О ком ты хочешь говорить?", "tough": "Осторожнее со словами, чужак."}[act]
        elif act == "back":
            dg["page"] = "main"
        elif act.startswith("gift:"):
            rid = act[5:]
            if p.res[rid] <= 0:
                return
            p.res[rid] -= 1
            v = round(GIFT_VALUE[rid] * FACTION_TYPES[f["type"]].get("likes", {}).get(rid, 1))
            f["gift"] += v
            self.change_rel(f, v)
            if f["type"] == "survivors" and (rid in HEALS or rid in FOOD):
                for m in self.animals:
                    if m.faction == a.faction and not m.dead:
                        m.hp = min(m.max_hp, m.hp + m.max_hp * 0.3)
            if f["gift"] >= 10:
                while f["gift"] >= 10:
                    f["gift"] -= 10
                    f["truce"] = min(max(f["truce"], self.day) + 2, self.day + 6)
                dg["line"] = f"Дар принят. До конца дня {f['truce']} мы тебя не тронем."
                self.msg(f"Перемирие ({f['name']}) до конца дня {f['truce']}", (140, 255, 140))
            else:
                dg["line"] = f"Хороший дар. (до перемирия ещё {10 - f['gift']} ценности)"
        elif act.startswith("trade:"):
            give, get = DIALOG["trades"][f["type"]][int(act[6:])]
            if any(p.res[k] < v for k, v in give.items()):
                dg["line"] = "У тебя нет того, что нужно. Не трать моё время."
                return
            for k, v in give.items():
                p.res[k] -= v
            got = self.give_reward(get)
            self.change_rel(f, 2)
            dg["line"] = f"Честный обмен. Бери: {got}."
        elif act == "quest_new":
            q = dict(random.choice(DIALOG["quests"][f["type"]]))
            if q["type"] == "kill":
                q["start"] = sum(self.kill_counts.get(k, 0) for k in q["kinds"])
            f["quest"] = q
            dg["line"] = q["text"] + " Сделай это — и мы запомним."
        elif act == "quest_info":
            q = f["quest"]
            dg["line"] = f"{q['text']} (сделано: {max(0, self.quest_progress(q))}/{q['need']})"
        elif act == "quest_done":
            q = f["quest"]
            if q["type"] == "bring":
                p.res[q["res"]] -= q["need"]
            f["quest"] = None
            got = self.give_reward(random.choice(DIALOG["quest_rewards"]))
            self.change_rel(f, 25)
            dg["line"] = f"Ты сделал великое дело. Прими дар: {got}."
            self.log(f"Выполнено задание для: {f['name']}")
        elif act == "lore":
            dg["line"] = self.lore_line(a)
        elif act.startswith("war:"):
            ti = int(act[4:])
            target = self.world.factions[ti]
            if ti in f["wars"]:
                dg["line"] = "Мы уже воюем с ними. Помоги нам — убей их воинов."
            elif f["rel"] < 50:
                dg["line"] = DIALOG["alliance_no"]
            else:
                self.declare_war(a.faction, ti)
                self.change_rel(target, -30)
                for _ in range(3):
                    m = self.spawn_member(a.faction)
                    if m:
                        m.war_target = ti
                dg["line"] = DIALOG["alliance_yes"].format(target=target["name"])
                self.show_banner("Война", f"{f['name']} по твоему слову напали на {target['name']}!")
        elif act == "help":
            if f["rel"] < 70:
                dg["line"] = "Наши воины не пойдут за чужаком. (нужно отношение 70+)"
                return
            f["help_day"] = self.day + 1
            for _ in range(2):
                m = self.spawn_member(a.faction, near=(p.x, p.y), spread=2)
                if m:
                    m.ally, m.ally_until = True, self.day + 1
            dg["line"] = DIALOG["help_yes"]
        elif act == "invite":
            if not self.flag:
                dg["line"] = DIALOG["invite_noflag"]
            elif len(self.settlers()) >= self.settle_capacity():
                dg["line"] = DIALOG["invite_full"]
            else:
                self.make_settler(a)
                self.change_rel(f, 5)
                self.menu, self.dialog = None, None
                self.msg(f"{a.name}: «{DIALOG['invite_yes']}»", (140, 255, 140))
                self.log(f"{a.name} ({f['name']}) переехал в твоё поселение")
        elif act == "recruit":
            a.ally, a.raid, a.stay, a.ally_until, a.settler = True, False, False, 0, False
            self.menu, self.dialog = None, None
            self.msg(f"{a.name} теперь ходит с тобой и защищает тебя!", (140, 255, 140))
            self.log(f"{a.name} ({f['name']}) стал твоим спутником")
        elif act == "rescue":
            self.rescue(a.faction)
        elif act == "threaten":
            if f["threat_day"] == self.day:
                dg["line"] = "Ты уже грозил нам сегодня. Второй раз не сработает."
                return
            f["threat_day"] = self.day
            power = self.player_power()
            strength = 15 + 8 * sum(1 for m in self.animals if m.faction == a.faction and not m.ally
                                    and math.hypot(m.x - p.x, m.y - p.y) < 12 * TILE)
            if random.random() < power / (power + strength):
                loot = self.world.loot_chest(random, FACTION_TYPES[f["type"]]["camp"])
                got = []
                for k, v in list(loot["res"].items())[:3]:
                    p.res[k] += v
                    got.append(f"{v} {RES_INFO[k][0]}")
                self.change_rel(f, -15)
                dg["line"] = random.choice(DIALOG["threat_win"]) + " (получено: " + ", ".join(got) + ")"
            else:
                self.change_rel(f, -10)
                f["anger"] = 60
                self.menu, self.dialog = None, None
                self.msg(f"{a.name}: «{random.choice(DIALOG['threat_fail'])}»", (255, 110, 100))
        elif act == "shoo":
            self.change_rel(f, -8)
            dg["line"] = random.choice(DIALOG["shoo"])
            for m in self.animals:
                if m.faction == a.faction and not m.ally:
                    m.flee_t = 3
        elif act == "declare":
            f["truce"] = 0
            self.change_rel(f, -100)
            f["anger"] = 120
            self.menu, self.dialog = None, None
            self.msg(f"{a.name}: «{random.choice(DIALOG['war'])}»", (255, 110, 100))
            self.log(f"Ты объявил войну: {f['name']}")

    def lore_line(self, a):
        w = self.world
        best, bd = None, 1e9
        for i, (kind, r, fi) in enumerate(w.structs):
            d = math.hypot((r.centerx + 0.5) * TILE - a.x, (r.centery + 0.5) * TILE - a.y)
            if d < 9 * TILE:                       # свой дом — не новость
                w.seen.add(i)
            if i in w.seen:
                continue
            if d < bd:
                best, bd = i, d
        if best is None:
            return "Ты уже знаешь эти земли не хуже нас."
        kind, r, fi = w.structs[best]
        w.seen.add(best)
        self.map_timer = 0
        where = direction((r.centerx + 0.5) * TILE - a.x, (r.centery + 0.5) * TILE - a.y, DIALOG["directions"])
        name = DIALOG["struct_names"][kind] + (f" ({w.factions[fi]['name']})" if fi >= 0 else "")
        return f"На {where} отсюда, шагах в {int(bd / TILE)}, есть {name}. Я отметил это на твоей карте."

    # ------------------------------------------------------------ крушения и выжившие
    def start_crash(self):
        w = self.world
        p = self.player
        site = w.find_crash_site(random)
        if not site:
            return False
        fi = w.add_faction(random, "survivors", site, 6)
        f = w.factions[fi]
        f.update(crash_t=CRASH_TIME, resolved=False, found=False)
        si = w.build_crash(random, site[0], site[1], fi)
        w.seen.add(si)
        cx, cy = (site[0] + 0.5) * TILE, (site[1] + 0.5) * TILE
        for _ in range(random.randint(2, 4)):
            m = self.spawn_member(fi, "survivor", near=(cx, cy), spread=3)
            if m:
                m.hp = m.max_hp * random.uniform(0.35, 0.7)
        self.map_timer = 0
        where = direction(cx - p.x, cy - p.y, DIALOG["directions"])
        self.show_banner("Крушение!", f"Самолёт рухнул на {where}, шагах в {int(math.hypot(cx - p.x, cy - p.y) / TILE)} "
                         f"(отмечено на карте). Выжившие продержатся около суток — потом погибнут "
                         f"или построят свой лагерь. Там же ящики с припасами.")
        return True

    def update_crashes(self, dt):
        p = self.player
        for fi, f in enumerate(self.world.factions):
            if f["type"] != "survivors" or not f["alive"] or f.get("resolved", True):
                continue
            f["crash_t"] -= dt
            cx, cy = (f["center"][0] + 0.5) * TILE, (f["center"][1] + 0.5) * TILE
            if not f["found"] and math.hypot(p.x - cx, p.y - cy) < 8 * TILE:
                f["found"] = True
                self.msg("«Сюда! Мы здесь!» — выжившие машут тебе руками. Поговори с ними [E].", (255, 230, 150))
            members = [a for a in self.animals if a.faction == fi and not a.dead and not a.ally]
            if not members:
                f["resolved"], f["alive"] = True, False
                self.show_banner("Трагедия", f"Никто из выживших с {f['short']} не уцелел.")
                continue
            if f["crash_t"] <= 0:
                if random.random() < 0.5:
                    self.survivors_settle(fi)
                else:
                    for m in members:
                        m.dead = True
                        self.drop_at(m.x, m.y, [], {"bandage": 1, "cloth": 1})
                    f["resolved"], f["alive"] = True, False
                    self.show_banner("Помощь не пришла", f"Выжившие с {f['short']} погибли у обломков. "
                                     "Их вещи остались на месте крушения.")

    def survivors_settle(self, fi, helped=False):
        w = self.world
        f = w.factions[fi]
        f["resolved"] = True
        w.build_survivor_camp(random, f["center"][0], f["center"][1], fi)
        self.map_timer = 0
        if helped:
            self.change_rel(f, 30)
        self.show_banner("Новый лагерь", f"{f['name']} обустроили свой лагерь у обломков. Теперь это новая фракция.")

    def rescue(self, fi):
        w = self.world
        f = w.factions[fi]
        members = [m for m in self.animals if m.faction == fi and not m.dead and not m.ally]
        free = self.settle_capacity() - len(self.settlers()) if self.flag else 0
        moved = 0
        for m in members:
            if free > 0:
                self.make_settler(m)
                free -= 1
                moved += 1
            elif not self.flag and self.followers_count() < 3:
                m.ally, m.stay, m.ally_until = True, False, 0
                moved += 1
        f["resolved"] = True
        self.change_rel(f, 30)
        self.menu, self.dialog = None, None
        if moved == len(members):
            f["alive"] = False
            line = DIALOG["rescue_lines"]["settle" if self.flag else "follow"]
        else:
            self.survivors_settle(fi, helped=True)
            line = DIALOG["rescue_lines"]["camp"]
        self.msg(f"Выжившие: «{line}»", (140, 255, 140))
        self.log(f"Ты спас выживших с {f['short']} ({moved} чел. пошли с тобой)")

    # ------------------------------------------------------------ события
    def update_events(self, dt):
        for k in list(self.events):
            self.events[k] -= dt
            if self.events[k] <= 0:
                del self.events[k]
                if k == "storm":
                    self.weather = "clear"
                    self.msg("Ливень закончился", (200, 220, 255))
                elif k == "fog":
                    self.msg("Туман рассеялся", (220, 220, 220))
                elif k == "drought":
                    self.msg("Жара спала", (220, 220, 220))
                elif k == "blizzard":
                    self.msg("Метель утихла", (220, 230, 255))
        self.event_timer -= dt
        if self.event_timer > 0:
            return
        self.event_timer = random.uniform(140, 260)
        night = self.is_night()
        season = self.season()
        ok = []
        for eid, e in EVENTS.items():
            if eid in self.events:
                continue
            if eid == "blizzard" and season != "winter":
                continue
            if eid in ("storm", "wildfire", "drought", "migration") and season == "winter":
                continue
            if eid == "drought" and season != "summer":
                continue
            if eid == "wildfire" and (night or self.raining() or self.day < 2):
                continue
            if eid in ("fog", "drought") and self.raining():
                continue
            if eid == "blood_moon" and not (0.55 < self.time < 0.72 and self.day >= 3):
                continue
            if eid == "caravan" and not any(f["type"] == "traders" and f["alive"] and self.attitude(f) != "hostile"
                                            for f in self.world.factions):
                continue
            if eid == "crash" and (self.day < 2 or any(f["type"] == "survivors" and f["alive"] and not f.get("resolved", True)
                                                       for f in self.world.factions)):
                continue
            ok += [eid] * e["weight"]
        if ok:
            self.start_event(random.choice(ok))

    def start_event(self, eid):
        e = EVENTS[eid]
        p = self.player
        w = self.world
        if eid == "crash":
            self.start_crash()
            return
        if "duration" in e:
            self.events[eid] = random.uniform(*e["duration"])
        if eid == "storm":
            self.weather = "storm"
            for pos in list(w.burning):
                w.burning[pos] = min(w.burning[pos], 1.0)
        elif eid == "blood_moon":
            self.events[eid] = DAY_LENGTH * 0.5
        elif eid == "wildfire":
            started = 0
            for _ in range(400):
                tx = int(p.x // TILE) + random.randint(-30, 30)
                ty = int(p.y // TILE) + random.randint(-30, 30)
                o = w.objects.get((tx, ty))
                if o and o["t"] == "tree" and math.hypot(tx * TILE - p.x, ty * TILE - p.y) > 14 * TILE and w.ignite((tx, ty)):
                    started += 1
                    if started >= 3:
                        break
            if not started:
                return
        elif eid == "caravan":
            fi = next(i for i, f in enumerate(w.factions) if f["type"] == "traders" and f["alive"])
            a = random.uniform(0, math.tau)
            spot = (p.x + math.cos(a) * 12 * TILE, p.y + math.sin(a) * 12 * TILE)
            for role in ("trader", "guard", "guard"):
                m = self.spawn_member(fi, role, near=spot)
                if m:
                    m.visitor_t = 150
        elif eid == "migration":
            a = random.uniform(0, math.tau)
            spot = (p.x + math.cos(a) * 14 * TILE, p.y + math.sin(a) * 14 * TILE)
            for _ in range(8):
                self.spawn_animal("deer", around=spot)
        elif eid == "airdrop":
            for _ in range(200):
                a = random.uniform(0, math.tau)
                d = random.uniform(15, 25) * TILE
                tx, ty = int((p.x + math.cos(a) * d) // TILE), int((p.y + math.sin(a) * d) // TILE)
                if w.free_tile(tx, ty) and w.ground[ty][tx] != FLOOR:
                    w.objects[(tx, ty)] = w.loot_chest(random, "airdrop")
                    w.structs.append(["airdrop", pygame.Rect(tx, ty, 1, 1), -1])
                    w.seen.add(len(w.structs) - 1)
                    self.map_timer = 0
                    where = direction(tx * TILE - p.x, ty * TILE - p.y, DIALOG["directions"])
                    bandits = [i for i, f in enumerate(w.factions) if f["type"] == "bandits" and f["alive"]]
                    if bandits:
                        for _ in range(2):
                            m = self.spawn_member(random.choice(bandits), near=(tx * TILE, ty * TILE), spread=4)
                            if m:
                                m.home = [tx * TILE + 20, ty * TILE + 20]
                    self.show_banner(e["name"], f"Ящик упал на {where}, шагах в {int(d / TILE)}. За ним уже идут бандиты!")
                    return
            return
        self.show_banner(e["name"], e["text"])

    def on_dawn(self):
        self.check_season_change()
        self.events.pop("blood_moon", None)
        self.war_parties()
        self.settlement_produce()
        self.save_game(auto=True)

    # ------------------------------------------------------------ сохранение
    def save_game(self, auto=False, new_slot=False):
        w = self.world
        if new_slot:
            self.slot = saves.make_slot_id(self.settings["name"])
        data = {
            "version": VERSION,
            "world": {"w": w.w, "h": w.h, "seed": w.seed, "ground": w.ground, "shade": w.shade,
                      "objects": [[x, y, o] for (x, y), o in w.objects.items()],
                      "deck": [[x, y, o] for (x, y), o in w.deck.items()],
                      "timed": [list(t) for t in w.timed], "fires": [list(t) for t in w.fires],
                      "burning": [[x, y, t] for (x, y), t in w.burning.items()],
                      "structs": [[k, r.x, r.y, r.w, r.h, fi] for k, r, fi in w.structs],
                      "roofs": w.roofs, "factions": w.factions,
                      "own_floor": [list(t) for t in w.own_floor], "seen": list(w.seen),
                      "lairs": w.lairs, "radio": w.radio},
            "player": self.player.__dict__,
            "animals": [a.__dict__ for a in self.animals if not a.dead],
            "game": {k: getattr(self, k) for k in SAVE_FIELDS},
        }
        meta = {"name": self.settings["name"], "day": self.day, "size": self.settings["size"],
                "diff": self.settings["diff"], "seed": w.seed}
        try:
            saves.write(self.slot, data, meta)
            self.msg("Автосохранение" if auto else f"Игра сохранена в слот «{self.slot}»", (140, 255, 140))
        except OSError as e:
            self.msg(f"Не удалось сохранить: {e}", (255, 120, 110))

    def load_game(self, slot):
        try:
            data = saves.read(slot)
            wd = data["world"]
            w = World.__new__(World)
            w.rng = random.Random()
            w.w, w.h, w.seed = wd["w"], wd["h"], wd["seed"]
            w.ground, w.shade = wd["ground"], wd["shade"]
            w.objects = {(x, y): o for x, y, o in wd["objects"]}
            w.deck = {(x, y): o for x, y, o in wd.get("deck", [])}
            w.timed = {tuple(t) for t in wd["timed"]}
            w.fires = {tuple(t) for t in wd["fires"]}
            w.burning = {(x, y): t for x, y, t in wd["burning"]}
            w.structs = [[k, pygame.Rect(x, y, rw, rh), fi] for k, x, y, rw, rh, fi in wd["structs"]]
            w.roofs, w.factions = wd["roofs"], wd["factions"]
            w.own_floor = {tuple(t) for t in wd["own_floor"]}
            w.seen = set(wd["seen"])
            w.grow_mult = 1.0
            if "lairs" in wd:
                w.lairs, w.radio = wd["lairs"], wd.get("radio")
            w.fix_after_load()
            player = Player(0, 0)
            player.__dict__.update(data["player"])
            for k in RES_INFO:                       # новые ресурсы из обновлений
                player.res.setdefault(k, 0)
            for c in CRAFTS:                         # новые рецепты без изучения
                if not c.get("research") and c["id"] not in player.known:
                    player.known.append(c["id"])
            if player.on_tower and player.tower_roof < 0:
                player.on_tower = None
            animals = []
            for ad in data["animals"]:
                a = Creature(ad["kind"], 0, 0)
                a.__dict__.update(ad)
                animals.append(a)
            game = data["game"]
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.msg(f"Не удалось загрузить: {e}", (255, 120, 110))
            return False
        self.world, self.player, self.animals = w, player, animals
        self.flag = None
        self.spoil_acc = {}                      # нет в сохранениях до v1.6 — иначе AttributeError
        self.new_story()
        for k, v in game.items():
            setattr(self, k, v)
        self.fix_story()
        self.reset_transient()
        self.ensure_bosses()
        self.msg(f"Загружено: {self.settings['name']}, день {self.day}", (140, 255, 140))
        return True

    # ------------------------------------------------------------ обновление
    def update(self, dt):
        p = self.player
        w = self.world
        self.clock_t += dt
        prev = self.time
        self.time = (self.time + dt / DAY_LENGTH) % 1.0
        if prev < 0.25 <= self.time:
            self.day += 1
            self.msg(f"Рассвет. День {self.day}. Хищники стали сильнее...", (255, 230, 140))
            self.on_dawn()
        if prev < 0.72 <= self.time:
            shadows = self.day >= 2 and not self.story["heart"]
            self.msg("Темнеет... Волки выходят на охоту" + (", а из чащи ползут Тени" if shadows else "") +
                     ". Разведи костёр!", (255, 180, 120))
        self.update_weather(dt)
        self.update_events(dt)
        self.update_crashes(dt)
        self.update_story(dt)
        season = self.season()
        w.season = season
        w.frozen = season == "winter"
        broken = p.cond.get("fracture", 0) > 0

        # движение
        keys = pygame.key.get_pressed()
        mx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        my = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        in_water = self.player_in_water()
        sprint = False
        p.moving = bool(mx or my) and self.menu is None
        if p.moving:
            ln = math.hypot(mx, my)
            if p.on_tower:                                       # ходим по площадке вышки
                x, y, rw, rh = self.tower_rect()
                p.x = clamp(p.x + mx / ln * 140 * dt, x * TILE + 10, (x + rw) * TILE - 10)
                p.y = clamp(p.y + my / ln * 140 * dt, y * TILE + 10, (y + rh) * TILE - 10)
            else:
                sprint = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and not p.exhausted and not in_water \
                    and not broken
                speed = 170 * (1.6 if sprint else 1.0) * w.speed_mult(p.x, p.y) * (0.6 if broken else 1.0)
                if in_water:
                    speed *= SWIM_SLOW
                    p.stamina -= 6 * dt
                move_entity(w, p, mx / ln * speed * dt, my / ln * speed * dt, swim=True, doors=True)
            p.walk_t += dt * (12 if sprint else 8)
            if p.fishing:
                p.fishing = None
                self.msg("Рыба ушла — во время рыбалки нельзя двигаться", (255, 200, 140))
        if sprint:
            p.stamina -= 22 * dt
            p.thirst -= 0.15 * dt
        elif in_water:
            p.stamina -= 2 * dt
        else:
            sick = p.cond.get("cold", 0) > 0 or p.cond.get("infection", 0) > 0
            p.stamina = min(60 if sick else 100, p.stamina + (7 if sick else 14) * dt)
            if p.exhausted and p.stamina > 30:
                p.exhausted = False
        if in_water and not self.was_in_water:
            self.sfx("splash", vol=0.6)
        self.was_in_water = in_water
        if p.stamina <= 0:
            p.stamina = 0
            p.exhausted = True
            if in_water:
                p.damage(8 * dt, "утопления")
                p.hurt = max(p.hurt, 0.1)
                self.msg("Ты тонешь! Выбирайся на берег!", (255, 110, 110))
        mxp, myp = pygame.mouse.get_pos()
        p.angle = math.atan2(myp + self.cam_y - (p.y - (DECK_H if p.on_tower else 0)), mxp + self.cam_x - p.x)

        # рыбалка
        if p.fishing:
            p.fishing[0] -= dt
            if p.fishing[0] <= 0:
                if random.random() < 0.7 + 0.03 * self.skill_lvl("fishing"):
                    p.res["fish"] += 1
                    self.popup(p.x, p.y - 30, "+1 Рыба", (150, 200, 255))
                    self.add_xp("fishing", 8)
                    self.sfx("splash", vol=0.4)
                    self.wear_held()
                else:
                    self.popup(p.x, p.y - 30, "Сорвалась!", (220, 220, 220))
                p.fishing = None

        # влажность, тепло и биомы
        dark = self.darkness()
        g = w.ground_at(p.x, p.y) if not p.on_tower else FLOOR
        near_fire = w.nearest_fire(p.x, p.y, 3.5 * TILE) is not None or w.burning_near(p.x, p.y, 2) is not None
        sheltered = self.sheltered()
        if in_water:
            if p.wet < 99:
                self.msg("Ты промок до нитки — потом обязательно погрейся у костра", (150, 200, 255))
            p.wet = 100
            if p.held_id() == "torch":
                self.wear_held(25 * dt)
        elif self.raining() and not sheltered and not near_fire:
            p.wet += (1.5 if season == "winter" else 9 if self.weather == "storm" else 4) * dt
        elif g == SWAMP and not near_fire:
            p.wet = min(70, p.wet + 1.5 * dt)
        else:
            p.wet -= (14 if near_fire else 2.5 if dark < 0.3 else 0.8) * dt
        p.wet = clamp(p.wet, 0, 100)

        thirst_k = (1.5 if "drought" in self.events else 1.0) * (1.3 if g == STEPPE and dark < 0.5 else 1.0) * \
            (1.2 if season == "summer" else 1.0)
        dys = 2.0 if p.cond.get("dysentery", 0) > 0 else 1.0
        p.hunger -= 0.2 * dt * self.needs_mult * dys
        p.thirst -= 0.28 * dt * self.needs_mult * thirst_k * dys
        if near_fire:
            p.warmth += 6 * dt
        else:
            night_k = {"winter": 1.5, "autumn": 1.2, "summer": 0.6}.get(season, 1.0)
            loss = (0.9 * dark * night_k if dark > 0.3 else 0) + 1.6 * p.wet / 100 + (0.5 if g == SNOW else 0)
            if season == "winter":
                loss += 0.6                                    # зимой холодно и днём
            if "blizzard" in self.events and not sheltered:
                loss += 1.2
            if p.cond.get("cold", 0) > 0:
                loss *= 1.3
            if loss > 0:
                if p.cloak:
                    loss *= 0.35 if p.wet < 50 else 0.7     # мокрая накидка греет хуже
                if ITEMS.get(p.held_id() or "", {}).get("warm"):
                    loss *= 0.5
                if sheltered:
                    loss *= 0.5
                p.warmth -= loss * dt
            else:
                p.warmth += 1.5 * dt
        p.hunger = clamp(p.hunger, 0, 100)
        p.thirst = clamp(p.thirst, 0, 100)
        p.warmth = clamp(p.warmth, 0, 100)
        if p.hunger <= 0:
            p.damage(1.5 * dt, "голода")
        if p.thirst <= 0:
            p.damage(2.0 * dt, "жажды")
        if p.warmth <= 0:
            p.damage(1.5 * dt, "холода")
        if p.poison > 0:
            p.poison -= dt
            p.damage(1.5 * dt, "яда")
        if (int(p.x // TILE), int(p.y // TILE)) in w.burning and not p.on_tower:
            p.damage(10 * dt, "огня")
            p.hurt = max(p.hurt, 0.1)
            p.cond["burn"] = max(p.cond.get("burn", 0), 120)
        self.update_conditions(dt)
        no_regen = p.poison > 0 or any(p.cond.get(k, 0) > 0 for k in ("bleed", "infection", "burn"))
        if p.hunger > 50 and p.thirst > 50 and p.warmth > 30 and p.hp < 100 and not no_regen:
            p.hp = min(100, p.hp + 0.5 * dt)
        self.update_spoil(dt)
        # частицы: кровь на земле, пар изо рта на морозе
        for b in self.blood:
            b[2] -= dt
        self.blood = [b for b in self.blood if b[2] > 0][-200:]
        if (season == "winter" or (dark > 0.6 and season == "autumn")) and not in_water and random.random() < dt * 0.8:
            self.breath.append([p.x + math.cos(p.angle) * 14, p.y + math.sin(p.angle) * 14 - (DECK_H if p.on_tower else 0), 1.2])
        for b in self.breath:
            b[1] -= 8 * dt
            b[2] -= dt
        self.breath = [b for b in self.breath if b[2] > 0]

        held = ITEMS.get(p.held_id() or "", {})
        if held.get("light") and not held.get("legend"):        # факел и фонарь прогорают, клинок рассвета — нет
            self.wear_held(dt)
        p.cd -= dt
        p.swing = max(0, p.swing - dt)
        p.flash = max(0, p.flash - dt)
        p.hurt -= dt
        self.shake = max(0, self.shake - dt)
        self.flash_t = max(0, self.flash_t - dt)
        self.build_cd -= dt
        for ex in self.explosions:
            ex[2] -= dt
        self.explosions = [ex for ex in self.explosions if ex[2] > 0]

        self.hover = self.compute_hover() if self.menu is None and not self.build_mode else None
        if pygame.mouse.get_pressed()[0] and self.menu is None:
            if self.build_mode:
                if not self.over_palette(pygame.mouse.get_pos()):
                    self.try_build()
            elif not self.over_queue(pygame.mouse.get_pos()):
                self.try_use()
        self.update_projectiles(dt)
        self.update_crafting(dt)
        self.update_turrets(dt)

        rain = self.raining()
        w.grow_mult = 0.0 if season == "winter" else 2.0 if rain else 1.0
        w.update(dt, fire_mult={"storm": 4.0, "rain": 2.0}.get(self.weather, 1.0))
        spread = (2.0 if "drought" in self.events else 1.0)
        self.after_burn(w.update_fire(dt, spread, rain))
        for a in self.animals:
            a.update(self, dt)
        self.animals = [a for a in self.animals if not a.dead]
        self.update_factions(dt)
        self.spawn_tick(dt)

        self.seen_timer -= dt
        if self.seen_timer <= 0:
            self.seen_timer = 1.0
            for i, (kind, r, fi) in enumerate(w.structs):
                if i not in w.seen and math.hypot((r.centerx + 0.5) * TILE - p.x, (r.centery + 0.5) * TILE - p.y) < 10 * TILE:
                    w.seen.add(i)
                    self.map_timer = 0
                    name = DIALOG["struct_names"][kind] + (f" — {w.factions[fi]['name']}" if fi >= 0 else "")
                    self.msg(f"Ты нашёл: {name}", (255, 230, 150))
                    self.log(f"Найдено: {name}")

        for pp in self.popups:
            pp[1] -= 30 * dt
            pp[4] -= dt
        self.popups = [pp for pp in self.popups if pp[4] > 0]
        self.hint = self.interaction_hint()

        if p.hp <= 0:
            p.hp = 0
            self.dead = True
            self.log(f"Гибель от {p.cause}")

    def update_weather(self, dt):
        if self.weather == "storm":
            self.lightning_t -= dt
            if self.lightning_t <= 0:
                self.lightning_t = random.uniform(5, 12)
                self.flash_t = 0.15
                p = self.player
                for _ in range(30):
                    tx = int(p.x // TILE) + random.randint(-18, 18)
                    ty = int(p.y // TILE) + random.randint(-14, 14)
                    o = self.world.objects.get((tx, ty))
                    if o and o["t"] == "tree":
                        self.world.objects[(tx, ty)] = {"t": "charred"}
                        self.popup(tx * TILE + 20, ty * TILE, "Молния!", (255, 255, 200))
                        break
                self.sfx("thunder", vol=0.8)
            return
        self.weather_t -= dt
        if self.weather_t > 0:
            return
        if self.weather == "rain":
            self.weather, self.weather_t = "clear", random.uniform(150, 280)
            self.msg("Дождь закончился", (200, 220, 255))
        elif random.random() < {"autumn": 0.7, "summer": 0.35}.get(self.season(), 0.5) and "drought" not in self.events:
            self.weather, self.weather_t = "rain", random.uniform(60, 140)
            if self.season() == "winter":
                self.msg("Пошёл снег", (220, 230, 255))
            else:
                self.msg("Начинается дождь — найди укрытие, иначе промокнешь", (170, 200, 255))
        else:
            self.weather_t = random.uniform(100, 200)

    def spawn_tick(self, dt):
        self.passive_timer -= dt
        k = (self.world.w / 160) ** 2
        season = self.season()
        if self.passive_timer <= 0:
            self.passive_timer = 3
            kinds = list(PASSIVE_CAP)
            random.shuffle(kinds)
            for kind in kinds:
                cap = PASSIVE_CAP[kind] * k * SEASON_CAP[season].get(kind, 1.0)
                if sum(1 for a in self.animals if a.kind == kind) < cap:
                    self.spawn_animal(kind)
                    break
        winter = season == "winter"
        if not self.is_night() and not winter:
            return
        blood = 2 if "blood_moon" in self.events else 1
        self.wolf_timer -= dt * blood * (1.0 if self.is_night() else 0.4)
        if self.wolf_timer <= 0:
            self.wolf_timer = random.uniform(7, 13)
            wolves = sum(1 for a in self.animals if a.beh == "hunter")
            cap = (min(1 + self.day, 10) + (2 if winter else 0)) * blood
            if self.is_night() and wolves < cap:
                self.sfx("howl", vol=0.45)
            if wolves < cap:
                leader = None
                if self.day >= 3 and random.random() < 0.35 and not any(a.kind == "alpha" for a in self.animals):
                    leader = self.spawn_animal("alpha", min_d=14, max_d=20)
                    if leader:
                        self.msg("Вдалеке воет вожак стаи...", (255, 140, 110))
                if leader is None:
                    leader = self.spawn_animal("wolf", min_d=14, max_d=20)
                pack = 0 if self.day == 1 else random.randint(1, 2)
                for _ in range(min(pack, cap - wolves - 1)):
                    if leader:
                        m = self.spawn_animal("wolf", around=(leader.x, leader.y))
                        if m:
                            m.color = list(leader.color) if leader.kind == "wolf" else m.color
        if not self.is_night():
            return
        if self.day >= 2 and not self.story["heart"]:          # после разбитого Чёрного сердца Тени не приходят
            self.shadow_timer -= dt * blood
            if self.shadow_timer <= 0:
                self.shadow_timer = random.uniform(15, 25)
                if sum(1 for a in self.animals if a.kind == "shadow") < min(self.day - 1, 4) + 2 * (blood - 1):
                    self.spawn_animal("shadow", min_d=11, max_d=15)
        self.raid_timer -= dt
        if self.raid_timer <= 0:
            self.raid_timer = 30
            p = self.player
            for fi, f in enumerate(self.world.factions):
                if not f["alive"] or not FACTION_TYPES[f["type"]]["raids"]:
                    continue
                if self.attitude(f) == "hostile" and f["raid_day"] != self.day and random.random() < 0.5:
                    f["raid_day"] = self.day
                    if self.flag and random.random() < 0.6:        # набег на поселение
                        target = ((self.flag[0] + 0.5) * TILE, (self.flag[1] + 0.5) * TILE)
                    else:
                        target = (p.x, p.y)
                    a = random.uniform(0, math.tau)
                    spot = (target[0] + math.cos(a) * 15 * TILE, target[1] + math.sin(a) * 15 * TILE)
                    for _ in range(2 if self.day < 4 else random.randint(2, 4)):
                        self.spawn_member(fi, near=spot, raid=True)
                    self.msg(f"Слышен шум... {f['name']} идёт набегом!", (255, 110, 100))
                    self.log(f"Набег: {f['name']}")

    def tick_ui(self, dt):
        for m in self.messages:
            m[2] -= dt
        self.messages = [m for m in self.messages if m[2] > 0]
        self.map_timer -= dt
        if self.banner:
            self.banner[2] -= dt
            if self.banner[2] <= 0:
                self.banner = None
