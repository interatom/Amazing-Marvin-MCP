"""Orchestration for query_docs — label resolution, XOR validation, response shaping.

Kept separate from main.py to keep tool registration thin and to allow direct
testing of the logic without the FastMCP decorator.
"""

import logging
import time
from typing import Any, Literal

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

logger = logging.getLogger(__name__)

_ENDPOINT = "CouchDB _find"


def _resolve_label_names(
    names: list[str],
    all_labels: list[dict],
) -> tuple[list[str], list[str]]:
    """Case-insensitive name → ID resolution. Returns (resolved_ids, unknown_names)."""
    name_to_id = {lbl.get("title", "").lower(): lbl.get("_id") for lbl in all_labels}
    resolved, unknown = [], []
    for name in names:
        lid = name_to_id.get(name.lower())
        if lid:
            resolved.append(lid)
        else:
            unknown.append(name)
    return resolved, unknown


def _validation_error(msg: str, debug: bool, start_time: float) -> StandardResponse:
    response_time = int((time.time() - start_time) * 1000)
    return StandardResponse(
        data=[],
        metadata=ResponseMetadata(count=0, source=_ENDPOINT, data_freshness="unavailable"),
        summary=ResponseSummary(text=msg, status="error", action_completed="validation_failed"),
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
        ) if debug else None,
        success=False,
    )


def _empty_result(
    summary: str,
    debug: bool,
    start_time: float,
    api_calls: int = 0,
) -> StandardResponse:
    response_time = int((time.time() - start_time) * 1000)
    return StandardResponse(
        data={"docs": [], "count": 0},
        metadata=ResponseMetadata(count=0, source=_ENDPOINT, data_freshness="real_time"),
        summary=ResponseSummary(text=summary, status="success", action_completed="docs_queried"),
        debug=ResponseDebug(
            api_endpoint=_ENDPOINT,
            response_time_ms=response_time,
            api_calls_made=api_calls,
        ) if debug else None,
        success=True,
    )


