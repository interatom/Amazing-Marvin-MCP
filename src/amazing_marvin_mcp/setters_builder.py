"""Convert TaskUpdateRequest into Marvin's setters format for /doc/update."""

import time

from .models import TaskUpdateRequest

# Map snake_case model fields to Marvin camelCase API keys
_FIELD_MAP: dict[str, str] = {
    "title": "title",
    "due_date": "dueDate",
    "scheduled_date": "day",
    "note": "note",
    "label_ids": "labelIds",
    "priority": "priority",
    "parent_id": "parentId",
    "is_starred": "isStarred",
    "is_frogged": "isFrogged",
    "time_estimate": "timeEstimate",
    "backburner": "backburner",
}

# Fields for which Marvin also expects a fieldUpdates.<key> timestamp entry.
# Any user-visible field edit warrants a fieldUpdates entry so sync conflict
# resolution can prefer the most recent change per field.
_TRACKED_FIELDS: set[str] = {
    "title",
    "note",
    "parentId",
    "dueDate",
    "day",
    "timeEstimate",
    "labelIds",
    "priority",
    "isStarred",
    "isFrogged",
    "backburner",
}


def build_setters(update: TaskUpdateRequest) -> list[dict]:
    """Convert a TaskUpdateRequest into Marvin's setters array format.

    Returns a list of {"key": ..., "val": ...} dicts ready to pass to /doc/update.
    Only includes fields that are not None. Appends fieldUpdates.<key> timestamp
    entries for tracked fields, and always appends updatedAt.

    Wire-format conventions enforced here:
    - timeEstimate: input is minutes; stored as milliseconds (×60 000).
    - isStarred / isFrogged: input is bool; stored as tier number (True → 1,
      False → null). Marvin uses 1/2/3 for tier levels and null for cleared.
      To set a specific tier, use update_document with an explicit setter.
    - parentId: caller-supplied. Conventions: "unassigned" = inbox,
      "root" = top-level, null = same as root, or a category/project _id.

    Timestamps are in milliseconds since epoch (UTC).
    """
    now_ms = int(time.time() * 1000)
    setters: list[dict] = []

    for model_field, marvin_key in _FIELD_MAP.items():
        value = getattr(update, model_field)
        if value is None:
            continue
        if model_field == "time_estimate":
            value = value * 60 * 1000
        elif model_field in ("is_starred", "is_frogged"):
            value = 1 if value else None
        setters.append({"key": marvin_key, "val": value})
        if marvin_key in _TRACKED_FIELDS:
            setters.append({"key": f"fieldUpdates.{marvin_key}", "val": now_ms})

    setters.append({"key": "updatedAt", "val": now_ms})
    return setters
