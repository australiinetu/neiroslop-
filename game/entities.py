# -*- coding: utf-8 -*-
"""Игрок, звери и люди (члены фракций, спутники, жители поселения)."""
import math
import random

from .config import TILE, BAG_SIZES, SETTLE_RADIUS
from .data import ITEMS, HANDS, ANIMALS, ROLES, CRAFTS, BREAKABLE, RES_INFO, PITS
from .util import clamp
from .world import move_entity


class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.r = 13
        self.hp = 100.0
        self.hunger = 100.0
        self.thirst = 100.0
        self.warmth = 100.0
        self.stamina = 100.0
        self.wet = 0.0
        self.poison = 0.0
        self.exhausted = False
        self.slots = [None, None, None]     # 0 — руки, 1 — пояс, 2 — спина
        self.sel = 0
        self.bag = 0
        self.backpack = [None] * BAG_SIZES[0]
        self.res = {k: 0 for k in RES_INFO}
        self.known = [c["id"] for c in CRAFTS if not c.get("research")]
        self.cloak = False
        self.armor = 0                      # 0 — нет, 1 — кожаная, 2 — железная
        self.on_tower = None                # клетка лестницы, если стоишь на вышке
        self.tower_roof = -1
        self.tower_ret = (x, y)
        self.angle = 0.0
        self.cd = 0.0
        self.swing = 0.0
        self.anim = "swing"
        self.flash = 0.0
        self.hurt = 0.0
        self.walk_t = 0.0
        self.moving = False
        self.fishing = None                 # [осталось секунд, tx, ty]
        self.fire_mode = False              # стрелять огненными стрелами
        self.cond = {}                      # раны и болезни: имя -> секунды (bleed, infection, fracture...)
        self.skills = {}                    # навыки: имя -> опыт
        self.chill = 0.0                    # сколько мёрзнешь (простуда)
        self.frost_t = 0.0                  # сколько при нулевом тепле (обморожение)
        self.dirty = 0.0                    # сколько кровоточит без бинта (заражение)
        self.cause = ""

    def held(self):
        return self.slots[self.sel]

    def held_id(self):
        it = self.slots[self.sel]
        return it["id"] if it else None

    def stats(self):
        it = self.held()
        return ITEMS[it["id"]] if it else HANDS

    def light(self):
        iid = self.held_id()
        return ITEMS[iid].get("light", 0) if iid else 0

    def has_tool(self, flag):
        return any(s and ITEMS[s["id"]].get(flag) for s in self.slots)

    def damage(self, amount, cause):
        self.hp -= amount
        self.cause = cause


