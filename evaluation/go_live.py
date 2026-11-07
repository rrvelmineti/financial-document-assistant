"""Go-live gate: compare an evaluation run with the criteria agreed with the client.

    python evaluation/run_eval.py --answers      # first, needs a Gemini key
    python evaluation/go_live.py                 # reads evaluation/results/answers-gemini.json
    python evaluation/go_live.py --results evaluation/results/retrieval-hashing.json

Writes evaluation/results/go-live.md and exits with 0 for GO, 1 for NO-GO and 2 when the evaluation
needed for a decision has not been run yet. The decision is GO only when every blocking check passes.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITERIA = ROOT / "evaluation" / "go_live_criteria.json"
RESULTS = ROOT / "evaluation" / "results"
DEFAULT_RUN = RESULTS / "answers-gemini.json"

GO, NO_GO, NOT_READY = "GO", "NO-GO", "NOT READY"


def check(summary, c):
    """One criterion against one summary: {'id', 'label', 'result', 'target', 'status', 'blocking'}."""
    out = {"id": c["id"], "label": c["label"], "blocking": c["blocking"]}
    value = summary.get(c["metric"])
    total = summary.get(c["of"]) if "of" in c else None
    if value is None or ("of" in c and not total):
        return {**out, "result": "not measured", "target": target_text(c), "status": "missing"}
    if "of" in c:
        share = value / total
        passed = share >= c["min_share"]
        result = f"{value} of {total} ({share:.0%})"
    else:
        passed = value <= c["max"]
        result = str(value)
    return {**out, "result": result, "target": target_text(c), "status": "pass" if passed else "fail"}


def target_text(c):
    return f"at least {c['min_share']:.0%}" if "min_share" in c else f"at most {c['max']}"


def decide(checks):
    blocking = [c for c in checks if c["blocking"]]
    if any(c["status"] == "missing" for c in blocking):
        return NOT_READY
    return GO if all(c["status"] == "pass" for c in blocking) else NO_GO


def report(summary, checks, decision, source):
    icon = {"pass": "Pass", "fail": "**Fail**", "missing": "Not measured"}
    lines = ["# Go-live readiness", "",
             f"**Decision: {decision}**", "",
             f"Evaluation run: `{source}`, run on {summary.get('run_on', 'unknown date')}, "
             f"answer model `{summary.get('model') or 'none'}`, retrieval `{summary.get('embedder', 'unknown')}`.", "",
             "| Check | Result | Target | Blocking | Status |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {c['label']} | {c['result']} | {c['target']} | {'yes' if c['blocking'] else 'no'} | {icon[c['status']]} |"
              for c in checks]
    lines += ["", {
        GO: "Every blocking check passes. Go live with the pilot group, keep the review queue staffed "
            "(`GET /api/review-queue`) and watch `GET /api/usage` daily during hypercare.",
        NO_GO: "At least one blocking check fails. Do not go live. Review the failing questions in the "
               "per-question table of the evaluation report, fix, and run the evaluation again.",
        NOT_READY: "A blocking figure has not been measured. Run `python evaluation/run_eval.py --answers` "
                   "with a Gemini key, then run this gate again.",
    }[decision], "", "Sign-off: ______________________  (client owner)   Date: __________", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=DEFAULT_RUN, help="evaluation JSON written by run_eval.py")
    parser.add_argument("--criteria", type=Path, default=CRITERIA)
    parser.add_argument("--out", type=Path, default=RESULTS / "go-live.md")
    args = parser.parse_args(argv)
    criteria = json.loads(args.criteria.read_text())["checks"]
    summary = json.loads(args.results.read_text())["summary"] if args.results.exists() else {}
    checks = [check(summary, c) for c in criteria]
    decision = decide(checks)
    try:
        source = args.results.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        source = args.results.name
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(summary, checks, decision, source), encoding="utf-8")
    for c in checks:
        print(f"  {c['status']:8} {c['label']}: {c['result']} (target {c['target']})")
    print(f"\nDecision: {decision}. Wrote {args.out}")
    return {GO: 0, NO_GO: 1, NOT_READY: 2}[decision]


if __name__ == "__main__":
    sys.exit(main())
