"""
Evaluation harness for the music agent.

Runs the full pipeline (guardrails -> retrieval -> plan -> recommend -> critique -> revise)
on predefined requests in evaluation/cases.json and prints a pass/fail summary, with
confidence scores, a retrieval on/off comparison, and a repeatability check.

Run from the project root:
    python -m evaluation.run_eval
    python -m evaluation.run_eval --out assets/eval_results.txt --traces assets/agent_traces.md

Exit code is 0 when every case passes, 1 otherwise (usable in CI).
"""

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agent import AgentResult, MusicAgent  # noqa: E402
from src.agent_log import setup_logging  # noqa: E402
from src.recommender import load_songs  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "cases.json"
SONGS_CSV = ROOT / "data" / "songs.csv"
UNDERSTOOD = ("ok", "needs_review")


def check(result: AgentResult, expect: Dict) -> List[str]:
    """Compare a result with the expectations; return a list of failure descriptions."""
    failures: List[str] = []
    profile = result.plan.profile if result.plan else {}
    recs = result.recommendations
    top = recs[0][0] if recs else None

    def want(name, actual, expected):
        if actual != expected:
            failures.append(f"{name}: expected {expected!r}, got {actual!r}")

    if "status" in expect:
        want("status", result.status, expect["status"])
    if "profile_genre" in expect:
        want("profile genre", profile.get("favorite_genre"), expect["profile_genre"])
    if "profile_mood" in expect:
        want("profile mood", profile.get("favorite_mood"), expect["profile_mood"])
    if "diversity" in expect:
        want("diversity", bool(result.plan and result.plan.diversity), expect["diversity"])
    if "top_title" in expect:
        want("top title", top["title"] if top else None, expect["top_title"])
    if "top_genre" in expect:
        want("top genre", top["genre"] if top else None, expect["top_genre"])
    if "top5_contains" in expect and expect["top5_contains"] not in [s["title"] for s, _, _ in recs]:
        failures.append(f"top 5 should contain {expect['top5_contains']!r}")
    if "top5_excludes_genre" in expect and any(s["genre"] == expect["top5_excludes_genre"] for s, _, _ in recs):
        failures.append(f"top 5 should not contain genre {expect['top5_excludes_genre']!r}")
    if "max_energy" in expect and profile.get("target_energy", 1.0) > expect["max_energy"]:
        failures.append(f"target energy {profile.get('target_energy')} above {expect['max_energy']}")
    if "min_revisions" in expect and result.revisions < expect["min_revisions"]:
        failures.append(f"expected at least {expect['min_revisions']} revision(s), got {result.revisions}")
    return failures


def run_cases(agent: MusicAgent, cases: List[Dict]) -> List[Tuple[Dict, AgentResult, List[str]]]:
    rows = []
    for case in cases:
        result = agent.ask(case["text"])
        rows.append((case, result, check(result, case["expect"])))
    return rows


def short(text: str, width: int = 44) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 3] + "..."


