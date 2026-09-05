"""Score saved VISTA V3 locality-corpus results against the independently
authored manifest. The manifest is the sole source of expected labels.
"""
from __future__ import annotations
import argparse, csv, hashlib, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STATUS_BY_POLICY = {"structurally_certifiable": "supported-and-compatible",
                    "structural_requirements_not_met": "supported-but-incompatible",
                    "formalization_required": "unsupported"}


def rate(a, b):
    return "n/a" if not b else f"{a}/{b} ({a / b:.1%})"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def verify_condition_fingerprint(options, fingerprint, experiment):
    issues = []
    for field in ("condition_name", "corpus_freeze_revision", "execution_revision"):
        if fingerprint.get(field) != experiment.get(field):
            issues.append(f"condition fingerprint {field} contradicts saved experiment")
    if fingerprint.get("manifest_sha256") != sha256_file(options.manifest):
        issues.append("condition fingerprint manifest_sha256 does not match manifest bytes")
    sources = fingerprint.get("source_sha256")
    if not isinstance(sources, dict):
        return [*issues, "condition fingerprint source_sha256 is missing or invalid"]
    for name, recorded in sources.items():
        path = ROOT / Path(name.replace("\\", "/"))
        if not path.is_file():
            issues.append(f"condition fingerprint source is unavailable: {name}")
        elif sha256_file(path) != recorded:
            issues.append(f"condition fingerprint source_sha256 mismatch: {name}")
    return issues


def verify_bundle(options, manifest_cases, primary, rows):
    issues = []
    by_id = {case["id"]: case for case in manifest_cases}
    row_ids = {row["case_id"] for row in primary}
    for missing in sorted(set(by_id) - row_ids):
        issues.append(f"manifest case absent from results: {missing}")
    for extra in sorted(row_ids - set(by_id)):
        issues.append(f"result case not in manifest: {extra}")
    per_case = defaultdict(list)
    for row in rows:
        per_case[row["case_id"]].append(row)
    for case_id, items in per_case.items():
        if case_id not in by_id:
            continue
        if len({r["repeat"] for r in items}) < 3:
            issues.append(f"{case_id}: fewer than 3 repeats recorded")
        for row in items:
            case = by_id[case_id]
            expected = case["expected"]["semantic_status"]
            if row["expected_status"] != expected:
                issues.append(f"{case_id}[{row['repeat']}]: csv expected_status {row['expected_status']!r} contradicts manifest {expected!r}")
            evidence_path = options.results / case_id / row["repeat"] / "evidence.json"
            if not evidence_path.exists():
                issues.append(f"{case_id}[{row['repeat']}]: evidence bundle missing")
                continue
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            artifact = options.artifacts / f"{case_id}.pt2"
            recorded = evidence.get("artifact_sha256")
            if artifact.exists():
                actual = sha256_file(artifact)
                if recorded != actual:
                    issues.append(f"{case_id}[{row['repeat']}]: artifact_sha256 does not match artifact bytes")
            ir = evidence.get("structural_ir")
            policy = evidence.get("policy")
            if ir and policy:
                if STATUS_BY_POLICY.get(policy.get("status")) != row["observed_semantic_status"]:
                    issues.append(f"{case_id}[{row['repeat']}]: observed_semantic_status contradicts recorded policy status")
            lean = evidence.get("lean_verification")
            if row["certificate_status"] == "verified":
                if not lean or lean.get("status") != "verified":
                    issues.append(f"{case_id}[{row['repeat']}]: certificate_status verified without verified Lean check")
                if evidence.get("certificate", {}).get("ir_sha256") != evidence.get("policy", {}).get("ir_sha256"):
                    issues.append(f"{case_id}[{row['repeat']}]: certificate IR binding mismatch")
            if (row["translation_valid"] == "True") != bool((ir or {}).get("translation_validation", {}).get("status") == "translation_validated"):
                issues.append(f"{case_id}[{row['repeat']}]: translation_valid column contradicts evidence")
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--artifacts", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, required=True)
    options = parser.parse_args()
    options.artifacts = options.artifacts or options.results.parents[1].parent / "build" / "vista-structural-v3-corpus"
    fingerprint_path = options.results / "condition_fingerprint.json"
    manifest_cases = json.loads(options.manifest.read_text())["cases"]
    rows = list(csv.DictReader((options.results / "cases.csv").open()))
    primary = [r for r in rows if r["repeat"] == "0"]

    issues = verify_bundle(options, manifest_cases, primary, rows)
    if fingerprint_path.exists():
        fingerprint = json.loads(fingerprint_path.read_text())
        experiment_path = options.results / "experiment.json"
        if experiment_path.exists():
            issues.extend(verify_condition_fingerprint(options, fingerprint, json.loads(experiment_path.read_text())))
        else:
            issues.append("result experiment.json is missing")

    by_case = {case["id"]: case for case in manifest_cases}
    correct = [r for r in primary if by_case.get(r["case_id"], {}).get("expected", {}).get("semantic_status") == r["observed_semantic_status"]]
    negatives = [r for r in primary if by_case[r["case_id"]]["expected"]["semantic_status"] != "supported-and-compatible"]
    false_cert = [r for r in negatives if r["certificate_status"] == "verified"]
    positives = [r for r in primary if by_case[r["case_id"]]["expected"]["semantic_status"] == "supported-and-compatible"]
    tamper = []
    for row in primary:
        path = options.results / row["case_id"] / "0" / "evidence.json"
        if path.exists():
            tamper.extend(json.loads(path.read_text(encoding="utf-8")).get("tampering", []))
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["case_id"]].append(row)
    stable = sum(len({(x["observed_semantic_status"], x["observed_ir_value"], x["lean_status"], x["certificate_status"]) for x in items}) == 1 for items in grouped.values())

    summary = {
        "cases": len(primary),
        "exact_semantic_classification": rate(len(correct), len(primary)),
        "false_certification": rate(len(false_cert), len(negatives)),
        "positive_acceptance": rate(sum(r["certificate_status"] == "verified" for r in positives), len(positives)),
        "near_miss_certificate_withheld": rate(sum(r["certificate_status"] != "verified" for r in primary if r["class"] == "near_miss"), sum(r["class"] == "near_miss" for r in primary)),
        "unsupported_certificate_withheld": rate(sum(r["certificate_status"] != "verified" for r in primary if by_case[r["case_id"]]["expected"]["semantic_status"] == "unsupported"), sum(by_case[r["case_id"]]["expected"]["semantic_status"] == "unsupported" for r in primary)),
        "malformed_input_rejected": rate(sum(r["observed_semantic_status"] == "malformed" for r in primary if by_case[r["case_id"]]["expected"]["semantic_status"] == "malformed"), sum(by_case[r["case_id"]]["expected"]["semantic_status"] == "malformed" for r in primary)),
        "tamper_detection": rate(sum(t["detected"] for t in tamper), len(tamper)),
        "reproducible_disposition": rate(stable, len(grouped)),
        "bundle_integrity_issues": len(issues),
        "note": "exact_semantic_classification is the correctness headline; *_withheld metrics measure certificate refusal only",
    }
    if not fingerprint_path.exists():
        summary["bundle_integrity_issues"] += 1

    (options.results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
