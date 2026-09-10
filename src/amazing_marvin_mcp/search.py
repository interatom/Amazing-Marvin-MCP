"""Orchestration for search_docs — Mango pre-filter, subtask scan, full matcher.

Kept separate from main.py so tests can exercise the pipeline directly with a
mocked MarvinAPIClient, without requiring CouchDB env vars at import time.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from .api import MarvinAPIClient
from .db_filters import build_selector
from .doc_types import VALID_DOC_TYPES
from .response_models import (
    ErrorDetails,
    ResponseDebug,
    ResponseMetadata,
    ResponseSummary,
    StandardResponse,
)
from .search_matcher import longest_token, matches as _query_matches

logger = logging.getLogger(__name__)

_ENDPOINT = "CouchDB _find"


def _validation_error(msg: str, start_time: float) -> StandardResponse:
    response_time = int((time.time() - start_time) * 1000)
    return StandardResponse(
        data=[],
        metadata=ResponseMetadata(
            count=0, source=_ENDPOINT, data_freshness="unavailable"
        ),
        summary=ResponseSummary(
            text=msg, status="error", action_completed="validation_failed"
        ),
        debug=ResponseDebug(
            api_endpoint=_ENDPOINT,
            response_time_ms=response_time,
            api_calls_made=0,
            error=ErrorDetails(
                error_type="validation_error",
                message=msg,
                user_message=msg,
                retry_suggested=True,
            ),
        ),
        success=False,
    )


def _augment_with_text_filter(
    selector: dict, token: str, search_notes: bool
) -> dict:
    """Add a regex-on-title (and optionally note) clause to an existing selector."""
    escaped = re.escape(token)
    pattern = f"(?i){escaped}"
    text_filter: dict[str, Any]
    if search_notes:
        text_filter = {
            "$or": [
                {"title": {"$regex": pattern}},
                {"note": {"$regex": pattern}},
            ]
        }
    else:
        text_filter = {"title": {"$regex": pattern}}
    if "$and" in selector:
        selector["$and"].append(text_filter)
        return selector
    return {"$and": [selector, text_filter]}


def execute_search_docs(
    api_client: MarvinAPIClient,
    query: str,
    doc_types: list[str] | None = None,
    search_notes: bool = True,
    search_subtasks: bool = True,
    include_done: bool = False,
    include_deleted: bool = False,
    fields: list[str] | None = None,
    limit: int = 100,
) -> StandardResponse:
    """Run the search pipeline: Mango pre-filter, subtask scan, full matcher."""
    start_time = time.time()

    if not query or not query.strip():
        return _validation_error("query is required and must be non-empty", start_time)

    doc_types = list(doc_types) if doc_types else ["Tasks", "Categories"]
    for dt in doc_types:
        if dt not in VALID_DOC_TYPES:
            return _validation_error(
                f"Unknown doc_type {dt!r}; valid: {sorted(VALID_DOC_TYPES)}",
                start_time,
            )

    limit = max(1, min(500, limit))

    fetch_fields: set[str] = set(fields or [])
    fetch_fields.update({"_id", "db", "title", "updatedAt", "createdAt"})
    if search_notes:
        fetch_fields.add("note")
    if search_subtasks and "Tasks" in doc_types:
        fetch_fields.add("subtasks")
    fetch_fields_list = sorted(fetch_fields)

    prefilter = longest_token(query)
    api_calls = 0
    candidates: dict[str, dict] = {}

    for dt in doc_types:
        base = build_selector(
            dt,
            include_done=include_done,
            include_deleted=include_deleted,
        )
        selector = (
            _augment_with_text_filter(base, prefilter, search_notes)
            if prefilter
            else base
        )
        response = api_client.find_docs(
            selector, fields=fetch_fields_list, limit=limit * 3
        )
        api_calls += 1
        for d in response.get("docs", []):
            candidates[d["_id"]] = d

    if search_subtasks and "Tasks" in doc_types:
        subtask_base = build_selector(
            "Tasks",
            include_done=include_done,
            include_deleted=include_deleted,
        )
        subtask_filter = {"subtasks": {"$exists": True}}
        if "$and" in subtask_base:
            subtask_base["$and"].append(subtask_filter)
            subtask_selector = subtask_base
        else:
            subtask_selector = {"$and": [subtask_base, subtask_filter]}
        response = api_client.find_docs(
            subtask_selector, fields=fetch_fields_list, limit=500
        )
        api_calls += 1
        for d in response.get("docs", []):
            candidates.setdefault(d["_id"], d)

    matched: list[dict] = []
    for d in candidates.values():
        haystacks: list[str | None] = [d.get("title")]
        if search_notes:
            haystacks.append(d.get("note"))
        if search_subtasks and d.get("db") == "Tasks":
            subtasks = d.get("subtasks") or {}
            if isinstance(subtasks, dict):
                for st in subtasks.values():
                    if isinstance(st, dict):
                        haystacks.append(st.get("title"))
        if _query_matches(query, haystacks):
            matched.append(d)

    matched.sort(key=lambda d: -(d.get("updatedAt") or d.get("createdAt") or 0))
    matched = matched[:limit]

    if fields is not None:
        keep = set(fields) | {"_id", "db"}
        matched = [{k: v for k, v in d.items() if k in keep} for d in matched]

    response_time = int((time.time() - start_time) * 1000)
    return StandardResponse(
        data={"docs": matched, "count": len(matched)},
        metadata=ResponseMetadata(
            count=len(matched), source=_ENDPOINT, data_freshness="real_time"
        ),
        summary=ResponseSummary(
            text=(
                f"Found {len(matched)} match(es) for {query!r} "
                f"across {doc_types} ({api_calls} CouchDB calls)"
            ),
            status="success",
            action_completed="docs_searched",
        ),
        debug=ResponseDebug(
            api_endpoint=_ENDPOINT,
            response_time_ms=response_time,
            api_calls_made=api_calls,
        ),
        success=True,
    )
