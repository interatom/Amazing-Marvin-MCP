"""CouchDB doc-type schemas for Amazing Marvin.

Transcribed from https://github.com/amazingmarvin/MarvinAPI/wiki/Marvin-Data-Types.
Used by describe_doc_type (discoverability) and the query_docs validation layer.
"""

from typing import Literal

DocType = Literal[
    "Tasks", "Categories", "Labels", "LabelGroups", "Habits", "Goals",
    "Trackers", "Rewards", "Events", "PlannerItems", "Calendars",
    "RecurringTasks", "SavedItems", "ProfileItems", "SmartLists",
]

DOC_TYPE_SCHEMAS: dict[str, dict] = {
    "Tasks": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Tasks')",
            "title": "string",
            "note": "string (markdown)",
            "done": "boolean",
            "doneAt": "number (epoch ms when completed)",
            "workedOnAt": "number | null (epoch ms last time worked on or tracked)",
            "dueDate": "string (YYYY-MM-DD)",
            "day": "string (YYYY-MM-DD or 'unassigned')",
            "startDate": "string (YYYY-MM-DD) | null",
            "endDate": "string (YYYY-MM-DD) | null",
            "firstScheduled": "string (YYYY-MM-DD) | null (first time this task was scheduled — drives procrastination tracking)",
            "plannedWeek": "string (YYYY-MM-DD of ISO week start) | null",
            "plannedMonth": "string (YYYY-MM-DD of month start) | null",
            "isStarred": "boolean | number (1/2/3 for priority tiers; null/false when cleared)",
            "isFrogged": "boolean | number (1/2/3 for frog tiers; null/false when cleared)",
            "isPinned": "boolean (true when this task is the pinned-task parent in the Master List)",
            "isUrgent": "boolean",
            "isReward": "boolean (true when this is a reward task from the Reward Tasks strategy)",
            "labelIds": "array of string (label IDs)",
            "parentId": "string ('unassigned' = inbox; 'root', null, or absent = top-level; otherwise a Categories _id)",
            "timeEstimate": "number (milliseconds)",
            "backburner": "boolean",
            "recurring": "boolean (true when this task instance was generated from a RecurringTasks template)",
            "recurringTaskId": "string (when recurring=true, the _id of the source RecurringTasks template)",
            "subtasks": "object (embedded subtasks keyed by their _id — NOT separate documents)",
            "rank": "number (manual sort order in the Day/Week planner view)",
            "masterRank": "number (manual sort order among siblings in the Master List / category tree)",
            "rank_<smartListId>": "number (manual sort order within a specific SmartList; field name is per-list, e.g. 'rank_abc123')",
            "reminder": "object | null (reminder configuration when set)",
            "remindAt": "number | null (epoch ms when the reminder fires)",
            "sectionId": "string (planner / time-block section assignment; '' if unset)",
            "dailySection": "string (Daily Structure section assignment, e.g. 'morning', 'afternoon')",
            "bonusSection": "string (Bonus Structure section assignment)",
            "customSection": "string (custom section assignment)",
            "timeBlockSection": "string (time block section assignment)",
            "fieldUpdates": "object (per-field timestamps of last edit, epoch ms)",
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
            "parentId='unassigned' means inbox; parentId='root', null, or absent means top-level",
            "Sections are NOT a separate doc type. The DSL !SectionName "
            "predicate matches against dailySection / bonusSection / "
            "customSection (case-insensitive). 'sectionId' is a separate "
            "field used for planner/time-block section assignment, not the "
            "same thing. To filter by section in query_docs, fetch Tasks "
            "and post-filter on dailySection/bonusSection/customSection — "
            "or use the SmartLists 'advanced' DSL.",
            "Subtasks are embedded in the parent Task's 'subtasks' object, not separate docs",
            "Recurring task instances are separate from their RecurringTasks templates",
            "done=true tasks excluded by default — use include_done=True to include them",
            "deletedAt docs excluded by default — use include_deleted=True to include them",
            "Manual ordering is per-view, not a single field: masterRank orders "
            "siblings in the Master List / category tree, rank orders the Day/Week "
            "planner view, and rank_<smartListId> orders a specific SmartList. When "
            "a view's own rank field is absent/non-numeric, ordering falls back to "
            "masterRank, then rank, then the item's current list position. Ranks "
            "are fractional (a reorder sets a value between its neighbours), so they "
            "are floats, not contiguous integers. No reorder tool exists and "
            "update_task cannot set them — write rank/masterRank via update_document "
            "with explicit setters.",
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
            "parentId": "string ('root', null, or absent = top-level; otherwise another Categories _id)",
            "labelIds": "array of string",
            "priority": "string ('low', 'mid', 'high')",
            "color": "string (hex color, e.g. '#5b9dff')",
            "icon": "string (icon name)",
            "rank": "number (manual sort order in the Day/Week planner view)",
            "masterRank": "number (manual sort order among siblings in the Master List / category tree)",
            "done": "boolean",
            "doneDate": "string (YYYY-MM-DD)",
            "day": "string (YYYY-MM-DD or 'unassigned'; projects can be scheduled like tasks)",
            "dueDate": "string (YYYY-MM-DD; projects can have due dates)",
            "startDate": "string (YYYY-MM-DD) | null",
            "endDate": "string (YYYY-MM-DD) | null",
            "firstScheduled": "string (YYYY-MM-DD) | null",
            "plannedWeek": "string (YYYY-MM-DD of ISO week start) | null",
            "plannedMonth": "string (YYYY-MM-DD of month start) | null",
            "reviewDate": "string (YYYY-MM-DD) | null",
            "isStarred": "boolean | number (1/2/3 priority tiers; null/false when cleared; projects can be starred)",
            "isFrogged": "boolean | number (1/2/3 frog tiers; null/false when cleared; projects can be frogged)",
            "strategySettings": "object (per-project strategy overrides)",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
            "createdAt": "number (epoch ms)",
            "updatedAt": "number (epoch ms)",
        },
        "applicable_filters": [
            "labels", "exclude_labels",
            "include_done", "include_deleted",
            "has_note", "has_due_date", "has_time_estimate", "has_scheduled_day",
            "due", "due_before", "due_after",
            "scheduled", "scheduled_before", "scheduled_after",
            "done_after", "done_before",
            "parent_id", "project_type", "priority",
            "is_starred", "is_frogged", "contains",
        ],
        "not_applicable": [],
        "gotchas": [
            "REST /categories strips the 'note' field; use query_docs to retrieve it",
            "Projects are stored in the same Categories collection as plain categories",
            "Use project_type='project' to return projects only",
            "doneDate is a string (YYYY-MM-DD), unlike Tasks which use epoch ms doneAt",
            "Projects (type='project') carry day, dueDate, startDate, endDate, "
            "firstScheduled, plannedWeek, plannedMonth, isStarred, isFrogged with "
            "the same semantics as Tasks. Plain categories rarely populate these "
            "scheduling/priority fields, so filtering Categories by them mostly "
            "selects projects in practice.",
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
            "note": "string (markdown)",
            "color": "string (hex color; '' if unset)",
            "parentId": "string ('unassigned' = inbox; otherwise a Categories _id)",
            "labelIds": "array of string",
            "isStarred": "number (1/2/3 priority tier; 0 when cleared)",
            "isFrogged": "number (1/2/3 frog tier; 0 when cleared)",
            "timeEstimate": "number (milliseconds; 0 if unset)",
            "startDate": "string (YYYY-MM-DD; when habit tracking started)",
            "endDate": "string (YYYY-MM-DD) | null",
            "history": "array (chronological record of habit completions / values)",
            "units": "string ('times', 'minutes', etc.; what the target counts)",
            "period": "string ('day', 'week', etc.; how often the target should be met)",
            "target": "number (target count per period)",
            "isPositive": "boolean (true = build habit; false = avoid habit)",
            "recordType": "string ('boolean' for done/not done; 'number' for quantitative; ...)",
            "showInDayView": "boolean",
            "showInCalendar": "boolean",
            "askOn": "array of integers (days of week the habit prompts; 1=Mon..7=Sun)",
            "time": "string | null (HH:MM; preferred time of day)",
            "startTime": "string | null (HH:MM; window start for the habit)",
            "showAfterSuccess": "boolean (continue showing after target reached)",
            "showAfterRecord": "boolean (continue showing after recording)",
            "sendReminders": "boolean",
            "reminderTimes": "array | null (specific reminder times)",
            "reminderDays": "array | null (days reminders fire)",
            "reminderText": "string | null",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
            "createdAt": "number (epoch ms)",
            "updatedAt": "number (epoch ms)",
        },
        "applicable_filters": ["labels", "exclude_labels", "include_deleted", "has_note", "contains"],
        "not_applicable": [
            "include_done", "has_due_date", "has_time_estimate", "has_scheduled_day",
            "due", "scheduled", "done_after", "done_before",
            "parent_id", "project_type", "is_starred", "is_frogged", "priority",
        ],
        "gotchas": [
            "Habit completions are appended to the 'history' array; use the "
            "record_habit MCP tool rather than writing history entries directly.",
            "isStarred/isFrogged on habits use 0 (cleared) and 1/2/3 (tier) — "
            "no boolean form like Tasks/Categories may carry.",
            "askOn uses 1=Monday..7=Sunday integers (different from RecurringTasks' "
            "weekDays which uses 0=Sunday..6=Saturday).",
        ],
        "examples": [
            'query_docs(doc_type="Habits")  # all habits',
            'query_docs(doc_type="Habits", fields=["_id","title","target","period","units"])',
        ],
    },
    "Goals": {
        "fields": {
            "_id": "string",
            "db": "string (always 'Goals')",
            "title": "string",
            "note": "string (markdown)",
            "labelIds": "array of string",
            "done": "boolean",
            "hasEnd": "boolean (true if the goal has a target end date)",
            "status": "string (goal lifecycle: 'pending' = created and started, 'backburner' = parked, 'active' = worksheet filled in, 'done' = completed)",
            "sections": "array of {_id, title} (Goal Phases / milestones; the UI calls these 'sections' but they are unrelated to project sections)",
            "dueDate": "string (YYYY-MM-DD) | null (target date; null whenever hasEnd is false)",
            "parentId": "string ('unassigned' or a Categories _id)",
            "isStarred": "boolean | number (1/2/3 for priority tiers)",
            "hideInDayView": "boolean (keep the goal out of the day view)",
            "doneAt": "number | null (epoch ms when the goal was completed)",
            "startedAt": "number (epoch ms when the goal first became active)",
            "committed": "boolean (set from the goal worksheet; cleared when parked)",
            "difficulty": "string | null (goal worksheet)",
            "importance": "string | null (goal worksheet)",
            "motivations": "array (goal worksheet)",
            "challenges": "array (goal worksheet)",
            "color": "string (goal colour used by the goal SmartList)",
            "taskProgress": "boolean (count task completion towards progress)",
            "trackerProgress_<trackerId>": "value (per-tracker contribution to progress; field name is per-tracker)",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
            "createdAt": "number (epoch ms)",
            "updatedAt": "number (epoch ms)",
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
        "gotchas": [
            "Membership in a goal is recorded on tasks/categories via a "
            "'g_in_<goalId>: true' field on the member doc, NOT as a list on "
            "the goal itself. To find a goal's members, query tasks/categories "
            "where g_in_<goalId> is truthy, or use the SmartLists DSL "
            "predicates inGoal / *inGoal.",
            "A new goal starts as 'pending' or 'backburner' and carries "
            "hasEnd, dueDate, parentId, isStarred, hideInDayView, labelIds and "
            "one default phase in 'sections'. Older documents predate parts of "
            "that set, so treat every optional field as possibly absent. Use "
            "create_goal rather than writing a goal document by hand.",
            "The 'done' boolean is legacy: completion is recorded as "
            "status='done' plus doneAt, not by setting done=true.",
            "A goal's 'sections' array contains Goal Phases (the milestones "
            "shown in the goal overlay UI), each {_id, title}. These are "
            "NOT project sections / DSL !SectionName matches; that's a "
            "separate concept stored on Tasks via dailySection / "
            "bonusSection / customSection. Same field name, unrelated data.",
        ],
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
            "recurringType": "string ('task' = generates Tasks; 'project' = generates Categories with type='project')",
            "title": "string",
            "note": "string (markdown)",
            "labelIds": "array of string",
            "parentId": "string ('unassigned' or a Categories _id)",
            "timeEstimate": "number (milliseconds)",
            "type": "string (recurrence pattern: 'daily' | 'repeat week' | 'n per week' | 'monthly' | 'repeat month' | 'repeat year' | 'echo' | 'custom')",
            "day": "number | null (for some patterns: day-of-week index, Sunday=0)",
            "date": "number | null (for monthly patterns: day of month, 1-31)",
            "weekDays": "array of integers (for 'n per week': day-of-week indices, Sunday=0..Saturday=6)",
            "repeat": "number (interval, e.g. 2 = every 2 weeks)",
            "repeatStart": "string (YYYY-MM-DD; recurrence start date)",
            "endDate": "string (YYYY-MM-DD) | null",
            "echoDays": "number (for echo recurrences)",
            "onCount": "number (for 'n on / m off' patterns: 'on' duration in days)",
            "offCount": "number (for 'n on / m off' patterns: 'off' duration in days)",
            "customRecurrence": "string (custom recurrence expression for type='custom')",
            "limitToWeekdays": "boolean (skip weekends when generating instances)",
            "dueIn": "number (days offset from each generated schedule date for the dueDate)",
            "endIn": "number (days offset from schedule date for the endDate)",
            "startIn": "number (days offset for the startDate)",
            "subtaskList": "array (template subtasks; each generated Task instance receives copies)",
            "descendants": "array (recurringType='project' only: template descendant tasks/projects)",
            "sectionId": "string | null",
            "isStarred": "boolean | number (1/2/3 priority tier)",
            "isFrogged": "boolean | number (1/2/3 frog tier)",
            "isUrgent": "boolean",
            "isReward": "boolean",
            "backburner": "boolean",
            "rewardPoints": "number",
            "taskTime": "string | null (HH:MM; default time-of-day on generated instances)",
            "reminderOffset": "number | null (offset for auto-reminders on generated instances)",
            "dailySection": "string (Daily Structure section for generated instances)",
            "bonusSection": "string (Bonus Structure section for generated instances)",
            "customSection": "string (custom section for generated instances)",
            "timeBlockSection": "string (time block section for generated instances)",
            "priority": "string (priority carried to generated instances)",
            "mentalWeight": "number (carried to generated instances)",
            "positiveEnergy": "number (carried to generated instances)",
            "focusLevel": "number (carried to generated instances)",
            "energyAmount": "number (carried to generated instances)",
            "isPhysical": "boolean (carried to generated instances)",
            "orbit": "value (Orbit assignment carried to generated instances)",
            "textStyle": "value (text styling carried to generated instances)",
            "subtasks": "object (embedded subtasks carried to generated instances)",
            "masterRank": "number (manual sort order among templates)",
            "scheduleIn": "number | null (days offset for the scheduled day)",
            "autoPlan": "value (client-side planning behaviour; leave to the client)",
            "autoSnooze": "value (client-side snooze behaviour; leave to the client)",
            "snooze": "value (client-side snooze state; leave to the client)",
            "permaSnoozeTime": "value (client-side snooze state; leave to the client)",
            "deletedAt": "number (epoch ms, present only when soft-deleted)",
            "createdAt": "number (epoch ms)",
            "updatedAt": "number (epoch ms)",
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
            "These are templates; each generates individual Task or project "
            "Categories docs when triggered. Generated instances carry "
            "recurring=true and recurringTaskId pointing back here.",
            "weekDays uses Sunday=0..Saturday=6 indexing (different from Habits' "
            "askOn which uses 1=Mon..7=Sun).",
            "recurringType='project' templates also use 'descendants' to define "
            "template descendant tasks; recurringType='task' templates use "
            "'subtaskList' for embedded subtasks instead.",
            "'type' is the recurrence pattern, NOT the projects/categories type. "
            "Common values: 'daily', 'repeat week', 'n per week', 'monthly', "
            "'repeat month', 'repeat year', 'echo'.",
            "day / date / weekDays are derived from repeatStart, not independent "
            "settings — write them consistently with the anchor or let "
            "create_recurring_task derive them.",
            "autoPlan, autoSnooze, snooze, permaSnoozeTime and masterRank are set "
            "by the client from context an API caller does not have. Leave them "
            "alone unless mirroring an existing template.",
        ],
        "examples": [
            'query_docs(doc_type="RecurringTasks")  # all recurring task templates',
            'query_docs(doc_type="RecurringTasks", fields=["_id","title","type","repeat","repeatStart"])  # see recurrence rules',
        ],
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
        "gotchas": [
            "profile.strategySettings.plannerSmartLists holds the Planner view's "
            "pinned smart-list IDs (when configured). Smart-list definitions "
            "themselves live in the SmartLists collection — see "
            'describe_doc_type("SmartLists").',
            "Reminders are not a queryable doc type — they exist server-side only "
            "and are not stored in CouchDB.",
        ],
        "examples": ['query_docs(doc_type="ProfileItems")  # all profile items'],
    },
    "SmartLists": {
        "fields": {
            "_id": "string",
            "_rev": "string",
            "db": "string (always 'SmartLists')",
            "name": "string (display name; NOT called 'title')",
            "note": "string | null (markdown)",
            "groupBy": "string | null (e.g. 'mainCategoryId')",
            "oneRT": "boolean (one-recurring-task expansion flag)",
            "removeRedundancies": "boolean",
            "isPinned": "boolean (Planner pin state; presence varies)",
            "sort": "array",
            "limit": "integer (0 = unlimited observed)",
            "refill": "string ('auto' observed)",
            "createdAt": "number (epoch ms)",
            "updatedAt": "number (epoch ms)",
            "fieldUpdates": "object (per-field timestamps, epoch ms)",
            "itemType": "object {op, val} | null (filter clause; e.g. {'op':'task'})",
            "recurring": "object {op, val} | null",
            "parentId": "object {op, val} | null",
            "goalId": "object {op, val} | null",
            "title": "object {op, val} | null (filter on task title; not the SmartList's own name)",
            "hasTime": "object {op, val} | null",
            "created": "object {op, val} | null",
            "day": "object {op, val} | null",
            "dueDate": "object {op, val} | null",
            "endDate": "object {op, val} | null",
            "startDate": "object {op, val} | null",
            "pledgeDate": "object {op, val} | null",
            "firstScheduled": "object {op, val} | null",
            "procrastinationCount": "object {op, val} | null",
            "backburner": "object {op, val} | null",
            "isStarred": "object {op, val} | null",
            "isFrogged": "object {op, val} | null",
            "labelIds": "object {op, val} | null",
            "project": "object {op, val} | null",
            "nextStep": "object {op, val} | null",
            "planAhead": "object {op, val} | null",
            "timeEstimate": "object {op, val} | null",
            "timeBlock": "object {op, val} | null",
            "advanced": "object {op, val} | null (val carries Marvin internal query DSL)",
        },
        "applicable_filters": ["include_deleted"],
        "not_applicable": [
            "contains (query_docs searches title/note; SmartLists uses 'name' for "
            "display, so contains will not match smart-list names — only their notes)",
            "labels, exclude_labels (no labelIds on the SmartList itself)",
            "include_done, has_due_date, has_time_estimate, has_scheduled_day, "
            "due/due_*, scheduled/scheduled_*, done_*, parent_id, project_type, "
            "is_starred, is_frogged, priority (Tasks/Categories-specific filters)",
        ],
        "gotchas": [
            "Each filter field is null or an {'op': operator, 'val': value} object — "
            "the UI-driven structure stored in CouchDB, distinct from the advanced "
            "DSL. Call describe_smartlist_dsl(category='per_field_ops') for the "
            "full op vocabulary per field (18 fields covered: itemType, day, "
            "parentId, labelIds, goalId, backburner, hasTime, isPinned, orbit, "
            "recurring, timeEstimate, timeBlock, title, planAhead, "
            "procrastinationCount, created, firstScheduled, nextStep). Quirk: "
            "the 'backburner' field's clause sometimes omits 'op' and uses bare "
            "{'val': 'y'|'n'}.",
            "The 'advanced' field's val is a postfix-RPN DSL. Call "
            "describe_smartlist_dsl() for a summary, then "
            "describe_smartlist_dsl(category='predicates'|'functions'|'operators'|"
            "'tokens') to dump a registry, or describe_smartlist_dsl(name='...') "
            "to look up a single identifier (e.g. name='isNextStep', name='&&', "
            "name='parent'). Coverage: 130 predicates (boolean tests, date "
            "keywords, comparable fields), 6 functions (parent, anyAncestor, "
            "anyChild, allChildren, anySibling, allSiblings), 11 operators "
            "(! && || == != > < >= <= + -), 15 token types. Help center subset: "
            "https://help.amazingmarvin.com/en/articles/2070779-advanced-smart-list-filters",
            "Workflow-preset smart lists (IDs prefixed 'WF_') are stored sparsely "
            "with only filter-relevant fields populated; user-created smart lists "
            "default to a full field set with most filter fields null.",
            "Display name is in 'name', not 'title'. The query_docs 'contains' "
            "filter targets title/note and will not match smart-list names.",
            "Planner-view pinned IDs are stored separately at "
            "profile.strategySettings.plannerSmartLists in a ProfileItems doc, "
            "not on the smart-list itself.",
        ],
        "examples": [
            'query_docs(doc_type="SmartLists")  # list all smart lists',
            'get_document("WF_GTD_nextActions")  # fetch a workflow-preset smart list by ID',
        ],
    },
}

VALID_DOC_TYPES: frozenset[str] = frozenset(DOC_TYPE_SCHEMAS.keys())
