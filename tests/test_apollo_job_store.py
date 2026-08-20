from __future__ import annotations

from bloom_engine.apollo.job_store import InMemoryVisualJobStore


def test_interrupted_running_job_pauses_without_retry_or_completion():
    store = InMemoryVisualJobStore()
    store.start(
        visual_job_id="APOLLO-VIS-JOB::test",
        request_key="VIS-RUN::test",
        arc="Aster Hollow / At the Threshold",
        subject_id="BLM-CHR-000001",
        subject_name="Florence Maeve MacKellar",
        command="Build Florence profile",
        shot_list=("left_profile",),
        required_anchor_assets=("FACE_GOLD",),
    )

    recovered = store.pause_orphaned_running_jobs()

    assert len(recovered) == 1
    state = recovered[0]
    assert state.status == "RECOVERY_REQUIRED"
    assert state.recovery_required is True
    assert state.error == "HOST_RESTART_DURING_VISUAL_JOB"
    assert state.result is None
    assert store.get(state.visual_job_id) == state


def test_recovery_scan_is_idempotent():
    store = InMemoryVisualJobStore()
    store.start(
        visual_job_id="APOLLO-VIS-JOB::test",
        request_key="VIS-RUN::test",
        arc="Aster Hollow / At the Threshold",
        subject_id="BLM-CHR-000001",
        subject_name="Florence Maeve MacKellar",
        command="Build Florence profile",
        shot_list=("left_profile",),
        required_anchor_assets=("FACE_GOLD",),
    )

    assert len(store.pause_orphaned_running_jobs()) == 1
    assert store.pause_orphaned_running_jobs() == ()


def test_finished_job_is_never_reclassified_as_orphaned():
    store = InMemoryVisualJobStore()
    store.start(
        visual_job_id="APOLLO-VIS-JOB::test",
        request_key="VIS-RUN::test",
        arc="Aster Hollow / At the Threshold",
        subject_id="BLM-CHR-000001",
        subject_name="Florence Maeve MacKellar",
        command="Build Florence profile",
        shot_list=("left_profile",),
        required_anchor_assets=("FACE_GOLD",),
    )
    store.finish(
        "APOLLO-VIS-JOB::test",
        status="SYSTEM_PASS",
        result={"requires_human_approval": True},
    )

    assert store.pause_orphaned_running_jobs() == ()
    state = store.get("APOLLO-VIS-JOB::test")
    assert state is not None
    assert state.status == "SYSTEM_PASS"
