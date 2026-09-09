"""Pydantic request models for Amazing Marvin MCP operations."""

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from .doc_ids import new_document_id


class TaskUpdateRequest(BaseModel):
    """Friendly task update — converted to Marvin setters format internally.

    Pass only the fields you want to change; omitted fields (None) are left untouched.

    Limitation: None means "leave unchanged", so there is currently no way to clear a field
    (e.g. remove a due date) via this model. Use update_document with explicit setters instead.
    """

    item_id: str
    title: str | None = None
    due_date: str | None = Field(default=None, description="YYYY-MM-DD")
    scheduled_date: str | None = Field(
        default=None, description="YYYY-MM-DD (maps to 'day' in Marvin)"
    )
    note: str | None = None
    label_ids: list[str] | None = None
    priority: str | None = None
    parent_id: str | None = None
    is_starred: bool | None = None
    is_frogged: bool | None = None
    time_estimate: int | None = Field(default=None, description="Time estimate in minutes")
    backburner: bool | None = None


class GoalCreateRequest(BaseModel):
    """Input for create_goal — mirrors the field set Marvin writes for a new goal.

    Goals are created in one of two states: 'pending' (started, ready to be
    worked out) or 'backburner'. The remaining lifecycle states ('active' once
    the goal worksheet is filled in, 'done' on completion) are reached by
    updating the goal, not by creating it.
    """

    title: str = Field(..., min_length=1, description="Goal name")
    has_end: bool = Field(
        ...,
        description="True for a goal with a target date, False for an ongoing one. "
        "Required — Marvin refuses to create a goal without this answer.",
    )
    due_date: str | None = Field(
        default=None,
        description="Target date YYYY-MM-DD. Ignored (stored as null) when has_end is False.",
    )
    note: str | None = Field(default=None, description="Markdown note")
    label_ids: list[str] = Field(default_factory=list, description="Label IDs to attach")
    parent_id: str = Field(
        default="unassigned", description="Owning category ID, or 'unassigned'"
    )
    is_starred: int = Field(default=0, description="Priority tier: 0, 1, 2 or 3")
    hide_in_day_view: bool = Field(
        default=False, description="Keep the goal out of the day view"
    )
    status: Literal["pending", "backburner"] = Field(
        default="pending", description="Initial state of the goal"
    )
    sections: list[dict[str, Any]] | None = Field(
        default=None,
        description="Goal Phases, each {_id, title}. Defaults to a single empty phase.",
    )

    def to_document(self) -> dict[str, Any]:
        """Build the document to send to /doc/create.

        The endpoint stores verbatim, so every field Marvin's own client would
        set is filled in here — including the _id, the creation timestamp and
        the empty per-field update map used for conflict resolution.
        """
        return {
            "_id": new_document_id(),
            "db": "Goals",
            "title": self.title,
            "hasEnd": self.has_end,
            "dueDate": self.due_date if self.has_end else None,
            "note": self.note or "",
            "labelIds": list(self.label_ids),
            "parentId": self.parent_id,
            "isStarred": self.is_starred,
            "hideInDayView": self.hide_in_day_view,
            "status": self.status,
            "sections": (
                self.sections
                if self.sections is not None
                else [{"_id": "d", "title": ""}]
            ),
            "createdAt": int(time.time() * 1000),
            "fieldUpdates": {},
        }
