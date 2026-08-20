"""Preview composition root for Ama + APOLLO.

The currently deployed read-only service may continue using `bloom_engine.api:app`.
This module composes that proven surface with the APOLLO visual router so the
visual runtime can be tested and reviewed without silently changing the live
entrypoint.
"""

from fastapi import Depends

from bloom_engine.api import app, require_auth
from bloom_engine.apollo.api import router as visual_router


# Every APOLLO route is bearer-protected at the composition boundary. Individual
# visual handlers therefore cannot accidentally be mounted publicly later by
# forgetting a per-route dependency.
app.include_router(visual_router, dependencies=[Depends(require_auth)])