def build_report(songs: List[Dict], cases: List[Dict]) -> Tuple[str, bool, List[Tuple[Dict, AgentResult]]]:
    full = MusicAgent(songs)
    baseline = MusicAgent(songs, use_retrieval=False)

    rows = run_cases(full, cases)
    base_rows = run_cases(baseline, cases)

    lines: List[str] = []
    out = lines.append
    out("MUSIC AGENT EVALUATION")
    out("=" * 96)
    out(f"{'case':<28}{'request':<46}{'status':<14}{'conf':<6}{'rev':<5}result")
    out("-" * 96)
    for case, result, failures in rows:
        conf = f"{result.assessment.confidence:.2f}" if result.assessment else "-"
        verdict = "PASS" if not failures else "FAIL"
        out(f"{case['id']:<28}{short(case['text']):<46}{result.status:<14}{conf:<6}{result.revisions:<5}{verdict}")
        for failure in failures:
            out(f"    -> {failure}")
    out("-" * 96)

    passed = sum(1 for _, _, f in rows if not f)
    confs = [r.assessment.confidence for _, r, _ in rows if r.assessment]
    ok_confs = [r.assessment.confidence for _, r, _ in rows if r.status == "ok"]
    review = [c["id"] for c, r, _ in rows if r.status == "needs_review"]
    guard = [(c, r) for c, r, _ in rows if c["id"].startswith("guard-")]
    guard_pass = sum(1 for c, r in guard if not check(r, c["expect"]))
    normal = [(c, r, f) for c, r, f in rows if not c["id"].startswith("guard-")]

    out(f"Cases passed:                 {passed}/{len(rows)}")
    out(f"Normal requests passed:       {sum(1 for _, _, f in normal if not f)}/{len(normal)}")
    out(f"Guardrail cases passed:       {guard_pass}/{len(guard)}  (rejections, gibberish, missing genres)")
    out(f"Average confidence:           {mean(confs):.2f} over {len(confs)} answered requests")
    out(f"  - status ok:                {mean(ok_confs):.2f}" if ok_confs else "  - status ok:                n/a")
    out(f"Flagged for human review:     {len(review)} ({', '.join(review) or 'none'})")
    out(f"Total revisions made:         {sum(r.revisions for _, r, _ in rows)}")

    # Retrieval on/off comparison (the RAG enhancement evidence).
    out("")
    out("RETRIEVAL COMPARISON (glossary documents on vs. off; catalog vocabulary stays on in both)")
    out("-" * 96)
    understood_full = sum(1 for _, r, _ in normal if r.status in UNDERSTOOD)
    understood_base = sum(1 for (_, r, _) in [x for x in base_rows if not x[0]["id"].startswith("guard-")] if r.status in UNDERSTOOD)
    correct_full = sum(1 for _, _, f in normal if not f)
    base_normal = [x for x in base_rows if not x[0]["id"].startswith("guard-")]
    correct_base = sum(1 for _, _, f in base_normal if not f)
    out(f"Normal requests understood:   with documents {understood_full}/{len(normal)}   without {understood_base}/{len(normal)}")
    out(f"Normal requests correct:      with documents {correct_full}/{len(normal)}   without {correct_base}/{len(normal)}")
    out("Examples (top pick, with documents -> without):")
    for (case, result, _), (_, base_result, _) in list(zip(rows, base_rows))[:12]:
        with_top = result.recommendations[0][0]["title"] if result.recommendations else f"[{result.status}]"
        without_top = (base_result.recommendations[0][0]["title"] if base_result.recommendations
                       else f"[{base_result.status}]")
        out(f"  {case['id']:<28}{with_top:<26}->  {without_top}")

    # Repeatability.
    out("")
    out("REPEATABILITY (every case run a second time; titles and confidence must match exactly)")
    out("-" * 96)
    repeat = MusicAgent(songs)
    same = 0
    for case, result, _ in rows:
        again = repeat.ask(case["text"])
        key = lambda r: ([s["title"] for s, _, _ in r.recommendations],
                         r.assessment.confidence if r.assessment else None, r.status)
        same += key(result) == key(again)
    out(f"Identical on re-run:          {same}/{len(rows)}")

    ok = passed == len(rows) and same == len(rows)
    out("")
    out("RESULT: " + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    return "\n".join(lines), ok, [(c, r) for c, r, _ in rows]


def traces_markdown(results: List[Tuple[Dict, AgentResult]]) -> str:
    parts = ["# Agent reasoning traces", "",
             "Generated by `python -m evaluation.run_eval --traces assets/agent_traces.md`. "
             "Each block shows every step the agent took for one request.", ""]
    for case, result in results:
        parts += [f"## {case['id']}", "", f"Request: `{case['text'][:80]}`", "", "```text"]
        parts += [f"{i}. {step}" for i, step in enumerate(result.trace, start=1)]
        if result.recommendations:
            parts.append("")
            parts.append("Top 3: " + "; ".join(f"{s['title']} ({sc:.2f})" for s, sc, _ in result.recommendations[:3]))
        parts += ["```", ""]
    return "\n".join(parts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the music agent on predefined requests")
    parser.add_argument("--out", help="also write the report to this file")
    parser.add_argument("--traces", help="write every case's reasoning trace to this markdown file")
    args = parser.parse_args(argv)

    setup_logging()
    songs = load_songs(str(SONGS_CSV))
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    report, ok, results = build_report(songs, cases)
    print(report)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report + "\n", encoding="utf-8")
    if args.traces:
        Path(args.traces).parent.mkdir(parents=True, exist_ok=True)
        Path(args.traces).write_text(traces_markdown(results), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
