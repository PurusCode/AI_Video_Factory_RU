from video_farm.production_director import _is_blocking_review


def make_review(
    *,
    verdict="accept",
    relevance=5,
    feasibility=5,
    narration=5,
    factual_risk="low",
):
    return {
        "verdict": verdict,
        "relevance_score": relevance,
        "feasibility_score": feasibility,
        "narration_coverage_score": narration,
        "factual_risk": factual_risk,
    }


def test_revise_verdict_alone_is_not_a_blocker():
    assert _is_blocking_review(make_review(verdict="revise")) is False


def test_low_feasibility_score_blocks_production():
    assert _is_blocking_review(make_review(feasibility=3)) is True


def test_low_narration_coverage_blocks_production():
    assert _is_blocking_review(make_review(narration=2)) is True


def test_high_factual_risk_blocks_even_with_high_scores():
    assert _is_blocking_review(make_review(factual_risk="high")) is True


def test_medium_factual_risk_with_good_scores_is_not_automatic_blocker():
    assert _is_blocking_review(make_review(factual_risk="medium")) is False


def test_missing_score_fails_closed():
    review = make_review()
    del review["feasibility_score"]
    assert _is_blocking_review(review) is True
