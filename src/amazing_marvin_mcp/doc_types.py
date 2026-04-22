"""CouchDB doc-type schemas for Amazing Marvin.

Transcribed from https://github.com/amazingmarvin/MarvinAPI/wiki/Marvin-Data-Types.
Used by describe_doc_type (discoverability) and the query_docs validation layer.
"""

from typing import Literal

DocType = Literal[
    "Tasks", "Categories", "Labels", "LabelGroups", "Habits", "Goals",
    "Trackers", "Rewards", "Events", "PlannerItems", "Calendars",
    "RecurringTasks", "SavedItems", "ProfileItems",
]

DOC_TYPE_SCHEMAS: dict[str, dict] = {
    "Tasks": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Tasks')",
            "title": "string",
            "done": "boolean",
            "doneAt": "number (epoch ms)",
            "dueDate": "string (YYYY-MM-DD)",
            "day": "string (YYYY-MM-DD or 'unassigned')",
            "isStarred": "boolean | number (1/2/3 for priority tiers)",
            "isFrogged": "boolean | number (1/2/3 for frog tiers)",
            "labelIds": "array of string (label IDs)",
            "parentId": "string (parent category/project ID; absent = inbox)",
            "timeEstimate": "number (milliseconds)",
            "note": "string (markdown)",
            "backburner": "boolean",
            "fieldUpdates": "object (timestamps of last field changes, epoch ms per field)",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
            "createdAt": "number (epoch ms)",
            "updatedAt": "number (epoch ms)",
        },
        "applicable_filters": [
            "labels", "exclude_labels",
            "include_done", "include_deleted",
            "has_due_date", "has_note", "has_time_estimate", "has_scheduled_day",
            "due", "due_before", "due_after",
            "scheduled", "scheduled_before", "scheduled_after",
            "done_after", "done_before",
            "parent_id", "is_starred", "is_frogged", "contains",
        ],
        "not_applicable": [
            "priority (Categories/projects only)",
            "project_type (Categories only)",
        ],
        "gotchas": [
            "isStarred stored as boolean OR number 1/2/3 (priority tiers); "
            "is_starred=True matches any truthy value",
            "isFrogged stored as boolean OR number 1/2/3 (frog tiers); "
            "is_frogged=True matches any truthy value",
            "day field can be the string 'unassigned', not null",
            "Subtasks are embedded in the parent Task's 'subtasks' object, not separate docs",
            "Recurring task instances are separate from their RecurringTasks templates",
            "done=true tasks excluded by default — use include_done=True to include them",
            "deletedAt docs excluded by default — use include_deleted=True to include them",
        ],
        "examples": [
            'query_docs(doc_type="Tasks", parent_id="unassigned")  # inbox tasks',
            'query_docs(doc_type="Tasks", has_due_date=True, has_time_estimate=False)  # triage',
            'query_docs(doc_type="Tasks", labels=["urgent"], exclude_labels=["waiting"])',
        ],
    },
    "Categories": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Categories')",
            "title": "string",
            "type": "string ('project' for projects; absent or other value for categories)",
            "note": "string (markdown — NOT returned by the REST /categories endpoint)",
            "parentId": "string",
            "labelIds": "array of string",
            "priority": "string ('low', 'mid', 'high')",
            "done": "boolean",
            "doneDate": "string (YYYY-MM-DD)",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
            "createdAt": "number (epoch ms)",
            "updatedAt": "number (epoch ms)",
        },
        "applicable_filters": [
            "labels", "exclude_labels",
            "include_done", "include_deleted",
            "has_note", "done_after", "done_before",
            "parent_id", "project_type", "priority", "contains",
        ],
        "not_applicable": [
            "is_frogged (Tasks only)",
            "is_starred (Tasks only)",
            "has_due_date (Tasks only)",
            "has_time_estimate (Tasks only)",
            "has_scheduled_day (Tasks only)",
            "due/due_before/due_after (Tasks only)",
            "scheduled/scheduled_before/scheduled_after (Tasks only)",
        ],
        "gotchas": [
            "REST /categories strips the 'note' field; use query_docs to retrieve it",
            "Projects are stored in the same Categories collection as plain categories",
            "Use project_type='project' to return projects only",
            "doneDate is a string (YYYY-MM-DD), unlike Tasks which use epoch ms doneAt",
        ],
        "examples": [
            'query_docs(doc_type="Categories", fields=["_id","title","note"])  # all category notes',
            'query_docs(doc_type="Categories", project_type="project")  # projects only',
            'query_docs(doc_type="Categories", priority="high")  # high-priority categories',
        ],
    },
    "Labels": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Labels')",
            "title": "string",
            "color": "string (hex color)",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
        },
        "applicable_filters": ["include_deleted", "contains"],
        "not_applicable": [
            "labels", "exclude_labels", "include_done",
            "has_due_date", "has_note", "has_time_estimate", "has_scheduled_day",
            "due", "scheduled", "done_after", "done_before",
            "parent_id", "project_type", "is_starred", "is_frogged", "priority",
        ],
        "gotchas": [
            "Label IDs (not names) are stored in the labelIds array on tasks/categories",
        ],
        "examples": ['query_docs(doc_type="Labels")  # all labels'],
    },
    "LabelGroups": {
        "fields": {
            "_id": "string",
            "db": "string (always 'LabelGroups')",
            "title": "string",
            "labelIds": "array of string",
        },
        "applicable_filters": ["include_deleted", "contains"],
        "not_applicable": [],
        "gotchas": [],
        "examples": ['query_docs(doc_type="LabelGroups")  # all label groups'],
    },
    "Habits": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Habits')",
            "title": "string",
            "note": "string",
            "labelIds": "array of string",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
        },
        "applicable_filters": ["labels", "exclude_labels", "include_deleted", "has_note", "contains"],
        "not_applicable": [
            "include_done", "has_due_date", "has_time_estimate", "has_scheduled_day",
            "due", "scheduled", "done_after", "done_before",
            "parent_id", "project_type", "is_starred", "is_frogged", "priority",
        ],
        "gotchas": [],
        "examples": ['query_docs(doc_type="Habits")  # all habits'],
    },
    "Goals": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Goals')",
            "title": "string",
            "note": "string",
            "labelIds": "array of string",
            "done": "boolean",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
        },
        "applicable_filters": [
            "labels", "exclude_labels", "include_done", "include_deleted",
            "has_note", "contains",
        ],
        "not_applicable": [
            "has_due_date", "has_time_estimate", "has_scheduled_day",
            "due", "scheduled", "done_after", "done_before",
            "parent_id", "project_type", "is_starred", "is_frogged", "priority",
        ],
        "gotchas": [],
        "examples": ['query_docs(doc_type="Goals")  # all goals'],
    },
    "Trackers": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Trackers')",
            "title": "string",
            "note": "string",
        },
        "applicable_filters": ["include_deleted", "has_note", "contains"],
        "not_applicable": [],
        "gotchas": [],
        "examples": ['query_docs(doc_type="Trackers")  # all trackers'],
    },
    "Rewards": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Rewards')",
            "title": "string",
            "note": "string",
            "points": "number",
        },
        "applicable_filters": ["include_deleted", "has_note", "contains"],
        "not_applicable": [],
        "gotchas": [],
        "examples": ['query_docs(doc_type="Rewards")  # all rewards'],
    },
    "Events": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Events')",
            "title": "string",
            "start": "string (ISO 8601 datetime)",
            "end": "string (ISO 8601 datetime)",
            "note": "string",
            "labelIds": "array of string",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
        },
        "applicable_filters": ["labels", "exclude_labels", "include_deleted", "has_note", "contains"],
        "not_applicable": [
            "include_done", "has_due_date", "has_time_estimate", "has_scheduled_day",
            "due", "scheduled", "done_after", "done_before",
            "parent_id", "project_type", "is_starred", "is_frogged", "priority",
        ],
        "gotchas": [],
        "examples": ['query_docs(doc_type="Events")  # all events'],
    },
    "PlannerItems": {
        "fields": {
            "_id": "string",
            "db": "string (always 'PlannerItems')",
            "title": "string",
            "day": "string (YYYY-MM-DD)",
        },
        "applicable_filters": [
            "include_deleted",
            "scheduled", "scheduled_before", "scheduled_after",
            "contains",
        ],
        "not_applicable": [],
        "gotchas": [],
        "examples": ['query_docs(doc_type="PlannerItems")  # all planner items'],
    },
    "Calendars": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Calendars')",
            "title": "string",
            "color": "string",
        },
        "applicable_filters": ["include_deleted", "contains"],
        "not_applicable": [],
        "gotchas": [],
        "examples": ['query_docs(doc_type="Calendars")  # all calendars'],
    },
    "RecurringTasks": {
        "fields": {
            "_id": "string",
            "db": "string (always 'RecurringTasks')",
            "title": "string",
            "note": "string",
            "labelIds": "array of string",
            "timeEstimate": "number (milliseconds)",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
        },
        "applicable_filters": [
            "labels", "exclude_labels", "include_deleted",
            "has_note", "has_time_estimate", "contains",
        ],
        "not_applicable": [
            "include_done", "has_due_date", "has_scheduled_day",
            "due", "scheduled", "done_after", "done_before",
            "parent_id", "project_type", "is_starred", "is_frogged", "priority",
        ],
        "gotchas": [
            "These are templates; each generates individual Task docs when triggered",
        ],
        "examples": ['query_docs(doc_type="RecurringTasks")  # all recurring task templates'],
    },
    "SavedItems": {
        "fields": {
            "_id": "string",
            "db": "string (always 'SavedItems')",
            "title": "string",
        },
        "applicable_filters": ["include_deleted", "contains"],
        "not_applicable": [],
        "gotchas": [],
        "examples": ['query_docs(doc_type="SavedItems")  # all saved items'],
    },
    "ProfileItems": {
        "fields": {
            "_id": "string",
            "db": "string (always 'ProfileItems')",
            "title": "string",
        },
        "applicable_filters": ["include_deleted", "contains"],
        "not_applicable": [],
        "gotchas": [],
        "examples": ['query_docs(doc_type="ProfileItems")  # all profile items'],
    },
}

VALID_DOC_TYPES: frozenset[str] = frozenset(DOC_TYPE_SCHEMAS.keys())
