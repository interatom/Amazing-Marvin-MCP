"""Pure-Python Mango selector builder for Amazing Marvin CouchDB queries.

No I/O — fully unit-testable without network access.
"""

import re
from datetime import datetime, timedelta, timezone


def _date_to_epoch_ms_start(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _date_to_epoch_ms_end(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int((dt + timedelta(days=1)).timestamp() * 1000) - 1


def _truthy_flag(field: str) -> dict:
    return {field: {"$in": [True, 1, 2, 3]}}


def _falsy_flag(field: str) -> dict:
    return {"$or": [{field: {"$exists": False}}, {field: {"$in": [False, 0, None]}}]}


def not_equal_or_missing(field: str, value: object) -> dict:
    """Mango selector matching docs where ``field`` is missing or != ``value``.

    Plain ``{"field": {"$ne": value}}`` excludes docs without the field — a
    CouchDB Mango quirk. This helper wraps the field-absent case explicitly,
    so docs with no ``field`` at all (e.g. an imported Task with no ``done``
    flag) are treated as "not equal to value".
    """
    return {"$or": [{field: {"$exists": False}}, {field: {"$ne": value}}]}


def _exists_nonempty(field: str, extra_empty: list | None = None) -> dict:
    nin = [None, ""]
    if extra_empty:
        nin.extend(extra_empty)
    return {field: {"$exists": True, "$nin": nin}}


def _absent_or_empty(field: str, extra_empty: list | None = None) -> dict:
    empties = [None, ""]
    if extra_empty:
        empties.extend(extra_empty)
    return {"$or": [{field: {"$exists": False}}, {field: {"$in": empties}}]}


_TASKS_OR_CATEGORIES_PARAMS = {"is_frogged", "is_starred"}
_CATEGORIES_ONLY_PARAMS = {"priority", "project_type"}


def build_selector(doc_type: str, **filters) -> dict:
    """Build a Mango _find selector for the given doc_type and filter kwargs.

    All kwargs are optional — supply only what you need. Fragments are combined
    with $and. Raises ValueError for per-doc_type violations (e.g. priority on
    Tasks, is_frogged on Habits).

    Args:
        doc_type: CouchDB collection name (e.g. "Tasks", "Categories").
        label_ids: Resolved label IDs for any-of matching.
        exclude_label_ids: Resolved label IDs to exclude.
        include_done: Include done=true docs (default False).
        include_deleted: Include soft-deleted docs (default False).
        has_due_date, has_note, has_time_estimate, has_scheduled_day: bool | None
        due, due_before, due_after: YYYY-MM-DD exact or range on dueDate.
        scheduled, scheduled_before, scheduled_after: same on day field.
        done_after, done_before: YYYY-MM-DD; Tasks use epoch-ms doneAt, others use doneDate string.
        parent_id: parentId equality (str).
        project_type: 'project' | 'category' — Categories only.
        is_starred, is_frogged: bool | None — Tasks and Categories (projects can
            be starred/frogged with the same 1/2/3 tier semantics as tasks).
        priority: 'low' | 'mid' | 'high' — Categories only.
        contains: case-insensitive regex OR-matched across title and note.
    """
    for param in _TASKS_OR_CATEGORIES_PARAMS:
        if filters.get(param) is not None and doc_type not in ("Tasks", "Categories"):
            raise ValueError(
                f"{param!r} is a Tasks/Categories-only filter and cannot be used with "
                f"doc_type={doc_type!r}."
            )
    for param in _CATEGORIES_ONLY_PARAMS:
        if filters.get(param) is not None and doc_type != "Categories":
            suffix = " For tasks, use is_starred instead." if param == "priority" else ""
            raise ValueError(
                f"{param!r} is a Categories-only filter and cannot be used with "
                f"doc_type={doc_type!r}.{suffix}"
            )

    frags: list[dict] = [{"db": doc_type}]

    # Soft-delete exclusion (default: off)
    if not filters.get("include_deleted", False):
        frags.append({"deletedAt": {"$exists": False}})

    # Completion exclusion — Tasks, Categories, and Goals carry the done field
    if doc_type in ("Tasks", "Categories", "Goals") and not filters.get("include_done", False):
        frags.append(not_equal_or_missing("done", True))

    # Label any-of (resolved IDs)
    label_ids = filters.get("label_ids")
    if label_ids:
        frags.append({"labelIds": {"$elemMatch": {"$in": label_ids}}})

    # Label exclusion (resolved IDs)
    exclude_label_ids = filters.get("exclude_label_ids")
    if exclude_label_ids:
        frags.append({"labelIds": {"$not": {"$elemMatch": {"$in": exclude_label_ids}}}})

    # has_due_date
    hdd = filters.get("has_due_date")
    if hdd is True:
        frags.append(_exists_nonempty("dueDate"))
    elif hdd is False:
        frags.append(_absent_or_empty("dueDate"))

    # has_note
    hn = filters.get("has_note")
    if hn is True:
        frags.append(_exists_nonempty("note"))
    elif hn is False:
        frags.append(_absent_or_empty("note"))

    # has_time_estimate
    hte = filters.get("has_time_estimate")
    if hte is True:
        frags.append(_exists_nonempty("timeEstimate"))
    elif hte is False:
        frags.append(_absent_or_empty("timeEstimate"))

    # has_scheduled_day (day field; "unassigned" counts as absent)
    hsd = filters.get("has_scheduled_day")
    if hsd is True:
        frags.append(_exists_nonempty("day", extra_empty=["unassigned"]))
    elif hsd is False:
        frags.append(_absent_or_empty("day", extra_empty=["unassigned"]))

    # due — exact or range
    due = filters.get("due")
    due_before = filters.get("due_before")
    due_after = filters.get("due_after")
    if due:
        frags.append({"dueDate": due})
    elif due_before or due_after:
        cond: dict = {}
        if due_after:
            cond["$gte"] = due_after
        if due_before:
            cond["$lte"] = due_before
        frags.append({"dueDate": cond})

    # scheduled / day field — exact or range
    scheduled = filters.get("scheduled")
    scheduled_before = filters.get("scheduled_before")
    scheduled_after = filters.get("scheduled_after")
    if scheduled:
        frags.append({"day": scheduled})
    elif scheduled_before or scheduled_after:
        cond = {}
        if scheduled_after:
            cond["$gte"] = scheduled_after
        if scheduled_before:
            cond["$lte"] = scheduled_before
        frags.append({"day": cond})

    # done_after / done_before
    done_after = filters.get("done_after")
    done_before = filters.get("done_before")
    if done_after or done_before:
        if doc_type == "Tasks":
            # doneAt is epoch milliseconds
            cond = {}
            if done_after:
                cond["$gte"] = _date_to_epoch_ms_start(done_after)
            if done_before:
                cond["$lte"] = _date_to_epoch_ms_end(done_before)
            frags.append({"doneAt": cond})
        else:
            # doneDate is a YYYY-MM-DD string
            cond = {}
            if done_after:
                cond["$gte"] = done_after
            if done_before:
                cond["$lte"] = done_before
            frags.append({"doneDate": cond})

    # parent_id
    parent_id = filters.get("parent_id")
    if parent_id is not None:
        frags.append({"parentId": parent_id})

    # project_type (Categories only — validated above)
    project_type = filters.get("project_type")
    if project_type == "project":
        frags.append({"type": "project"})
    elif project_type == "category":
        frags.append(not_equal_or_missing("type", "project"))

    # is_starred (Tasks only — validated above)
    is_starred = filters.get("is_starred")
    if is_starred is True:
        frags.append(_truthy_flag("isStarred"))
    elif is_starred is False:
        frags.append(_falsy_flag("isStarred"))

    # is_frogged (Tasks only — validated above)
    is_frogged = filters.get("is_frogged")
    if is_frogged is True:
        frags.append(_truthy_flag("isFrogged"))
    elif is_frogged is False:
        frags.append(_falsy_flag("isFrogged"))

    # priority (Categories only — validated above)
    priority = filters.get("priority")
    if priority is not None:
        frags.append({"priority": priority})

    # contains — case-insensitive regex OR across title and note
    contains = filters.get("contains")
    if contains is not None:
        escaped = re.escape(contains)
        frags.append({"$or": [
            {"title": {"$regex": f"(?i){escaped}"}},
            {"note": {"$regex": f"(?i){escaped}"}},
        ]})

    if len(frags) == 1:
        return frags[0]
    return {"$and": frags}
