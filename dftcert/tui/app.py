"""The main interactive curses screen: `TuiApp` (hypothesis report,
coverage, search/run inspector, proof review, live run dashboard). The
separate assumption-review screen lives in `assumption_review.py`."""
from __future__ import annotations

import curses
from pathlib import Path
from typing import Any

from ..legacy.hypothesis import policy_coverage
from ..legacy.policy import Policy
from .constants import EXAMPLES
from .curses_widgets import attr, draw_box, init_colors
from .inspectors import build_proof_review, build_run_inspector
from .rendering import (
    assessment_lines,
    build_hypothesis_report,
    coverage_lines,
    event_summary_lines,
    label,
    proof_review_entries,
    report_lines,
    run_inspector_lines,
    search_result_lines,
    status_color,
    wrap_lines,
)


class TuiApp:
    def __init__(self, *, policy: Policy, model_id: str, hypothesis: str,
                 mode: str = "report", data: dict[str, Any] | None = None,
                 refresh_path: str | Path | None = None):
        self.policy = policy
        self.model_id = model_id
        self.hypothesis = hypothesis
        self.example_names = list(EXAMPLES)
        self.example_index = 0
        self.mode = mode
        self.scroll = 0
        self.left_scroll = 0
        self.current_scroll = 0
        self.prompt_scroll = 0
        self.log_scroll = 0
        self.focus = "past"
        self.artifact_index: int | None = None
        self.refresh_path = Path(refresh_path) if refresh_path is not None else None
        self.message = "F5 run · F2 coverage · F3 example · Ctrl-U clear · q/Esc quit"
        self.data: dict[str, Any] = data or build_hypothesis_report(
            policy=policy, model_id=model_id, hypothesis=hypothesis
        )

    def run(self) -> None:
        curses.wrapper(self._main)

    def _main(self, screen: Any) -> None:
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        screen.keypad(True)
        try:
            curses.mousemask(curses.ALL_MOUSE_EVENTS)
        except curses.error:
            pass
        screen.timeout(1000 if self.refresh_path is not None else -1)
        self._colors()
        while True:
            self._refresh_if_needed()
            self._draw(screen)
            try:
                key = screen.get_wch()
            except curses.error:
                continue
            if key == curses.KEY_MOUSE and self.mode == "inspector":
                self._handle_mouse(screen)
                continue
            if key in ("\x11", "\x1b", "q", "Q"):  # Ctrl-Q / Esc / q
                return
            if key == "\t" and self.mode == "inspector":
                self._next_focus()
                self.message = f"{self.focus} pane focused · arrows scroll · q/Esc quit"
                continue
            if key in ("[", curses.KEY_LEFT) and self.mode in {"inspector", "proof_review"}:
                self._cycle_artifact(-1)
                continue
            if key in ("]", curses.KEY_RIGHT) and self.mode in {"inspector", "proof_review"}:
                self._cycle_artifact(1)
                continue
            if key == "\x15":  # Ctrl-U
                self.hypothesis = ""
                self.message = "cleared hypothesis"
                continue
            if key in (curses.KEY_F5, "\x12"):  # F5 / Ctrl-R
                self._run_report()
                continue
            if key == curses.KEY_F2:
                self.mode = "coverage"
                self.data = policy_coverage(self.policy)
                self.scroll = 0
                self.focus = "past"
                self.message = "coverage loaded"
                continue
            if key == curses.KEY_F3:
                self._load_next_example()
                continue
            if key == curses.KEY_DOWN:
                self._scroll_focused(1)
                continue
            if key == curses.KEY_UP:
                self._scroll_focused(-1)
                continue
            if key in (curses.KEY_NPAGE,):
                self._scroll_focused(8)
                continue
            if key in (curses.KEY_PPAGE,):
                self._scroll_focused(-8)
                continue
            if key in ("\b", "\x7f", curses.KEY_BACKSPACE):
                self.hypothesis = self.hypothesis[:-1]
                continue
            if key in ("\n", "\r"):
                self.hypothesis += "\n"
                continue
            if isinstance(key, str) and key.isprintable():
                self.hypothesis += key

    def _refresh_if_needed(self) -> None:
        if self.refresh_path is None:
            return
        try:
            self.data = (
                build_proof_review(self.refresh_path)
                if self.mode == "proof_review" else build_run_inspector(self.refresh_path)
            )
            self.message = "proof review · [] proof · arrows scroll · q/Esc quit" if self.mode == "proof_review" else "live run inspector · Tab focus · mouse/arrows scroll · q/Esc quit"
        except Exception as error:
            self.message = f"{type(error).__name__}: {error}"

    def _scroll_focused(self, delta: int) -> None:
        if self.mode == "proof_review":
            self.scroll = max(0, self.scroll + delta)
            return
        if self.mode == "inspector":
            if self.focus in {"left", "past"}:
                self.left_scroll = max(0, self.left_scroll + delta)
                return
            if self.focus == "current":
                self.current_scroll = max(0, self.current_scroll + delta)
                return
            if self.focus == "prompt":
                self.prompt_scroll = max(0, self.prompt_scroll + delta)
                return
            if self.focus == "logs":
                self.log_scroll = max(0, self.log_scroll + delta)
                return
        self.scroll = max(0, self.scroll + delta)

    def _next_focus(self) -> None:
        if self.mode == "inspector" and self.data.get("inspector_kind") == "run":
            order = ["past", "current", "prompt", "logs"]
        else:
            order = ["left", "right"]
        try:
            index = order.index(self.focus)
        except ValueError:
            index = 0
        self.focus = order[(index + 1) % len(order)]

    def _cycle_artifact(self, delta: int) -> None:
        artifacts = self.data.get("artifacts", [])
        if not isinstance(artifacts, list) or not artifacts:
            self.message = "no past task artifacts yet"
            return
        current = self._selected_artifact_index(len(artifacts))
        self.artifact_index = (current + delta) % len(artifacts)
        self.left_scroll = 0
        self.focus = "past"
        self.scroll = 0
        self.message = (
            f"proof {self.artifact_index + 1}/{len(artifacts)} selected · [] cycle · arrows scroll · q/Esc quit"
            if self.mode == "proof_review" else
            f"past task {self.artifact_index + 1}/{len(artifacts)} selected · [] cycle · Tab focus · mouse/arrows scroll · q/Esc quit"
        )

    def _selected_artifact_index(self, count: int) -> int:
        if count <= 0:
            return 0
        if self.artifact_index is None:
            return count - 1
        self.artifact_index = max(0, min(self.artifact_index, count - 1))
        return self.artifact_index

    def _handle_mouse(self, screen: Any) -> None:
        try:
            _, x, y, _, state = curses.getmouse()
        except curses.error:
            return
        self.focus = self._focus_at(y, x, *screen.getmaxyx())
        wheel_up = getattr(curses, "BUTTON4_PRESSED", 0)
        wheel_down = getattr(curses, "BUTTON5_PRESSED", 0)
        if wheel_up and state & wheel_up:
            self._scroll_focused(-3)
        elif wheel_down and state & wheel_down:
            self._scroll_focused(3)
        self.message = f"{self.focus} pane focused · mouse/arrows scroll · q/Esc quit"

    def _focus_at(self, y: int, x: int, height: int, width: int) -> str:
        if (
            self.data.get("inspector_kind") == "run"
            and height >= 24
            and width >= 100
        ):
            left_w = max(38, min(66, width // 3))
            if x <= left_w:
                return "past"
            right_x = left_w + 2
            content_h = height - 3
            current_h = max(8, content_h // 2)
            bottom_y = 2 + current_h + 1
            if y < bottom_y:
                return "current"
            right_w = width - left_w - 3
            prompt_w = max(34, right_w // 2)
            return "prompt" if x < right_x + prompt_w + 1 else "logs"
        left_w = max(34, min(58, width // 3))
        return "left" if x <= left_w else "right"

    def _colors(self) -> None:
        init_colors()

    def _attr(self, name: str) -> int:
        return attr(name)

    def _run_report(self) -> None:
        try:
            self.data = build_hypothesis_report(
                policy=self.policy, model_id=self.model_id,
                hypothesis=self.hypothesis,
            )
            self.mode = "report"
            self.scroll = 0
            self.message = "draft report generated"
        except Exception as error:
            self.message = f"{type(error).__name__}: {error}"

    def _load_next_example(self) -> None:
        name = self.example_names[self.example_index % len(self.example_names)]
        self.example_index += 1
        self.model_id = f"example-{name}"
        self.hypothesis = EXAMPLES[name]
        self._run_report()
        self.message = f"loaded example: {name}"

    def _box(self, screen: Any, y: int, x: int, h: int, w: int,
             title: str = "") -> None:
        draw_box(screen, y, x, h, w, title)

    def _draw_wrapped(self, screen: Any, y: int, x: int, width: int,
                      height: int, text: str, attr: int = 0,
                      scroll: int = 0) -> int:
        lines: list[str] = []
        for paragraph in text.splitlines() or [""]:
            lines.extend(wrap_lines(paragraph, width))
        visible = lines[scroll:scroll + height]
        for row, line in enumerate(visible):
            screen.addstr(y + row, x, line[:width], attr)
        return len(lines)

    def _draw_lines(self, screen: Any, y: int, x: int, width: int,
                    height: int, lines: list[tuple[str, str]],
                    scroll: int = 0) -> int:
        visible = lines[scroll:scroll + height]
        for row, (text, color) in enumerate(visible):
            screen.addstr(y + row, x, text[:width], self._attr(color))
        return len(lines)

    def _focused_title(self, title: str, focus: str) -> str:
        return f"{title} [focused]" if self.focus == focus else title

    def _running_task(self) -> dict[str, Any] | None:
        state = self.data.get("state", {})
        if not isinstance(state, dict):
            return None
        for item in state.get("tasks", []):
            if isinstance(item, dict) and item.get("status") == "running":
                return item
        return None

    def _run_overview_lines(self, width: int) -> list[tuple[str, str]]:
        state = self.data.get("state", {})
        artifacts = [item for item in self.data.get("artifacts", []) if isinstance(item, dict)]
        lines: list[tuple[str, str]] = []
        if isinstance(state, dict):
            status = str(state.get("status", "unknown"))
            lines.append((f"RUN  {state.get('run_id', 'unknown')}", status_color(status)))
            lines.append((f"status: {label(status)}", status_color(status)))
            lines.append(("", "muted"))
            lines.append(("TASKS", "title"))
            for item in state.get("tasks", []):
                if isinstance(item, dict):
                    lines.append((
                        f"■ {item.get('task_id')} [{label(item.get('status'))}]",
                        status_color(str(item.get("status"))),
                    ))
            if state.get("blocked"):
                lines.append(("", "muted"))
                lines.append(("BLOCKED", "warn"))
                for item in state.get("blocked", []):
                    if isinstance(item, dict):
                        lines.append((f"! {item.get('task_id')} [{label(item.get('status'))}]", "warn"))
        lines.append(("", "muted"))
        if artifacts:
            selected = self._selected_artifact_index(len(artifacts))
            self.data["selected_artifact_index"] = selected
            lines.append((f"PAST TASK  {selected + 1}/{len(artifacts)}  ([/] cycle)", "title"))
            lines.extend(search_result_lines(artifacts[selected], width))
        else:
            lines.append(("PAST TASKS", "title"))
            lines.append(("No completed task artifacts yet.", "muted"))
        return lines

    def _current_task_lines(self, width: int) -> list[tuple[str, str]]:
        running = self._running_task()
        if not running:
            return [("No task is currently running.", "muted")]
        lines: list[tuple[str, str]] = []
        task = running.get("task", {})
        lines.append((f"TASK  {running.get('task_id', 'unknown')}  [{label(running.get('status'))}]", "title"))
        if isinstance(task, dict):
            lines.append((f"target: {task.get('target') or '(generated obligation)'}", "muted"))
            for line in wrap_lines(f"theorem: {task.get('theorem', '')}", width, indent=""):
                lines.append((line, "muted"))
            context = str(task.get("context", "")).strip()
            if context:
                lines.append(("", "muted"))
                lines.append(("CONTEXT", "title"))
                for line in wrap_lines(context, width, indent=""):
                    lines.append((line, "muted"))
            subgoals = task.get("subgoals", [])
            if isinstance(subgoals, list) and subgoals:
                lines.append(("", "muted"))
                lines.append(("SUBGOALS", "title"))
                for item in subgoals:
                    if isinstance(item, dict):
                        lines.append((f"◆ {item.get('id')}", "gap"))
                        for line in wrap_lines(str(item.get("context", "")), width - 2, indent="  "):
                            lines.append((line, "muted"))
        return lines

    def _recent_activity_lines(self, width: int) -> list[tuple[str, str]]:
        events = self.data.get("events", [])
        lines: list[tuple[str, str]] = []
        if isinstance(events, list) and events:
            for event in events[-28:]:
                if isinstance(event, dict):
                    lines.extend(event_summary_lines(event, width))
        else:
            lines.append(("No events yet.", "muted"))
        return lines

    def _run_prompt_text(self) -> str:
        events = self.data.get("events", [])
        if isinstance(events, list):
            for event in reversed(events):
                if not isinstance(event, dict):
                    continue
                if event.get("type") == "model_call_started" and event.get("prompt"):
                    header = (
                        f"agent: {event.get('agent', 'unknown')}\n"
                        f"model: {event.get('model', 'default')}\n"
                        f"call: {event.get('call_index', '?')}\n\n"
                    )
                    system = str(event.get("system", "")).strip()
                    prompt = str(event.get("prompt", "")).strip()
                    if system:
                        return header + "SYSTEM\n" + system + "\n\nPROMPT\n" + prompt
                    return header + prompt
        state = self.data.get("state", {})
        if isinstance(state, dict):
            for item in state.get("tasks", []):
                if not isinstance(item, dict) or item.get("status") != "running":
                    continue
                task = item.get("task", {})
                if isinstance(task, dict):
                    return (
                        f"task: {item.get('task_id', 'unknown')}\n"
                        f"target: {task.get('target') or '(generated obligation)'}\n\n"
                        f"THEOREM\n{task.get('theorem', '')}\n\n"
                        f"CONTEXT\n{task.get('context') or '(none supplied)'}"
                    )
        return "Waiting for the next model prompt."

    def _left_pane(self) -> tuple[str, str, str]:
        if self.mode == "inspector" and self.data.get("inspector_kind") == "run":
            state = self.data.get("state", {})
            running = ""
            if isinstance(state, dict):
                for item in state.get("tasks", []):
                    if isinstance(item, dict) and item.get("status") == "running":
                        running = str(item.get("task_id", "running task"))
                        break
            return (
                f"current task: {running}" if running else "current task",
                self._run_prompt_text(),
                "Tab focus · mouse/arrows scroll · q/Esc quit",
            )
        if self.mode == "inspector" and self.data.get("inspector_kind") == "assessment":
            manifest = self.data.get("manifest", {})
            source = manifest.get("source", {}) if isinstance(manifest, dict) else {}
            description = source.get("description", "") if isinstance(source, dict) else ""
            return (
                "architecture description",
                str(description) or "description unavailable",
                "LLM assessment is review-only · q/Esc quit",
            )
        return (
            "hypothesis",
            self.hypothesis,
            "type to edit · F5 run · F3 examples",
        )

    def _draw(self, screen: Any) -> None:
        screen.erase()
        height, width = screen.getmaxyx()
        if height < 18 or width < 72:
            screen.addstr(0, 0, "terminal too small; use at least 72x18")
            screen.refresh()
            return
        if (
            self.mode == "inspector"
            and self.data.get("inspector_kind") == "run"
            and height >= 24
            and width >= 100
        ):
            self._draw_run_dashboard(screen, height, width)
            return
        if self.mode == "proof_review":
            self._draw_proof_review(screen, height, width)
            return
        left_w = max(34, min(58, width // 3))
        right_w = width - left_w - 3
        screen.addstr(0, 2, "† PROOF VIBE", self._attr("title") | curses.A_BOLD)
        screen.addstr(0, 18, self.message[:width - 20], self._attr("muted"))

        left_title, left_text, left_footer = self._left_pane()
        if self.mode == "inspector" and self.focus == "left":
            left_title += " [focused]"
        self._box(screen, 2, 1, height - 3, left_w, left_title)
        left_height = height - 10
        left_scroll = self.left_scroll if self.mode == "inspector" else 0
        left_total = self._draw_wrapped(
            screen, 4, 3, left_w - 4, height - 10, left_text,
            self._attr("muted"), left_scroll,
        )
        self.left_scroll = min(self.left_scroll, max(0, left_total - left_height))
        screen.addstr(height - 5, 3, left_footer[:left_w - 4], self._attr("title"))
        screen.addstr(height - 4, 3, f"id: {self.model_id}"[:left_w - 4], self._attr("muted"))
        if self.left_scroll:
            screen.addstr(height - 6, 3, f"↑ prompt scrolled {self.left_scroll}"[:left_w - 4],
                          self._attr("warn"))

        title = (
            "coverage" if self.mode == "coverage"
            else "artifact report" if self.mode == "artifact"
            else "model assessment" if self.data.get("inspector_kind") == "assessment"
            else "agentic run inspector" if self.mode == "inspector"
            else "draft sanity report"
        )
        if self.mode == "inspector" and self.focus == "right":
            title += " [focused]"
        self._box(screen, 2, left_w + 2, height - 3, right_w, title)
        if self.mode == "coverage":
            source = coverage_lines(self.data, right_w - 4)
        elif self.mode == "inspector":
            if self.data.get("inspector_kind") == "assessment":
                source = assessment_lines(self.data["assessment"], right_w - 4)
            elif self.data.get("inspector_kind") == "run":
                artifacts = self.data.get("artifacts", [])
                if isinstance(artifacts, list):
                    self.data["selected_artifact_index"] = self._selected_artifact_index(len(artifacts))
                source = run_inspector_lines(self.data, right_w - 4)
            else:
                source = search_result_lines(self.data["result"], right_w - 4)
        else:
            source = report_lines(self.data, right_w - 4)
        visible = source[self.scroll:self.scroll + height - 7]
        for row, (text, color) in enumerate(visible):
            screen.addstr(4 + row, left_w + 4, text[:right_w - 4], self._attr(color))
        if self.scroll:
            screen.addstr(height - 4, left_w + 4, f"↑ scrolled {self.scroll}", self._attr("warn"))
        screen.refresh()

    def _draw_proof_review(self, screen: Any, height: int, width: int) -> None:
        entries = proof_review_entries(self.data)
        selected = self._selected_artifact_index(len(entries))
        entry = entries[selected] if entries else None
        left_w = max(30, min(48, width // 3))
        right_x = left_w + 2
        right_w = width - right_x - 1
        screen.addstr(0, 2, "† PROOF REVIEW", self._attr("title") | curses.A_BOLD)
        screen.addstr(0, 20, "[] proof · arrows scroll · q/Esc quit"[:width - 22], self._attr("muted"))
        self._box(screen, 2, 1, height - 3, left_w, "proofs")
        proof_list: list[tuple[str, str]] = []
        for index, item in enumerate(entries):
            prefix = "› " if index == selected else "  "
            for line in wrap_lines(f"{prefix}{item['id']} [{label(item['status'])}]", left_w - 4):
                proof_list.append((line, status_color(str(item["status"]))))
        self._draw_lines(screen, 4, 3, left_w - 4, height - 7, proof_list)
        self._box(screen, 2, right_x, height - 3, right_w, "accepted Lean proof")
        if entry is None:
            self._draw_wrapped(screen, 4, right_x + 2, right_w - 4, height - 7,
                               "No proof artifacts yet.", self._attr("muted"), self.scroll)
        else:
            details = (
                f"THEOREM\n{entry['theorem']}\n\n"
                f"PROJECT  {entry['project']}\nMODULE   {entry['module']}\n"
                f"STATUS   {label(entry['status'])}\n\n"
                f"PROOF\n{entry['proof']}\n\n"
                f"VERIFIER\n{entry['diagnostics']}"
            )
            self._draw_wrapped(screen, 4, right_x + 2, right_w - 4, height - 7,
                               details, self._attr("muted"), self.scroll)
        screen.refresh()

    def _draw_run_dashboard(self, screen: Any, height: int, width: int) -> None:
        left_w = max(38, min(66, width // 3))
        right_x = left_w + 2
        right_w = width - left_w - 3
        content_y = 2
        content_h = height - 3
        current_h = max(8, content_h // 2)
        bottom_h = content_h - current_h - 1
        bottom_y = content_y + current_h + 1
        prompt_w = max(34, right_w // 2)
        logs_x = right_x + prompt_w + 1
        logs_w = right_w - prompt_w - 1

        screen.addstr(0, 2, "† PROOF VIBE", self._attr("title") | curses.A_BOLD)
        screen.addstr(
            0, 18,
            "live run dashboard · Tab focus · [] past task · mouse/arrows scroll · q/Esc quit"[:width - 20],
            self._attr("muted"),
        )

        past_title = self._focused_title("run + past tasks", "past")
        self._box(screen, content_y, 1, content_h, left_w, past_title)
        past_height = content_h - 4
        past_lines = self._run_overview_lines(left_w - 4)
        past_total = self._draw_lines(
            screen, content_y + 2, 3, left_w - 4, past_height,
            past_lines, self.left_scroll,
        )
        self.left_scroll = min(self.left_scroll, max(0, past_total - past_height))
        if self.left_scroll:
            screen.addstr(content_y + content_h - 2, 3,
                          f"↑ scrolled {self.left_scroll}"[:left_w - 4], self._attr("warn"))

        current_title = self._focused_title("current task", "current")
        self._box(screen, content_y, right_x, current_h, right_w, current_title)
        current_height = current_h - 4
        current_lines = self._current_task_lines(right_w - 4)
        current_total = self._draw_lines(
            screen, content_y + 2, right_x + 2, right_w - 4, current_height,
            current_lines, self.current_scroll,
        )
        self.current_scroll = min(self.current_scroll, max(0, current_total - current_height))
        if self.current_scroll:
            screen.addstr(content_y + current_h - 2, right_x + 2,
                          f"↑ scrolled {self.current_scroll}"[:right_w - 4], self._attr("warn"))

        prompt_title = self._focused_title("active prompt", "prompt")
        self._box(screen, bottom_y, right_x, bottom_h, prompt_w, prompt_title)
        prompt_height = bottom_h - 4
        prompt_total = self._draw_wrapped(
            screen, bottom_y + 2, right_x + 2, prompt_w - 4, prompt_height,
            self._run_prompt_text(), self._attr("muted"), self.prompt_scroll,
        )
        self.prompt_scroll = min(self.prompt_scroll, max(0, prompt_total - prompt_height))
        if self.prompt_scroll:
            screen.addstr(bottom_y + bottom_h - 2, right_x + 2,
                          f"↑ scrolled {self.prompt_scroll}"[:prompt_w - 4], self._attr("warn"))

        logs_title = self._focused_title("recent logs", "logs")
        self._box(screen, bottom_y, logs_x, bottom_h, logs_w, logs_title)
        logs_height = bottom_h - 4
        log_lines = self._recent_activity_lines(logs_w - 4)
        log_total = self._draw_lines(
            screen, bottom_y + 2, logs_x + 2, logs_w - 4, logs_height,
            log_lines, self.log_scroll,
        )
        self.log_scroll = min(self.log_scroll, max(0, log_total - logs_height))
        if self.log_scroll:
            screen.addstr(bottom_y + bottom_h - 2, logs_x + 2,
                          f"↑ scrolled {self.log_scroll}"[:logs_w - 4], self._attr("warn"))
        screen.refresh()
