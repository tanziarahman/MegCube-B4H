"""
Helpers for reading box JSON whose exact shape isn't documented.
Each lookup tries several possible key names anywhere in the nested data.
Once you confirm the real names (GET /api/recognition/raw-sample), put them first in the lists.
"""
from collections import deque
from typing import Any, Iterable

LIST_KEYS = ("alarm_list", "list", "records", "items", "groups", "group_list",
             "device_list", "channel_list", "data", "rows", "result")
TOTAL_KEYS = ("total", "total_num", "total_count", "count", "num")


def find(obj: Any, keys: Iterable[str], default=None):
    """Breadth-first search for the first non-empty value stored under any of `keys`."""
    keys = tuple(keys)
    queue = deque([obj])
    while queue:
        cur = queue.popleft()
        if isinstance(cur, dict):
            for k in keys:
                v = cur.get(k)
                if v not in (None, "", [], {}):
                    return v
            queue.extend(v for v in cur.values() if isinstance(v, (dict, list)))
        elif isinstance(cur, list):
            queue.extend(v for v in cur if isinstance(v, (dict, list)))
    return default


def find_all(obj: Any, keys: Iterable[str]) -> list:
    """Every non-empty value stored under any of `keys` (e.g. all group names)."""
    keys = tuple(keys)
    out: list = []

    def walk(node: Any):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in keys and v not in (None, "", [], {}):
                    out.extend(v if isinstance(v, list) else [v])
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(obj)
    return out


def find_list(resp: Any) -> list:
    """The list of records inside a box response, wherever it sits."""
    if isinstance(resp, list):
        return resp
    queue = deque([resp])
    while queue:
        cur = queue.popleft()
        if isinstance(cur, dict):
            for k in LIST_KEYS:
                if isinstance(cur.get(k), list):
                    return cur[k]
            queue.extend(v for v in cur.values() if isinstance(v, dict))
    return []


def find_total(resp: Any, fallback: int) -> int:
    try:
        return int(find(resp, TOTAL_KEYS))
    except (TypeError, ValueError):
        return fallback


def to_score(v) -> float | None:
    """Box scores may be 0–1 or 0–100; always return 0–100 with one decimal."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f * 100, 1) if 0 < f <= 1 else round(f, 1)


def to_str(v) -> str | None:
    return None if v in (None, "") else str(v)


def collect_images(obj: Any) -> list[dict]:
    """All image references in a record, in document order: [{"uri": ..., "type": <label or "">}]."""
    found: list[dict] = []

    def walk(node: Any):
        if isinstance(node, dict):
            uri = node.get("image_uri") or node.get("uri") or node.get("url") or node.get("image_url")
            if uri is None and node.get("image_data_format") in (2, "2"):
                uri = node.get("image_data")
            if isinstance(uri, str) and uri:
                label = node.get("image_type") or node.get("type") or node.get("pic_type") or node.get("name")
                found.append({"uri": uri, "type": str(label).lower() if label is not None else ""})
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(obj)
    return found