async def execute_query_docs(
    api_client: MarvinAPIClient,
    doc_type: str,
    fields: list[str] | None,
    labels: list[str] | None,
    exclude_labels: list[str] | None,
    include_done: bool,
    include_deleted: bool,
    has_due_date: bool | None,
    has_note: bool | None,
    has_time_estimate: bool | None,
    has_scheduled_day: bool | None,
    contains: str | None,
    due: str | None,
    due_before: str | None,
    due_after: str | None,
    scheduled: str | None,
    scheduled_before: str | None,
    scheduled_after: str | None,
    done_after: str | None,
    done_before: str | None,
    parent_id: str | None,
    project_type: Literal["project", "category"] | None,
    is_starred: bool | None,
    is_frogged: bool | None,
    priority: Literal["low", "mid", "high"] | None,
    sort_by: str | None,
    sort_desc: bool,
    limit: int,
    bookmark: str | None,
    debug: bool,
) -> StandardResponse:
    start_time = time.time()

    try:
        # ── Validation ──────────────────────────────────────────────────────────
        if doc_type not in VALID_DOC_TYPES:
            return _validation_error(
                f"Unknown doc_type {doc_type!r}. Valid types: {sorted(VALID_DOC_TYPES)}.",
                debug,
                start_time,
            )

        if due and (due_before or due_after):
            return _validation_error(
                "Use either `due` for an exact date, or `due_before`/`due_after` "
                "for a range, not both.",
                debug,
                start_time,
            )

        if scheduled and (scheduled_before or scheduled_after):
            return _validation_error(
                "Use either `scheduled` for an exact date, or "
                "`scheduled_before`/`scheduled_after` for a range, not both.",
                debug,
                start_time,
            )

        # ── Label resolution ────────────────────────────────────────────────────
        label_ids: list[str] | None = None
        exclude_label_ids: list[str] | None = None
        rest_calls = 0

        if labels or exclude_labels:
            all_labels = api_client.get_labels()
            rest_calls += 1

            if labels:
                resolved, unknown = _resolve_label_names(labels, all_labels)
                if unknown:
                    known = sorted(lbl.get("title", "") for lbl in all_labels)
                    return _empty_result(
                        f"No label matching {unknown!r}. "
                        f"Available labels: {known} (from /labels). "
                        "Tip: label names are case-insensitive.",
                        debug,
                        start_time,
                        api_calls=rest_calls,
                    )
                label_ids = resolved

            if exclude_labels:
                resolved_ex, unknown_ex = _resolve_label_names(exclude_labels, all_labels)
                if unknown_ex:
                    known = sorted(lbl.get("title", "") for lbl in all_labels)
                    return _empty_result(
                        f"No label matching {unknown_ex!r} in exclude_labels. "
                        f"Available labels: {known}. "
                        "Tip: label names are case-insensitive.",
                        debug,
                        start_time,
                        api_calls=rest_calls,
                    )
                exclude_label_ids = resolved_ex

        # ── Build selector (raises ValueError for per-doc_type violations) ──────
        selector = build_selector(
            doc_type,
            label_ids=label_ids,
            exclude_label_ids=exclude_label_ids,
            include_done=include_done,
            include_deleted=include_deleted,
            has_due_date=has_due_date,
            has_note=has_note,
            has_time_estimate=has_time_estimate,
            has_scheduled_day=has_scheduled_day,
            contains=contains,
            due=due,
            due_before=due_before,
            due_after=due_after,
            scheduled=scheduled,
            scheduled_before=scheduled_before,
            scheduled_after=scheduled_after,
            done_after=done_after,
            done_before=done_before,
            parent_id=parent_id,
            project_type=project_type,
            is_starred=is_starred,
            is_frogged=is_frogged,
            priority=priority,
        )

        # ── CouchDB query ────────────────────────────────────────────────────────
        sort = [{sort_by: "desc" if sort_desc else "asc"}] if sort_by else None
        envelope = api_client.find_docs(
            selector=selector,
            fields=fields,
            limit=limit,
            sort=sort,
            bookmark=bookmark,
        )

        docs: list[dict] = envelope.get("docs", [])
        raw_count = len(docs)
        result_bookmark: str | None = envelope.get("bookmark")

        # Tasks collection stores categories/projects too — post-filter them out
        if doc_type == "Tasks":
            docs = [d for d in docs if d.get("type") not in ("project", "category")]

        # ── Build response ───────────────────────────────────────────────────────
        response_data: dict[str, Any] = {"docs": docs, "count": len(docs)}
        if fields:
            response_data["fields_returned"] = sorted(set(fields) | {"_id"})
        if result_bookmark and raw_count == limit:
            response_data["bookmark"] = result_bookmark

        applied = [f"doc_type={doc_type!r}"]
        if labels:
            applied.append(f"labels={labels!r}")
        if exclude_labels:
            applied.append(f"exclude_labels={exclude_labels!r}")
        if include_done:
            applied.append("include_done=True")
        if include_deleted:
            applied.append("include_deleted=True")
        if has_due_date is not None:
            applied.append(f"has_due_date={has_due_date}")
        if contains:
            applied.append(f"contains={contains!r}")
        if parent_id:
            applied.append(f"parent_id={parent_id!r}")

        summary_text = f"CouchDB _find returned {len(docs)} {doc_type} doc(s)"
        if len(applied) > 1:
            summary_text += f" [{', '.join(applied[1:])}]"
        if result_bookmark and raw_count == limit:
            summary_text += " — pass bookmark to paginate"

        response_time = int((time.time() - start_time) * 1000)
        return StandardResponse(
            data=response_data,
            metadata=ResponseMetadata(
                count=len(docs),
                source=_ENDPOINT,
                data_freshness="real_time",
                filters_applied=applied,
            ),
            summary=ResponseSummary(
                text=summary_text, status="success", action_completed="docs_queried"
            ),
            debug=ResponseDebug(
                api_endpoint=_ENDPOINT,
                response_time_ms=response_time,
                api_calls_made=rest_calls + 1,
            ) if debug else None,
            success=True,
        )

    except ValueError as exc:
        return _validation_error(str(exc), debug, start_time)

    except Exception:
        logger.exception("query_docs failed")
        response_time = int((time.time() - start_time) * 1000)
        return StandardResponse(
            data=[],
            metadata=ResponseMetadata(
                count=0, source=_ENDPOINT, data_freshness="unavailable"
            ),
            summary=ResponseSummary(
                text="CouchDB query failed — check credentials and network.",
                status="error",
                action_completed="query_failed",
            ),
            debug=ResponseDebug(
                api_endpoint=_ENDPOINT,
                response_time_ms=response_time,
                api_calls_made=0,
            ) if debug else None,
            success=False,
        )
