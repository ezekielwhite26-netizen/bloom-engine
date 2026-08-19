from bloom_engine.cold_boot import (
    BackfillState,
    ColdBootSnapshot,
    TemporalFact,
    ThreadState,
    compile_minimal_packet,
    opening_thread_candidates,
    reconstruct_mutable_state,
    subsystem_backfill_state,
    temporally_valid_facts,
)


def test_blm_tst_000020_cb006_dormant_thread_does_not_become_opening_plot():
    snapshot = ColdBootSnapshot(
        threads=(
            ThreadState("quiet-family-scene", "ACTIVE", attention=1, matured_trigger=False),
            ThreadState("old-high-attention-mystery", "DORMANT", attention=99, matured_trigger=False),
            ThreadState("matured-consequence", "ACTIVE", attention=2, matured_trigger=True),
        )
    )
    assert opening_thread_candidates(snapshot) == ("matured-consequence",)


def test_blm_tst_000021_cb007_minimal_context_packet_excludes_irrelevant_high_attention_material():
    records = {
        "scene-body": {"kind": "BODY", "value": "scene-relevant"},
        "present-character": {"kind": "character", "value": "present"},
        "due-obligation": {"kind": "schedule", "value": "due"},
        "old-cosmology": {"kind": "author-only", "attention": 100},
        "dormant-mystery": {"kind": "thread", "attention": 90},
    }
    packet = compile_minimal_packet(
        records,
        ("scene-body", "present-character", "due-obligation", "missing-unknown"),
    )
    assert tuple(packet) == ("scene-body", "present-character", "due-obligation")
    assert "old-cosmology" not in packet
    assert "dormant-mystery" not in packet
    assert "missing-unknown" not in packet


def test_blm_tst_000022_cb008_commitment_and_temporary_possession_survive_exactly():
    snapshot = ColdBootSnapshot(
        obligations={"BLM-SCH-EXAMPLE": {"status": "UNFULFILLED", "due": "14:00"}},
        possessions={
            "BLM-OBJ-EXAMPLE": {
                "canonical_owner": "BLM-CHR-OWNER",
                "current_holder": "BLM-CHR-TEMP-HOLDER",
                "location": None,
            }
        },
    )
    rebuilt = reconstruct_mutable_state(snapshot)
    assert rebuilt["obligations"]["BLM-SCH-EXAMPLE"]["status"] == "UNFULFILLED"
    assert rebuilt["possessions"]["BLM-OBJ-EXAMPLE"]["canonical_owner"] == "BLM-CHR-OWNER"
    assert rebuilt["possessions"]["BLM-OBJ-EXAMPLE"]["current_holder"] == "BLM-CHR-TEMP-HOLDER"
    assert rebuilt["possessions"]["BLM-OBJ-EXAMPLE"]["location"] is None


def test_blm_tst_000023_cb009_cross_book_temporal_boundary_blocks_future_leakage():
    snapshot = ColdBootSnapshot(
        temporal_facts=(
            TemporalFact("aster-2009-state", 2009, "valid"),
            TemporalFact("later-public-world-state", 2018, "future"),
            TemporalFact("adult-character-state", 2025, "future"),
        )
    )
    scene_facts = temporally_valid_facts(snapshot, 2009)
    assert tuple(f.key for f in scene_facts) == ("aster-2009-state",)

    author_facts = temporally_valid_facts(snapshot, 2009, author_cross_book=True)
    assert tuple(f.key for f in author_facts) == (
        "aster-2009-state",
        "later-public-world-state",
        "adult-character-state",
    )


def test_blm_tst_000024_cb010_empty_subsystem_is_unknown_not_nonexistence():
    snapshot = ColdBootSnapshot(
        subsystem_rows={
            "new-structured-subsystem": (),
            "backfilled-subsystem": ({"key": "record-1"},),
        }
    )
    assert subsystem_backfill_state(snapshot, "new-structured-subsystem") is BackfillState.UNKNOWN
    assert subsystem_backfill_state(snapshot, "missing-subsystem") is BackfillState.UNKNOWN
    assert subsystem_backfill_state(snapshot, "backfilled-subsystem") is BackfillState.KNOWN
