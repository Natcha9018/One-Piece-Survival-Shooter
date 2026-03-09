"""
🏴‍☠️ ONE PIECE SURVIVAL — GUM-GUM EDITION
==========================================
Controls:
  W A S D      — Move  (กำหนดทิศทางหมัด)
  SPACE        — Gum-Gum Pistol  (หมัดยืดทิศที่เดิน)
  SHIFT        — Gear Second! (ตัวแดง+ควัน, ต่อยแรง×2, 8 วินาที)
  ESC          — Quit

Run:  python one_piece_survival.py
Need: pip install pygame   OR   pip install pygame-ce
"""

import pygame, math, random, sys

# ══════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════
WIDTH, HEIGHT = 960, 640
FPS  = 60
TILE = 64

C_SKY       = (135, 206, 250)
C_OCEAN_D   = ( 25,  80, 160)
C_OCEAN_L   = ( 40, 120, 200)
C_SAND      = (210, 180, 120)
C_SAND_D    = (180, 150,  90)
C_STONE     = (130, 130, 130)
C_STONE_D   = (100, 100, 100)
C_WHITE     = (255, 255, 255)
C_BLACK     = (  0,   0,   0)
C_RED       = (220,  30,  30)
C_RED_D     = (160,  10,  10)
C_GREEN     = ( 50, 200,  50)
C_YELLOW    = (255, 220,   0)
C_NAVY      = ( 20,  50, 120)
C_NAVY_L    = ( 60,  90, 180)
C_PINK      = (250, 150, 150)
C_PURPLE    = (150,  50, 200)
C_GREY      = (160, 160, 160)
C_DARK_GREY = ( 60,  60,  60)
C_SKIN      = (230, 185, 130)
C_VEST      = (220,  40,  40)
C_HAT       = (230, 180,  40)
C_HP_BG     = ( 80,   0,   0)
C_HP_FG     = (220,  30,  30)
C_HP_BD     = (200, 200, 200)
C_GOLD      = (255, 210,  50)
C_ARM       = (210, 160, 100)
C_FIST      = (190, 130,  80)

# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════
def clamp(v, lo, hi): return max(lo, min(hi, v))

def norm(dx, dy):
    d = math.hypot(dx, dy)
    return (dx/d, dy/d) if d else (0.0, 0.0)

def lerp_col(a, b, t):
    t = clamp(t, 0, 1)
    return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))

# ══════════════════════════════════════════════════════════
#  SOUND  (pure pygame, ไม่ต้องใช้ไฟล์ภายนอก)
# ══════════════════════════════════════════════════════════
class Sound:
    def __init__(self):
        self._s = {}
        try:
            pygame.mixer.init(44100, -16, 1, 512)
            self._s['punch']   = self._mk('sq', 220, 0.10, 0.50)
            self._s['gear2']   = self._mk('sq', 160, 0.22, 0.60)
            self._s['hit']     = self._mk('sq',  70, 0.09, 0.45)
            self._s['death']   = self._mk('no',   0, 0.28, 0.55)
        except Exception:
            pass

    def _mk(self, kind, freq, dur, vol):
        try:
            import numpy as np
            sr = 44100; n = int(sr*dur)
            t  = np.linspace(0, dur, n, False)
            if   kind == 'sq': w = np.sign(np.sin(2*math.pi*freq*t))
            elif kind == 'no': w = np.random.uniform(-1,1,n)
            else:              w = np.sin(2*math.pi*freq*t)
            fade = np.linspace(1, 0, n)
            pcm  = (w*fade*vol*32767).astype(np.int16)
            return pygame.sndarray.make_sound(pcm)
        except Exception:
            return None

    def play(self, name):
        s = self._s.get(name)
        if s:
            try: s.play()
            except: pass

# ══════════════════════════════════════════════════════════
#  PARTICLE
# ══════════════════════════════════════════════════════════
class Particle:
    def __init__(self, x, y, col, vx, vy, life=0.5, r=5):
        self.x=x; self.y=y; self.col=col
        self.vx=vx; self.vy=vy
        self.life=life; self.ml=life; self.r=r

    def update(self, dt):
        self.x+=self.vx*dt; self.y+=self.vy*dt
        self.vy+=220*dt; self.life-=dt
        return self.life>0

    def draw(self, surf):
        a = self.life/self.ml
        r = max(1, int(self.r*a))
        pygame.draw.circle(surf, lerp_col(self.col, C_WHITE, 1-a),
                           (int(self.x), int(self.y)), r)

