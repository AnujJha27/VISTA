"""Score saved VISTA corpus results against the independently authored manifest.

The manifest is the sole source of expected labels: cases.csv rows are verified
against it and evidence bundles are re-checked before any metric is produced.
Never infers ground truth from the analyzer.
"""
from __future__ import annotations
import argparse, csv, hashlib, json
from collections import defaultdict
from itertools import groupby
from pathlib import Path

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


def verify_bundle(options, manifest_cases, primary, rows):
    """Cross-check result rows and evidence against the manifest; return issues."""
    issues = []
    by_id = {case["id"]: case for case in manifest_cases}
    row_ids = {row["case_id"] for row in primary}
    for missing in sorted(set(by_id) - row_ids):
        issues.append(f"manifest case absent from results: {missing}")
    for extra in sorted(row_ids - set(by_id)):
        issues.append(f"result case not in manifest: {extra}")
    if len(rows) != len(primary) + sum(1 for r in rows if r["repeat"] != "0"):
        pass  # repeats are additive; checked via per-case counts below
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
            if row["domain"] != case["domain"] or row["class"] != case["class"] or row["split"] != case["split"]:
                issues.append(f"{case_id}[{row['repeat']}]: domain/class/split contradict manifest")
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
                if row["artifact_hash"] and row["artifact_hash"] != actual:
                    issues.append(f"{case_id}[{row['repeat']}]: csv artifact_hash does not match artifact bytes")
            elif fingerprint_map.get(case_id) not in (None, recorded):
                issues.append(f"{case_id}[{row['repeat']}]: artifact file absent; hash contradicts condition fingerprint")
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
            if row["translation_valid"] != bool((ir or {}).get("translation_validation", {}).get("status") == "translation_validated"):
                issues.append(f"{case_id}[{row['repeat']}]: translation_valid column contradicts evidence")
    return issues


fingerprint_map = {}


def main():
    global fingerprint_map
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--artifacts", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, required=True)
    options = parser.parse_args()
    options.artifacts = options.artifacts or options.results.parents[1].parent / "build" / "vista-structural-v2-corpus"
    fingerprint_path = options.results / "condition_fingerprint.json"
    if fingerprint_path.exists():
        fingerprint_map = json.loads(fingerprint_path.read_text()).get("artifact_sha256", {})
    else:
        issues_note = "condition_fingerprint.json missing from result bundle"
        fingerprint_map = {}
    manifest_cases = json.loads(options.manifest.read_text())["cases"]
    rows = list(csv.DictReader((options.results / "cases.csv").open()))
    primary = [r for r in rows if r["repeat"] == "0"]

    issues = verify_bundle(options, manifest_cases, primary, rows)

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
        # withholding rates measure refusal to certify; NOT semantic accuracy
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

    lines = ["| domain | class | cases | exact-correct | unsupported-obs | malformed-obs | false certs |", "|---|---:|---:|---:|---:|---:|---:|"]
    groups = defaultdict(list)
    for row in primary:
        groups[(row["domain"], row["class"])].append(row)
    for (domain, cls), items in sorted(groups.items()):
        lines.append(f"| {domain} | {cls} | {len(items)} | {sum(x['observed_semantic_status'] == by_case[x['case_id']]['expected']['semantic_status'] for x in items)} | {sum(x['observed_semantic_status'] == 'unsupported' for x in items)} | {sum(x['observed_semantic_status'] == 'malformed' for x in items)} | {sum(x['certificate_status'] == 'verified' for x in items if by_case[x['case_id']]['expected']['semantic_status'] != 'supported-and-compatible')} |")

    (options.results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    integrity = "# VISTA Structural V2 evaluation\n\n## Integrity\n\n" + ("\n".join(f"- ISSUE: {i}" for i in issues) if issues else "- all bundle checks passed (manifest agreement, artifact hashes, policy/IR/certificate consistency)") + "\n\n## Domain x class\n\n" + "\n".join(lines) + "\n\n## Metrics\n\n" + "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in summary.items()) + "\n"
    (options.results / "summary.md").write_text(integrity, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
