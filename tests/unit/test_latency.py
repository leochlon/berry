"""One round for all claims, and one shared connection pool."""

from __future__ import annotations

import inspect
import math
import threading
import time
from typing import Any, List

from berry.hallucination_detector import core, trace_budget
from berry.hallucination_detector.backends import openai_backend
from berry.hallucination_detector.backends.base import BackendConfig, OpenAIBackend
from berry.hallucination_detector.backends.openai_backend import TextResult


def _answer(p_yes: float) -> List[dict[str, Any]]:
    p_no = max(1.0 - p_yes, 1e-9)
    return [
        {
            "token": "YES",
            "logprob": math.log(p_yes),
            "top_logprobs": [
                {"token": "YES", "logprob": math.log(p_yes)},
                {"token": "NO", "logprob": math.log(p_no)},
            ],
        }
    ]


class FakeBackend:
    """Supported claims: confident with the evidence visible, not without it. A claim that says
    'invented' is never supported."""

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def call_text_batch(self, *, prompts, **_kw: Any) -> List[TextResult]:
        self.batches.append(list(prompts))
        out = []
        for p in prompts:
            claim = p.split("CLAIM:\n", 1)[1].split("\n", 1)[0]
            if "invented" in claim:
                p_yes = 0.05
            else:
                p_yes = 0.05 if "[REDACTED]" in p else 0.97
            out.append(TextResult(text="YES", response_id=None, logprobs=_answer(p_yes)))
        return out

    def reset_state(self) -> None:
        pass


STEPS = [
    {"idx": 0, "claim": "The question asks for the total of revenue.", "cites": ["Q"]},
    {"idx": 1, "claim": "The question asks for an invented limit.", "cites": ["Q"]},
    {"idx": 2, "claim": "The question asks for the number of orders.", "cites": ["Q"]},
]
SPANS = [{"sid": "Q", "text": 'The user\'s request, quoted exactly: "What was revenue in 2026?".'}]


def _run(monkeypatch, backend: FakeBackend) -> dict[str, Any]:
    monkeypatch.setattr(trace_budget, "make_backend", lambda cfg: backend)
    return core.run_audit_trace_budget(
        steps=STEPS, spans=SPANS, verifier_model="m", default_target=0.9, require_citations=True
    )


def test_every_prompt_goes_out_in_a_single_batch(monkeypatch):
    backend = FakeBackend()
    _run(monkeypatch, backend)
    assert len(backend.batches) == 1  # was two, one after the other
    batch = backend.batches[0]
    assert len(batch) == 2 * len(STEPS)
    with_evidence, without = batch[: len(STEPS)], batch[len(STEPS) :]
    assert all("[REDACTED]" not in p for p in with_evidence)
    assert all("[REDACTED]" in p for p in without)


def test_results_still_line_up_with_their_claims(monkeypatch):
    result = _run(monkeypatch, FakeBackend())
    flagged = {d["idx"] for d in result["details"] if d["flagged"]}
    assert flagged == {1}  # only the invented claim; a swapped split would flag the others


def test_the_summary_says_how_long_the_check_took(monkeypatch):
    summary = _run(monkeypatch, FakeBackend())["summary"]
    assert isinstance(summary["elapsed_ms"], int) and summary["elapsed_ms"] >= 0


def test_the_default_concurrency_covers_one_round_of_all_calls():
    for fn in (core.run_audit_trace_budget, core.run_detect_hallucination):
        assert inspect.signature(fn).parameters["max_concurrency"].default >= 32


def test_all_threads_share_one_client():
    openai_backend._client_cache.clear()
    seen: list[Any] = []
    threads = [
        threading.Thread(target=lambda: seen.append(openai_backend._get_client(api_key="k")))
        for _ in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({id(c) for c in seen}) == 1
    assert openai_backend._get_client(api_key="k") is seen[0]  # and later batches reuse it


def test_a_batch_never_starts_more_threads_than_it_has_prompts():
    backend = OpenAIBackend(BackendConfig(max_concurrency=20))
    idents: set[int] = set()

    def fake_call(**kw: Any) -> TextResult:
        idents.add(threading.get_ident())
        time.sleep(0.05)
        return TextResult(text=kw["prompt"], response_id=None, logprobs=None)

    backend.call_text = fake_call  # type: ignore[method-assign]
    results = backend.call_text_batch(prompts=["a", "b", "c"])
    assert [r.text for r in results] == ["a", "b", "c"]  # order preserved
    assert len(idents) <= 3
