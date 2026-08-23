"""Generate paper-ready LaTeX/Markdown tables from a saved VISTA corpus result bundle."""
from __future__ import annotations
import argparse, csv, json
from collections import defaultdict
from pathlib import Path


def rate(a, b):
    return "n/a" if not b else f"{a}/{b} ({a / b:.1%})"


def load(results: Path):
    rows = list(csv.DictReader((results / "cases.csv").open()))
    primary = [r for r in rows if r["repeat"] == "0"]
    evidence = {}
    for row in primary:
        path = results / row["case_id"] / "0" / "evidence.json"
        if path.exists():
            evidence[row["case_id"]] = json.loads(path.read_text(encoding="utf-8"))
    return rows, primary, evidence


def metrics(rows, primary, evidence, results_dir):
    negatives = [r for r in primary if r["expected_status"] != "supported-and-compatible"]
    false_certs = [r for r in negatives if r["certificate_status"] == "verified"]
    positives = [r for r in primary if r["expected_status"] == "supported-and-compatible"]
    tamper = [t for ev in evidence.values() for t in ev.get("tampering", [])]
    by_case = defaultdict(list)
    for r in rows:
        by_case[r["case_id"]].append(r)
    stable = sum(
        len({(x["observed_semantic_status"], x["observed_ir_value"], x["lean_status"], x["certificate_status"]) for x in items}) == 1
        for items in by_case.values()
    )
    obligation_stable = 0
    total_with_obligations = 0
    for case_id, items in by_case.items():
        hashes = set()
        ok = True
        for x in items:
            path = results_dir / case_id / x["repeat"] / "evidence.json"
            if not path.exists():
                ok = False
                break
            ev = json.loads(path.read_text(encoding="utf-8"))
            if "generated_obligations" not in ev:
                ok = False
                break
            hashes.add(ev["generated_obligations"].get("ir_sha256", ""))
        if not ok:
            continue
        total_with_obligations += 1
        if len(hashes) <= 1:
            obligation_stable += 1
    return {
        "exact_semantic_classification": rate(sum(r["observed_semantic_status"] == r["expected_status"] for r in primary), len(primary)),
        "total_cases": len(primary),
        "false_certification": rate(len(false_certs), len(negatives)),
        "positive_acceptance": rate(sum(r["certificate_status"] == "verified" for r in positives), len(positives)),
        "near_miss_certificate_withheld": rate(sum(r["certificate_status"] != "verified" for r in primary if r["class"] == "near_miss"), sum(r["class"] == "near_miss" for r in primary)),
        "unsupported_certificate_withheld": rate(sum(r["certificate_status"] != "verified" for r in primary if r["expected_status"] == "unsupported"), sum(r["expected_status"] == "unsupported" for r in primary)),
        "malformed_input_rejected": rate(sum(r["observed_semantic_status"] == "malformed" for r in primary if r["expected_status"] == "malformed"), sum(r["expected_status"] == "malformed" for r in primary)),
        "tamper_detection": rate(sum(t["detected"] for t in tamper), len(tamper)),
        "reproducible_disposition": rate(stable, len(by_case)),
        "stable_obligation_hash": rate(obligation_stable, total_with_obligations),
    }


def tex_escape(value):
    return str(value).replace("_", "\\_")


def write_tex(path, tables):
    path.write_text("\n\n".join(tables) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    options = parser.parse_args()
    rows, primary, evidence = load(options.results)
    summary = metrics(rows, primary, evidence, options.results)
    (options.results / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    groups = defaultdict(list)
    for r in primary:
        groups[(r["domain"], r["class"])].append(r)
    agg_lines = ["| domain | class | cases | correct | unsupported | malformed | false certs |",
                 "|---|---:|---:|---:|---:|---:|---:|"]
    agg_tex = ["\\begin{tabular}{llrrrrr}", "\\toprule",
               "domain & class & cases & correct & unsupported & malformed & false certs \\", "\\midrule"]
    for (domain, cls), items in sorted(groups.items()):
        correct = sum(x["correct"] == "True" for x in items)
        unsup = sum(x["observed_semantic_status"] == "unsupported" for x in items)
        malf = sum(x["observed_semantic_status"] == "malformed" for x in items)
        fc = sum(x["certificate_status"] == "verified" and x["expected_status"] != "supported-and-compatible" for x in items)
        agg_lines.append(f"| {domain} | {cls} | {len(items)} | {correct} | {unsup} | {malf} | {fc} |")
        agg_tex.append(f"{domain} & {cls.replace('_', ' ')} & {len(items)} & {correct} & {unsup} & {malf} & {fc} \\")
    agg_tex += ["\\bottomrule", "\\end{tabular}"]

    metric_tex = ["\\begin{tabular}{lr}", "\\toprule", "metric & value \\", "\\midrule"]
    for key, value in summary.items():
        metric_tex.append(f"{key.replace('_', ' ')} & {tex_escape(value)} \\")
    metric_tex += ["\\bottomrule", "\\end{tabular}"]

    per_mutation = defaultdict(lambda: [0, 0])
    for ev in evidence.values():
        for t in ev.get("tampering", []):
            per_mutation[t["tamper_id"]][1] += 1
            if t["detected"]:
                per_mutation[t["tamper_id"]][0] += 1
    tamper_lines = ["| mutation | detected | rejected by |", "|---|---:|---|"]
    tamper_tex = ["\\begin{tabular}{lrl}", "\\toprule", "mutation & detected & rejected by \\", "\\midrule"]
    for name, (det, tot) in sorted(per_mutation.items()):
        stage = "translation validation" if det else "not detected (documented gap)"
        tamper_lines.append(f"| {name} | {det}/{tot} | {stage} |")
        tamper_tex.append(f"{tex_escape(name)} & {det}/{tot} & {tex_escape(stage)} \\")
    tamper_tex += ["\\bottomrule", "\\end{tabular}"]

    (options.results / "tables.md").write_text(
        "# VISTA structural eval v1 tables\n\n## Metrics\n\n"
        + "\n".join(f"- {k}: {v}" for k, v in summary.items())
        + "\n\n## Domain x class\n\n" + "\n".join(agg_lines)
        + "\n\n## Tampering\n\n" + "\n".join(tamper_lines) + "\n",
        encoding="utf-8")
    write_tex(options.results / "tables.tex", [
        "% metrics\n" + "\n".join(metric_tex),
        "% domain x class\n" + "\n".join(agg_tex),
        "% tampering\n" + "\n".join(tamper_tex)])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