# ══════════════════════════════════════════════════════════
#  RUBBER FIST  — หมัดยางยืดของลูฟี่ 🥊
# ══════════════════════════════════════════════════════════
class RubberFist:
    """
    แขนยางยืดจากตัว Luffy → ยืดออกตามทิศ → ชนศัตรู → หดกลับ
    State machine: 'out' → 'hit' → 'back' → active=False
    """
    EXTEND_SPD  = 720    # px/วินาที ขาออก
    RETRACT_SPD = 950    # px/วินาที ขากลับ
    FIST_R      = 14     # รัศมีหมัด (collision + visual)
    MAX_REACH   = 340    # ระยะสูงสุด (Pistol)
    DAMAGE      = 35
    HIT_PAUSE   = 0.07   # วิ หยุดค้างเมื่อชนโดนศัตรู

    GATLING_REACH  = 210
    GATLING_DAMAGE = 18

    def __init__(self, ox, oy, dx, dy, is_gatling=False, dmg_mult=1.0):
        self.ox, self.oy = ox, oy
        self.dx, self.dy = dx, dy
        self.is_gatling  = is_gatling
        self.reach = self.GATLING_REACH if is_gatling else self.MAX_REACH
        self.dmg   = int((self.GATLING_DAMAGE if is_gatling else self.DAMAGE) * dmg_mult)

        self.dist     = 0.0     # ระยะปัจจุบัน
        self.state    = 'out'   # 'out' | 'hit' | 'back'
        self.active   = True
        self.hit_timer= 0.0
        self.wobble_t = random.uniform(0, 6.28)
        self.hit_set  = set()   # id ศัตรูที่ชนแล้ว

    @property
    def tip(self):
        return (self.ox + self.dx*self.dist,
                self.oy + self.dy*self.dist)

    def update(self, dt):
        self.wobble_t += dt * 16

        if self.state == 'out':
            self.dist += self.EXTEND_SPD * dt
            if self.dist >= self.reach:
                self.dist = self.reach
                self.state = 'back'

        elif self.state == 'hit':
            self.hit_timer -= dt
            if self.hit_timer <= 0:
                self.state = 'back'

        elif self.state == 'back':
            self.dist -= self.RETRACT_SPD * dt
            if self.dist <= 0:
                self.dist  = 0
                self.active = False

    def try_hit(self, enemy):
        """ตรวจ collision ตลอดความยาวแขน คืน True ถ้าตีได้"""
        if id(enemy) in self.hit_set:
            return False
        steps = max(6, int(self.dist / 15))
        for i in range(steps+1):
            frac = i / max(steps, 1)
            px = self.ox + self.dx*self.dist*frac
            py = self.oy + self.dy*self.dist*frac
            if math.hypot(px-enemy.x, py-enemy.y) < enemy.RADIUS + self.FIST_R:
                self.hit_set.add(id(enemy))
                if self.state == 'out':
                    self.state     = 'hit'
                    self.hit_timer = self.HIT_PAUSE
                return True
        return False

    def draw(self, surf):
        if not self.active or self.dist < 2:
            return

        tx, ty = self.tip

        # ── แขนยางโค้งงอ ─────────────────────────────────
        segs = max(8, int(self.dist/16))
        pts  = []
        for i in range(segs+1):
            frac = i / segs
            bx = self.ox + self.dx*self.dist*frac
            by = self.oy + self.dy*self.dist*frac
            # wobble ตั้งฉาก — สูงสุดตรงกลาง
            perp_x = -self.dy; perp_y = self.dx
            amp   = 9 * math.sin(frac*math.pi)
            phase = math.sin(frac*math.pi*2.5 - self.wobble_t)
            bx += perp_x*amp*phase
            by += perp_y*amp*phase
            pts.append((int(bx), int(by)))

        if len(pts) >= 2:
            for i in range(len(pts)-1):
                frac = i / len(pts)
                col  = lerp_col(C_SKIN, C_ARM, frac)
                thickness = max(3, int(11*(1-frac*0.4)))
                pygame.draw.line(surf, col, pts[i], pts[i+1], thickness)

        # ── กำปั้น ────────────────────────────────────────
        fx, fy = int(tx), int(ty)
        r = self.FIST_R

        # เงา
        pygame.draw.circle(surf, (80,40,10), (fx+3, fy+3), r+2)
        # ฐาน
        pygame.draw.circle(surf, C_FIST, (fx, fy), r+3)
        pygame.draw.circle(surf, C_SKIN, (fx, fy), r)

        # นิ้ว 4 นิ้ว
        ka = math.atan2(self.dy, self.dx) + math.pi/2
        for ki in range(4):
            ang = ka + (ki-1.5)*0.32
            kx  = fx + int(math.cos(ang)*(r-1))
            ky  = fy + int(math.sin(ang)*(r-1))
            pygame.draw.circle(surf, lerp_col(C_FIST,C_SKIN,0.4), (kx,ky), 5)
            pygame.draw.circle(surf, (100,60,30), (kx,ky), 5, 1)

        # flash ขาวเมื่อชน
        if self.state == 'hit':
            s = pygame.Surface((r*5, r*5), pygame.SRCALPHA)
            a = int(220*(self.hit_timer/self.HIT_PAUSE))
            pygame.draw.circle(s, (255,255,180,a), (r*5//2,r*5//2), r*2)
            surf.blit(s, (fx-r*5//2, fy-r*5//2))

# ══════════════════════════════════════════════════════════
#  PLAYER — Monkey D. Luffy
# ══════════════════════════════════════════════════════════
class Player:
    SPEED       = 225.0
    MAX_HP      = 100
    RADIUS      = 18
    PISTOL_CD   = 0.35
    GEAR2_DUR   = 8.0    # วินาที Gear Second active
    GEAR2_CD    = 15.0   # cooldown หลัง gear หมด
    IFRAME      = 0.50

    # Gear Second bonus
    G2_DMG_MULT  = 2.0   # ดาเมจ x2
    G2_CD_MULT   = 0.45  # cooldown x0.45 (ยิงเร็วขึ้น)
    G2_SPEED_MULT= 1.4   # วิ่งเร็วขึ้น

    def __init__(self, x, y):
        self.x=float(x); self.y=float(y)
        self.hp=self.MAX_HP; self.alive=True
        self.facing    = (1.0, 0.0)
        self.walk_t    = 0.0
        self.pistol_t  = 0.0
        self.gear2_t   = 0.0    # >0 = กำลัง active, <=0 = ไม่ active
        self.gear2_cd  = 0.0    # cooldown หลัง gear หมด
        self.iframe_t  = 0.0
        self.flash_t   = 0.0
        self.punch_anim= 0.0
        self.steam_t   = 0.0    # timer ปล่อยควัน

    @property
    def in_gear2(self): return self.gear2_t > 0

    def take_damage(self, dmg):
        if self.iframe_t > 0: return
        self.hp       = max(0, self.hp-dmg)
        self.iframe_t = self.IFRAME
        self.flash_t  = 0.15
        if self.hp == 0: self.alive = False

    def update(self, dt, keys):
        ix = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - \
             int(keys[pygame.K_a] or keys[pygame.K_LEFT])
        iy = int(keys[pygame.K_s] or keys[pygame.K_DOWN])  - \
             int(keys[pygame.K_w] or keys[pygame.K_UP])

        spd = self.SPEED * (self.G2_SPEED_MULT if self.in_gear2 else 1.0)
        nx, ny = norm(ix, iy)
        self.x = clamp(self.x + nx*spd*dt, 20, WIDTH-20)
        self.y = clamp(self.y + ny*spd*dt, 20, HEIGHT-20)

        if ix or iy:
            self.facing  = norm(ix, iy)
            self.walk_t += dt * (10 if self.in_gear2 else 8)

        self.pistol_t  = max(0.0, self.pistol_t  - dt)
        self.iframe_t  = max(0.0, self.iframe_t  - dt)
        self.flash_t   = max(0.0, self.flash_t   - dt)
        self.punch_anim= max(0.0, self.punch_anim - dt)
        self.steam_t   = max(0.0, self.steam_t   - dt)

        # Gear Second countdown
        if self.gear2_t > 0:
            self.gear2_t -= dt
            if self.gear2_t <= 0:
                self.gear2_t  = 0.0
                self.gear2_cd = self.GEAR2_CD
        elif self.gear2_cd > 0:
            self.gear2_cd -= dt

    # ── Gum-Gum Pistol (เล็งเมาส์) ───────────────────────
    def try_pistol(self, mx, my, sound):
        cd = self.PISTOL_CD * (self.G2_CD_MULT if self.in_gear2 else 1.0)
        if self.pistol_t > 0: return None
        self.pistol_t   = cd
        self.punch_anim = cd * 1.2
        sound.play('punch')
        dx, dy = norm(mx - self.x, my - self.y)
        self.facing = (dx, dy)
        dmg_mult = self.G2_DMG_MULT if self.in_gear2 else 1.0
        return RubberFist(self.x, self.y, dx, dy, dmg_mult=dmg_mult)

    # ── Gear Second ───────────────────────────────────────
    def try_gear2(self, sound):
        if self.gear2_t > 0 or self.gear2_cd > 0: return False
        self.gear2_t = self.GEAR2_DUR
        sound.play('gear2')
        return True

    # ── ปล่อยควัน Gear Second (เรียกจาก main loop) ───────
    def emit_steam(self, particles):
        if not self.in_gear2 or self.steam_t > 0: return
        self.steam_t = 0.06   # ทุก 0.06 วินาที
        for _ in range(3):
            angle = random.uniform(0, 6.28)
            dist  = random.uniform(8, 20)
            ox = self.x + math.cos(angle)*dist
            oy = self.y + math.sin(angle)*dist
            vx = math.cos(angle)*random.uniform(20, 60)
            vy = math.sin(angle)*random.uniform(20, 60) - 40
            col = random.choice([(255,180,140),(255,140,100),(255,200,180)])
            particles.append(Particle(ox, oy, col, vx, vy,
                                      life=random.uniform(0.4,0.9),
                                      r=random.randint(5,12)))

    # ── draw ───────────────────────────────────────────────
    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        f = 1 if self.facing[0] >= 0 else -1
        g2 = self.in_gear2

        # hit flash
        if self.flash_t > 0:
            s = pygame.Surface((50,66), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (255,255,255,220), s.get_rect())
            surf.blit(s, (x-25, y-33)); return

        # iframe blink
        if self.iframe_t > 0 and int(self.iframe_t*10)%2==0: return

        bob     = int(math.sin(self.walk_t)*3)
        stretch = min(int(self.punch_anim * 22), 22)

        # สีผิวเปลี่ยนตาม Gear Second
        skin_col = (220, 80, 60)   if g2 else C_SKIN
        vest_col = (180, 20, 20)   if g2 else C_VEST
        arm_col  = (200, 70, 50)   if g2 else C_SKIN

        # ── Gear Second aura (วงแสงแดง) ──────────────────
        if g2:
            t0 = pygame.time.get_ticks()/120
            pulse = int(30 + 20*math.sin(t0))
            for i in range(4):
                al = max(0, pulse - i*7)
                s  = pygame.Surface((100,100), pygame.SRCALPHA)
                pygame.draw.circle(s, (255,80,30,al), (50,50), 44-i*7)
                surf.blit(s, (x-50, y-50))

        # ── ขาและรองเท้า ──────────────────────────────────
        pygame.draw.rect(surf,(30,30,100),(x-11,y+10+bob,10,18),border_radius=4)
        pygame.draw.rect(surf,(30,30,100),(x+2, y+10+bob,10,18),border_radius=4)
        pygame.draw.ellipse(surf,C_DARK_GREY,(x-14,y+24+bob,14,8))
        pygame.draw.ellipse(surf,C_DARK_GREY,(x+1, y+24+bob,14,8))

        # ── ตัว ──────────────────────────────────────────
        pygame.draw.rect(surf,vest_col,(x-14,y-10+bob,28,22),border_radius=5)
        pygame.draw.polygon(surf,skin_col,[
            (x-6,y-10+bob),(x+6,y-10+bob),(x,y-2+bob)])

        # ── แขน ──────────────────────────────────────────
        swing = int(math.sin(self.walk_t)*8)
        lx2 = x - 28*f - stretch*f
        ly2 = y + 8 + bob + swing
        pygame.draw.line(surf,arm_col,(x-14*f,y-5+bob),(lx2,ly2),8)
        pygame.draw.circle(surf,arm_col,(lx2,ly2),7)
        rx2 = x + 28*f + stretch*f
        ry2 = y + 8 + bob - swing
        pygame.draw.line(surf,arm_col,(x+14*f,y-5+bob),(rx2,ry2),8)
        pygame.draw.circle(surf,arm_col,(rx2,ry2),7)

        # ── หัว ──────────────────────────────────────────
        pygame.draw.ellipse(surf,skin_col,(x-16,y-38+bob,32,30))
        pygame.draw.line(surf,C_RED_D,(x+6*f,y-24+bob),(x+10*f,y-20+bob),2)
        # ตา — โตขึ้นและดุขึ้นตอน Gear 2
        eye_r = 5 if g2 else 4
        for ex in [-6, 6]:
            pygame.draw.circle(surf,C_BLACK,(x+ex,y-27+bob),eye_r)
            # แวว
            pygame.draw.circle(surf,C_WHITE,(x+ex,y-28+bob),2)
        if g2:
            # คิ้วขมวด
            pygame.draw.line(surf,C_BLACK,(x-12,y-33+bob),(x-3,y-30+bob),2)
            pygame.draw.line(surf,C_BLACK,(x+3, y-30+bob),(x+12,y-33+bob),2)
        sw = 8 + int(self.punch_anim*4)
        pygame.draw.arc(surf,C_BLACK,(x-sw,y-20+bob,sw*2,10),math.pi,2*math.pi,2)

        # ── หมวกฟาง ──────────────────────────────────────
        hy = y-40+bob + int(math.sin(self.walk_t*0.8)*2)
        pygame.draw.ellipse(surf,C_HAT,(x-28,hy,56,14))
        pygame.draw.ellipse(surf,(180,140,20),(x-28,hy,56,14),2)
        pygame.draw.ellipse(surf,C_HAT,(x-18,hy-14,36,22))
        pygame.draw.ellipse(surf,(180,140,20),(x-18,hy-14,36,22),2)
        pygame.draw.rect(surf,C_RED,(x-28,hy,56,5))

        # ── "GEAR 2nd!" ข้อความเมื่อเปิดใหม่ ──────────────
        if g2 and self.gear2_t > self.GEAR2_DUR - 0.8:
            a = min(1.0, (self.GEAR2_DUR - self.gear2_t) / 0.3)
            alpha = int(255 * (1 - abs(self.gear2_t - self.GEAR2_DUR + 0.4)/0.4))
            # วาดข้อความผ่าน surface
            pass

# ══════════════════════════════════════════════════════════
#  ENEMIES
# ══════════════════════════════════════════════════════════
class Enemy:
    SPEED=80; MAX_HP=60; RADIUS=16; DAMAGE=10; SCORE=50

    def __init__(self, x, y):
        self.x=float(x); self.y=float(y)
        self.hp=self.MAX_HP; self.alive=True
        self.flash_t=0.0; self.walk_t=random.uniform(0,6.28)
        self.facing=1

    def take_damage(self, dmg):
        self.hp-=dmg; self.flash_t=0.12
        if self.hp<=0: self.hp=0; self.alive=False

    def update(self, dt, px, py):
        dx=px-self.x; dy=py-self.y
        nx,ny=norm(dx,dy)
        self.x+=nx*self.SPEED*dt; self.y+=ny*self.SPEED*dt
        self.walk_t+=dt*(self.SPEED/40)
        self.facing=1 if dx>=0 else -1
        self.flash_t=max(0.0,self.flash_t-dt)

    def collides_player(self, p):
        return math.hypot(self.x-p.x,self.y-p.y)<self.RADIUS+p.RADIUS

    def _hp_bar(self, surf):
        bw,bh=38,5; bx=int(self.x)-bw//2; by=int(self.y)-40
        pygame.draw.rect(surf,C_HP_BG,(bx,by,bw,bh),border_radius=2)
        fw=int(bw*self.hp/self.MAX_HP)
        if fw>0: pygame.draw.rect(surf,C_HP_FG,(bx,by,fw,bh),border_radius=2)
        pygame.draw.rect(surf,C_HP_BD,(bx,by,bw,bh),1,border_radius=2)

    def draw(self, surf): raise NotImplementedError

# ── Marine Soldier ────────────────────────────────────────
class MarineSoldier(Enemy):
    SPEED=75; MAX_HP=50; SCORE=30

    def draw(self, surf):
        x,y=int(self.x),int(self.y); f=self.facing
        bob=int(math.sin(self.walk_t)*3)
        if self.flash_t>0:
            s=pygame.Surface((40,56),pygame.SRCALPHA)
            pygame.draw.ellipse(s,(255,255,255,210),s.get_rect())
            surf.blit(s,(x-20,y-28))
        else:
            pygame.draw.rect(surf,(20,20,80),(x-10,y+10+bob,9,16),border_radius=3)
            pygame.draw.rect(surf,(20,20,80),(x+2, y+10+bob,9,16),border_radius=3)
            pygame.draw.rect(surf,C_WHITE,(x-13,y-10+bob,26,22),border_radius=4)
            pygame.draw.rect(surf,C_NAVY, (x-13,y-2+bob, 26, 5))
            pygame.draw.ellipse(surf,(210,170,120),(x-13,y-34+bob,26,26))
            pygame.draw.ellipse(surf,C_WHITE,(x-16,y-36+bob,32,10))
            pygame.draw.ellipse(surf,C_NAVY, (x-12,y-40+bob,24,14))
            pygame.draw.circle(surf,C_BLACK,(x-4*f,y-24+bob),3)
            pygame.draw.circle(surf,C_BLACK,(x+4*f,y-24+bob),3)
            pygame.draw.rect(surf,C_DARK_GREY,(x+12*f,y-5+bob,4*f,20),border_radius=1)
        self._hp_bar(surf)

# ── Buggy the Clown ───────────────────────────────────────
class BuggyClown(Enemy):
    SPEED=100; MAX_HP=80; SCORE=80; DAMAGE=15

    def __init__(self, x, y):
        super().__init__(x,y); self.laugh_t=0.0; self.hp=self.MAX_HP

    def update(self, dt, px, py):
        super().update(dt,px,py); self.laugh_t+=dt

    def draw(self, surf):
        x,y=int(self.x),int(self.y); f=self.facing
        bob=int(math.sin(self.walk_t)*4)
        if self.flash_t>0:
            s=pygame.Surface((44,60),pygame.SRCALPHA)
            pygame.draw.ellipse(s,(255,255,255,210),s.get_rect())
            surf.blit(s,(x-22,y-30))
        else:
            pygame.draw.rect(surf,(180,0,180),(x-11,y+10+bob,10,18),border_radius=3)
            pygame.draw.rect(surf,(255,165,0),(x+2, y+10+bob,10,18),border_radius=3)
            pygame.draw.rect(surf,C_NAVY_L,(x-15,y-10+bob,15,22),border_radius=4)
            pygame.draw.rect(surf,C_RED,   (x,   y-10+bob,15,22),border_radius=4)
            pygame.draw.ellipse(surf,(230,210,200),(x-15,y-38+bob,30,28))
            pygame.draw.circle(surf,C_RED,(x,y-26+bob),7)
            pygame.draw.circle(surf,C_WHITE,(x-7*f,y-32+bob),5)
            pygame.draw.circle(surf,C_WHITE,(x+5*f,y-32+bob),5)
            pygame.draw.circle(surf,(200,0,200),(x-7*f,y-32+bob),3)
            pygame.draw.circle(surf,(200,0,200),(x+5*f,y-32+bob),3)
            pygame.draw.polygon(surf,C_PURPLE,
                [(x,y-55+bob),(x-16,y-38+bob),(x+16,y-38+bob)])
            pygame.draw.circle(surf,C_YELLOW,(x,y-55+bob),6)
            go=int(4*abs(math.sin(self.laugh_t*3)))
            pygame.draw.arc(surf,C_BLACK,(x-8,y-20+bob,16,8+go),math.pi,2*math.pi,2)
        self._hp_bar(surf)

# ── Smoker ───────────────────────────────────────────────
class Smoker(Enemy):
    SPEED=55; MAX_HP=160; SCORE=130; DAMAGE=22; RADIUS=22

    def __init__(self, x, y):
        super().__init__(x,y); self.smoke_t=0.0; self.hp=self.MAX_HP

    def update(self, dt, px, py):
        super().update(dt,px,py); self.smoke_t+=dt

    def draw(self, surf):
        x,y=int(self.x),int(self.y); f=self.facing
        bob=int(math.sin(self.walk_t)*2)
        if self.flash_t>0:
            s=pygame.Surface((56,70),pygame.SRCALPHA)
            pygame.draw.ellipse(s,(255,255,255,210),s.get_rect())
            surf.blit(s,(x-28,y-40))
        else:
            pygame.draw.rect(surf,(40,40,40),(x-14,y+12+bob,12,20),border_radius=4)
            pygame.draw.rect(surf,(40,40,40),(x+3, y+12+bob,12,20),border_radius=4)
            pygame.draw.rect(surf,C_WHITE,(x-20,y-15+bob,40,30),border_radius=6)
            for i in range(-2,3):
                pygame.draw.line(surf,C_GREY,(x+i*5,y-15+bob),(x+i*5,y-5+bob),2)
            pygame.draw.ellipse(surf,(190,155,110),(x-18,y-48+bob,36,34))
            for hx in range(-14,15,5):
                pygame.draw.line(surf,C_WHITE,(x+hx,y-48+bob),(x+hx,y-42+bob),3)
            pygame.draw.line(surf,C_BLACK,(x-12*f,y-32+bob),(x-4*f,y-32+bob),2)
            pygame.draw.line(surf,C_BLACK,(x+4*f, y-32+bob),(x+12*f,y-32+bob),2)
            pygame.draw.rect(surf,(120,80,40),(x+10*f,y-28+bob,16*f,4),border_radius=2)
            pygame.draw.rect(surf,(120,80,40),(x+12*f,y-24+bob,14*f,4),border_radius=2)
            for i in range(3):
                st=(self.smoke_t+i*0.4)%1.2
                sr2=int(4+st*10); sa=int(max(0,180*(1-st/1.2)))
                sx2=int(self.x+22*f); sy2=int(self.y-24+bob-int(st*30))
                sc=pygame.Surface((sr2*2,sr2*2),pygame.SRCALPHA)
                pygame.draw.circle(sc,(200,200,200,sa),(sr2,sr2),sr2)
                surf.blit(sc,(sx2-sr2,sy2-sr2))
        self._hp_bar(surf)

# ══════════════════════════════════════════════════════════
#  MAP
# ══════════════════════════════════════════════════════════
class GameMap:
    def __init__(self):
        self.wave_t = 0.0
        self._bg    = self._build()
        self.rocks  = [(random.randint(80,WIDTH-80),
                        random.randint(300,HEIGHT-60),
                        random.randint(12,28)) for _ in range(12)]

    def _build(self):
        bg=pygame.Surface((WIDTH,HEIGHT))
        sky_h=HEIGHT//4
        for y in range(sky_h):
            pygame.draw.line(bg,lerp_col(C_SKY,(160,220,255),y/sky_h),(0,y),(WIDTH,y))
        o0=sky_h; o1=sky_h+HEIGHT//5
        for y in range(o0,o1):
            pygame.draw.line(bg,lerp_col(C_OCEAN_L,C_OCEAN_D,(y-o0)/(o1-o0)),(0,y),(WIDTH,y))
        gs=o1
        for y in range(gs,HEIGHT):
            pygame.draw.line(bg,lerp_col(C_SAND,C_SAND_D,(y-gs)/(HEIGHT-gs)),(0,y),(WIDTH,y))
        for ci in range(0,WIDTH,TILE*2):
            pygame.draw.rect(bg,C_STONE,(ci,gs-40,TILE,40))
            pygame.draw.rect(bg,C_STONE_D,(ci,gs-40,TILE,40),3)
            for bi in range(3):
                pygame.draw.rect(bg,C_STONE,(ci+bi*16,gs-56,12,20))
        pygame.draw.rect(bg,C_NAVY,(WIDTH//2-130,38,260,72),border_radius=8)
        pygame.draw.rect(bg,C_WHITE,(WIDTH//2-130,38,260,72),3,border_radius=8)
        return bg

    def update(self, dt): self.wave_t+=dt

    def draw(self, surf):
        surf.blit(self._bg,(0,0))
        oy=HEIGHT//4+HEIGHT//5-12
        for i in range(6):
            wx=int((i*180+self.wave_t*60)%(WIDTH+40))-20
            wy=oy+int(math.sin(self.wave_t*2+i)*4)
            pygame.draw.arc(surf,(180,230,255),(wx,wy,80,18),0,math.pi,3)
        for fx,fy in [(200,30),(WIDTH-200,30),(WIDTH//2,20)]:
            pygame.draw.line(surf,C_STONE_D,(fx,fy),(fx,fy+70),3)
            wv=int(math.sin(self.wave_t*3)*5)
            pygame.draw.polygon(surf,C_NAVY,
                [(fx,fy),(fx+36+wv,fy+10+wv//2),(fx,fy+22)])
        for rx,ry,rr in self.rocks:
            pygame.draw.ellipse(surf,C_STONE_D,(rx-rr,ry-rr//2,rr*2,rr))
            pygame.draw.ellipse(surf,C_STONE,  (rx-rr+2,ry-rr//2,rr*2-4,rr-2))

# ══════════════════════════════════════════════════════════
#  SPAWN MANAGER
# ══════════════════════════════════════════════════════════
class SpawnManager:
    def __init__(self): self.timer=0.0; self.wave=1; self.wave_t=0.0

    def _interval(self): return max(0.55, 2.5-self.wave*0.07)

    def update(self, dt, enemies):
        self.timer+=dt; self.wave_t+=dt
        if self.wave_t>15: self.wave_t=0; self.wave+=1
        out=[]
        if self.timer>=self._interval():
            self.timer=0
            n=random.randint(1,1+self.wave//3)
            for _ in range(n): out.append(self._spawn())
        return out

    def _spawn(self):
        side=random.randint(0,3)
        if   side==0: x,y=random.randint(0,WIDTH),-30
        elif side==1: x,y=random.randint(0,WIDTH),HEIGHT+30
        elif side==2: x,y=-30,random.randint(0,HEIGHT)
        else:         x,y=WIDTH+30,random.randint(0,HEIGHT)
        cls=random.choices([MarineSoldier,BuggyClown,Smoker],[70,20,10])[0]
        return cls(x,y)

# ══════════════════════════════════════════════════════════
#  UI
# ══════════════════════════════════════════════════════════
class UI:
    def __init__(self, fonts): self.f=fonts

    def draw(self, surf, player, score, elapsed, wave):
        # ── HP bar ─────────────────────────────────────────
        bw,bh=200,22; bx,by=20,20
        pygame.draw.rect(surf,C_HP_BG,(bx,by,bw,bh),border_radius=6)
        fw=int(bw*player.hp/player.MAX_HP)
        if fw>0:
            pygame.draw.rect(surf,lerp_col(C_RED,C_GREEN,player.hp/player.MAX_HP),
                             (bx,by,fw,bh),border_radius=6)
        pygame.draw.rect(surf,C_HP_BD,(bx,by,bw,bh),2,border_radius=6)
        surf.blit(self.f['sm'].render(f"HP  {player.hp}/{player.MAX_HP}",True,C_WHITE),(bx+6,by+3))

        # ── Gear Second bar ────────────────────────────────
        sk_y=by+34
        sbw=200; sbh=14

        if player.in_gear2:
            # Active: แสดง duration ที่เหลือ — สีแดงร้อน
            label = self.f['sm'].render("⚡ GEAR 2nd ACTIVE!",True,(255,120,60))
            surf.blit(label,(bx,sk_y))
            frac = player.gear2_t / player.GEAR2_DUR
            pygame.draw.rect(surf,(60,0,0),(bx,sk_y+20,sbw,sbh),border_radius=5)
            t0 = pygame.time.get_ticks()/200
            pulse_col = lerp_col((220,40,0),(255,160,50), 0.5+0.5*math.sin(t0))
            pygame.draw.rect(surf,pulse_col,(bx,sk_y+20,int(sbw*frac),sbh),border_radius=5)
            pygame.draw.rect(surf,(255,80,30),(bx,sk_y+20,sbw,sbh),2,border_radius=5)
            secs_left = self.f['xs'].render(f"{player.gear2_t:.1f}s",True,C_WHITE)
            surf.blit(secs_left,(bx+sbw+6,sk_y+20))
        elif player.gear2_cd > 0:
            # Cooldown
            label = self.f['sm'].render("GEAR 2nd [SHIFT]",True,C_GREY)
            surf.blit(label,(bx,sk_y))
            frac = max(0,1 - player.gear2_cd/player.GEAR2_CD)
            pygame.draw.rect(surf,(40,20,0),(bx,sk_y+20,sbw,sbh),border_radius=5)
            if frac>0:
                pygame.draw.rect(surf,lerp_col(C_RED,C_YELLOW,frac),
                                 (bx,sk_y+20,int(sbw*frac),sbh),border_radius=5)
            pygame.draw.rect(surf,C_GOLD,(bx,sk_y+20,sbw,sbh),1,border_radius=5)
            cd_txt = self.f['xs'].render(f"{player.gear2_cd:.1f}s",True,C_GREY)
            surf.blit(cd_txt,(bx+sbw+6,sk_y+20))
        else:
            # Ready
            label = self.f['sm'].render("GEAR 2nd [SHIFT]",True,C_GOLD)
            surf.blit(label,(bx,sk_y))
            pygame.draw.rect(surf,(40,20,0),(bx,sk_y+20,sbw,sbh),border_radius=5)
            pygame.draw.rect(surf,C_YELLOW,(bx,sk_y+20,sbw,sbh),border_radius=5)
            pygame.draw.rect(surf,C_GOLD,(bx,sk_y+20,sbw,sbh),2,border_radius=5)
            surf.blit(self.f['xs'].render("READY!",True,(50,50,0)),(bx+sbw//2-20,sk_y+22))

        # ── Score / time ───────────────────────────────────
        sc=self.f['md'].render(f"Score  {score:,}",True,C_GOLD)
        surf.blit(sc,(WIDTH-sc.get_width()-20,20))
        t_=self.f['sm'].render(f"{int(elapsed)//60:02d}:{int(elapsed)%60:02d}",True,C_WHITE)
        surf.blit(t_,(WIDTH-t_.get_width()-20,56))

        # ── Wave & banner ──────────────────────────────────
        wt=self.f['sm'].render(f"WAVE {wave}",True,C_PINK)
        surf.blit(wt,(WIDTH//2-wt.get_width()//2,16))
        mt=self.f['md'].render("MARINE BASE",True,C_WHITE)
        surf.blit(mt,(WIDTH//2-mt.get_width()//2,55))

        # ── Hint ───────────────────────────────────────────
        h=self.f['xs'].render(
            "WASD = Move   |   Mouse = Aim   |   SPACE = Gum-Gum Pistol   |   SHIFT = Gear Second",
            True,(180,180,180))
        surf.blit(h,(WIDTH//2-h.get_width()//2,HEIGHT-22))

# ══════════════════════════════════════════════════════════
#  GAME OVER
# ══════════════════════════════════════════════════════════
def draw_gameover(surf, fonts, score, elapsed, wave):
    ov=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    ov.fill((0,0,0,185)); surf.blit(ov,(0,0))
    for text,fk,col,cy in [
        ("GAME OVER",              'xl', C_RED,           HEIGHT//2-115),
        ("— Luffy has fallen! —",  'md', C_GREY,          HEIGHT//2-60),
        (f"Score:  {score:,}",     'lg', C_GOLD,          HEIGHT//2),
        (f"Survived:  {int(elapsed)//60:02d}:{int(elapsed)%60:02d}",
                                   'md', C_WHITE,         HEIGHT//2+62),
        (f"Wave: {wave}",          'md', C_PINK,          HEIGHT//2+104),
        ("Press  R  to restart  |  ESC  to quit",
                                   'sm', (180,180,180),   HEIGHT//2+162),
    ]:
        r=fonts[fk].render(text,True,col)
        surf.blit(r,(WIDTH//2-r.get_width()//2,cy))

# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════
def main():
    pygame.init()
    pygame.display.set_caption("🏴‍☠️ One Piece — Gum-Gum Survival")
    screen = pygame.display.set_mode((WIDTH,HEIGHT))
    clock  = pygame.time.Clock()

    fonts = {
        'xl': pygame.font.SysFont("Arial",64,bold=True),
        'lg': pygame.font.SysFont("Arial",48,bold=True),
        'md': pygame.font.SysFont("Arial",32,bold=True),
        'sm': pygame.font.SysFont("Arial",18),
        'xs': pygame.font.SysFont("Arial",13),
    }

    try:    sound=Sound()
    except: sound=type('S',(),{'play':lambda*a:None})()

    def new_game():
        return (Player(WIDTH//2,HEIGHT//2),
                [], [], [],
                SpawnManager(), GameMap(), UI(fonts))

    player,enemies,fists,particles,spawner,gmap,ui = new_game()
    score=0; elapsed=0.0; score_t=0.0; game_over=False

    # ── MAIN LOOP ─────────────────────────────────────────
    while True:
        dt = min(clock.tick(FPS)/1000.0, 0.05)

        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if game_over and ev.key==pygame.K_r:
                    player,enemies,fists,particles,spawner,gmap,ui=new_game()
                    score=0; elapsed=0.0; score_t=0.0; game_over=False

        if not game_over:
            keys = pygame.key.get_pressed()

            # Player
            player.update(dt, keys)

            # SPACE → Pistol (เล็งด้วยเมาส์)
            mx, my = pygame.mouse.get_pos()
            if keys[pygame.K_SPACE]:
                f = player.try_pistol(mx, my, sound)
                if f: fists.append(f)

            # SHIFT → Gear Second
            if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
                if player.try_gear2(sound):
                    # burst ควันและแสงตอนเปิด Gear 2
                    for _ in range(20):
                        a=random.uniform(0,6.28); sp=random.uniform(100,300)
                        particles.append(Particle(player.x,player.y,
                            (255,random.randint(60,160),30),
                            math.cos(a)*sp,math.sin(a)*sp,
                            life=random.uniform(0.4,1.0),r=random.randint(6,14)))

            # ── Steam ควัน Gear Second ────────────────────
            player.emit_steam(particles)

            # Survival score
            elapsed+=dt; score_t+=dt
            if score_t>=1.0: score_t-=1.0; score+=5

            # Map & Spawn
            gmap.update(dt)
            enemies.extend(spawner.update(dt,enemies))

            # Fist update
            for fi in fists: fi.update(dt)
            fists = [fi for fi in fists if fi.active]

            # Enemy update + damage player
            for e in enemies:
                e.update(dt,player.x,player.y)
                if e.collides_player(player):
                    player.take_damage(e.DAMAGE)
                    sound.play('hit')

            # Fist vs Enemy
            for fi in fists:
                for e in enemies:
                    if not e.alive: continue
                    if fi.try_hit(e):
                        e.take_damage(fi.dmg)
                        sound.play('punch')
                        tx,ty=fi.tip
                        hit_col = (255,80,30) if player.in_gear2 else C_SKIN
                        for _ in range(8):
                            a=random.uniform(0,6.28)
                            sp=random.uniform(90,240)
                            particles.append(Particle(tx,ty,hit_col,
                                math.cos(a)*sp,math.sin(a)*sp,
                                life=random.uniform(0.2,0.5),
                                r=random.randint(3,9)))

            # Dead enemies → score + particles
            for e in [e for e in enemies if not e.alive]:
                score+=e.SCORE; sound.play('hit')
                for _ in range(12):
                    a=random.uniform(0,6.28); sp=random.uniform(80,260)
                    particles.append(Particle(e.x,e.y,C_RED,
                        math.cos(a)*sp,math.sin(a)*sp,
                        life=random.uniform(0.3,0.7),r=random.randint(4,11)))
            enemies=[e for e in enemies if e.alive]

            particles=[p for p in particles if p.update(dt)]

            if not player.alive:
                game_over=True; sound.play('death')

        # ── DRAW ──────────────────────────────────────────
        gmap.draw(screen)
        for p  in particles: p.draw(screen)
        for fi in fists:     fi.draw(screen)
        for e  in enemies:   e.draw(screen)
        if not game_over:    player.draw(screen)
        ui.draw(screen,player,score,elapsed,spawner.wave)
        if game_over: draw_gameover(screen,fonts,score,elapsed,spawner.wave)

        pygame.display.flip()

if __name__=="__main__":
    main()