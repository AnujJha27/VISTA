"""Turn report/run/search/assessment data dicts into (text, color) lines,
plus the small JSON loaders and report builders that produce those dicts.
No curses dependency -- these functions back both the interactive `TuiApp`
and `render_plain`'s non-interactive `--once` output."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from ..legacy.hypothesis import draft_hypothesis
from ..legacy.policy import Policy
from ..legacy.report import sanity_report
from ..manifest import ArchitectureManifest


def build_hypothesis_report(*, policy: Policy, model_id: str,
                            hypothesis: str) -> dict[str, Any]:
    manifest = draft_hypothesis(
        model_id=model_id, hypothesis=hypothesis, policy=policy
    )
    return {
        "status": "draft",
        "manifest": manifest.value,
        "report": sanity_report(manifest=manifest, policy=policy),
    }


def load_json_object(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_json_value(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_json_list(path: str | Path) -> list[dict[str, Any]]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{path} must contain a JSON array of objects")
    return value


def load_jsonl_objects(path: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            items.append(value)
    return items[-limit:] if limit is not None else items


def build_artifact_report(
    *,
    policy: Policy,
    manifest_path: str | Path,
    proof_results_path: str | Path | None = None,
    certificate_report_path: str | Path | None = None,
) -> dict[str, Any]:
    manifest = ArchitectureManifest.load(manifest_path)
    proof_results = load_json_list(proof_results_path) if proof_results_path else None
    certificate_report = (
        load_json_object(certificate_report_path)
        if certificate_report_path else None
    )
    return {
        "status": "artifact",
        "manifest": manifest.value,
        "proof_results": proof_results or [],
        "certificate_report": certificate_report,
        "report": sanity_report(
            manifest=manifest,
            policy=policy,
            proof_results=proof_results,
            certificate_report=certificate_report,
        ),
    }


def status_color(status: str) -> str:
    if status in {"consistent_with_policy", "approved", "verified"}:
        return "good"
    if status in {"violates_required_principle", "certificate_check_failed", "refuted", "rejected", "not_sound"}:
        return "bad"
    if status in {"formalization_gap"}:
        return "gap"
    if status in {
        "proof_required", "inconclusive_missing_assumption", "project_not_built",
        "needs_user_confirmation", "needs_clarification", "unknown", "inconclusive",
    }:
        return "warn"
    return "muted"


def label(value: Any) -> str:
    return str(value if value is not None else "unknown").replace("_", " ")


def wrap_lines(text: str, width: int, *, indent: str = "") -> list[str]:
    if width < 8:
        return [text[:width]]
    return textwrap.wrap(
        text, width=width, initial_indent=indent, subsequent_indent=indent
    ) or [indent]


def report_lines(data: dict[str, Any], width: int) -> list[tuple[str, str]]:
    report = data["report"]
    manifest = data.get("manifest", {})
    lines: list[tuple[str, str]] = []
    status = report["status"]
    lines.append((f"VERDICT  {label(status).upper()}", status_color(status)))
    for line in wrap_lines(report.get("summary", ""), width):
        lines.append((line, "muted"))
    lines.append(("", "muted"))
    lines.append(("PRINCIPLE CHECKS", "title"))
    for item in report.get("obligations", []):
        color = status_color(item["category"])
        lines.append((f"■ {item['fact']}  [{label(item['category'])}]", color))
        for line in wrap_lines(item["principle"], width - 2, indent="  "):
            lines.append((line, "muted"))
        claim = item.get("normalized_claim")
        claim_text = json.dumps(claim, sort_keys=True) if claim is not None else "No claim supplied"
        lines.append((f"  evidence: {item.get('evidence_kind') or 'missing'}", "muted"))
        lines.append((f"  lean: {item.get('lean_task_id') or 'not generated'}", "muted"))
        for line in wrap_lines(f"claim: {claim_text}", width - 2, indent="  "):
            lines.append((line, "muted"))
        for line in wrap_lines(f"reason: {item.get('reason', '')}", width - 2, indent="  "):
            lines.append((line, "muted"))
        lines.append(("", "muted"))
    questions = report.get("clarification_questions", [])
    if questions:
        lines.append(("CLARIFY BEFORE FORMALIZING", "title"))
        for item in questions:
            lines.append((f"? {item.get('fact', 'clarification')}", "warn"))
            for line in wrap_lines(item.get("question", ""), width - 2, indent="  "):
                lines.append((line, "muted"))
        lines.append(("", "muted"))
    issues = [
        item for item in report.get("assumptions", [])
        if item.get("status") in {"needs_clarification", "missing", "unresolved"}
        or item.get("source") == "missing"
    ]
    if issues:
        lines.append(("OPEN ISSUES", "title"))
        for item in issues:
            lines.append((f"! {item.get('id')}  [{label(item.get('status'))}]", "warn"))
            for line in wrap_lines(item.get("statement", ""), width - 2, indent="  "):
                lines.append((line, "muted"))
        lines.append(("", "muted"))
    lines.append(("TRACE", "title"))
    lines.append((f"manifest: {manifest.get('manifest_sha256', 'draft')}", "muted"))
    proof_results = data.get("proof_results") or []
    certificate_report = data.get("certificate_report")
    if proof_results:
        lines.append(("", "muted"))
        lines.append(("PROOF SEARCH ARTIFACTS", "title"))
        for item in proof_results:
            lines.append((
                f"■ {item.get('id', 'unknown')}  [{label(item.get('status'))}]",
                status_color(str(item.get("status"))),
            ))
            winner = item.get("winner")
            if isinstance(winner, dict) and winner.get("patch"):
                patch = " ".join(str(winner["patch"]).split())
                for line in wrap_lines(f"winner: {patch}", width - 2, indent="  "):
                    lines.append((line, "muted"))
    if certificate_report:
        lines.append(("", "muted"))
        lines.append(("CERTIFICATE CHECK", "title"))
        cert_status = certificate_report.get("status")
        lines.append((f"status: {label(cert_status)}", status_color(str(cert_status))))
        verification = certificate_report.get("certificate_verification", {})
        if isinstance(verification, dict):
            lines.append((
                f"lean check: {label(verification.get('status'))}",
                status_color(str(verification.get("status"))),
            ))
            if verification.get("elapsed_ms") is not None:
                lines.append((f"elapsed_ms: {verification['elapsed_ms']}", "muted"))
        if certificate_report.get("report_sha256"):
            lines.append((f"report: {certificate_report['report_sha256']}", "muted"))
    return lines


def _short_json(value: Any, width: int) -> str:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    return " ".join(text.split())


def event_summary(event: dict[str, Any]) -> tuple[str, str]:
    kind = str(event.get("type", "event"))
    when = str(event.get("time", ""))[11:19] if event.get("time") else "--:--:--"
    task = event.get("task_id") or event.get("task") or ""
    prefix = f"{when} {kind}"
    if task:
        prefix += f" {task}"
    color = "muted"
    detail = ""
    if kind == "model_call_started":
        color = "gap"
        detail = f"call={event.get('call_index')} agent={event.get('agent')} model={event.get('model')}"
    elif kind == "model_call_completed":
        color = "good"
        detail = f"call={event.get('call_index')} agent={event.get('agent')}"
    elif kind == "model_call_failed":
        color = "bad"
        detail = f"call={event.get('call_index')} agent={event.get('agent')} {event.get('message')}"
    elif kind == "round_started":
        color = "title"
        detail = (
            f"round={event.get('round')} frontier={event.get('frontier_width')} "
            f"model_calls={event.get('model_calls')} candidates={event.get('unique_candidates')}"
        )
    elif kind == "supervisor_decision":
        color = "warn" if event.get("action") == "stop" else "muted"
        detail = f"round={event.get('round')} action={event.get('action')} reason={event.get('reason')}"
    elif kind == "candidates_collected":
        detail = f"round={event.get('round')} count={event.get('candidate_count')}"
    elif kind == "verification_started":
        color = "gap"
        detail = f"round={event.get('round')} count={event.get('candidate_count')}"
    elif kind == "verification_completed":
        color = status_color(str(event.get("status")))
        detail = (
            f"round={event.get('round')} status={event.get('status')} "
            f"attempts={event.get('attempt_count')} winner={event.get('winner_id')}"
        )
    elif kind == "model_parallelism_backoff":
        color = "warn"
        detail = (
            f"round={event.get('round')} parallelism "
            f"{event.get('previous_parallelism')}→{event.get('new_parallelism')} "
            f"reason={event.get('reason')}"
        )
    elif kind in {"task_started", "task_completed", "search_completed"}:
        color = status_color(str(event.get("status", "running")))
        detail = f"status={event.get('status', 'running')}"
    elif event.get("message"):
        color = "bad"
        detail = str(event.get("message"))
    text = f"{prefix}  {detail}".rstrip()
    return text, color


def event_summary_lines(event: dict[str, Any], width: int) -> list[tuple[str, str]]:
    text, color = event_summary(event)
    return [(line, color) for line in wrap_lines(text, width)]


def human_turn_summary(summary: Any) -> str:
    text = str(summary)
    if text.startswith("accepted ") and " candidate" in text:
        return "proposed " + text.removeprefix("accepted ")
    return text


def search_outcome(status: str, data: dict[str, Any]) -> str:
    if status == "verified":
        winner = data.get("winner")
        winner_id = winner.get("id") if isinstance(winner, dict) else data.get("winner_id")
        suffix = f"; winner={winner_id}" if winner_id else ""
        return "outcome: Lean verified a candidate proof" + suffix
    if status == "exhausted":
        calls = data.get("model_calls", 0)
        candidates = data.get("unique_candidates", 0)
        return f"outcome: no verified proof before search stopped; model_calls={calls}, candidates={candidates}"
    if status == "project_not_built":
        return "outcome: verifier infrastructure is missing compiled Lean modules"
    return f"outcome: {label(status)}"


def search_result_lines(data: dict[str, Any], width: int) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    status = str(data.get("status", "unknown"))
    lines.append((f"SEARCH  {data.get('id', 'unknown')}  [{label(status)}]", status_color(status)))
    lines.append((search_outcome(status, data), status_color(status)))
    lines.append((
        f"model_calls={data.get('model_calls', 0)}  "
        f"unique_candidates={data.get('unique_candidates', 0)}  "
        f"rounds={data.get('rounds_used', 0)}",
        "muted",
    ))
    task = data.get("task", {})
    if isinstance(task, dict):
        lines.append((f"target: {task.get('target') or '(generated obligation)'}", "muted"))
        for line in wrap_lines(f"theorem: {task.get('theorem', '')}", width, indent=""):
            lines.append((line, "muted"))
        subgoals = task.get("subgoals", [])
        if isinstance(subgoals, list) and subgoals:
            lines.append(("", "muted"))
            lines.append(("PROOF GRAPH / SUBGOAL DAG", "title"))
            for item in subgoals:
                if isinstance(item, dict):
                    deps = ", ".join(item.get("depends_on", [])) if isinstance(item.get("depends_on"), list) else ""
                    lines.append((f"◆ {item.get('id')}  deps=[{deps}]", "gap"))
                    for line in wrap_lines(str(item.get("theorem", "")), width - 2, indent="  "):
                        lines.append((line, "muted"))
    lines.append(("", "muted"))
    lines.append(("SUPERVISOR DECISIONS", "title"))
    for decision in data.get("supervisor_decisions", []):
        if isinstance(decision, dict):
            lines.append((
                f"■ r{decision.get('round')} {decision.get('action')} — {decision.get('reason')}",
                "warn" if decision.get("action") == "stop" else "good",
            ))
            for line in wrap_lines(
                f"assignments: {_short_json(decision.get('assignments', {}), width - 2)}",
                width - 2, indent="  ",
            ):
                lines.append((line, "muted"))
    lines.append(("", "muted"))
    lines.append(("AGENT TURNS", "title"))
    for turn in data.get("agent_turns", []):
        if isinstance(turn, dict):
            lines.append((
                f"■ {turn.get('agent')} r{turn.get('round')} {turn.get('action')} [{label(turn.get('status'))}]",
                status_color(str(turn.get("status"))),
            ))
            if turn.get("received_handoff_id"):
                lines.append((f"  routed input: {turn['received_handoff_id']}", "gap"))
            for line in wrap_lines(human_turn_summary(turn.get("output_summary", "")), width - 2, indent="  "):
                lines.append((line, "muted"))
    handoffs = data.get("handoffs", [])
    receipts = data.get("handoff_receipts", [])
    if handoffs or receipts:
        lines.append(("", "muted"))
        lines.append(("ROUTING HANDOFFS", "title"))
        lines.append(("These are advisory candidate routes between agents, not Lean proof verdicts.", "muted"))
        for item in handoffs:
            if isinstance(item, dict):
                state = "used later" if item.get("accepted") else "offered"
                lines.append((
                    f"↳ {item.get('id')} {item.get('from_agent')} -> {item.get('to_agent')} "
                    f"node={item.get('node_id')} [{state}]",
                    "gap",
                ))
        for item in receipts:
            if isinstance(item, dict):
                used = bool(item.get("accepted"))
                color = "good" if used else "muted"
                state = "used routed candidate" if used else "did not use routed candidate"
                lines.append((
                    f"→ {item.get('handoff_id')} receiver={item.get('receiver_agent')} [{state}]",
                    color,
                ))
                for line in wrap_lines(str(item.get("receiver_summary", "")), width - 2, indent="  "):
                    lines.append((line, "muted"))
    scorecard = data.get("agent_scorecard", {})
    if isinstance(scorecard, dict) and scorecard:
        lines.append(("", "muted"))
        lines.append(("SCORECARD", "title"))
        for agent, stats in scorecard.items():
            for line in wrap_lines(
                f"■ {agent}: {_short_json(stats, width - len(agent) - 4)}", width
            ):
                lines.append((line, "muted"))
    attempts = data.get("attempts", [])
    if attempts:
        lines.append(("", "muted"))
        lines.append(("LEAN DIAGNOSTICS", "title"))
        for attempt in attempts:
            if isinstance(attempt, dict):
                color = status_color(str(attempt.get("status")))
                lines.append((
                    f"■ {attempt.get('id')} [{label(attempt.get('status'))}]",
                    color,
                ))
                if attempt.get("status") == "project_not_built":
                    lines.append(("  infrastructure issue: build the Lean project before running proof search", "warn"))
                diagnostics = str(attempt.get("diagnostics", "")) or "(none)"
                for line in wrap_lines(diagnostics, width - 2, indent="  "):
                    lines.append((line, "muted"))
    certificate = data.get("certificate_report")
    if isinstance(certificate, dict):
        lines.append(("", "muted"))
        lines.append(("CERTIFICATE STATUS", "title"))
        cert_status = str(certificate.get("status", "unknown"))
        lines.append((f"status: {label(cert_status)}", status_color(cert_status)))
    return lines


def proof_review_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for artifact in data.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        task = artifact.get("task", {})
        winner = artifact.get("winner", {})
        if not isinstance(task, dict):
            task = {}
        if not isinstance(winner, dict):
            winner = {}
        attempts = artifact.get("attempts", [])
        verified = next(
            (item for item in attempts if isinstance(item, dict) and item.get("status") == "verified"),
            {},
        )
        if not isinstance(verified, dict):
            verified = {}
        entries.append({
            "id": artifact.get("id", "unknown"),
            "status": artifact.get("status", "unknown"),
            "theorem": task.get("theorem", ""),
            "module": task.get("module", ""),
            "project": task.get("project", ""),
            "proof": winner.get("patch") or verified.get("patch") or "(no accepted proof)",
            "diagnostics": verified.get("diagnostics", "(not verified)"),
        })
    return entries


def proof_review_lines(data: dict[str, Any], width: int) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = [("PROOF REVIEW", "title")]
    for entry in proof_review_entries(data):
        status = str(entry["status"])
        lines.append((f"■ {entry['id']} [{label(status)}]", status_color(status)))
        for heading, value in (("theorem", entry["theorem"]), ("proof", entry["proof"]),
                               ("verification", entry["diagnostics"])):
            lines.append((heading.upper(), "gap"))
            for line in wrap_lines(str(value), width - 2, indent="  "):
                lines.append((line, "muted"))
        lines.append(("", "muted"))
    return lines or [("No proof artifacts yet.", "muted")]


def assessment_lines(data: dict[str, Any], width: int) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    verdict = str(data.get("verdict", "inconclusive"))
    color = {
        "physically_sound": "good",
        "not_sound": "bad",
        "inconclusive": "warn",
    }.get(verdict, "muted")
    lines.append((f"VERDICT  {label(verdict).upper()}", color))
    for line in wrap_lines(str(data.get("summary", "")), width):
        lines.append((line, "muted"))
    lines.append(("", "muted"))
    lines.append(("ASSUMPTIONS", "title"))
    assumptions = data.get("assumptions", [])
    if isinstance(assumptions, list) and assumptions:
        for item in assumptions:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "unknown"))
            lines.append((f"■ {item.get('id', 'assumption')}  [{label(status)}]", status_color(status)))
            evidence = str(item.get("evidence", "")).strip()
            if evidence:
                for line in wrap_lines(f"evidence: {evidence}", width - 2, indent="  "):
                    lines.append((line, "muted"))
            value = item.get("value")
            if value is not None:
                for line in wrap_lines(f"value: {_short_json(value, width - 9)}", width - 2, indent="  "):
                    lines.append((line, "muted"))
            question = str(item.get("question") or "").strip()
            if question:
                for line in wrap_lines(f"clarify: {question}", width - 2, indent="  "):
                    lines.append((line, "warn"))
            review = item.get("proof_review")
            if isinstance(review, dict):
                assessment = str(review.get("assessment", "insufficient"))
                lines.append((f"  rationale review: {label(assessment)} (not Lean-verified)", "warn"))
                rationale = str(review.get("review", "")).strip()
                if rationale:
                    for line in wrap_lines(rationale, width - 4, indent="    "):
                        lines.append((line, "muted"))
    else:
        lines.append(("No assumptions extracted yet.", "muted"))
    lines.append(("", "muted"))
    lines.append(("VERDICT EVIDENCE", "title"))
    checks = data.get("checks", [])
    if isinstance(checks, list) and checks:
        for item in checks:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "unknown"))
            lines.append((f"◆ {item.get('id', 'check')}  [{label(status)}]", status_color(status)))
            for line in wrap_lines(str(item.get("reason", "")), width - 2, indent="  "):
                lines.append((line, "muted"))
    else:
        lines.append(("No formal checks have been mapped yet.", "muted"))
    lines.append(("", "muted"))
    lines.append(("NEXT ACTION", "title"))
    for action in data.get("next_actions", []) or ["Open proof details when you need to audit the decision."]:
        for line in wrap_lines(f"■ {action}", width):
            lines.append((line, "warn"))
    lines.append(("", "muted"))
    lines.append(("SYSTEM DIAGNOSTICS", "title"))
    lines.append((f"assessment: {data.get('assessment_sha256', 'draft')}", "muted"))
    artifacts = data.get("artifacts", {})
    if isinstance(artifacts, dict):
        for name, path in artifacts.items():
            lines.append((f"{name}: {path}", "muted"))
    return lines


def run_inspector_lines(data: dict[str, Any], width: int) -> list[tuple[str, str]]:
    state = data.get("state", {})
    artifacts = [item for item in data.get("artifacts", []) if isinstance(item, dict)]
    lines: list[tuple[str, str]] = []
    status = str(state.get("status", "unknown")) if isinstance(state, dict) else "unknown"
    lines.append((f"RUN  {state.get('run_id', 'unknown') if isinstance(state, dict) else 'unknown'}  [{label(status)}]", status_color(status)))
    if isinstance(state, dict):
        lines.append(("", "muted"))
        lines.append(("TASK QUEUE", "title"))
        for item in state.get("tasks", []):
            if isinstance(item, dict):
                lines.append((
                    f"■ {item.get('task_id')} [{label(item.get('status'))}] artifact={item.get('artifact')}",
                    status_color(str(item.get("status"))),
                ))
        if state.get("blocked"):
            lines.append(("", "muted"))
            lines.append(("BLOCKED", "warn"))
            for item in state.get("blocked", []):
                if isinstance(item, dict):
                    lines.append((f"! {item.get('task_id')} [{label(item.get('status'))}]", "warn"))
        if state.get("completed"):
            lines.append(("", "muted"))
            lines.append(("COMPLETED", "good"))
            for item in state.get("completed", []):
                if isinstance(item, dict):
                    lines.append((f"✓ {item.get('task_id')} [{label(item.get('status'))}]", "good"))
    events = data.get("events", [])
    if isinstance(events, list) and events:
        lines.append(("", "muted"))
        lines.append(("RECENT ACTIVITY", "title"))
        for event in events[-18:]:
            if isinstance(event, dict):
                lines.extend(event_summary_lines(event, width))
    lines.append(("", "muted"))
    if artifacts:
        selected = data.get("selected_artifact_index", len(artifacts) - 1)
        if not isinstance(selected, int):
            selected = len(artifacts) - 1
        selected = max(0, min(selected, len(artifacts) - 1))
        artifact = artifacts[selected]
        lines.append((f"PAST TASK  {selected + 1}/{len(artifacts)}  ([/] cycle)", "title"))
        lines.extend(search_result_lines(artifact, width))
    else:
        lines.append(("PAST TASKS", "title"))
        lines.append(("No completed task artifacts yet.", "muted"))
    return lines


def coverage_lines(data: dict[str, Any], width: int) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = [
        (f"POLICY  {data['policy']['id']} v{data['policy']['version']}", "title"),
        (f"Lean library: {data['project']['lean_library']}", "muted"),
        (f"Toolchain: {data['project']['toolchain']}", "muted"),
        ("", "muted"),
        ("SUPPORTED CHECKS", "title"),
    ]
    for item in data["supported_claims"]:
        lines.append((f"■ {item['fact']}", "good"))
        for line in wrap_lines(item["description"], width - 2, indent="  "):
            lines.append((line, "muted"))
    lines.append(("", "muted"))
    lines.append(("FORMALIZATION PROFILES", "title"))
    for item in data["formalization_profiles"]:
        lines.append((f"◆ {item['id']}", "gap"))
        lines.append((f"  module: {item['module']}", "muted"))
        lines.append((f"  facts: {', '.join(item['facts'])}", "muted"))
    return lines


def render_plain(data: dict[str, Any], *, coverage: bool = False,
                 width: int = 100) -> str:
    if data.get("inspector_kind") == "assessment":
        source = assessment_lines(data["assessment"], width)
    elif data.get("inspector_kind") == "search_result":
        source = search_result_lines(data["result"], width)
    elif data.get("inspector_kind") == "run":
        source = run_inspector_lines(data, width)
    elif data.get("inspector_kind") == "proof_review":
        source = proof_review_lines(data, width)
    else:
        source = coverage_lines(data, width) if coverage else report_lines(data, width)
    return "\n".join(text for text, _ in source)
