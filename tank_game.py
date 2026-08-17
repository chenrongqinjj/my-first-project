"""
坦克大战 (Tank Battle) - 一个用 pygame 实现的简单小游戏

玩法:
    方向键 (↑ ↓ ← →) 控制坦克移动
    空格键 (Space)   发射炮弹
    P 键             暂停 / 继续
    R 键             游戏结束后重新开始
    Esc 键           退出游戏

目标:
    击毁所有来袭的敌方坦克, 同时保护自己不被击中。
    敌人碰到你或击中你都会让你损失一条生命。
    砖墙可以被炮弹逐渐打掉, 钢墙无法被摧毁。

依赖:
    pip install pygame
运行:
    python tank_game.py
"""

import random
import sys

import pygame

# ------------------------------------------------------------------ 常量配置
TILE = 40                       # 每个网格 and 坦克的像素大小
COLS, ROWS = 16, 13            # 地图的列数与行数
WIDTH, HEIGHT = COLS * TILE, ROWS * TILE
FPS = 60

# 颜色 (R, G, B)
BLACK = (17, 17, 17)
WHITE = (240, 240, 240)
GREEN = (80, 200, 100)
RED = (220, 70, 70)
YELLOW = (240, 210, 90)
GRAY = (130, 130, 130)
BROWN = (150, 90, 50)
DARK = (40, 40, 40)

# 方向向量
UP, DOWN, LEFT, RIGHT = "up", "down", "left", "right"
DIRS = {
    UP: (0, -1),
    DOWN: (0, 1),
    LEFT: (-1, 0),
    RIGHT: (1, 0),
}


