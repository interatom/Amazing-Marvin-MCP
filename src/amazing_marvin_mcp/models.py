"""Pydantic request models for Amazing Marvin MCP operations."""

import time
from datetime import date
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
    """Input for create_goal — mirrors the field set Marvin writes for a new goal.

    Goals are created in one of two states: 'pending' (started, ready to be
    worked out) or 'backburner'. The remaining lifecycle states ('active' once
    the goal worksheet is filled in, 'done' on completion) are reached by
    updating the goal, not by creating it.
    """

    title: str = Field(..., min_length=1, description="Goal name")
    has_end: bool = Field(
        ...,
        description="True for a goal with a target date, False for an ongoing one. "
        "Required — Marvin refuses to create a goal without this answer.",
    )
    due_date: str | None = Field(
        default=None,
        description="Target date YYYY-MM-DD. Ignored (stored as null) when has_end is False.",
    )
    note: str | None = Field(default=None, description="Markdown note")
    label_ids: list[str] = Field(
        default_factory=list, description="Label IDs to attach"
    )
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
        set is filled in here — including the _id, the creation timestamp and
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


RECURRENCE_TYPES = (
    "daily",
    "repeat week",
    "n per week",
    "monthly",
    "repeat month",
    "repeat year",
    "echo",
    "custom",
)


class RecurringTaskCreateRequest(BaseModel):
    """Input for create_recurring_task — a template, not an occurrence.

    Marvin's client generates the occurrences from this document; never build
    one by hand, their IDs are derived from the template and would collide.

    Only 'project' templates are supported for now. They generate a project
    Categories document whose children come from 'descendants'.
    """

    title: str = Field(..., min_length=1, description="Template title")
    type: Literal[RECURRENCE_TYPES] = Field(  # type: ignore[valid-type]
        ..., description="Recurrence pattern"
    )
    repeat_start: str = Field(
        ...,
        description="Anchor date YYYY-MM-DD. Occurrences are computed from this "
        "anchor; it is not advanced as they are generated.",
    )
    recurring_type: Literal["project"] = Field(
        default="project", description="Only 'project' templates are supported"
    )
    repeat: int = Field(default=1, ge=1, description="Interval, e.g. 2 = every second")
    parent_id: str | None = Field(default=None, description="Owning category ID")
    note: str | None = Field(default=None, description="Markdown note")
    label_ids: list[str] = Field(default_factory=list)
    time_estimate: int | None = Field(
        default=None, description="Time estimate in milliseconds"
    )
    due_in: int | None = Field(
        default=None, description="Days from each occurrence to its due date"
    )
    start_in: int | None = Field(default=None, description="Days offset for startDate")
    end_in: int | None = Field(default=None, description="Days offset for endDate")
    end_date: str | None = Field(
        default=None, description="YYYY-MM-DD after which nothing is generated"
    )
    task_time: str | None = Field(default=None, description="HH:MM on occurrences")
    reminder_offset: int | None = Field(default=None)
    limit_to_weekdays: bool = Field(default=False, description="Skip weekends")
    echo_days: int = Field(default=1, description="Only used by type='echo'")
    on_count: int = Field(default=7, description="Only used by on/off patterns")
    off_count: int = Field(default=7, description="Only used by on/off patterns")
    custom_recurrence: str = Field(
        default="", description="Expression for type='custom'"
    )
    is_starred: int = Field(default=0, description="Priority tier 0-3")
    is_frogged: int = Field(default=0, description="Frog tier 0-3")
    is_urgent: bool = Field(default=False)
    is_reward: bool = Field(default=False)
    reward_points: int = Field(default=0)
    backburner: bool = Field(default=False)
    descendants: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Template children, each a Tasks-shaped dict. Every generated "
        "occurrence receives a copy.",
    )

    def _anchor(self) -> date:
        return date.fromisoformat(self.repeat_start)

    def to_document(self) -> dict[str, Any]:
        """Build the document to send to /doc/create.

        The calendar fields are derived from repeat_start rather than taken
        from the caller, so they cannot contradict the anchor.
        """
        anchor = self._anchor()
        weekday = anchor.isoweekday() % 7  # Marvin counts Sunday as 0

        return {
            "_id": new_document_id(),
            "db": "RecurringTasks",
            "recurringType": self.recurring_type,
            "title": self.title,
            "type": self.type,
            "repeat": self.repeat,
            "repeatStart": self.repeat_start,
            "day": weekday,
            "date": anchor.day,
            "weekDays": [weekday],
            "echoDays": self.echo_days,
            "onCount": self.on_count,
            "offCount": self.off_count,
            "customRecurrence": self.custom_recurrence,
            "limitToWeekdays": self.limit_to_weekdays,
            "startIn": self.start_in,
            "dueIn": self.due_in,
            "endIn": self.end_in,
            "endDate": self.end_date,
            "taskTime": self.task_time,
            "reminderOffset": self.reminder_offset,
            "sectionId": None,
            "parentId": self.parent_id or "unassigned",
            "note": self.note or "",
            "labelIds": list(self.label_ids),
            "timeEstimate": self.time_estimate or 0,
            "isStarred": self.is_starred,
            "isFrogged": self.is_frogged,
            "isUrgent": self.is_urgent,
            "isReward": self.is_reward,
            "rewardPoints": self.reward_points,
            "backburner": self.backburner,
            "descendants": list(self.descendants),
            "createdAt": int(time.time() * 1000),
            "fieldUpdates": {},
        }
