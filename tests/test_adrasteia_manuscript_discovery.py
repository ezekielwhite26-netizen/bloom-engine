import time

from bloom_engine.runtime import manuscript as manuscript
from bloom_engine.runtime.manuscript_discovery import review_manuscript_with_discovery


def _session() -> manuscript.ManuscriptReviewSession:
    now = time.time()
    return manuscript.ManuscriptReviewSession(
        context_id="MCTX::discovery-test",
        allowed_fact_keys=frozenset({"EVID::KNOWN"}),
        protected_domains=frozenset(),
        created_at=now,
        expires_at=now + 60,
    )


def _review(claims):
    return review_manuscript_with_discovery(
        session=_session(),
        phase="DRAFT",
        claims=claims,
        reader_new_subjects=(),
        oriented_subjects=(),
        reader_ledger_commit_requested=False,
    )


def test_adjacent_detail_is_marked_not_blocked_and_never_persisted():
    result = _review(({"kind": "ADJACENT_DETAIL", "key": "MDETAIL::FLORENCE_CURTAINS"},))

    assert result["status"] == "PASS"
    assert result["story_canon_persisted"] is False
    assert result["reader_ledger_committed"] is False
    assert result["replacement_prose"] is None
    finding = next(item for item in result["findings"] if item.get("authority_class") == "SUPPORTED/ADJACENT")
    assert finding["result"] == "PASS"
    assert finding["may_remain_provisionally"] is True
    assert finding["canon_promotion_authorized"] is False


def test_discovery_candidate_can_remain_but_requires_author_promotion():
    result = _review(({"kind": "CANON_CANDIDATE", "key": "MDISC::ASTERIA_BALCONY"},))

    assert result["status"] == "PASS_WITH_WARNINGS"
    finding = next(item for item in result["findings"] if item.get("authority_class") == "CANON CANDIDATE/DISCOVERY")
    assert finding["may_remain_provisionally"] is True
    assert finding["canon_promotion_authorized"] is False
    assert "AUTHOR" in finding["responsible_owner"]


def test_open_detail_is_not_silently_promoted():
    result = _review(({"kind": "OPEN_DETAIL", "key": "MOPEN::AIRPORT_TO_HEARTH_ROUTE"},))

    assert result["status"] == "PASS_WITH_WARNINGS"
    finding = next(item for item in result["findings"] if item.get("authority_class") == "OPEN")
    assert finding["provisional_only"] is True
    assert finding["canon_promotion_authorized"] is False


def test_conflicting_detail_still_blocks():
    result = _review(({"kind": "CONFLICTING_DETAIL", "key": "MCONFLICT::ASTERIA_STAYED_HOME"},))

    assert result["status"] == "BLOCKED"
    finding = next(item for item in result["findings"] if item.get("authority_class") == "CONFLICTING")
    assert finding["result"] == "BLOCK"
    assert finding["may_remain_provisionally"] is False


def test_unissued_fact_still_blocks_under_original_evidence_gate():
    result = _review(({"kind": "FACT", "key": "NOT-ISSUED"},))

    assert result["status"] == "BLOCKED"
    assert any("not supported by the issued authoring evidence" in item["message"] for item in result["findings"])


def test_issued_fact_still_passes():
    result = _review(({"kind": "FACT", "key": "EVID::KNOWN"},))

    assert result["status"] == "PASS"
    assert result["authority_policy"]["absence_of_record_is_not_contradiction"] is True
