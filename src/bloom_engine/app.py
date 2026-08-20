"""Preview composition root for Ama + APOLLO.

The currently deployed read-only service may continue using `bloom_engine.api:app`.
This module composes that proven surface with the APOLLO visual router so the
visual runtime can be tested and reviewed without silently changing the live
entrypoint.
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends

from bloom_engine.api import app, require_auth
from bloom_engine.apollo.api import router as visual_router
from bloom_engine.apollo.job_store import AirtableVisualJobStore

logger = logging.getLogger("uvicorn.error")


# Every APOLLO route is bearer-protected at the composition boundary. Individual
# visual handlers therefore cannot accidentally be mounted publicly later by
# forgetting a per-route dependency.
app.include_router(visual_router, dependencies=[Depends(require_auth)])


@app.on_event("startup")
def pause_interrupted_apollo_jobs() -> None:
    """Fail safe after a process restart; never auto-repeat paid generation.

    FastAPI BackgroundTasks are process-local. If Render restarts a process, any
    in-flight generation coroutine is gone even though its Visual Batch survives.
    The replacement process therefore pauses prior RUNNING APOLLO batches as
    RECOVERY_REQUIRED. A later human/operator may inspect already-persisted
    candidates before deciding whether another paid call is appropriate.
    """

    if os.getenv("APOLLO_RECOVER_ON_STARTUP", "1") != "1":
        return
    token = os.getenv("AIRTABLE_PAT")
    if not token:
        return
    base_id = os.getenv("BLOOM_AIRTABLE_BASE_ID", "appNhl43NzKfbsTAw")
    try:
        recovered = AirtableVisualJobStore(base_id=base_id, token=token).pause_orphaned_running_jobs()
    except Exception as exc:
        # Preserve the read-only runtime even if operational recovery metadata is
        # temporarily unavailable. We still never auto-resubmit the old jobs.
        logger.error("APOLLO_RECOVERY_SCAN_FAILED type=%s message=%s", type(exc).__name__, str(exc)[:500])
        return
    if recovered:
        logger.warning(
            "APOLLO_RECOVERY_REQUIRED jobs=%s",
            ",".join(state.visual_job_id for state in recovered),
        )
