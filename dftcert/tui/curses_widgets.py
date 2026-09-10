"""Raw curses primitives shared by the interactive TUI screens."""
from __future__ import annotations

import curses
from typing import Any


def attr(name: str) -> int:
    pairs = {"muted": 1, "title": 2, "good": 3, "warn": 4, "bad": 5, "gap": 6}
    return curses.color_pair(pairs.get(name, 1)) if curses.has_colors() else 0


def init_colors() -> None:
    if not curses.has_colors():
        return
    curses.start_color()
    curses.use_default_colors()
    palette = {
        "muted": curses.COLOR_WHITE,
        "title": curses.COLOR_RED,
        "good": curses.COLOR_GREEN,
        "warn": curses.COLOR_YELLOW,
        "bad": curses.COLOR_RED,
        "gap": curses.COLOR_MAGENTA,
    }
    for pair_index, name in enumerate(palette, start=1):
        curses.init_pair(pair_index, palette[name], -1)


def draw_box(screen: Any, y: int, x: int, h: int, w: int, title: str = "") -> None:
    if h < 2 or w < 2:
        return
    screen.attron(attr("title"))
    screen.addstr(y, x, "┌" + "─" * (w - 2) + "┐")
    for row in range(y + 1, y + h - 1):
        screen.addstr(row, x, "│")
        screen.addstr(row, x + w - 1, "│")
    screen.addstr(y + h - 1, x, "└" + "─" * (w - 2) + "┘")
    if title:
        screen.addstr(y, x + 2, f" {title} "[:max(0, w - 4)])
    screen.attroff(attr("title"))
