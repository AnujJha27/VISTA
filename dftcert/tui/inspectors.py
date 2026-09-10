"""Load a search-result/run-directory/proof-review path into the data dict
shape `rendering.py`/`app.py` expect."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .rendering import load_json_object, load_json_value, load_jsonl_objects


def build_search_inspector(path: str | Path) -> dict[str, Any]:
    value = load_json_value(path)
    if isinstance(value, dict):
        return {"inspector_kind": "search_result", "result": value}
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return {
            "inspector_kind": "run",
            "state": {
                "run_id": str(path),
                "status": "loaded_artifacts",
                "tasks": [
                    {
                        "task_id": item.get("id", "unknown"),
                        "status": item.get("status", "unknown"),
                        "artifact": str(path),
                    }
                    for item in value
                ],
                "blocked": [
                    {"task_id": item.get("id", "unknown"), "status": item.get("status", "unknown")}
                    for item in value
                    if item.get("status") not in {"verified", "approved"}
                ],
                "completed": [
                    {"task_id": item.get("id", "unknown"), "status": item.get("status", "unknown")}
                    for item in value
                    if item.get("status") in {"verified", "approved"}
                ],
            },
            "artifacts": value,
        }
    raise ValueError(f"{path} must contain a search object or array of search objects")


def build_run_inspector(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    assessment = root / "assessment.json"
    if assessment.exists():
        manifest = root / "manifest.json"
        return {
            "inspector_kind": "assessment",
            "assessment": load_json_object(assessment),
            "manifest": load_json_object(manifest) if manifest.exists() else {},
        }
    state = load_json_object(root / "state.json")
    if isinstance(state.get("proof_results"), list):
        results = {
            item.get("id"): item
            for item in state["proof_results"]
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        generated = state.get("generation", {}).get("obligations", [])
        tasks = []
        if isinstance(generated, list):
            for task in generated:
                if not isinstance(task, dict) or not isinstance(task.get("id"), str):
                    continue
                result = results.get(task["id"])
                tasks.append({
                    "task_id": task["id"],
                    "status": result.get("status") if result else (
                        "running" if state.get("status") == "proof_search_running" else task.get("status", "pending")
                    ),
                    "task": task,
                    "artifact": str(root / "state.json"),
                })
        state = {
            "run_id": str(root),
            "status": state.get("status", "unknown"),
            "tasks": tasks,
            "blocked": [],
        }
    artifacts: list[dict[str, Any]] = []
    artifact_root = root / "artifacts"
    if artifact_root.exists():
        for artifact in sorted(artifact_root.glob("*.json")):
            artifacts.append(load_json_object(artifact))
    events = []
    for entry in load_jsonl_objects(root / "events.jsonl", limit=200):
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("type"), str):
            normalized = dict(entry)
        else:
            fields = entry.get("fields", {})
            normalized = dict(fields) if isinstance(fields, dict) else {}
            normalized["type"] = entry.get("event", "event")
            normalized["time"] = entry.get("timestamp", "")
        events.append(normalized)
    return {"inspector_kind": "run", "state": state, "artifacts": artifacts, "events": events}


def build_proof_review(path: str | Path) -> dict[str, Any]:
    inspected = build_run_inspector(path)
    return {"inspector_kind": "proof_review", "artifacts": inspected.get("artifacts", [])}
