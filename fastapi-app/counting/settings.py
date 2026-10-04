"""Counting settings (env vars) and the box time zone the local date/hour/weekday columns use."""
import os
from datetime import timedelta
from zoneinfo import ZoneInfo

import core

# A face track F and a body track F-1 on one camera are the same person (the box hands out face and
# body ids from one counter, body first), provided their first records are at most this far apart.
PAIR_MAX = timedelta(seconds=int(os.getenv("COUNT_PAIR_MAX_SECONDS", "120")))
# The same identified person on the same camera again within this gap is still one visit.
VISIT_GAP_SECONDS = int(os.getenv("COUNT_VISIT_GAP_SECONDS", "120"))

BUCKET = timedelta(minutes=15)


def box_tz() -> ZoneInfo:
    """The box's time zone. Unlike the rest of the portal there's no fallback to this PC's zone:
    counts filed under the wrong local day or hour would be silently wrong."""
    if core.BOX_TZ is not None:
        return core.BOX_TZ
    return ZoneInfo(core.BOX_TIMEZONE_NAME)    # raises if the zone really is missing
