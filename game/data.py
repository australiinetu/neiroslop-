# -*- coding: utf-8 -*-
"""Загрузка игровых данных из data/*.json — их можно править без изменения кода."""
import json
import os

from .config import DATA_DIR, BIOME_IDS


def _load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data.pop("_info", None)
    return data


_res = _load("resources.json")
RES_INFO = {k: (v["name"], tuple(v["color"])) for k, v in _res.items()}
FOOD = {k: tuple(v["food"]) for k, v in _res.items() if "food" in v}
HEALS = {k: v["heal"] for k, v in _res.items() if "heal" in v}
CURES = {k: set(v["cures"]) for k, v in _res.items() if v.get("cures")}   # что лечит: bleed, poison, cold...
SPOIL = {k: v["spoil"] for k, v in _res.items() if v.get("spoil")}         # доля, что портится за минуту
GIFT_VALUE = {k: v["gift"] for k, v in _res.items() if v.get("gift")}
QUEST_RES = {k for k, v in _res.items() if v.get("quest")}                  # детали рации
USABLE = tuple(dict.fromkeys(list(FOOD) + ["meat"] + list(HEALS) + list(CURES)))
CONDITIONS = {"bleed": ("Кровотечение", (230, 60, 60), "бинт или аптечка"),
              "infection": ("Заражение", (190, 200, 60), "аптечка или мазь"),
              "fracture": ("Перелом", (230, 230, 230), "шина"),
              "burn": ("Ожог", (255, 150, 60), "мазь или аптечка"),
              "cold": ("Простуда", (150, 200, 255), "отвар или сон в кровати"),
              "dysentery": ("Дизентерия", (170, 140, 80), "отвар; пей кипячёную воду"),
              "frostbite": ("Обморожение", (180, 220, 255), "мазь или тепло костра"),
              "poison": ("Отравление", (150, 255, 110), "отвар или аптечка")}

ITEMS = _load("items.json")
for _it in ITEMS.values():
    _it.setdefault("anim", "swing")
    _it.setdefault("cd", 0.45)
    _it.setdefault("chop", 1)
    _it.setdefault("mine", 0)
    _it.setdefault("reach", 1.0)
HANDS = {"name": "Голые руки", "dmg": 1.5, "chop": 1, "mine": 0, "anim": "swing", "cd": 0.45, "reach": 1.0}

CRAFTS = _load("recipes.json")
CRAFT_BY_ID = {c["id"]: c for c in CRAFTS}
BUILDS = _load("builds.json")
BUILD_BY_ID = {b["id"]: b for b in BUILDS}
BUILD_CATS = [("base", "Основа"), ("defense", "Стены"), ("traps", "Ловушки"), ("home", "Жильё")]
ANIMALS = _load("creatures.json")
for _a in ANIMALS.values():
    _a["biome_ids"] = {BIOME_IDS[b] for b in _a.get("biomes", ["grass", "snow", "swamp", "steppe", "rocky"])}
LOOT = _load("loot.json")
_fac = _load("factions.json")
FACTION_TYPES = _fac["types"]
ROLES = _fac["roles"]
DIALOG = _load("dialog.json")
EVENTS = _load("events.json")
LORE = _load("lore.json")
LAIRS = LORE["lairs"]
NOTES = {n["id"]: n for n in LORE["notes"]}
ENDINGS = LORE["endings"]

BENCH_TIER = {"bench1": 1, "bench2": 2, "bench3": 3}
TURRETS = {"turret": "arrows", "gun_turret": "ammo"}       # турель -> чем стреляет
HEARTS = {"totem", "camp_banner", "altar"}                  # «сердце» лагеря фракции
PITS = {"pit", "spiked_pit"}

# что нельзя проходить насквозь (деревья — можно, но медленно)
BLOCKING = {"rock", "ore", "coal_node", "wall_old", "hut_wall", "tower_wall", "table", "totem", "altar", "pillar",
            "wreck_part", "menhir", "ice_spike", "den", "radio_mast", "dark_heart", "heli"} | \
           {b["id"] for b in BUILDS if b.get("blocking")}
DOORS = {"door", "iron_door"}
HITBOX = {"rock": (4, 6, 32, 30), "ore": (4, 6, 32, 30), "coal_node": (4, 6, 32, 30), "chest": (6, 8, 28, 26),
          "table": (6, 6, 28, 28), "totem": (12, 8, 16, 28), "altar": (6, 10, 28, 22), "pillar": (10, 10, 20, 20),
          "bench1": (2, 8, 36, 26), "bench2": (2, 8, 36, 26), "bench3": (2, 8, 36, 26), "furnace": (4, 4, 32, 32),
          "turret": (6, 6, 28, 28), "gun_turret": (6, 6, 28, 28), "wreck_part": (2, 4, 36, 32),
          "menhir": (10, 6, 20, 30), "ice_spike": (10, 8, 20, 28), "den": (0, 4, 40, 34), "radio_mast": (12, 12, 16, 16),
          "dark_heart": (8, 8, 24, 24), "heli": (0, 0, 40, 40)}

# что ломается: id -> (ресурс, сколько выпадает, прочность)
BREAKABLE = {"wall_old": ("wood", 2, 8), "table": ("wood", 2, 6), "hut_wall": ("fiber", 2, 15),
             "tower_wall": ("wood", 2, 30), "totem": ("wood", 3, 30), "rack": ("wood", 1, 5),
             "pillar": ("stone", 3, 60), "altar": ("stone", 4, 80), "camp_banner": ("cloth", 1, 40),
             "wreck_part": ("scrap", 2, 40), "dark_heart": ("essence", 5, 150)}
for _b in BUILDS:
    if "hp" in _b:
        _k, _v = next(iter(_b["cost"].items()))
        BREAKABLE[_b["id"]] = (_k, max(1, _v // 2), _b["hp"])

FLAMMABLE = {"tree", "tuft", "bush", "reed", "dry_bush", "wall_old", "hut_wall", "tower_wall", "table", "rack",
             "totem", "bed_old", "tent_old", "mat", "garden", "drop", "camp_banner"} | \
            {b["id"] for b in BUILDS if b.get("flammable")}
SLEEP = {"bed": 20, "tent_old": 25, "mat": 25, "bed_old": 30, "tent": 40, "bigbed": 60}
INTERACTIVE = {"fire", "chest", "ladder", "drop", "garden", "trap", "charred", "altar", "door", "iron_door", "flag",
               "furnace", "smokehouse", "cellar", "bones", "hive", "radio", "heli", "flower"} | \
              set(SLEEP) | set(BENCH_TIER) | set(TURRETS) | PITS
STORAGE = {"chest", "flag", "cellar"}
GATHER = {"tree", "rock", "ore", "coal_node", "bush", "tuft", "pebble", "charred", "reed", "mushroom", "toadstool",
          "dry_bush", "flower"}
LIGHT_OBJ = {b["id"]: b["light"] for b in BUILDS if b.get("light")}
