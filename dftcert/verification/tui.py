"""Theorem-centered terminal UI (spec section 15): the primary screen is a
selected target's premise/evidence tree, not the raw artifact inventory.
An authoring/review surface only -- every action goes through
`VerificationSession` methods (`accept_assumption`/`save`), the same ones
the Python API uses (spec section 16); this module adds no resolution
semantics of its own.

`render_target_tree`/`node_detail_lines` are plain functions returning text,
independent of `curses`, so they're testable without a real screen -- the
same split `dftcert.tui` already uses (`render_plain` vs `curses.wrapper`).

Known scope gap: section 15's `[b] choose artifact binding` action for an
`ambiguous_binding` node is not wired here yet. Resolving an ambiguity is
a `binding_choices` entry in the *package*, not session-local state, so
doing it live would mean this TUI writing to the package file and
re-invoking `start_session` (which re-runs Lean) rather than just calling
a `VerificationSession` method. Today that path works end to end through
`VerificationPackageBuilder(binding_choices=...)` + `vista verify start`
(see `tests/test_verification_session.py`); it is just not yet reachable
from inside `interact` without leaving it. A weaker-but-sound gap, not a
guess -- nothing here silently picks among ambiguous candidates.
"""
from __future__ import annotations

from typing import Any

from .session import VerificationSession, resume_session

_STATUS_TAG = {
    "artifact_grounded": "ARTIFACT",
    "specified_interface": "SPECIFIED",
    "formally_discharged": "PROVED",
    "specified_assumption": "ASSUMED",
    "ambiguous_binding": "AMBIGUOUS",
    "unresolved": "UNRESOLVED",
}


def _node_line(node_id: str, node: dict[str, Any], *, prefix: str) -> str:
    tag = _STATUS_TAG.get(node["status"], node["status"].upper())
    label = f"{node['binder_name']} : {node['pretty_type']}"
    line = f"{prefix}{label}"
    pad = max(1, 60 - len(line))
    return f"{line}{' ' * pad}[{tag}]"


def render_target_tree(session: dict[str, Any], entrypoint: str, *, width: int = 100) -> str:
    """The primary screen (spec section 15): the target and its ordered
    binder nodes, most-blocking-first status visible at a glance."""
    target = next((t for t in session["targets"] if t["entrypoint"] == entrypoint), None)
    if target is None:
        return f"no such target: {entrypoint}"
    nodes = {node_id: session["nodes"][node_id] for node_id in target["root_node_ids"]}
    ordered = sorted(nodes.items(), key=lambda item: int(item[1]["binder_path"]))
    blocked = any(node["status"] in {"unresolved", "ambiguous_binding"} for _, node in ordered)
    lines = [f"{entrypoint}     [{'BLOCKED' if blocked else 'READY'}]", "│"]
    for index, (node_id, node) in enumerate(ordered):
        last = index == len(ordered) - 1
        branch = "└─ " if last else "├─ "
        lines.append(_node_line(node_id, node, prefix=branch))
        if node.get("candidate_keys") and node["status"] != "unresolved":
            continuation = "     " if last else "│    "
            chosen = node.get("chosen_candidate_key")
            if chosen:
                lines.append(f"{continuation}└─ candidate: {chosen}")
    return "\n".join(line[:width] for line in lines)


def node_detail_lines(session: dict[str, Any], node_id: str) -> list[str]:
    """The section-15 "selecting an unresolved node" screen."""
    node = session["nodes"].get(node_id)
    if node is None:
        return [f"no such node: {node_id}"]
    lines = [
        f"Required by:", f"  {node['entrypoint']}", "",
        "Exact Lean proposition:" if node["kind"] == "premise" else "Binder type:",
        f"  {node['pretty_type']}", "",
    ]
    if node["status"] == "ambiguous_binding":
        lines += ["Candidates that typecheck:", *[f"  {key}" for key in node["candidate_keys"]], ""]
    elif node["status"] == "unresolved":
        lines += [
            "Available resolution:", "  no artifact binding", "  no verified formal proof",
            "  no explicit assumption", "",
        ]
        if node["kind"] == "premise":
            lines += ["Actions:", "  [a] accept as explicit external assumption", "  [l] leave unresolved", "  [q] save and quit"]
    else:
        tag = _STATUS_TAG.get(node["status"], node["status"])
        lines += [f"Status: {tag}"]
        if node.get("external_assumption"):
            lines += [f"  rationale: {node['external_assumption']['rationale']}"]
    return lines


def run_interactive(session_path: str) -> int:
    """`vista verify interact --session ...`. Never provides "assume
    everything" -- exactly one exact proposition at a time, saved
    immediately (spec section 15)."""
    import curses

    session = resume_session(session_path)

    def main(screen: Any) -> None:
        curses.curs_set(0)
        screen.keypad(True)
        targets = [target["entrypoint"] for target in session.value["targets"]]
        target_index = 0
        node_index = 0
        message = ""
        while True:
            screen.erase()
            entrypoint = targets[target_index]
            tree = render_target_tree(session.value, entrypoint)
            for row, line in enumerate(tree.splitlines()):
                screen.addstr(row, 0, line)
            node_ids = sorted(
                next(t for t in session.value["targets"] if t["entrypoint"] == entrypoint)["root_node_ids"],
                key=lambda nid: int(session.value["nodes"][nid]["binder_path"]),
            )
            node_index = min(node_index, len(node_ids) - 1)
            current_id = node_ids[node_index]
            detail_row = len(tree.splitlines()) + 1
            for offset, line in enumerate(node_detail_lines(session.value, current_id)):
                screen.addstr(detail_row + offset, 0, line)
            if message:
                screen.addstr(detail_row + 20, 0, message)
            screen.addstr(detail_row + 22, 0, "[Up/Down] select  [Tab] next target  [a] assume  [q] save+quit")
            screen.refresh()
            key = screen.get_wch()
            if key in ("q", "Q", "\x1b"):
                session.save()
                return
            if key in (curses.KEY_UP, "k"):
                node_index = max(0, node_index - 1)
            elif key in (curses.KEY_DOWN, "j"):
                node_index = min(len(node_ids) - 1, node_index + 1)
            elif key == "\t":
                target_index = (target_index + 1) % len(targets)
                node_index = 0
            elif key in ("a", "A"):
                node = session.value["nodes"][current_id]
                if node["kind"] != "premise" or node["status"] != "unresolved":
                    message = f"{current_id} is not eligible for an explicit assumption"
                    continue
                curses.echo()
                screen.addstr(detail_row + 21, 0, "rationale: ")
                screen.refresh()
                rationale = screen.getstr(detail_row + 21, 11, 200).decode("utf-8", errors="replace")
                curses.noecho()
                session.accept_assumption(premise_id=current_id, rationale=rationale or "accepted via TUI")
                message = f"accepted {current_id} as an explicit assumption"

    curses.wrapper(main)
    return 0
