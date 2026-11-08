# -*- coding: utf-8 -*-
"""Общие настройки игры. Игровые данные (предметы, рецепты, фракции...) лежат в папке data/."""
import os

VERSION = "1.6"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SAVE_DIR = os.path.join(BASE_DIR, "saves")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
TILE = 40
DAY_LENGTH = 300.0          # длина суток в секундах
REACH = 1.9 * TILE          # дальность действия руками
BUILD_REACH = 4.5 * TILE    # дальность стройки
DARK_RGB = (6, 8, 28)
FOG_RGB = (170, 176, 184)
TREE_SLOW = 0.55            # замедление в чаще
SWIM_SLOW = 0.55            # замедление в воде
DITCH_SLOW = 0.35           # замедление во рву
GARDEN_TIME = 150.0         # сколько растёт грядка
MAX_BURNING = 350           # предел одновременно горящих клеток
CHEST_TOOLS = 9
BAG_SIZES = [6, 10, 14]     # размер рюкзака: без сумки / сумка / большой рюкзак
CRAFT_QUEUE = 8
DECK_H = 34                 # насколько площадка вышки поднята над землёй (в пикселях)
SETTLE_RADIUS = 10          # радиус поселения вокруг флага (в клетках)
CRASH_TIME = 300.0          # сколько выжившие ждут помощи после крушения (секунд)
SEASON_DAYS = 4             # сколько дней длится одно время года
SEASONS = [("spring", "Весна"), ("summer", "Лето"), ("autumn", "Осень"), ("winter", "Зима")]
SKILLS = [("chop", "Рубка"), ("mine", "Добыча"), ("hunt", "Охота"), ("combat", "Ближний бой"),
          ("archery", "Стрельба"), ("medicine", "Медицина"), ("craft", "Ремесло"), ("fishing", "Рыбалка")]
SKILL_MAX = 10

GRASS, WATER, SAND, FLOOR, DITCH, SNOW, SWAMP, STEPPE, ROCKY, MEADOW = range(10)
GROUND_COL = {GRASS: (66, 128, 58), WATER: (42, 94, 162), SAND: (198, 184, 122), FLOOR: (122, 92, 62),
              DITCH: (70, 50, 34), SNOW: (222, 228, 236), SWAMP: (72, 94, 60), STEPPE: (178, 168, 96),
              ROCKY: (122, 118, 112), MEADOW: (88, 148, 64)}
LAND = {GRASS, SNOW, SWAMP, STEPPE, ROCKY, MEADOW}
BIOME_NAMES = {GRASS: "Лес", SNOW: "Тайга", SWAMP: "Болото", STEPPE: "Степь", ROCKY: "Горы", SAND: "Пляж",
               WATER: "Вода", FLOOR: "Постройка", DITCH: "Ров", MEADOW: "Цветочная поляна"}
BIOME_IDS = {"grass": GRASS, "snow": SNOW, "swamp": SWAMP, "steppe": STEPPE, "rocky": ROCKY, "sand": SAND,
             "meadow": MEADOW}
LAIR_RADIUS = 7             # с какого расстояния от логова босс замечает тебя (в клетках)
LAIR_LEASH = 15             # дальше этого босс не уходит от логова
RESCUE_TIME = 300.0         # через сколько секунд после сигнала SOS прилетит вертолёт


def tile_hash(x, y, salt=0):
    """Случайное, но постоянное число для клетки (без косых полос, как у x*a+y*b)."""
    n = (x * 374761393 + y * 668265263 + salt * 2246822519) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return n ^ (n >> 16)

# параметры генерации мира: id -> (название, значение)
WORLD_SIZES = {"small": ("Маленький", 120), "medium": ("Средний", 160), "large": ("Большой", 210)}
DIFFICULTIES = {"easy": ("Лёгкая", 0.6, 0.8), "normal": ("Нормальная", 1.0, 1.0), "hard": ("Тяжёлая", 1.4, 1.25)}
DENSITIES = {"sparse": ("Редкий лес", 0.6), "normal": ("Обычный лес", 1.0), "dense": ("Густой лес", 1.45)}
FACTION_AMOUNTS = {
    "few": ("Мало", {"tribe": 2, "bandits": 1, "traders": 1, "cult": 0}),
    "normal": ("Обычно", {"tribe": 3, "bandits": 1, "traders": 1, "cult": 1}),
    "many": ("Много", {"tribe": 4, "bandits": 2, "traders": 1, "cult": 1}),
}
