"""The interactive assumption-review screen (`vista tui` writes a
confirmed/rejected/unknown status back into the manifest for each extracted
assumption before finalizing the review)."""
from __future__ import annotations

import curses
from typing import Any

from ..legacy.model_assessment import apply_assumption_status, finalize_assumption_review
from ..legacy.policy import Policy
from ..manifest import ArchitectureManifest
from .curses_widgets import attr, draw_box, init_colors
from .rendering import _short_json, label, status_color, wrap_lines


def confirm_assumptions_tui(manifest: ArchitectureManifest, policy: Policy) -> None:
    assumptions = [
        item for item in manifest.value.get("assumptions", [])
        if isinstance(item, dict)
    ]
    if not assumptions:
        finalize_assumption_review(manifest, policy)
        return

    index = 0
    message = "y accept · n reject · u unknown · ↑/↓ move · Enter finish · q cancel"

    def row_status(item: dict[str, Any]) -> str:
        return str(item.get("status", "needs_user_confirmation"))

    def draw(screen: Any) -> None:
        screen.erase()
        height, width = screen.getmaxyx()
        if height < 20 or width < 78:
            screen.addstr(0, 0, "terminal too small; use at least 78x20")
            screen.refresh()
            return
        left_w = max(32, min(48, width // 3))
        right_x = left_w + 2
        right_w = width - left_w - 3
        screen.addstr(0, 2, "† VISTA ASSUMPTION REVIEW", attr("title") | curses.A_BOLD)
        screen.addstr(0, 32, message[:max(0, width - 34)], attr("muted"))

        draw_box(screen, 2, 1, height - 3, left_w, "extracted assumptions")
        for row, item in enumerate(assumptions[:height - 7]):
            selected = row == index
            status = row_status(item)
            marker = "›" if selected else " "
            color = status_color(status)
            text = f"{marker} {item.get('id', 'assumption')} [{label(status)}]"
            screen.addstr(4 + row, 3, text[:left_w - 4], attr(color) | (curses.A_REVERSE if selected else 0))

        current = assumptions[index]
        status = row_status(current)
        draw_box(screen, 2, right_x, height - 3, right_w, "decision")
        y = 4
        screen.addstr(y, right_x + 2, f"{current.get('id', 'assumption')}  [{label(status)}]",
                      attr(status_color(status)) | curses.A_BOLD)
        y += 2
        statement = str(current.get("statement") or current.get("principle") or "")
        for line in wrap_lines(statement, right_w - 4):
            if y >= height - 9:
                break
            screen.addstr(y, right_x + 2, line[:right_w - 4], attr("muted"))
            y += 1
        y += 1
        value = current.get("value")
        if value is None:
            screen.addstr(y, right_x + 2, "value: missing from model text", attr("warn"))
            y += 1
        else:
            for line in wrap_lines(f"value: {_short_json(value, right_w - 11)}", right_w - 4):
                if y >= height - 7:
                    break
                screen.addstr(y, right_x + 2, line[:right_w - 4], attr("muted"))
                y += 1
        evidence = str(current.get("evidence") or current.get("rationale") or "").strip()
        if evidence and y < height - 7:
            y += 1
            for line in wrap_lines(f"evidence: {evidence}", right_w - 4):
                if y >= height - 7:
                    break
                screen.addstr(y, right_x + 2, line[:right_w - 4], attr("muted"))
                y += 1
        question = str(current.get("question") or "").strip()
        if question and y < height - 7:
            y += 1
            for line in wrap_lines(f"question: {question}", right_w - 4):
                if y >= height - 7:
                    break
                screen.addstr(y, right_x + 2, line[:right_w - 4], attr("warn"))
                y += 1

        reviewed = sum(
            1 for item in assumptions
            if row_status(item) in {"confirmed", "rejected", "unknown"}
        )
        footer = f"reviewed {reviewed}/{len(assumptions)} · Enter writes assessment when all are reviewed"
        screen.addstr(height - 4, right_x + 2, footer[:right_w - 4], attr("title"))
        screen.refresh()

    def main(screen: Any) -> None:
        nonlocal index, message
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        screen.keypad(True)
        init_colors()
        while True:
            draw(screen)
            try:
                key = screen.get_wch()
            except curses.error:
                continue
            if key in ("q", "Q", "\x1b", "\x11"):
                raise KeyboardInterrupt("assumption review cancelled")
            if key in (curses.KEY_DOWN, "j"):
                index = min(len(assumptions) - 1, index + 1)
                continue
            if key in (curses.KEY_UP, "k"):
                index = max(0, index - 1)
                continue
            if key in ("y", "Y"):
                apply_assumption_status(
                    manifest, fact_id=str(assumptions[index].get("id")), status="confirmed"
                )
                index = min(len(assumptions) - 1, index + 1)
                continue
            if key in ("n", "N"):
                apply_assumption_status(
                    manifest, fact_id=str(assumptions[index].get("id")), status="rejected"
                )
                index = min(len(assumptions) - 1, index + 1)
                continue
            if key in ("u", "U"):
                apply_assumption_status(
                    manifest, fact_id=str(assumptions[index].get("id")), status="unknown"
                )
                index = min(len(assumptions) - 1, index + 1)
                continue
            if key in ("\n", "\r"):
                pending = [
                    item.get("id", "assumption")
                    for item in assumptions
                    if row_status(item) not in {"confirmed", "rejected", "unknown"}
                ]
                if pending:
                    message = f"still needs decision: {pending[0]}"
                    continue
                finalize_assumption_review(manifest, policy)
                return

    curses.wrapper(main)
