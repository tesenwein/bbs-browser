"""Arcade — Paddle and Stacker directly in the terminal ('game' opens the menu).

Both games run in raw mode (cbreak) and draw via absolute cursor positions,
just like the Matrix screensaver. High scores go into the state file under
the "games" section.
"""

import contextlib
import random
import sys
import time

from . import keys, lightbar
from .constants import BOLD, CLEAR, DIM, RESET
from .i18n import t
from .state import load_section, save_section

HIDE, SHOW = "\033[?25l", "\033[?25h"


def _pos(y, x):
    return f"\033[{y};{x}H"


@contextlib.contextmanager
def _raw_screen():
    """Raw mode + blank screen without cursor — and everything cleanly restored."""
    sys.stdout.write(HIDE + CLEAR)
    try:
        with keys.raw_mode():
            yield
    finally:
        sys.stdout.write(RESET + SHOW + CLEAR)
        sys.stdout.flush()


_key = keys.read_game_key


def _draw(lines, color, top=2, left=3):
    """Write finished frame lines to the screen in one go."""
    out = [color]
    for i, line in enumerate(lines):
        out.append(_pos(top + i, left) + line)
    out.append(RESET)
    sys.stdout.write("".join(out))
    sys.stdout.flush()


# -- High scores ---------------------------------------------------------

def _highscore(name):
    return int(load_section("games").get(name, 0))


def _save_highscore(name, score):
    """Saves only if the value beats the old record."""
    if score <= _highscore(name):
        return False
    games = load_section("games")
    games[name] = score
    save_section("games", games)
    return True


def _game_over(term, name, score):
    """End screen with record notice — Enter returns to the menu."""
    record = _save_highscore(name, score)
    term.rule(t("games.game_over"))
    term.type_out(t("games.your_score", score=score), delay=0.003)
    if record:
        term.type_out(t("games.new_highscore"), delay=0.004)
        term.beep(2)
    else:
        term.type_out(t("games.highscore", score=_highscore(name)), delay=0.002)
    term.rule()
    term.prompt(t("games.press_enter"))


# -- Paddle -------------------------------------------------------------

PONG_W, PONG_H = 58, 18       # inner dimensions of the playing field in characters
PADDLE = 4                    # paddle length in rows
PONG_FRAME = 0.045
WIN_SCORE = 7


def paddle(term):
    """Paddle duel against the computer. w/s or arrows up/down, q quits."""
    if not sys.stdin.isatty():
        term.error(t("games.tty_required"))
        return
    you = cpu = 0
    player_y = enemy_y = (PONG_H - PADDLE) / 2
    ball_x, ball_y = PONG_W / 2, PONG_H / 2
    vx, vy = -0.9, random.choice((-0.45, 0.45))
    quit_early = False

    with _raw_screen():
        while max(you, cpu) < WIN_SCORE:
            key = _key(PONG_FRAME)
            if key == "q":
                quit_early = True
                break
            if key in ("w", "up"):
                player_y = max(0, player_y - 1.5)
            elif key in ("s", "down"):
                player_y = min(PONG_H - PADDLE, player_y + 1.5)

            # The computer aims for the ball's center, but sluggishly enough to let you win.
            target = ball_y - PADDLE / 2
            enemy_y += max(-0.7, min(0.7, target - enemy_y))
            enemy_y = max(0, min(PONG_H - PADDLE, enemy_y))

            ball_x += vx
            ball_y += vy
            if ball_y <= 0 or ball_y >= PONG_H - 1:
                vy = -vy
                ball_y = max(0, min(PONG_H - 1, ball_y))
                term.beep()

            # Paddle hit: the point of contact determines the bounce angle.
            if ball_x <= 1 and player_y <= ball_y <= player_y + PADDLE and vx < 0:
                vx = -vx * 1.03
                vy += (ball_y - (player_y + PADDLE / 2)) * 0.25
                term.beep()
            elif ball_x >= PONG_W - 2 and enemy_y <= ball_y <= enemy_y + PADDLE and vx > 0:
                vx = -vx * 1.03
                vy += (ball_y - (enemy_y + PADDLE / 2)) * 0.25

            if ball_x < 0 or ball_x > PONG_W - 1:
                # Serve always goes to whoever just conceded.
                if ball_x < 0:
                    cpu, vx = cpu + 1, 0.9
                else:
                    you, vx = you + 1, -0.9
                ball_x, ball_y = PONG_W / 2, PONG_H / 2
                vy = random.choice((-0.45, 0.45))
                time.sleep(0.4)

            _draw(_pong_frame(you, cpu, player_y, enemy_y, ball_x, ball_y), term.color)

    if quit_early:
        return
    term.type_out(t("games.pong_result", you=you, cpu=cpu), delay=0.004)
    _game_over(term, "paddle", you)


