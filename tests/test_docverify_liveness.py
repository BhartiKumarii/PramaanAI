"""Liveness check on the live photo: advisory evidence, never a verdict."""
from datetime import date

import pytest

from app.services.docverify.pipeline import Ctx, _liveness_check
from app.services.docverify.types import CheckStatus as S


def run(liveness):
    ctx = Ctx(on=date(2026, 1, 1), liveness=liveness)
    _liveness_check(ctx, 0)
    (c,) = ctx.checks
    assert c.name == "liveness" and c.blocking is False
    return c


def test_prompts_passed_and_real_score_passes():
    c = run({"active": "PASSED", "challenges": ["BLINK", "TURN_HEAD"], "passive_score": 0.93, "source": "camera"})
    assert c.status == S.PASS and "0.93" in c.summary


def test_low_anti_spoof_score_asks_for_in_person_check_even_if_prompts_passed():
    c = run({"active": "PASSED", "passive_score": 0.12, "source": "camera"})
    assert c.status == S.REVIEW_REQUIRED and "photo or screen" in c.summary


def test_prompts_not_completed():
    c = run({"active": "NOT_COMPLETED", "passive_score": 0.8, "source": "camera"})
    assert c.status == S.REVIEW_REQUIRED and "not completed" in c.summary


@pytest.mark.parametrize("lv", [None, {"active": "NOT_PERFORMED", "source": "gallery"}])
def test_not_checked(lv):
    assert run(lv).status == S.NOT_VERIFIED


def test_wording_never_accuses():
    for lv in ({"active": "NOT_COMPLETED", "source": "camera"}, {"active": "PASSED", "passive_score": 0.0}):
        text = run(lv).summary.lower()
        assert not any(w in text for w in ("fake", "fraud", "criminal", "forged", "deny"))
