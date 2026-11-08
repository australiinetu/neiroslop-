# -*- coding: utf-8 -*-
"""
NeTheForest
Top-down выживание, стройка и дипломатия на Python + pygame-ce.

Запуск:  python survival.py

Код игры лежит в папке game/, игровые данные (предметы, рецепты, фракции, события, лут) — в data/*.json,
сохранения — в saves/.
"""
import sys

try:
    import pygame  # noqa: F401
except ImportError:
    print("Не найден pygame. Установи его командой:  python -m pip install pygame-ce")
    input("Нажми Enter для выхода...")
    sys.exit(1)

from game.main import run

if __name__ == "__main__":
    run()
