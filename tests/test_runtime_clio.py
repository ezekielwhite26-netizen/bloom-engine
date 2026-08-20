from bloom_engine.runtime import ClioEvent, ClioHandoff, ClioManifest, GatedClio, InMemoryClioTransactionStore


def handoff(token: str | None, realized=True, authorized=True):
    return ClioHandoff(
        transaction_key="TXN::TEST::001",
        packet_key="CTX::TEST",
        arc="Aster Hollow / At the Threshold",
        source_run="RUN::TEST",
        expected_pre_state_digest="{}",
        manifest=ClioManifest(
            event=ClioEvent(
                event_key="TEST-EVENT",
                arc="Aster Hollow / At the Threshold",
                in_world_time="fixture",
                location_ref="BLM-LOC-000004",
                location_name="The Green",
                event_type="Fixture",
                summary="Structured fixture event.",
                participant_refs=("BLM-CHR-000001",),
                source_provenance=("test fixture",),
            ),
            readback_assertions=("event exists after commit",),
        ),
        realized=realized,
        persistence_authorized=authorized,
        authorization_token=token,
    )


def test_clio_rejects_realization_without_non_model_capability():
    store = InMemoryClioTransactionStore()
    result = GatedClio(store).commit(handoff(token=None))
    assert result.status == "BLOCKED"
    assert not result.committed_event_ids
    assert not store.structured_events


def test_clio_commits_structured_manifest_exactly_once_and_reads_back():
    store = InMemoryClioTransactionStore()
    clio = GatedClio(store)
    first = clio.commit(handoff(token="AMA-CAP::fixture"))
    second = clio.commit(handoff(token="AMA-CAP::different-token-would-not-matter-after-idempotency"))
    assert first.status == "COMMITTED"
    assert first.readback_verified is True
    assert first.committed_event_ids == ("MEM-EVT-0001",)
    assert second == first
    assert tuple(store.structured_events) == ("MEM-EVT-0001",)


def test_clio_preview_is_no_op_even_if_manifest_contains_candidate_event():
    store = InMemoryClioTransactionStore()
    result = GatedClio(store).commit(
        handoff(token="AMA-CAP::fixture", realized=False, authorized=False)
    )
    assert result.status == "NO_OP"
    assert result.readback_verified is True
    assert not store.structured_events
