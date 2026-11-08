# -*- coding: utf-8 -*-
"""Главный цикл: сцены (меню, новый мир, загрузка, игра) и обработка ввода."""
import math
import random
import sys

import pygame

from .config import SCREEN_W, SCREEN_H, FPS, VERSION, WORLD_SIZES, DIFFICULTIES, DENSITIES, FACTION_AMOUNTS
from .data import BUILD_CATS, BUILD_BY_ID
from .util import make_font
from .core import GameLogic
from .story import StoryMixin
from .render import RenderMixin
from .ui import UIMixin, CRAFT_TABS
from .sound import Sounds
from . import saves


class Game(GameLogic, StoryMixin, RenderMixin, UIMixin):
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(f"NeTheForest v{VERSION}")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = make_font(18)
        self.font_s = make_font(14)
        self.font_b = make_font(26, bold=True)
        self.font_xl = make_font(60, bold=True)
        self.dark_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self.fog_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self.light_cache = {}
        self.glow_cache = {}
        self.icon_cache = {}
        self.clock_t = 0.0
        self.scene = "menu"
        self.scene_help = False
        self.slot_list = saves.list_slots()
        self.delete_confirm = None
        self.ng = None
        self.world = None
        self.messages = []
        self.settings = {"diff": "normal", "name": "Остров"}
        self.draw_menu_background_loading()
        self.sound = Sounds(saves.load_settings().get("sound", True))

    def draw_menu_background_loading(self):
        self.screen.fill((20, 36, 24))
        self.text("NeTheForest", self.font_xl, (255, 230, 150), (SCREEN_W // 2, SCREEN_H // 2 - 30), center=True)
        self.text("Загрузка звуков...", self.font, (210, 220, 200), (SCREEN_W // 2, SCREEN_H // 2 + 30), center=True)
        pygame.display.flip()

    def update_ambient(self):
        """Фоновые звуки: дождь, ветер зимой и в метель."""
        if self.scene != "play" or self.dead or self.menu in ("pause", "help"):
            self.sound.ambient("rain", 0)
            self.sound.ambient("wind", 0)
            return
        winter = self.season() == "winter"
        rain = 0.0 if winter or not self.raining() else (0.45 if self.weather == "storm" else 0.25)
        wind = 0.5 if "blizzard" in self.events else 0.12 if winter else 0.0
        self.sound.ambient("rain", rain)
        self.sound.ambient("wind", wind)

    # ------------------------------------------------------------ сцены
    def goto(self, scene):
        self.scene = scene
        self.scene_help = False
        self.slot_list = saves.list_slots()
        self.delete_confirm = None
        if scene == "new":
            n = len(self.slot_list) + 1
            self.ng = {"name": f"Остров {n}", "seed": "", "size": "medium", "diff": "normal", "dens": "normal",
                       "facs": "normal", "focus": None}
            pygame.key.start_text_input()
        else:
            pygame.key.stop_text_input()

    def start_new_world(self):
        ng = self.ng
        seed_txt = ng["seed"].strip()
        seed = int(seed_txt) if seed_txt.isdigit() else (abs(hash(seed_txt)) % 10 ** 9 if seed_txt
                                                          else random.randrange(10 ** 9))
        settings = {k: ng[k] for k in ("size", "diff", "dens", "facs")}
        settings["name"] = ng["name"].strip() or "Остров"
        settings["seed"] = seed
        self.draw_menu_background()
        self.text("Генерация мира...", self.font_xl, (255, 230, 150), (SCREEN_W // 2, SCREEN_H // 2), center=True)
        pygame.display.flip()
        self.new_game(settings)
        self.goto("play")
        self.menu = "help"
        self.save_game(auto=True)

    def open_slot(self, slot):
        if self.world is None:
            self.settings = {"diff": "normal"}
        if self.load_game(slot):
            self.goto("play")
        else:
            self.slot_list = saves.list_slots()

    # ------------------------------------------------------------ ввод вне игры
    def handle_menu_event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.scene_help:
                self.scene_help = False
            elif self.scene != "menu":
                self.goto("menu")
            return
        if self.scene_help:
            if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.scene_help = False
            return
        if self.scene == "menu" and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for act, label, r in self.main_buttons():
                if r.collidepoint(e.pos):
                    if act == "continue":
                        self.open_slot(self.continue_slot())
                    elif act == "new":
                        self.goto("new")
                    elif act == "load":
                        self.goto("load")
                    elif act == "help":
                        self.scene_help = True
                    else:
                        pygame.quit()
                        sys.exit()
        elif self.scene == "new":
            ng = self.ng
            if e.type == pygame.TEXTINPUT and ng["focus"] in ("name", "seed"):
                if len(ng[ng["focus"]]) < 24:
                    ng[ng["focus"]] += e.text
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_BACKSPACE and ng["focus"] in ("name", "seed"):
                    ng[ng["focus"]] = ng[ng["focus"]][:-1]
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if ng["focus"]:
                        ng["focus"] = None
                    else:
                        self.start_new_world()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
                ng["focus"] = None
                for key, r in self.newgame_rows().items():
                    if r.collidepoint(e.pos):
                        if key in ("name", "seed"):
                            ng["focus"] = key
                        else:
                            opts = list(self.NG_OPTIONS[key])
                            step = 1 if e.button == 1 and e.pos[0] > r.centerx else -1
                            ng[key] = opts[(opts.index(ng[key]) + step) % len(opts)]
                for act, label, r in self.newgame_buttons():
                    if r.collidepoint(e.pos) and e.button == 1:
                        if act == "random_seed":
                            ng["seed"] = str(random.randrange(10 ** 9))
                        elif act == "create":
                            self.start_new_world()
                        else:
                            self.goto("menu")
        elif self.scene == "load" and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for meta, r in zip(self.slot_list, self.load_rows()):
                if r.collidepoint(e.pos):
                    self.open_slot(meta["slot"])
                    return
                if pygame.Rect(r.right + 10, r.y, 120, 48).collidepoint(e.pos):
                    if self.delete_confirm == meta["slot"]:
                        saves.delete(meta["slot"])
                        self.slot_list = saves.list_slots()
                        self.delete_confirm = None
                    else:
                        self.delete_confirm = meta["slot"]
                    return
            if pygame.Rect(SCREEN_W // 2 - 150, 630, 300, 48).collidepoint(e.pos):
                self.goto("menu")

    # ------------------------------------------------------------ ввод в игре
    def handle_game_event(self, e):
        p = self.player
        if e.type == pygame.KEYDOWN:
            k = e.key
            if self.dead:
                if k == pygame.K_r:
                    self.new_game(dict(self.settings, seed=random.randrange(10 ** 9)))
                    self.menu = None
                elif k == pygame.K_F9:
                    self.load_game(self.slot)
                elif k == pygame.K_ESCAPE:
                    self.goto("menu")
                return
            if self.menu == "help":
                if k in (pygame.K_ESCAPE, pygame.K_F1, pygame.K_RETURN, pygame.K_SPACE):
                    self.menu = None
                return
            if self.menu == "pause":
                if k == pygame.K_ESCAPE:
                    self.menu = None
                return
            if self.menu == "note":
                if k in (pygame.K_e, pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.close_note()
                return
            if self.menu == "ending":
                return
            if self.menu == "radio":
                if k in (pygame.K_e, pygame.K_ESCAPE):
                    self.menu = None
                return
            if self.menu == "journal" and k in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.journal_tab = k - pygame.K_1
                return
            if self.menu in ("chest", "journal", "settlement", "skills"):
                if k in (pygame.K_e, pygame.K_ESCAPE, pygame.K_TAB, pygame.K_j, pygame.K_k):
                    self.menu = None
                return
            if self.menu == "dialog":
                if k == pygame.K_ESCAPE:
                    self.menu, self.dialog = None, None
                elif pygame.K_1 <= k <= pygame.K_9:
                    opts = self.dialog_options()
                    if k - pygame.K_1 < len(opts):
                        self.dialog_action(opts[k - pygame.K_1][1])
                return
            if k == pygame.K_ESCAPE:
                if self.build_mode:
                    self.build_mode = False
                else:
                    self.menu = None if self.menu else "pause"
            elif k == pygame.K_F1:
                self.menu = "help"
            elif k == pygame.K_F5:
                self.save_game()
            elif k == pygame.K_F9:
                self.load_game(self.slot)
            elif k == pygame.K_TAB:
                self.menu = None if self.menu == "inv" else "inv"
                self.build_mode = False
            elif k == pygame.K_c:
                self.menu = None if self.menu == "craft" else "craft"
                self.build_mode = False
            elif k == pygame.K_j:
                self.menu = "journal"
            elif k == pygame.K_k:
                self.menu = "skills"
            elif k == pygame.K_b and self.menu is None:
                self.build_mode = not self.build_mode
                self.demolish = False
                if self.build_mode and p.on_tower:
                    self.build_sel = "turret"
            elif k == pygame.K_x and self.build_mode:
                self.demolish = not self.demolish
            elif k in (pygame.K_1, pygame.K_2, pygame.K_3):
                p.sel = k - pygame.K_1
            elif k == pygame.K_m:
                self.show_map = not self.show_map
                self.map_timer = 0
            elif self.menu is None:
                if k == pygame.K_e:
                    self.interact()
                elif k == pygame.K_f:
                    self.eat()
                elif k == pygame.K_h:
                    self.heal()
                elif k == pygame.K_q:
                    self.stow_held()
                elif k == pygame.K_z:
                    self.shift_held()
                elif k == pygame.K_g:
                    self.drop_held()
                elif k == pygame.K_v:
                    self.ignite_target()
                elif k == pygame.K_t:
                    self.throw_bomb()
                elif k == pygame.K_r:
                    p.fire_mode = not p.fire_mode
                    self.msg("Огненные стрелы: " + ("ВКЛ — стрелы поджигают цель" if p.fire_mode else "выкл"),
                             (255, 190, 110))
        elif e.type == pygame.MOUSEWHEEL and self.menu in (None, "inv") and not self.dead:
            if self.build_mode:
                ids = [b["id"] for b in self.build_list()]
                i = ids.index(self.build_sel) if self.build_sel in ids else 0
                self.build_sel = ids[(i - e.y) % len(ids)]
                self.demolish = False
            else:
                p.sel = (p.sel - e.y) % 3
        elif e.type == pygame.MOUSEBUTTONDOWN and not self.dead and e.button in (1, 3):
            if self.menu in (None, "craft") and e.button == 3:
                for i, r in enumerate(self.queue_rects()):
                    if r.collidepoint(e.pos):
                        self.cancel_craft(i)
                        return
            if self.menu in ("inv", "chest"):
                ref = self.slot_at(e.pos)
                if e.button == 1 and ref and self.slot_get(ref):
                    self.drag = {"ref": ref, "start": e.pos}
                elif e.button == 3 and ref:
                    self.quick_move(ref)
                elif self.menu == "inv":
                    self.inv_click(e.pos, e.button)
                else:
                    self.chest_res_click(e.pos, e.button)
            elif self.menu == "craft" and e.button == 1:
                for i, r in enumerate(self.craft_tab_rects()):
                    if r.collidepoint(e.pos):
                        self.craft_tab = i
                for r, rec in zip(self.craft_rows(), self.craft_list()):
                    if r.collidepoint(e.pos):
                        self.craft_click(rec)
            elif self.menu == "dialog" and e.button == 1:
                for (label, act), r in zip(self.dialog_options(), self.dialog_rows()):
                    if r.collidepoint(e.pos):
                        self.dialog_action(act)
                        break
            elif self.menu == "settlement" and e.button == 1:
                for a, jr, fr in self.settlement_rows():
                    if jr.collidepoint(e.pos):
                        self.cycle_job(a)
                    elif fr.collidepoint(e.pos):
                        a.stay = not a.stay
                if self.settlement_stash_button().collidepoint(e.pos) and self.flag:
                    self.open_chest, self.open_deck = tuple(self.flag), False
                    self.menu = "chest"
            elif self.menu == "pause" and e.button == 1:
                for act, label, r in self.pause_buttons():
                    if r.collidepoint(e.pos):
                        self.pause_action(act)
            elif self.menu == "note" and e.button == 1:
                self.close_note()
            elif self.menu == "radio" and e.button == 1:
                for act, label, r in self.radio_buttons():
                    if r.collidepoint(e.pos):
                        self.radio_action(act)
                        break
            elif self.menu == "ending" and e.button == 1:
                for act, label, r in self.ending_buttons():
                    if r.collidepoint(e.pos):
                        self.ending_action(act)
                        break
            elif self.menu == "journal" and e.button == 1:
                for i, r in enumerate(self.journal_tab_rects()):
                    if r.collidepoint(e.pos):
                        self.journal_tab = i
                if self.journal_tab == 1:
                    for nid, r in self.note_list_rects():
                        if r.collidepoint(e.pos):
                            self.note_sel = nid
            elif self.menu is None and self.build_mode:
                if e.button == 3:
                    self.build_mode = False
                    return
                for (cat, label), r in zip(BUILD_CATS, self.build_tab_rects()):
                    if r.collidepoint(e.pos):
                        self.build_cat = cat
                        self.build_sel = self.build_list()[0]["id"]
                        self.demolish = False
                for r, b in zip(self.build_rows(), self.build_list()):
                    if r.collidepoint(e.pos):
                        self.build_sel, self.demolish = b["id"], False
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.drag:
            src = self.drag["ref"]
            moved = math.hypot(e.pos[0] - self.drag["start"][0], e.pos[1] - self.drag["start"][1]) > 6
            self.drag = None
            dst = self.slot_at(e.pos)
            if not moved:
                if self.menu == "chest":
                    self.quick_move(src)
                else:
                    self.slot_click(src)
            elif dst and dst != src:
                self.move_slots(src, dst)
            elif dst is None and not self.menu_panel().collidepoint(e.pos):
                item = self.slot_get(src)
                if item:
                    self.slot_set(src, None)
                    self.drop_at(p.x, p.y, [item], {})
                    self.msg("Предмет выброшен на землю")

    def pause_action(self, act):
        if act == "resume":
            self.menu = None
        elif act == "save":
            self.save_game()
        elif act == "save_new":
            self.save_game(new_slot=True)
        elif act == "load":
            self.save_game(auto=True)
            self.goto("load")
        elif act == "sound":
            self.sound.set_enabled(not self.sound.enabled)
            st = saves.load_settings()
            st["sound"] = self.sound.enabled
            saves.save_settings(st)
        elif act == "help":
            self.menu = "help"
        elif act == "main":
            self.save_game(auto=True)
            self.goto("menu")
        else:
            self.save_game(auto=True)
            pygame.quit()
            sys.exit()

    # ------------------------------------------------------------ рисование кадра
    def draw_game(self):
        p = self.player
        w = self.world
        self.cam_x = int(max(0, min(p.x - SCREEN_W / 2, w.w * 40 - SCREEN_W)))
        self.cam_y = int(max(0, min(p.y - SCREEN_H / 2, w.h * 40 - SCREEN_H)))
        if self.shake > 0:
            self.cam_x += random.randint(-4, 4)
            self.cam_y += random.randint(-4, 4)
        self.screen.fill((0, 0, 0))
        self.draw_world()
        self.draw_lighting()
        self.draw_weather()
        self.draw_bars()
        self.draw_clock()
        if self.build_mode and self.menu is None:
            self.draw_build_palette()
        elif self.show_map or (p.on_tower and not self.build_mode):
            self.draw_minimap()
        self.draw_hotbar()
        self.draw_queue()
        self.draw_messages()
        self.draw_inspect()
        self.draw_boss_bar()
        if not self.build_mode and self.menu is None:
            self.draw_goal(330 if (self.show_map or p.on_tower) else 98)
        self.draw_banner()
        if p.hurt > 0:
            s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            s.fill((200, 0, 0, int(90 * min(1, p.hurt / 0.3))))
            self.screen.blit(s, (0, 0))
        {"inv": self.draw_inventory, "chest": self.draw_chest, "craft": self.draw_craft, "dialog": self.draw_dialog,
         "journal": self.draw_journal, "help": self.draw_help, "pause": self.draw_pause,
         "settlement": self.draw_settlement, "skills": self.draw_skills, "note": self.draw_note,
         "radio": self.draw_radio, "ending": self.draw_ending}.get(self.menu, lambda: None)()
        if self.dead:
            self.draw_dead()

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    if self.scene == "play" and not self.dead:
                        self.save_game(auto=True)
                    pygame.quit()
                    sys.exit()
                if self.scene == "play":
                    self.handle_game_event(e)
                else:
                    self.handle_menu_event(e)
            if self.scene == "play":
                if not self.dead and self.menu in (None, "craft"):
                    self.update(dt)
                self.tick_ui(dt)
                self.update_ambient()
                self.draw_game()
            else:
                self.clock_t += dt
                {"menu": self.draw_main_menu, "new": self.draw_newgame, "load": self.draw_load}[self.scene]()
            pygame.display.flip()


def run():
    Game().run()