class Creature:
    def __init__(self, kind, x, y, level=0):
        d = ANIMALS[kind]
        self.kind = kind
        self.beh = d["beh"]
        self.human = self.beh == "human"
        self.ghost = self.beh == "shadow" or bool(d.get("ghost"))     # Тени летают сквозь всё
        self.x, self.y = x, y
        self.r = d["r"]
        lvl = level if self.beh in ("hunter", "shadow") else 0     # хищники крепнут с каждым днём
        self.hp = self.max_hp = d["hp"] * (1 + 0.25 * lvl)
        self.speed = d["speed"] + min(50, 5 * lvl)
        dmg = d.get("dmg", (0, 0))
        self.dmg = [dmg[0] + 2 * lvl, dmg[1] + 2 * lvl]
        self.color = list(d["color"])
        self.dir = random.uniform(0, math.tau)
        self.face = self.dir
        self.timer = random.uniform(0.5, 3)
        self.moving = True
        self.walking = False
        self.anim_t = random.uniform(0, 4)
        self.chasing = False
        self.flee_t = 0.0
        self.aggro_t = 0.0
        self.lunge_t = 0.0
        self.lunge_cd = random.uniform(1, 3)
        self.stun_t = 0.0
        self.burn_t = 0.0
        self.cd = 0.0
        self.hurt = 0.0
        self.swing = 0.0
        self.dead = False
        # поля людей
        self.faction = -1
        self.role = ""
        self.name = ""
        self.home = [x, y]
        self.raid = False
        self.ally = False
        self.ally_until = 0
        self.stay = False
        self.settler = False
        self.job = "guard"
        self.fleeing = False
        self.war_target = -1
        self.visitor_t = 0.0
        # звери
        self.sleeping = False               # медведь в спячке
        self.trust = 0                      # приручение собаки
        self.bark_cd = 0.0
        self.poison_t = 0.0                 # отравлен ядовитым клинком
        self.life = 0.0                     # >0 — призванный слуга босса, исчезнет через столько секунд
        # боссы
        self.lair = -1
        self.spec_cd = 4.0
        self.summoned = 0
        self.charge_ang = 0.0

    def setup_role(self, role):
        rd = ROLES[role]
        self.role = role
        self.hp = self.max_hp = rd["hp"]
        self.dmg = list(rd["dmg"])

    def hostile(self):
        return self.beh in ("hunter", "shadow") or (self.beh in ("neutral", "territorial", "boss") and self.aggro_t > 0)

    def wander(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.timer = random.uniform(1.5, 4)
            self.moving = random.random() < 0.6
            self.dir = random.uniform(0, math.tau)
        return (ANIMALS[self.kind]["walk"] if self.moving else 0), self.dir

    def can_open_doors(self, game):
        return self.human and (self.ally or not game.fac_hostile(self.faction))

    def walk(self, game, ang, speed, dt):
        """Идти; возвращает True, если упёрся в препятствие."""
        w = game.world
        self.walking = True
        self.anim_t += speed * dt / 16
        if self.ghost:
            self.x = clamp(self.x + math.cos(ang) * speed * dt, 0, w.w * TILE)
            self.y = clamp(self.y + math.sin(ang) * speed * dt, 0, w.h * TILE)
            return False
        speed *= w.speed_mult(self.x, self.y)
        doors = self.can_open_doors(game)
        vx, vy = math.cos(ang) * speed * dt, math.sin(ang) * speed * dt
        moved = move_entity(w, self, vx, vy, doors=doors)
        if moved < (abs(vx) + abs(vy)) * 0.3:       # упёрлись — обходим
            self.dir = ang + random.choice((-1, 1)) * random.uniform(1.0, 2.2)
            self.timer = 0.6
            move_entity(w, self, math.cos(self.dir) * speed * dt, math.sin(self.dir) * speed * dt, doors=doors)
            return True
        return False

    def siege(self, game, ang, dmg):
        """Упёрся в постройку игрока — ломает её (или поджигает, если фанатик)."""
        tx = int((self.x + math.cos(ang) * (self.r + 14)) // TILE)
        ty = int((self.y + math.sin(ang) * (self.r + 14)) // TILE)
        o = game.world.objects.get((tx, ty))
        if not o or not o.get("own") or o["t"] not in BREAKABLE or self.cd > 0:
            return
        self.cd = 1.2
        self.swing = 0.3
        if self.human and ROLES[self.role].get("ignite") and random.random() < 0.5:
            if game.world.ignite((tx, ty)):
                game.msg("Фанатики подожгли твою постройку!", (255, 140, 90))
                return
        game.damage_building((tx, ty), dmg)

    def triggers_traps(self, game):
        if self.ghost or self.ally:
            return False
        if self.human:
            return game.fac_hostile(self.faction) or self.raid
        return True

    def update(self, game, dt):
        for attr in ("cd", "hurt", "flee_t", "aggro_t", "lunge_t", "lunge_cd", "stun_t", "swing", "burn_t", "poison_t"):
            setattr(self, attr, getattr(self, attr) - dt)
        self.walking = False
        self.chasing = False
        if self.life > 0:                       # призванные боссом слуги живут недолго
            self.life -= dt
            if self.life <= 0:
                self.dead = True
                game.popup(self.x, self.y - 20, "исчез", (200, 200, 220))
                return
        w = game.world
        if not self.ghost:
            pos = (int(self.x // TILE), int(self.y // TILE))
            o = w.objects.get(pos)
            if o and self.triggers_traps(game):
                t = o["t"]
                if t == "trap" and o["armed"] and not self.human:
                    o["armed"] = False
                    self.stun_t = 4.0
                    game.popup(self.x, self.y - 26, "Капкан!", (255, 200, 120))
                    game.damage_creature(self, 20, by_player=True)
                elif t in PITS and self.stun_t <= 0 and (o.get("hidden") or random.random() < 0.02):
                    self.stun_t = 6.0
                    o["hidden"] = False
                    game.popup(self.x, self.y - 26, "Упал в яму!", (255, 200, 120))
                    game.damage_creature(self, 45 if t == "spiked_pit" else 15, by_player=True)
                elif t == "spikes":
                    game.damage_creature(self, 12 * dt, by_player=True)
                    o["hp"] = o.get("hp", 40) - 4 * dt
                    if o["hp"] <= 0:
                        game.remove_object(pos)
            if pos in w.burning:
                game.damage_creature(self, 8 * dt, by_player=False)
        if self.burn_t > 0:
            game.damage_creature(self, 6 * dt, by_player=True)
        if self.poison_t > 0:
            game.damage_creature(self, 4 * dt, by_player=True)
        if self.dead:
            return
        if self.human:
            self.update_human(game, dt)
        else:
            self.update_animal(game, dt)

    def flee_fire(self, game):
        w = game.world
        return w.nearest_fire(self.x, self.y, 3.5 * TILE) or w.burning_near(self.x, self.y, 2)

    def update_dog(self, game, dt):
        """Собака: дикая держится на расстоянии, ручная ходит за тобой, рычит на врагов и кусает их."""
        p = game.player
        dist = math.hypot(p.x - self.x, p.y - self.y)
        self.bark_cd -= dt
        speed, ang = 0.0, self.dir
        if self.stun_t > 0:
            return
        if self.ally:
            if self.hp < self.max_hp:
                self.hp = min(self.max_hp, self.hp + 0.4 * dt)
            danger = next((a for a in game.animals if game.is_threat(a) and abs(a.x - p.x) < 10 * TILE
                           and abs(a.y - p.y) < 10 * TILE), None)
            if danger and self.bark_cd <= 0:
                self.bark_cd = 20
                game.sfx("bark", self.x, self.y)
                game.msg(f"{self.name} рычит — рядом опасность!", (255, 200, 120))
            base = self.home if self.stay else (p.x, p.y)
            target = game.nearest_enemy(base[0], base[1], 7 * TILE, self)
            if target:
                self.chasing = False
                dd = math.hypot(target.x - self.x, target.y - self.y)
                ang = math.atan2(target.y - self.y, target.x - self.x)
                self.face = ang
                if dd < self.r + target.r + 8:
                    if self.cd <= 0:
                        self.cd, self.swing = 0.9, 0.3
                        game.damage_creature(target, random.randint(*self.dmg), by_player=True)
                else:
                    speed = self.speed
            elif self.stay:
                if math.hypot(self.home[0] - self.x, self.home[1] - self.y) > 3 * TILE:
                    ang, speed = math.atan2(self.home[1] - self.y, self.home[0] - self.x), ANIMALS["dog"]["walk"]
                else:
                    speed, ang = self.wander(dt)
            elif dist > 2.2 * TILE:
                ang = math.atan2(p.y - self.y, p.x - self.x)
                speed = self.speed if dist > 5 * TILE else ANIMALS["dog"]["walk"] * 2
                if dist > 25 * TILE and not p.on_tower:          # потерялся — прибегает
                    self.x, self.y = p.x + 30, p.y + 30
        else:
            food = p.res.get("meat", 0) + p.res.get("cooked", 0) + p.res.get("smoked_meat", 0)
            if self.flee_t > 0 or (dist < 3 * TILE and not (food and self.trust > 0) and p.moving):
                ang, speed = math.atan2(self.y - p.y, self.x - p.x), self.speed
            elif self.trust > 0 and food and 2 * TILE < dist < 9 * TILE:
                ang, speed = math.atan2(p.y - self.y, p.x - self.x), ANIMALS["dog"]["walk"]
            else:
                speed, ang = self.wander(dt)
        if speed > 0:
            self.face = ang
            self.walk(game, ang, speed, dt)

    def update_animal(self, game, dt):
        d = ANIMALS[self.kind]
        p = game.player
        if self.beh == "dog":
            self.update_dog(game, dt)
            return
        if self.beh == "boss":
            game.boss_ai(self, dt)
            return
        if self.kind == "bear":                              # зимой медведи спят
            if game.season() == "winter" and self.aggro_t <= 0:
                self.sleeping = True
                return
            self.sleeping = False
        if self.stun_t > 0:
            return
        dx, dy = p.x - self.x, p.y - self.y
        dist = math.hypot(dx, dy)
        reachable = self.ghost or (not p.on_tower and not game.player_in_water())
        night = game.is_night()
        speed, ang = 0.0, self.dir
        wander = chase = False
        beh = self.beh

        if beh == "flee":
            fire = game.world.burning_near(self.x, self.y, 2)
            if fire:
                ang, speed = math.atan2(self.y - fire[1], self.x - fire[0]), self.speed
            elif self.flee_t > 0 or dist < d["flee"] * TILE or self.burn_t > 0:
                ang = math.atan2(-dy, -dx) + math.sin(game.clock_t * 3 + id(self) % 7) * 0.4
                speed = self.speed
            else:
                wander = True
        else:
            fire = self.flee_fire(game) if beh != "neutral" else None
            if fire:                                    # хищники боятся огня
                ang = math.atan2(self.y - fire[1], self.x - fire[0])
                speed = self.speed
            elif self.flee_t > 0:
                ang = math.atan2(-dy, -dx)
                speed = self.speed
            else:
                if beh == "neutral":
                    chase = self.aggro_t > 0 and dist < 16 * TILE
                elif beh == "territorial":
                    hungry = self.kind == "bear" and game.season() == "spring"     # весной медведь голодный
                    if dist < d["aggro"] * (1.7 if hungry else 1) * TILE and reachable:
                        if self.aggro_t <= 0:
                            game.msg(f"{d['name']} нападает на тебя!" + (" Он голоден после спячки!" if hungry else ""),
                                     (255, 150, 110))
                            if self.kind == "bear":
                                game.sfx("growl", self.x, self.y)
                        self.aggro_t = max(self.aggro_t, 5)
                    chase = self.aggro_t > 0 and dist < 14 * TILE
                elif beh == "hunter":
                    smell = p.cond.get("bleed", 0) > 0 and dist < 13 * TILE       # запах крови
                    winter = game.season() == "winter" and dist < 10 * TILE      # зимой голодные волки охотятся и днём
                    chase = (night or self.aggro_t > 0 or dist < 6 * TILE or smell or winter) and dist < 22 * TILE
                else:
                    chase = dist < 30 * TILE
                wander = not chase
            if chase:
                self.chasing = True
                ang = math.atan2(dy, dx)
                speed = self.speed * (1.1 if beh == "hunter" and night else 1.0)
                if beh == "shadow" and p.light() and dist < 6 * TILE:
                    speed *= 0.4                         # свет сковывает Тень
                if beh == "hunter" and self.lunge_cd <= 0 and dist < 3.5 * TILE and reachable:
                    self.lunge_t, self.lunge_cd = 0.35, random.uniform(2.5, 4)
                if self.lunge_t > 0:
                    speed *= 2.2                         # рывок
                if not reachable and dist < 3 * TILE:
                    speed = 0                            # ждёт на берегу / под вышкой
                if dist < self.r + p.r + 8:
                    speed = 0
                    if reachable and self.cd <= 0:
                        self.cd = {"territorial": 1.6, "shadow": 1.5}.get(beh, 1.2)
                        self.swing = 0.3
                        kind = None if beh == "shadow" else "claw" if self.kind in ("bear", "moose", "alpha") else "bite"
                        game.hurt_player(random.randint(*self.dmg), d["cause"], kind)
                        if beh == "shadow":
                            p.warmth = max(0, p.warmth - 15)
                        if d.get("poison"):
                            p.poison = max(p.poison, d["poison"])
                            game.msg("Тебя укусила змея — ты отравлен! Нужен отвар или аптечка", (180, 255, 120))

        if beh == "hunter" and not night and self.aggro_t <= 0 and dist > 14 * TILE and game.season() != "winter":
            self.dead = True                             # днём хищники уходят
        if beh == "shadow" and not night and self.life <= 0:
            self.dead = True
            game.popup(self.x, self.y - 20, "Тень рассеялась", (190, 150, 255))

        if wander:
            speed, ang = self.wander(dt)
        if speed > 0:
            self.face = ang
            if self.walk(game, ang, speed, dt) and chase and d.get("siege"):
                self.siege(game, ang, random.randint(*self.dmg) // 2)

    def update_human(self, game, dt):
        p = game.player
        w = game.world
        rd = ROLES[self.role]
        fac = w.factions[self.faction] if self.faction >= 0 else None
        night = game.is_night()
        dist_p = math.hypot(p.x - self.x, p.y - self.y)
        target, goal, run = None, None, False
        if self.fleeing:                                       # лагерь уничтожен — уходят с острова
            ang = math.atan2(self.y - p.y, self.x - p.x)
            self.face = ang
            self.walk(game, ang, self.speed, dt)
            if dist_p > 16 * TILE:
                self.dead = True
            return
        if self.settler and not self.ally:
            self.settler = False
        if self.ally:
            if self.ally_until and game.day > self.ally_until:
                self.ally = False
                game.msg(f"{self.name} возвращается домой — срок помощи истёк")
            if self.settler and game.flag and self.stay:
                home = ((game.flag[0] + 0.5) * TILE, (game.flag[1] + 0.5) * TILE)
                self.home = list(home)
                target = game.nearest_enemy(home[0], home[1], SETTLE_RADIUS * TILE, self)
                if target is None:
                    if math.hypot(home[0] - self.x, home[1] - self.y) > 5 * TILE:
                        goal = home
                    if self.hp < self.max_hp:
                        self.hp = min(self.max_hp, self.hp + 0.5 * dt)
            else:
                base = (self.x, self.y) if self.stay else (p.x, p.y)
                target = game.nearest_enemy(base[0], base[1], 8 * TILE, self)
                if target is None and not self.stay and dist_p > 2.5 * TILE:
                    goal, run = (p.x, p.y), dist_p > 5 * TILE
        else:
            if self.raid and game.flag and dist_p > 14 * TILE and game.fac_hostile(self.faction):
                # набег на поселение: бьют жителей, а если их нет — идут к флагу и ломают всё на пути
                flag = ((game.flag[0] + 0.5) * TILE, (game.flag[1] + 0.5) * TILE)
                target = game.nearest_enemy(self.x, self.y, 12 * TILE, self)
                if target is None:
                    goal, run = flag, True
                    if math.hypot(flag[0] - self.x, flag[1] - self.y) < 2 * TILE:
                        game.damage_building(tuple(game.flag), 3 * dt)
            elif game.fac_hostile(self.faction) and (dist_p < 14 * TILE or self.raid):
                target = "player"
            else:
                target = game.nearest_enemy(self.x, self.y, 8 * TILE, self)
                if target is None:
                    if self.war_target >= 0:
                        tf = w.factions[self.war_target]
                        if not tf["alive"] or self.war_target not in fac["wars"]:
                            self.war_target = -1
                        else:
                            goal, run = ((tf["center"][0] + 0.5) * TILE, (tf["center"][1] + 0.5) * TILE), True
                    elif self.visitor_t > 0:
                        self.visitor_t -= dt
                        if dist_p > 3 * TILE:
                            goal = (p.x, p.y)
                        if self.visitor_t <= 0:
                            self.dead = True
                    elif self.raid:
                        goal, run = self.home, True
                        if not night and dist_p > 15 * TILE:
                            self.dead = True
                    elif math.hypot(self.home[0] - self.x, self.home[1] - self.y) > 5 * TILE:
                        goal = self.home
        speed, ang = 0.0, self.dir
        chasing = False
        if target is not None:
            self.chasing = target == "player"
            if target == "player":
                tx, ty, tr = p.x, p.y, p.r
                reachable = not p.on_tower and not game.player_in_water()
            else:
                tx, ty, tr = target.x, target.y, target.r
                reachable = True
            dd = math.hypot(tx - self.x, ty - self.y)
            ang = math.atan2(ty - self.y, tx - self.x)
            self.face = ang
            ranged = rd.get("ranged")
            if ranged:
                if dd < ranged["range"] * TILE and self.cd <= 0:
                    self.cd = ranged["cd"]
                    self.swing = 0.25
                    owner = "ally" if self.ally else "npc"
                    game.shoot(self.x, self.y, ang + random.uniform(-0.08, 0.08), ranged, owner, self.faction)
                if dd < 4 * TILE:
                    speed, ang = self.speed, ang + math.pi
                elif dd > ranged["range"] * TILE * 0.75:
                    speed, chasing = self.speed, True
            elif dd < self.r + tr + 10:
                if reachable and self.cd <= 0:
                    self.cd = 1.1
                    self.swing = 0.3
                    dmg = random.randint(*self.dmg)
                    if target == "player":
                        weapon = rd.get("weapon")
                        kind = "blunt" if weapon == "club" else "fire" if weapon == "torch" else "blade"
                        game.hurt_player(dmg, game.fac_cause(self.faction), kind)
                    else:
                        game.damage_creature(target, dmg, by_player=False)
            elif not reachable and dd < 3 * TILE:
                speed = 0
            else:
                speed, chasing = self.speed, True
        elif goal:
            ang = math.atan2(goal[1] - self.y, goal[0] - self.x)
            speed = self.speed if run else ANIMALS["human"]["walk"] * 1.5
            self.face = ang
        else:
            speed, ang = self.wander(dt)
            if speed:
                self.face = ang
        if self.stun_t > 0:
            speed = 0
        if speed > 0:
            if self.walk(game, ang, speed, dt) and ((chasing and target == "player") or (self.raid and goal)):
                self.siege(game, ang, random.randint(*self.dmg) // 2)
        # фанатики в набеге поджигают постройки
        if self.raid and rd.get("ignite") and random.random() < 0.004:
            pos = game.world.find_near(self.x, self.y, {"wall", "door", "palisade", "barricade", "chest", "bench1",
                                                        "bed", "bigbed", "tent", "flag"}, 2 * TILE)
            if pos and game.world.objects[pos].get("own") and game.world.ignite(pos):
                game.msg("Фанатики подожгли твою постройку!", (255, 140, 90))
