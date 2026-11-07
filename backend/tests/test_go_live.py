"""The go-live gate in evaluation/go_live.py. Offline; no AI calls."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evaluation"))
import go_live  # noqa: E402

CRITERIA = json.loads(go_live.CRITERIA.read_text())["checks"]
GOOD = {"run_on": "2026-11-06", "model": "m", "embedder": "gemini", "answerable": 20, "unanswerable": 5,
        "retrieval_hits": 18, "answers_correct": 17, "citations_correct": 18, "not_found_correct": 5,
        "false_answers_on_unanswerable": 0}


def decision(summary):
    return go_live.decide([go_live.check(summary, c) for c in CRITERIA])


class GoLiveTests(unittest.TestCase):
    def test_a_good_run_is_go(self):
        self.assertEqual(decision(GOOD), go_live.GO)

    def test_one_invented_answer_blocks_go_live(self):
        self.assertEqual(decision({**GOOD, "false_answers_on_unanswerable": 1}), go_live.NO_GO)

    def test_low_accuracy_blocks_go_live(self):
        self.assertEqual(decision({**GOOD, "answers_correct": 15}), go_live.NO_GO)    # 75% < 80%

    def test_a_non_blocking_miss_is_reported_but_does_not_block(self):
        checks = [go_live.check({**GOOD, "retrieval_hits": 10}, c) for c in CRITERIA]
        self.assertEqual(go_live.decide(checks), go_live.GO)
        self.assertEqual({c["id"]: c["status"] for c in checks}["retrieval"], "fail")

    def test_a_retrieval_only_run_is_not_ready(self):
        retrieval_only = {k: GOOD[k] for k in ("run_on", "embedder", "answerable", "unanswerable", "retrieval_hits")}
        self.assertEqual(decision(retrieval_only), go_live.NOT_READY)

    def test_the_committed_offline_run_is_not_ready_and_writes_a_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "go-live.md"
            code = go_live.main(["--results", str(go_live.RESULTS / "retrieval-hashing.json"), "--out", str(out)])
            self.assertEqual(code, 2)
            text = out.read_text()
            self.assertIn("**Decision: NOT READY**", text)
            self.assertIn("| Retrieval: evidence page among retrieved passages | 16 of 20 (80%)", text)


if __name__ == "__main__":
    unittest.main()
