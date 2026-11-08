# -*- coding: utf-8 -*-
"""Процедурные звуки: синтезируются кодом при запуске, без файлов. Если звук недоступен — игра работает молча."""
import math
import random
from array import array

import pygame

RATE = 22050


def _samples(n, fn):
    buf = array("h")
    for i in range(n):
        v = fn(i / RATE, i)
        buf.append(max(-32767, min(32767, int(v * 32767))))
    return buf


def _noise_burst(dur, decay, lp=0.3, vol=0.7, rng=None):
    rng = rng or random.Random(1)
    state = [0.0]

    def fn(t, i):
        state[0] += (rng.uniform(-1, 1) - state[0]) * lp
        return state[0] * vol * math.exp(-t * decay)
    return _samples(int(dur * RATE), fn)


def _tone(dur, f0, f1=None, decay=4.0, vol=0.5, vib=0.0, vib_f=5.0, shape="sine"):
    f1 = f1 or f0
    phase = [0.0]

    def fn(t, i):
        k = t / dur
        f = f0 + (f1 - f0) * k + (math.sin(t * vib_f * math.tau) * vib if vib else 0)
        phase[0] += f / RATE
        s = math.sin(phase[0] * math.tau)
        if shape == "square":
            s = 0.6 if s > 0 else -0.6
        env = min(1.0, t * 40) * math.exp(-t * decay)
        return s * vol * env
    return _samples(int(dur * RATE), fn)


def _mix(*bufs):
    n = max(len(b) for b in bufs)
    out = array("h", [0] * n)
    for b in bufs:
        for i, v in enumerate(b):
            out[i] = max(-32767, min(32767, out[i] + v))
    return out


def _concat(*bufs):
    out = array("h")
    for b in bufs:
        out.extend(b)
    return out


def _silence(dur):
    return array("h", [0] * int(dur * RATE))


def build_all():
    r = random.Random(7)
    return {
        "chop": _mix(_noise_burst(0.18, 22, 0.25, 0.8, r), _tone(0.12, 140, 90, 25, 0.5)),
        "mine": _mix(_noise_burst(0.12, 30, 0.7, 0.6, r), _tone(0.2, 900, 700, 18, 0.25)),
        "hit": _mix(_noise_burst(0.12, 30, 0.35, 0.8, r), _tone(0.1, 120, 60, 30, 0.5)),
        "swing": _noise_burst(0.15, 14, 0.12, 0.35, r),
        "bow": _tone(0.25, 520, 260, 12, 0.45),
        "gun": _mix(_noise_burst(0.35, 9, 0.6, 1.0, r), _tone(0.2, 90, 40, 12, 0.7)),
        "boom": _mix(_noise_burst(0.9, 4, 0.15, 1.0, r), _tone(0.8, 70, 30, 4, 0.7)),
        "thunder": _noise_burst(2.2, 1.6, 0.04, 1.0, r),
        "hurt": _mix(_tone(0.18, 220, 120, 10, 0.55, shape="square"), _noise_burst(0.1, 30, 0.3, 0.4, r)),
        "howl": _tone(1.8, 380, 520, 1.1, 0.4, vib=18, vib_f=5.5),
        "growl": _mix(_noise_burst(0.7, 3, 0.05, 0.8, r), _tone(0.7, 70, 55, 3, 0.5, vib=8, vib_f=22)),
        "bark": _concat(_mix(_tone(0.09, 500, 300, 18, 0.5, shape="square"), _noise_burst(0.09, 20, 0.4, 0.4, r)),
                        _silence(0.08),
                        _mix(_tone(0.09, 520, 320, 18, 0.5, shape="square"), _noise_burst(0.09, 20, 0.4, 0.4, r))),
        "pickup": _concat(_tone(0.06, 700, 700, 20, 0.35), _tone(0.08, 1050, 1050, 18, 0.35)),
        "chime": _concat(_tone(0.12, 660, 660, 10, 0.35), _tone(0.25, 990, 990, 7, 0.35)),
        "levelup": _concat(_tone(0.1, 523, 523, 8, 0.35), _tone(0.1, 659, 659, 8, 0.35), _tone(0.3, 784, 784, 5, 0.4)),
        "eat": _concat(_noise_burst(0.07, 30, 0.5, 0.45, r), _silence(0.05), _noise_burst(0.07, 30, 0.5, 0.45, r)),
        "splash": _noise_burst(0.5, 6, 0.5, 0.6, r),
        "door": _mix(_tone(0.25, 180, 140, 9, 0.35, vib=10, vib_f=30), _noise_burst(0.1, 25, 0.3, 0.3, r)),
        "cough": _concat(_noise_burst(0.12, 18, 0.3, 0.6, r), _silence(0.06), _noise_burst(0.1, 20, 0.3, 0.5, r)),
        "rain": _noise_burst(2.0, 0.0, 0.5, 0.18, r),
        "wind": _mix(_noise_burst(3.0, 0.0, 0.02, 0.6, r), _tone(3.0, 180, 240, 0.0, 0.05, vib=30, vib_f=0.3)),
    }


class Sounds:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.ok = False
        self.snd = {}
        self.loops = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 1, 512)
            freq, size, channels = pygame.mixer.get_init()
            for name, buf in build_all().items():
                data = buf.tobytes() if channels == 1 else array("h", [v for v in buf for _ in range(channels)]).tobytes()
                self.snd[name] = pygame.mixer.Sound(buffer=data)
            pygame.mixer.set_num_channels(16)
            self.ok = True
        except Exception:
            self.ok = False

    def play(self, name, vol=1.0):
        if not (self.ok and self.enabled) or name not in self.snd or vol <= 0.02:
            return
        s = self.snd[name]
        s.set_volume(min(1.0, vol))
        s.play()

    def ambient(self, name, vol):
        """Фоновая петля (дождь, ветер): vol=0 — выключить."""
        if not self.ok:
            return
        ch = self.loops.get(name)
        if vol <= 0.01 or not self.enabled:
            if ch:
                ch.stop()
                self.loops.pop(name, None)
            return
        if ch is None or not ch.get_busy():
            ch = self.snd[name].play(loops=-1)
            if ch is None:
                return
            self.loops[name] = ch
        ch.set_volume(vol)

    def set_enabled(self, on):
        self.enabled = on
        if not on and self.ok:
            for ch in self.loops.values():
                ch.stop()
            self.loops.clear()
