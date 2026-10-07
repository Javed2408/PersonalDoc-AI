"""Runs the retrieval evaluation set (evaluation/retrieval_dataset.json) with the real model."""

import statistics

import pytest

from evaluation.retrieval_eval import run

pytestmark = pytest.mark.model


def test_retrieval_evaluation_baseline(real_embedder):
    report = run(embedder=real_embedder, k=4)

    assert len(report.answerable) == 12
    assert len(report.unanswerable) == 3
    misses = [(r.id, r.question, r.top) for r in report.answerable if not r.rank or r.rank > 4]
    assert not misses, misses
    assert report.hit_rate(1) >= 0.9
    # Questions the documents can't answer match noticeably worse than ones they can.
    assert statistics.median(r.best_distance for r in report.unanswerable) > max(
        r.best_distance for r in report.answerable
    )