def _pong_frame(you, cpu, player_y, enemy_y, ball_x, ball_y):
    grid = [[" "] * PONG_W for _ in range(PONG_H)]
    for row in range(0, PONG_H, 2):          # center line
        grid[row][PONG_W // 2] = "┊"
    for i in range(PADDLE):
        grid[int(player_y) + i][0] = "█"
        grid[int(enemy_y) + i][PONG_W - 1] = "█"
    grid[int(ball_y)][int(ball_x)] = "●"
    top = "╔" + "═" * PONG_W + "╗"
    bottom = "╚" + "═" * PONG_W + "╝"
    score = f"{t('games.pong_you')} {you}   —   {cpu} {t('games.pong_cpu')}".center(PONG_W)
    return (
        [BOLD + score + RESET, top]
        + ["║" + "".join(row) + "║" for row in grid]
        + [bottom, DIM + t("games.pong_keys") + RESET]
    )


# -- Stacker ------------------------------------------------------------

TET_W, TET_H = 10, 20
CELL, EMPTY = "██", "  "
DROP_START = 0.55             # seconds per row at level 1
LINE_POINTS = (0, 40, 100, 300, 1200)

# (edge length of the rotation box, cells as (x, y))
PIECES = {
    "I": (4, [(0, 1), (1, 1), (2, 1), (3, 1)]),
    "J": (3, [(0, 0), (0, 1), (1, 1), (2, 1)]),
    "L": (3, [(2, 0), (0, 1), (1, 1), (2, 1)]),
    "O": (2, [(0, 0), (1, 0), (0, 1), (1, 1)]),
    "S": (3, [(1, 0), (2, 0), (0, 1), (1, 1)]),
    "T": (3, [(1, 0), (0, 1), (1, 1), (2, 1)]),
    "Z": (3, [(0, 0), (1, 0), (1, 1), (2, 1)]),
}


def _rotate(size, cells):
    return [(size - 1 - y, x) for x, y in cells]


def _fits(board, cells, ox, oy):
    for x, y in cells:
        px, py = ox + x, oy + y
        if not 0 <= px < TET_W or py >= TET_H:
            return False
        if py >= 0 and board[py][px]:
            return False
    return True


def stacker(term):
    """Stacker. a/d or arrows shift, w rotates, s drops faster,
    space hard-drops, q quits."""
    if not sys.stdin.isatty():
        term.error(t("games.tty_required"))
        return
    board = [[0] * TET_W for _ in range(TET_H)]
    bag = list(PIECES)
    random.shuffle(bag)
    nxt = bag.pop()
    score = lines = 0
    level = 1
    quit_early = False

    with _raw_screen():
        while True:
            name = nxt
            if not bag:
                bag = list(PIECES)
                random.shuffle(bag)
            nxt = bag.pop()
            size, cells = PIECES[name]
            ox, oy = (TET_W - size) // 2, -1
            if not _fits(board, cells, ox, oy):
                break                                  # stack reaches the top: game over
            interval = max(0.08, DROP_START - (level - 1) * 0.045)
            next_fall = time.monotonic() + interval

            while True:
                _draw(_tetris_frame(board, cells, ox, oy, nxt, score, lines, level), term.color)
                key = _key(max(0.01, next_fall - time.monotonic()))
                if key == "q":
                    quit_early = True
                    break
                if key in ("a", "left") and _fits(board, cells, ox - 1, oy):
                    ox -= 1
                elif key in ("d", "right") and _fits(board, cells, ox + 1, oy):
                    ox += 1
                elif key in ("w", "up"):
                    turned = _rotate(size, cells)
                    for kick in (0, -1, 1):            # dodge around the wall
                        if _fits(board, turned, ox + kick, oy):
                            cells, ox = turned, ox + kick
                            break
                elif key in ("s", "down") and _fits(board, cells, ox, oy + 1):
                    oy += 1
                    score += 1
                    next_fall = time.monotonic() + interval
                    continue
                elif key == " ":
                    while _fits(board, cells, ox, oy + 1):
                        oy += 1
                        score += 2
                    next_fall = 0                      # lock in immediately

                if time.monotonic() < next_fall:
                    continue
                if _fits(board, cells, ox, oy + 1):
                    oy += 1
                    next_fall = time.monotonic() + interval
                    continue
                break                                  # piece has landed

            if quit_early:
                break
            if any(oy + y < 0 for _, y in cells):
                break                                  # came to rest above the top edge
            for x, y in cells:
                board[oy + y][ox + x] = 1
            full = [i for i, row in enumerate(board) if all(row)]
            if full:
                for i in full:
                    board.pop(i)
                    board.insert(0, [0] * TET_W)
                lines += len(full)
                score += LINE_POINTS[len(full)] * level
                level = 1 + lines // 10
                term.beep(len(full))

    if quit_early:
        return
    _game_over(term, "stacker", score)


def _tetris_frame(board, cells, ox, oy, nxt, score, lines, level):
    grid = [row[:] for row in board]
    for x, y in cells:
        if oy + y >= 0:
            grid[oy + y][ox + x] = 2
    info = [
        BOLD + t("games.tetris_title") + RESET,
        "",
        t("games.tetris_score", score=score),
        t("games.tetris_lines", lines=lines),
        t("games.tetris_level", level=level),
        "",
        t("games.tetris_next"),
    ]
    size, cell_list = PIECES[nxt]
    preview = {(x, y) for x, y in cell_list}
    info += ["  " + "".join(CELL if (x, y) in preview else EMPTY for x in range(size))
             for y in range(size)]
    info += ["", DIM + t("games.tetris_keys_move") + RESET,
             DIM + t("games.tetris_keys_drop") + RESET]

    out = ["╔" + "══" * TET_W + "╗"]
    for i, row in enumerate(grid):
        body = "".join(BOLD + CELL + RESET if c == 2 else CELL if c else EMPTY for c in row)
        side = info[i] if i < len(info) else ""
        out.append("║" + body + "║  " + side + "\033[K")
    out.append("╚" + "══" * TET_W + "╝")
    return out


# -- Snake --------------------------------------------------------------

SNAKE_W, SNAKE_H = 29, 17     # field in cells; one cell is two characters
SNAKE_START = 0.13            # seconds per step at the start
SNAKE_MIN = 0.05
DIRECTIONS = {
    "w": (0, -1), "up": (0, -1), "s": (0, 1), "down": (0, 1),
    "a": (-1, 0), "left": (-1, 0), "d": (1, 0), "right": (1, 0),
}


def snake(term):
    """Snake. w/a/s/d or arrows steer, q quits. Each bite lengthens
    the snake and makes it a bit faster."""
    if not sys.stdin.isatty():
        term.error(t("games.tty_required"))
        return
    body = [(SNAKE_W // 2 - i, SNAKE_H // 2) for i in range(3)]
    dx, dy = 1, 0
    food = _snake_food(body)
    score = 0
    quit_early = False

    with _raw_screen():
        while True:
            interval = max(SNAKE_MIN, SNAKE_START - len(body) * 0.002)
            _draw(_snake_frame(body, food, score), term.color)
            key = _key(interval)
            if key == "q":
                quit_early = True
                break
            if key in DIRECTIONS:
                ndx, ndy = DIRECTIONS[key]
                # Ignore reversing directly into oneself.
                if (ndx, ndy) != (-dx, -dy):
                    dx, dy = ndx, ndy

            head = (body[0][0] + dx, body[0][1] + dy)
            if not (0 <= head[0] < SNAKE_W and 0 <= head[1] < SNAKE_H):
                break                                  # wall
            if head in body[:-1]:
                break                                  # bit itself
            body.insert(0, head)
            if head == food:
                score += 10
                term.beep()
                food = _snake_food(body)
                if food is None:
                    break                              # field full: perfect
            else:
                body.pop()

    if quit_early:
        return
    _game_over(term, "snake", score)


def _snake_food(body):
    """Free cell for the next bite — None if there's none left."""
    free = [(x, y) for y in range(SNAKE_H) for x in range(SNAKE_W)
            if (x, y) not in body]
    return random.choice(free) if free else None


def _snake_frame(body, food, score):
    grid = [[EMPTY] * SNAKE_W for _ in range(SNAKE_H)]
    for x, y in body[1:]:
        grid[y][x] = "▓▓"
    hx, hy = body[0]
    grid[hy][hx] = BOLD + "██" + RESET
    if food:
        fx, fy = food
        grid[fy][fx] = BOLD + "◆◆" + RESET
    inner = SNAKE_W * 2
    head_line = f"{t('games.snake_score', score=score)}   {t('games.snake_length', length=len(body))}"
    return (
        [BOLD + head_line.center(inner) + RESET, "╔" + "═" * inner + "╗"]
        + ["║" + "".join(row) + "║" for row in grid]
        + ["╚" + "═" * inner + "╝", DIM + t("games.snake_keys") + RESET]
    )


# -- Bricks -------------------------------------------------------------

BRICK_W, BRICK_COLS, BRICK_ROWS = 4, 14, 5
BRK_W, BRK_H = BRICK_W * BRICK_COLS, 18   # fits within 24 rows including the frame
BRK_PADDLE = 9
BRK_FRAME = 0.04
BRK_LIVES = 3


def bricks(term):
    """Bricks. a/d or arrows left/right move the paddle,
    q quits. Three lives; the upper rows are worth more points."""
    if not sys.stdin.isatty():
        term.error(t("games.tty_required"))
        return
    bricks = [[1] * BRICK_COLS for _ in range(BRICK_ROWS)]
    paddle_x = (BRK_W - BRK_PADDLE) / 2
    lives, score = BRK_LIVES, 0
    ball_x, ball_y, vx, vy = _brk_serve(paddle_x)
    quit_early = False

    with _raw_screen():
        while lives and any(any(row) for row in bricks):
            _draw(_brk_frame(bricks, paddle_x, ball_x, ball_y, score, lives), term.color)
            key = _key(BRK_FRAME)
            if key == "q":
                quit_early = True
                break
            if key in ("a", "left"):
                paddle_x = max(0, paddle_x - 2.5)
            elif key in ("d", "right"):
                paddle_x = min(BRK_W - BRK_PADDLE, paddle_x + 2.5)

            ball_x += vx
            ball_y += vy
            if ball_x <= 0 or ball_x >= BRK_W - 1:
                vx = -vx
                ball_x = max(0, min(BRK_W - 1, ball_x))
            if ball_y <= 0:
                vy = -vy
                ball_y = 0

            # Bricks: the rows sit directly below the ceiling.
            row = int(ball_y) - 1
            col = int(ball_x) // BRICK_W
            if 0 <= row < BRICK_ROWS and 0 <= col < BRICK_COLS and bricks[row][col]:
                bricks[row][col] = 0
                score += (BRICK_ROWS - row) * 10
                vy = -vy
                term.beep()

            # Paddle: the point of contact steers the ball, like in Paddle.
            if vy > 0 and ball_y >= BRK_H - 2 and paddle_x <= ball_x <= paddle_x + BRK_PADDLE:
                vy = -abs(vy)
                vx += (ball_x - (paddle_x + BRK_PADDLE / 2)) * 0.22
                vx = max(-1.2, min(1.2, vx))

            if ball_y > BRK_H - 1:
                lives -= 1
                if lives:
                    ball_x, ball_y, vx, vy = _brk_serve(paddle_x)
                    time.sleep(0.5)

    if quit_early:
        return
    if not any(any(row) for row in bricks):
        term.type_out(t("games.breakout_cleared"), delay=0.004)
        score += lives * 100
    _game_over(term, "bricks", score)


def _brk_serve(paddle_x):
    return paddle_x + BRK_PADDLE / 2, BRK_H - 3.0, random.choice((-0.55, 0.55)), -0.6


def _brk_frame(bricks, paddle_x, ball_x, ball_y, score, lives):
    grid = [[" "] * BRK_W for _ in range(BRK_H)]
    for r, row in enumerate(bricks):
        for c, alive in enumerate(row):
            if alive:
                for i in range(BRICK_W - 1):           # one column of gap
                    grid[r + 1][c * BRICK_W + i] = "▓"
    for i in range(BRK_PADDLE):
        grid[BRK_H - 1][int(paddle_x) + i] = "█"
    if 0 <= int(ball_y) < BRK_H:
        grid[int(ball_y)][int(ball_x)] = "●"
    head = f"{t('games.breakout_score', score=score)}   {t('games.breakout_lives', lives='♥' * lives)}"
    return (
        [BOLD + head.center(BRK_W) + RESET, "╔" + "═" * BRK_W + "╗"]
        + ["║" + "".join(row) + "║" for row in grid]
        + ["╚" + "═" * BRK_W + "╝", DIM + t("games.breakout_keys") + RESET]
    )


# -- Menu -----------------------------------------------------------------

def _dragon(term):
    """The door game lives in dragon.py — this is just the entry point."""
    from .dragon import run
    run(term)


def _space(term):
    """The trading door lives in space.py — this is just the entry point."""
    from .space import run
    run(term)


GAMES = [
    ("paddle", "games.menu_pong", paddle),
    ("stacker", "games.menu_tetris", stacker),
    ("snake", "games.menu_snake", snake),
    ("bricks", "games.menu_breakout", bricks),
    ("dragon", "games.menu_dragon", _dragon),
    ("space", "games.menu_space", _space),
]


def games_menu(term, arg=""):
    """'game' shows the arcade, 'game paddle' / 'game stacker' starts directly."""
    choice = arg.strip().lower()
    while True:
        if not choice:
            rows = [(str(i), t(label), t("games.menu_record", score=_highscore(name)))
                    for i, (name, label, _) in enumerate(GAMES, 1)]
            choice = lightbar.menu(term, t("games.menu_title"), rows,
                                   subtitle=t("games.menu_subtitle")).strip().lower()
        if not choice or choice in ("q", "0"):
            return
        entry = None
        if choice.isdigit() and 1 <= int(choice) <= len(GAMES):
            entry = GAMES[int(choice) - 1]
        else:
            entry = next((g for g in GAMES if g[0] == choice), None)
        if entry is None:
            term.error(t("games.unknown_game", name=choice))
        else:
            entry[2](term)
        choice = ""
