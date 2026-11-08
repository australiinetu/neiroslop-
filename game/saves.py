# -*- coding: utf-8 -*-
"""Слоты сохранений: saves/<слот>.json (мир) + saves/<слот>.meta.json (краткая информация для списка)."""
import json
import os
import re
import time

from .config import SAVE_DIR, SETTINGS_PATH, VERSION


def ensure_dir():
    os.makedirs(SAVE_DIR, exist_ok=True)


def make_slot_id(name):
    ensure_dir()
    base = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_") or "world"
    slot, n = base, 2
    while os.path.exists(os.path.join(SAVE_DIR, slot + ".json")):
        slot = f"{base}_{n}"
        n += 1
    return slot


def write(slot, data, meta):
    ensure_dir()
    path = os.path.join(SAVE_DIR, slot + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)                   # не портим старое сохранение, если запись прервётся
    meta = dict(meta, slot=slot, version=VERSION, saved=time.strftime("%d.%m.%Y %H:%M"), ts=time.time())
    with open(os.path.join(SAVE_DIR, slot + ".meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    settings = load_settings()
    settings["last_slot"] = slot
    save_settings(settings)


def read(slot):
    with open(os.path.join(SAVE_DIR, slot + ".json"), encoding="utf-8") as f:
        return json.load(f)


def list_slots():
    ensure_dir()
    out = []
    for name in os.listdir(SAVE_DIR):
        if name.endswith(".meta.json"):
            try:
                with open(os.path.join(SAVE_DIR, name), encoding="utf-8") as f:
                    meta = json.load(f)
                if os.path.exists(os.path.join(SAVE_DIR, meta["slot"] + ".json")):
                    out.append(meta)
            except (OSError, ValueError, KeyError):
                continue
    out.sort(key=lambda m: -m.get("ts", 0))
    return out


def delete(slot):
    for suffix in (".json", ".meta.json"):
        path = os.path.join(SAVE_DIR, slot + suffix)
        if os.path.exists(path):
            os.remove(path)


def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