# ------------------------------------------------------------------ 墙体
class Wall:
    """砖墙 (可被摧毁) 或钢墙 (不可摧毁)。"""

    def __init__(self, col, row, steel=False):
        self.rect = pygame.Rect(col * TILE, row * TILE, TILE, TILE)
        self.steel = steel

    def draw(self, surface):
        if self.steel:
            pygame.draw.rect(surface, GRAY, self.rect)
            pygame.draw.rect(surface, WHITE, self.rect, 2)
        else:
            pygame.draw.rect(surface, BROWN, self.rect)
            for i in range(2):
                for j in range(2):
                    bx = self.rect.x + i * TILE // 2
                    by = self.rect.y + j * TILE // 2
                    pygame.draw.rect(surface, DARK, (bx, by, TILE // 2, TILE // 2), 1)


# ------------------------------------------------------------------ 炮弹
class Bullet:
    SPEED = 8
    SIZE = 8

    def __init__(self, x, y, direction, owner):
        self.direction = direction
        self.owner = owner
        self.alive = True
        self.rect = pygame.Rect(0, 0, self.SIZE, self.SIZE)
        self.rect.center = (x, y)

    def update(self, walls):
        dx, dy = DIRS[self.direction]
        self.rect.x += dx * self.SPEED
        self.rect.y += dy * self.SPEED
        if (self.rect.left < 0 or self.rect.right > WIDTH or
                self.rect.top < 0 or self.rect.bottom > HEIGHT):
            self.alive = False
            return
        for wall in walls[:]:
            if self.rect.colliderect(wall.rect):
                self.alive = False
                if not wall.steel:
                    walls.remove(wall)
                break

    def draw(self, surface):
        color = YELLOW if self.owner == "player" else RED
        pygame.draw.rect(surface, color, self.rect)


# ------------------------------------------------------------------ 坦克
class Tank:
    def __init__(self, col, row, color, is_player=False):
        self.rect = pygame.Rect(col * TILE, row * TILE, TILE, TILE)
        self.color = color
        self.direction = UP if is_player else DOWN
        self.speed = 3 if is_player else 2
        self.is_player = is_player
        self.alive = True
        self.reload = 0
        self.reload_max = 20 if is_player else 45

    def _blocked(self, rect, walls, others):
        if rect.left < 0 or rect.right > WIDTH or rect.top < 0 or rect.bottom > HEIGHT:
            return True
        for wall in walls:
            if rect.colliderect(wall.rect):
                return True
        for other in others:
            if other is not self and other.alive and rect.colliderect(other.rect):
                return True
        return False

    def move(self, direction, walls, others):
        self.direction = direction
        dx, dy = DIRS[direction]
        new_rect = self.rect.move(dx * self.speed, dy * self.speed)
        if not self._blocked(new_rect, walls, others):
            self.rect = new_rect

    def shoot(self, bullets):
        if self.reload > 0:
            return
        self.reload = self.reload_max
        dx, dy = DIRS[self.direction]
        bx = self.rect.centerx + dx * (TILE // 2)
        by = self.rect.centery + dy * (TILE // 2)
        owner = "player" if self.is_player else "enemy"
        bullets.append(Bullet(bx, by, self.direction, owner))

    def update_reload(self):
        if self.reload > 0:
            self.reload -= 1

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, WHITE, self.rect, 2)
        cx, cy = self.rect.center
        dx, dy = DIRS[self.direction]
        end = (cx + dx * TILE // 2, cy + dy * TILE // 2)
        pygame.draw.line(surface, WHITE, (cx, cy), end, 5)


# ------------------------------------------------------------------ 敌方 AI
class EnemyTank(Tank):
    def __init__(self, col, row):
        super().__init__(col, row, RED, is_player=False)
        self.move_timer = 0

    def ai_update(self, walls, others, bullets, player):
        self.move_timer -= 1
        if self.move_timer <= 0:
            self.move_timer = random.randint(30, 90)
            if random.random() < 0.5 and player.alive:
                if abs(player.rect.centerx - self.rect.centerx) > \
                        abs(player.rect.centery - self.rect.centery):
                    self.direction = LEFT if player.rect.centerx < self.rect.centerx else RIGHT
                else:
                    self.direction = UP if player.rect.centery < self.rect.centery else DOWN
            else:
                self.direction = random.choice(list(DIRS.keys()))

        old = self.rect
        self.move(self.direction, walls, others)
        if self.rect == old:
            self.move_timer = 0

        if random.random() < 0.02:
            self.shoot(bullets)


# ------------------------------------------------------------------ 地图生成
def build_walls():
    walls = []
    forbidden = set()
    for c in range(6, 10):
        forbidden.add((c, ROWS - 1))
        forbidden.add((c, ROWS - 2))
    for c in [1, COLS // 2, COLS - 2]:
        forbidden.add((c, 0))
        forbidden.add((c, 1))

    for row in range(2, ROWS - 2):
        for col in range(1, COLS - 1):
            if (col, row) in forbidden:
                continue
            r = random.random()
            if r < 0.14:
                walls.append(Wall(col, row, steel=False))
            elif r < 0.17:
                walls.append(Wall(col, row, steel=True))
    return walls


# ------------------------------------------------------------------ 主游戏类
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("坦克大战 Tank Battle")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("simhei,microsoftyahei,arial", 22)
        self.big_font = pygame.font.SysFont("simhei,microsoftyahei,arial", 48)
        self.reset()

    def reset(self):
        self.walls = build_walls()
        self.player = Tank(COLS // 2, ROWS - 1, GREEN, is_player=True)
        self.enemies = []
        self.bullets = []
        self.score = 0
        self.lives = 3
        self.enemies_left = 8
        self.spawn_timer = 0
        self.max_enemies = 4
        self.state = "playing"
        self.spawn_points = [(1, 0), (COLS // 2, 0), (COLS - 2, 0)]

    def spawn_enemy(self):
        if self.enemies_left <= 0 or len(self.enemies) >= self.max_enemies:
            return
        self.spawn_timer -= 1
        if self.spawn_timer > 0:
            return
        self.spawn_timer = 90
        col, row = random.choice(self.spawn_points)
        spawn_rect = pygame.Rect(col * TILE, row * TILE, TILE, TILE)
        for t in self.enemies + [self.player]:
            if t.alive and spawn_rect.colliderect(t.rect):
                return
        self.enemies.append(EnemyTank(col, row))
        self.enemies_left -= 1

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.quit()
                if event.key == pygame.K_p and self.state in ("playing", "paused"):
                    self.state = "paused" if self.state == "playing" else "playing"
                if event.key == pygame.K_r and self.state in ("gameover", "win"):
                    self.reset()
                if event.key == pygame.K_SPACE and self.state == "playing":
                    self.player.shoot(self.bullets)

        if self.state != "playing":
            return
        keys = pygame.key.get_pressed()
        others = self.enemies
        if keys[pygame.K_UP]:
            self.player.move(UP, self.walls, others)
        elif keys[pygame.K_DOWN]:
            self.player.move(DOWN, self.walls, others)
        elif keys[pygame.K_LEFT]:
            self.player.move(LEFT, self.walls, others)
        elif keys[pygame.K_RIGHT]:
            self.player.move(RIGHT, self.walls, others)

    def update(self):
        if self.state != "playing":
            return

        self.player.update_reload()
        for enemy in self.enemies:
            enemy.update_reload()

        self.spawn_enemy()

        all_tanks = self.enemies + [self.player]
        for enemy in self.enemies:
            enemy.ai_update(self.walls, all_tanks, self.bullets, self.player)

        for bullet in self.bullets[:]:
            bullet.update(self.walls)
            if not bullet.alive:
                if bullet in self.bullets:
                    self.bullets.remove(bullet)
                continue
            if bullet.owner == "player":
                for enemy in self.enemies[:]:
                    if enemy.alive and bullet.rect.colliderect(enemy.rect):
                        enemy.alive = False
                        self.enemies.remove(enemy)
                        bullet.alive = False
                        self.score += 100
                        break
            else:
                if self.player.alive and bullet.rect.colliderect(self.player.rect):
                    bullet.alive = False
                    self.hit_player()
            if not bullet.alive and bullet in self.bullets:
                self.bullets.remove(bullet)

        for enemy in self.enemies:
            if enemy.alive and self.player.alive and enemy.rect.colliderect(self.player.rect):
                self.hit_player()
                break

        if self.lives <= 0:
            self.state = "gameover"
        elif self.enemies_left <= 0 and not self.enemies:
            self.state = "win"

    def hit_player(self):
        self.lives -= 1
        if self.lives > 0:
            self.player.rect.topleft = ((COLS // 2) * TILE, (ROWS - 1) * TILE)
            self.player.direction = UP

    def draw_hud(self):
        info = f"得分: {self.score}    生命: {self.lives}    剩余敌人: {self.enemies_left + len(self.enemies)}"
        text = self.font.render(info, True, WHITE)
        self.screen.blit(text, (10, 8))

    def draw_center_text(self, lines):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        y = HEIGHT // 2 - len(lines) * 30
        for line, big in lines:
            font = self.big_font if big else self.font
            surf = font.render(line, True, WHITE)
            rect = surf.get_rect(center=(WIDTH // 2, y))
            self.screen.blit(surf, rect)
            y += 60 if big else 34

    def draw(self):
        self.screen.fill(BLACK)
        for wall in self.walls:
            wall.draw(self.screen)
        if self.player.alive:
            self.player.draw(self.screen)
        for enemy in self.enemies:
            enemy.draw(self.screen)
        for bullet in self.bullets:
            bullet.draw(self.screen)
        self.draw_hud()

        if self.state == "paused":
            self.draw_center_text([("已暂停", True), ("按 P 继续", False)])
        elif self.state == "gameover":
            self.draw_center_text([
                ("游戏结束", True),
                (f"最终得分: {self.score}", False),
                ("按 R 重新开始, Esc 退出", False),
            ])
        elif self.state == "win":
            self.draw_center_text([
                ("胜利!", True),
                (f"最终得分: {self.score}", False),
                ("按 R 再玩一次, Esc 退出", False),
            ])

        pygame.display.flip()

    def run(self):
        while True:
            self.handle_input()
            self.update()
            self.draw()
            self.clock.tick(FPS)

    def quit(self):
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
