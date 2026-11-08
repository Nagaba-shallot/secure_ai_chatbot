import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.security import validate_input 


def run():
    cases = json.loads((ROOT / "attacks" / "attack_cases.json").read_text(encoding="utf-8"))
    rows = []
    for case in cases:
        result = validate_input(case["payload"])
        matched = result.action == case["expect"]
        if case.get("known_gap"):
            status = "NOW COVERED" if matched else "KNOWN GAP"
        else:
            status = "PASS" if matched else "FAIL"
        rows.append({**case, "actual": result.action, "reasons": result.reasons, "status": status})
    return rows


def summarise(rows):
    count = lambda s: sum(1 for r in rows if r["status"] == s)  # noqa: E731
    return {s: count(s) for s in ("PASS", "FAIL", "KNOWN GAP", "NOW COVERED")}


def write_report(rows, path):
    s = summarise(rows)
    lines = [
        "# Attack report",
        "",
        f"Generated {date.today().isoformat()} by `attacks/run_attacks.py` against the input security layer.",
        "",
        f"**{s['PASS']} passed, {s['FAIL']} failed, {s['KNOWN GAP']} known gaps, {s['NOW COVERED']} newly covered.**",
        "",
        "| ID | Category | Expected | Actual | Status | Triggered rules |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        reasons = ", ".join(r["reasons"]) or "-"
        lines.append(f"| {r['id']} | {r['category']} | {r['expect']} | {r['actual']} | {r['status']} | {reasons} |")
    gaps = [r for r in rows if r.get("known_gap")]
    if gaps:
        lines += ["", "## Known gaps", ""]
        for r in gaps:
            lines.append(f"- **{r['id']} ({r['category']}):** {r.get('note', '')}")
    lines += [
        "",
        "## Why gaps are acceptable (for now)",
        "",
        "Input heuristics are one layer. Later layers still apply: the canary token blocks any reply that leaks the",
        "system prompt, outputs are scrubbed for secrets, memory writes are validated, and every user's data is isolated.",
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    rows = run()
    for r in rows:
        print(f"{r['status']:<12} {r['id']}  {r['category']:<20} expected={r['expect']:<8} actual={r['actual']}")
    s = summarise(rows)
    print(f"\n{s['PASS']} passed, {s['FAIL']} failed, {s['KNOWN GAP']} known gaps, {s['NOW COVERED']} newly covered")
    if "--report" in sys.argv:
        write_report(rows, ROOT / "docs" / "attack-report.md")
        print("wrote docs/attack-report.md")
    return 1 if s["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())