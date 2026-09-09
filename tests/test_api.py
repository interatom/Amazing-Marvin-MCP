"""Pytest tests for Amazing Marvin MCP API functionality."""

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError

from amazing_marvin_mcp.main import create_goal as create_goal_tool
from amazing_marvin_mcp.main import (
    create_recurring_task as create_recurring_task_tool,
)
from amazing_marvin_mcp.main import create_project as create_project_tool
from amazing_marvin_mcp.main import create_project_with_tasks as create_project_with_tasks_tool
from amazing_marvin_mcp.main import delete_document as delete_document_tool
from amazing_marvin_mcp.main import get_categories
from amazing_marvin_mcp.main import get_child_tasks as get_child_tasks_tool
from amazing_marvin_mcp.main import get_completed_tasks_for_date
from amazing_marvin_mcp.main import get_goals
from amazing_marvin_mcp.main import get_labels
from amazing_marvin_mcp.main import get_tasks
from amazing_marvin_mcp.models import GoalCreateRequest, RecurringTaskCreateRequest
from amazing_marvin_mcp.analytics import (
    _get_daily_productivity_db,
    get_completed_tasks,
    get_daily_productivity_overview,
    get_productivity_summary,
)
from amazing_marvin_mcp.api import MarvinAPIClient, create_api_client
from amazing_marvin_mcp.config import get_settings
from amazing_marvin_mcp.projects import create_project_with_tasks
from amazing_marvin_mcp.response_models import Reference
from amazing_marvin_mcp.task_processor import create_clean_task
from amazing_marvin_mcp.tasks import (
    _get_all_children_db,
    apply_fields,
    batch_create_tasks,
    get_all_tasks_impl,
    get_daily_focus,
    quick_daily_planning,
)

# Constants for tests
TASK_COUNT = 3  # Number of tasks to create in tests


@pytest.fixture
def api_client():
    """Create API client for testing."""
    try:
        settings = get_settings()
        if not settings.amazing_marvin_api_key:
            pytest.skip("No API key available for testing")
        return MarvinAPIClient(api_key=settings.amazing_marvin_api_key)
    except Exception:
        pytest.skip("Configuration error - cannot create API client")


@pytest.fixture
def test_project_data():
    """Test project data."""
    return {
        "title": f"Pytest Test Project - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "type": "project",
    }


@pytest.fixture
def test_task_data():
    """Test task data."""
    return {
        "title": f"Pytest Test Task - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "note": "This is a test task created by pytest",
    }


class TestMarvinAPIClient:
    """Test the MarvinAPIClient class."""

    def test_api_connection(self, api_client):
        """Test API connection."""
        result = api_client.test_api_connection()
        assert result == "OK"

    def test_get_categories(self, api_client):
        """Test getting categories."""
        categories = api_client.get_categories()
        assert isinstance(categories, list)

    def test_get_projects(self, api_client):
        """Test getting projects."""
        projects = api_client.get_projects()
        assert isinstance(projects, list)

    def test_get_labels(self, api_client):
        """Test getting labels."""
        labels = api_client.get_labels()
        assert isinstance(labels, list)

    def test_get_due_items(self, api_client):
        """Test getting due items."""
        due_items = api_client.get_due_items()
        assert isinstance(due_items, list)

    def test_get_goals(self, api_client):
        """Test getting goals."""
        goals = api_client.get_goals()
        assert isinstance(goals, list)

    def test_get_account_info(self, api_client):
        """Test getting account info."""
        account = api_client.get_account_info()
        assert isinstance(account, dict)

    def test_get_currently_tracked_item(self, api_client):
        """Test getting currently tracked item."""
        tracked = api_client.get_currently_tracked_item()
        assert tracked is not None

    def test_get_habits(self, api_client):
        """Smoke test: get_habits returns a list."""
        result = api_client.get_habits()
        assert isinstance(result, list)

    def test_get_today_time_blocks(self, api_client):
        """Smoke test: get_today_time_blocks returns a list."""
        result = api_client.get_today_time_blocks()
        assert isinstance(result, list)


class TestTaskAndProjectManagement:
    """Test task and project creation, modification, and deletion."""

    def test_create_project(self, api_client, test_project_data):
        """Test creating a project."""
        created_project = api_client.create_project(test_project_data)
        assert created_project is not None
        assert created_project.get("title") == test_project_data["title"]
        assert "_id" in created_project

    def test_create_task(self, api_client, test_task_data):
        """Test creating a task."""
        created_task = api_client.create_task(test_task_data)
        assert created_task is not None
        assert created_task.get("title") == test_task_data["title"]
        assert "_id" in created_task

    def test_comprehensive_workflow(
        self, api_client, test_project_data, test_task_data
    ):
        """Test a complete workflow: create project, add tasks, manage tasks."""
        # Create test project
        created_project = api_client.create_project(test_project_data)
        project_id = created_project.get("_id")
        assert project_id is not None

        # Create tasks in the project
        test_tasks = []
        for i in range(3):
            task_data = {
                **test_task_data,
                "title": f"{test_task_data['title']} #{i + 1}",
                "parentId": project_id,
            }
            created_task = api_client.create_task(task_data)
            test_tasks.append(created_task)
            assert created_task.get("_id") is not None

        # Test getting children of the project
        children = api_client.get_children(project_id)
        assert isinstance(children, list)
        # Note: children might be empty if the endpoint is experimental

        # Mark first task as done
        if test_tasks and test_tasks[0].get("_id"):
            task_id = test_tasks[0]["_id"]
            completed = api_client.mark_task_done(task_id)
            assert completed is not None


class TestTimeTracking:
    """Test time tracking functionality."""

    def test_start_stop_tracking(self, api_client, test_task_data):
        """Test starting and stopping time tracking."""
        # First create a task to track
        created_task = api_client.create_task(test_task_data)
        task_id = created_task.get("_id")
        assert task_id is not None

        # Test starting tracking
        start_result = api_client.start_time_tracking(task_id)
        assert start_result is not None

        # Test stopping tracking
        stop_result = api_client.stop_time_tracking(task_id)
        assert stop_result is not None

    def test_get_time_tracks(self, api_client, test_task_data):
        """Test getting time tracking data."""
        # Create a task first
        created_task = api_client.create_task(test_task_data)
        task_id = created_task.get("_id")
        assert task_id is not None

        # Get time tracks for the task
        tracks = api_client.get_time_tracks([task_id])
        assert tracks is not None


class TestRewards:
    """Test reward system functionality."""

    def test_claim_reward_points(self, api_client, test_task_data):
        """Test claiming reward points."""
        # Create and complete a task first
        created_task = api_client.create_task(test_task_data)
        task_id = created_task.get("_id")
        assert task_id is not None

        # Mark task as done
        completed_task = api_client.mark_task_done(task_id)
        assert completed_task is not None

        # Try to claim reward points (might fail due to API restrictions)
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            reward_result = api_client.claim_reward_points(10, task_id, today)
            assert reward_result is not None
        except Exception as e:
            # Reward claiming might not be available for all accounts
            pytest.skip(f"Reward claiming not available: {e}")

    def test_get_kudos_info(self, api_client):
        """Test getting kudos information."""
        kudos = api_client.get_kudos_info()
        assert kudos is not None


class TestErrorHandling:
    """Test error handling in the API client."""

    def test_invalid_api_key(self):
        """Test behavior with invalid API key."""
        invalid_client = MarvinAPIClient(api_key="invalid_key")
        with pytest.raises(
            requests.exceptions.HTTPError, match="(400|401) Client Error"
        ):
            invalid_client.get_categories()

    def test_invalid_task_id(self, api_client):
        """Test behavior with invalid task ID."""
        with pytest.raises(requests.exceptions.HTTPError, match="4"):  # 4xx error
            api_client.mark_task_done("invalid_task_id")

    def test_invalid_project_id(self, api_client):
        """Test behavior with invalid project ID."""
        children = api_client.get_children("invalid_project_id")
        # Should return empty list due to error handling
        assert isinstance(children, list)


class TestTimezoneAwareness:
    """Unit tests for local timezone fix (caffme commit 1758871).

    Verifies that API calls for "today" items pass an explicit local date
    rather than relying on the Marvin API's UTC default. Without the fix,
    users in non-UTC timezones would receive wrong-day items during
    the window after local midnight but before UTC midnight.

    All tests mock the API client and DateUtils.get_today() — no API key needed.
    Before the fix: get_tasks() and get_done_items() were called without a date
    argument, so these assertions would fail.
    """

    FIXED_DATE = "2026-04-14"

    def _make_api_client(self):
        client = MagicMock(spec=MarvinAPIClient)
        client.has_couchdb = False  # force REST path so these timezone assertions hold
        client.get_tasks.return_value = []
        client.get_done_items.return_value = []
        client.get_due_items.return_value = []
        client.get_projects.return_value = []
        client.get_categories.return_value = []
        client.get_goals.return_value = []
        client.get_labels.return_value = []
        return client

    def test_get_daily_focus_passes_local_date(self):
        """get_daily_focus() must pass local date to get_tasks and get_done_items."""
        client = self._make_api_client()
        with patch(
            "amazing_marvin_mcp.tasks.DateUtils.get_today", return_value=self.FIXED_DATE
        ):
            get_daily_focus(client)
        client.get_tasks.assert_called_once_with(date=self.FIXED_DATE)
        client.get_done_items.assert_called_once_with(date=self.FIXED_DATE)

    def test_quick_daily_planning_passes_local_date(self):
        """quick_daily_planning() must pass local date to get_tasks."""
        client = self._make_api_client()
        with patch(
            "amazing_marvin_mcp.tasks.DateUtils.get_today", return_value=self.FIXED_DATE
        ):
            quick_daily_planning(client)
        client.get_tasks.assert_called_once_with(date=self.FIXED_DATE)

    def test_get_completed_tasks_passes_local_date(self):
        """get_completed_tasks() must pass local date to get_done_items for today."""
        client = self._make_api_client()
        with patch(
            "amazing_marvin_mcp.analytics.DateUtils.get_today",
            return_value=self.FIXED_DATE,
        ):
            get_completed_tasks(client)
        calls = [str(c) for c in client.get_done_items.call_args_list]
        assert any(self.FIXED_DATE in c for c in calls), (
            f"Expected get_done_items to be called with date={self.FIXED_DATE!r}, got: {calls}"
        )

    def test_get_daily_productivity_overview_passes_local_date(self):
        """get_daily_productivity_overview() must pass local date to get_tasks and get_done_items."""
        client = self._make_api_client()
        with patch(
            "amazing_marvin_mcp.analytics.DateUtils.get_today",
            return_value=self.FIXED_DATE,
        ):
            get_daily_productivity_overview(client)
        client.get_tasks.assert_called_once_with(date=self.FIXED_DATE)
        client.get_done_items.assert_called_once_with(date=self.FIXED_DATE)


class TestParentIdResolution:
    """Unit tests for parentId resolution fix (PR #8).

    These tests require no API key — they exercise create_clean_task()
    directly with hand-crafted lookup maps.

    Before the fix: tasks whose parentId pointed to a category had
    parent=None and project=None (orphaned). The 'parents' combined
    lookup map and 'parent' reference mapping did not exist.
    """

    def _make_lookup_maps(self, projects: dict, categories: dict) -> dict:
        return {
            "projects": projects,
            "categories": categories,
            "labels": {},
            "parents": {**categories, **projects},
        }

    def test_parentid_pointing_to_category_resolves_parent(self):
        """parentId that maps to a category should resolve parent, not project."""
        raw_task = {"_id": "task1", "title": "My Task", "parentId": "cat123"}
        lookup_maps = self._make_lookup_maps(
            projects={},
            categories={"cat123": "My Category"},
        )
        task, _ = create_clean_task(raw_task, lookup_maps)

        assert task.parent == Reference(item_id="cat123", name="My Category")
        assert task.parent_id == "cat123"
        assert task.project is None

    def test_parentid_pointing_to_project_resolves_both(self):
        """parentId that maps to a project should resolve both parent and project."""
        raw_task = {"_id": "task1", "title": "My Task", "parentId": "proj456"}
        lookup_maps = self._make_lookup_maps(
            projects={"proj456": "My Project"},
            categories={},
        )
        task, _ = create_clean_task(raw_task, lookup_maps)

        assert task.parent == Reference(item_id="proj456", name="My Project")
        assert task.project == Reference(item_id="proj456", name="My Project")
        assert task.parent_id == "proj456"

    def test_task_without_parentid_has_no_parent(self):
        """Tasks with no parentId should have parent=None and project=None."""
        raw_task = {"_id": "task1", "title": "Standalone Task"}
        lookup_maps = self._make_lookup_maps(projects={}, categories={})
        task, _ = create_clean_task(raw_task, lookup_maps)

        assert task.parent is None
        assert task.project is None
        assert task.parent_id is None


class TestProjectPlanningEnhancements:
    """Test the new project planning enhancement features."""

    def test_create_project_with_tasks(self, test_project_data):
        """Test creating a project with multiple tasks at once."""

        # Use test data
        api_client = create_api_client()
        task_titles = [f"Test Task {i + 1}" for i in range(TASK_COUNT)]
        result = create_project_with_tasks(
            api_client,
            project_title=test_project_data["title"],
            task_titles=task_titles,
        )

        assert result["created_project"] is not None
        assert result["task_count"] == TASK_COUNT
        assert len(result["created_tasks"]) == TASK_COUNT

    def test_get_daily_focus(self):
        """Test getting daily focus items."""

        api_client = create_api_client()
        result = get_daily_focus(api_client)

        assert "total_focus_items" in result
        assert "completed_today" in result
        assert "pending_items" in result
        assert "high_priority_items" in result
        assert "projects" in result
        assert "tasks" in result

    def test_get_productivity_summary(self):
        """Test getting productivity summary."""

        api_client = create_api_client()
        result = get_productivity_summary(api_client)

        assert "date" in result
        assert "active_goals" in result
        assert "summary" in result

    def test_quick_daily_planning(self):
        """Test quick daily planning feature."""

        api_client = create_api_client()
        result = quick_daily_planning(api_client)

        assert "planning_date" in result
        assert "overdue_items" in result
        assert "scheduled_today" in result
        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)

    def test_batch_create_tasks(self):
        """Test batch task creation."""

        # Create test tasks
        api_client = create_api_client()
        tasks = ["Test Task 1", "Test Task 2", "Test Task 3"]
        result = batch_create_tasks(api_client, tasks)

        assert "created_tasks" in result
        assert "failed_tasks" in result
        assert "success_count" in result
        assert result["success_count"] >= 0
        assert result["total_requested"] == TASK_COUNT


class TestFullAccessToken:
    """Unit tests for full-access token functionality. No live API calls."""

    BASE_URL = "https://serv.amazingmarvin.com/api"

    def _client(self, token: str = "") -> MarvinAPIClient:
        return MarvinAPIClient(api_key="key", full_access_token=token)

    def _mock_response(self, payload: Any, status: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        resp.content = b"x"
        resp.json.return_value = payload
        resp.raise_for_status.return_value = None
        return resp

    # --- has_full_access property ---

    def test_has_full_access_false_without_token(self):
        assert self._client().has_full_access is False

    def test_has_full_access_true_with_token(self):
        assert self._client("tok123").has_full_access is True

    # --- guard: ValueError when token absent ---

    def test_get_document_raises_without_token(self):
        with pytest.raises(ValueError, match="AMAZING_MARVIN_FULL_ACCESS_TOKEN"):
            self._client().get_document("id1")

    def test_update_document_raises_without_token(self):
        with pytest.raises(ValueError, match="AMAZING_MARVIN_FULL_ACCESS_TOKEN"):
            self._client().update_document("id1", {"title": "x"})

    def test_create_document_raises_without_token(self):
        with pytest.raises(ValueError, match="AMAZING_MARVIN_FULL_ACCESS_TOKEN"):
            self._client().create_document({"title": "x"})

    def test_delete_document_raises_without_token(self):
        with pytest.raises(ValueError, match="AMAZING_MARVIN_FULL_ACCESS_TOKEN"):
            self._client().delete_document("id1")

    # --- correct HTTP method, URL, headers, payload ---

    @patch("requests.get")
    def test_get_document_uses_get_and_full_access_header(self, mock_get: MagicMock):
        mock_get.return_value = self._mock_response({"_id": "id1", "title": "T"})
        result = self._client("tok").get_document("id1")
        mock_get.assert_called_once_with(
            f"{self.BASE_URL}/doc?id=id1",
            headers={"X-Full-Access-Token": "tok"},
        )
        assert result["_id"] == "id1"

    @patch("requests.post")
    def test_update_document_sends_correct_payload(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"_id": "id1"})
        self._client("tok").update_document("id1", {"note": "hi"})
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/doc/update",
            headers={"X-Full-Access-Token": "tok"},
            json={"itemId": "id1", "setters": [{"key": "note", "val": "hi"}]},
        )

    @patch("requests.post")
    def test_create_document_sends_document_as_body(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"_id": "new1"})
        self._client("tok").create_document({"_id": "new1", "title": "Raw"})
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/doc/create",
            headers={"X-Full-Access-Token": "tok"},
            json={"_id": "new1", "title": "Raw"},
        )

    @patch("requests.post")
    def test_create_document_does_not_wrap_body_in_envelope(self, mock_post: MagicMock):
        """A wrapped body is accepted with 200 but stores nothing, so it must
        never be sent."""
        mock_post.return_value = self._mock_response({"_id": "new1"})
        self._client("tok").create_document({"title": "Raw"})
        sent = mock_post.call_args.kwargs["json"]
        assert "doc" not in sent
        assert sent == {"title": "Raw"}

    @patch("requests.post")
    def test_create_goal_sends_document_as_body(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"_id": "g1"})
        self._client("tok").create_goal({"_id": "g1", "db": "Goals", "title": "Ship it"})
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/doc/create",
            headers={"X-Full-Access-Token": "tok"},
            json={"_id": "g1", "db": "Goals", "title": "Ship it"},
        )

    @patch("requests.post")
    def test_create_recurring_task_sends_document_as_body(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"_id": "r1"})
        self._client("tok").create_recurring_task(
            {"_id": "r1", "db": "RecurringTasks", "title": "Inspection"}
        )
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/doc/create",
            headers={"X-Full-Access-Token": "tok"},
            json={"_id": "r1", "db": "RecurringTasks", "title": "Inspection"},
        )

    @patch("requests.post")
    def test_delete_document_sends_correct_payload(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({})
        self._client("tok").delete_document("id1")
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/doc/delete",
            headers={"X-Full-Access-Token": "tok"},
            json={"itemId": "id1"},
        )

    @patch("requests.get")
    def test_get_document_does_not_use_api_token_header(self, mock_get: MagicMock):
        """Full-access requests must NOT send X-API-Token."""
        mock_get.return_value = self._mock_response({"_id": "id1"})
        self._client("tok").get_document("id1")
        call_headers = mock_get.call_args.kwargs["headers"]
        assert "X-API-Token" not in call_headers

    @patch("requests.post")
    def test_update_document_accepts_list_setters(self, mock_post: MagicMock):
        """update_document should pass list[dict] setters through unchanged."""
        mock_post.return_value = self._mock_response({"_id": "id1"})
        setters = [{"key": "title", "val": "New"}, {"key": "updatedAt", "val": 1700000000000}]
        self._client("tok").update_document("id1", setters)
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/doc/update",
            headers={"X-Full-Access-Token": "tok"},
            json={"itemId": "id1", "setters": setters},
        )


class TestGetAllTasksFieldProjection:
    """Unit tests for get_all_tasks fields parameter."""

    _TASK = {"_id": "t1", "title": "Task One", "note": "details", "parentId": "cat1"}

    def _make_api_client(self) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        # Exercise the DB path — find_docs returns the same task the REST path would
        client.has_couchdb = True
        client.find_docs.return_value = {"docs": [self._TASK], "bookmark": None}
        # REST fallbacks kept for completeness
        client.get_tasks.return_value = []
        client.get_due_items.return_value = []
        client.get_projects.return_value = []
        client.get_categories.return_value = [
            {"_id": "cat1", "type": "category", "title": "Work"}
        ]
        client.get_children.return_value = [self._TASK]
        return client

    def test_fields_none_returns_full_task_dicts(self):
        client = self._make_api_client()
        with patch(
            "amazing_marvin_mcp.tasks.DateUtils.get_today", return_value="2026-04-14"
        ):
            result = get_all_tasks_impl(client, label=None, fields=None)
        task = result["tasks"][0]
        assert "title" in task
        assert "note" in task

    def test_fields_list_projects_specified_keys_only(self):
        client = self._make_api_client()
        with patch(
            "amazing_marvin_mcp.tasks.DateUtils.get_today", return_value="2026-04-14"
        ):
            result = get_all_tasks_impl(client, label=None, fields=["_id", "title"])
        task = result["tasks"][0]
        assert set(task.keys()) == {"_id", "title"}

    def test_fields_silently_drops_missing_keys(self):
        """Requesting a field that doesn't exist on a task should not raise."""
        client = self._make_api_client()
        with patch(
            "amazing_marvin_mcp.tasks.DateUtils.get_today", return_value="2026-04-14"
        ):
            result = get_all_tasks_impl(
                client, label=None, fields=["_id", "nonexistent"]
            )
        task = result["tasks"][0]
        assert "nonexistent" not in task
        assert "_id" in task


class TestFieldsProjectionOnRestTools:
    """fields param on REST-only tools (get_tasks, get_categories, etc.) — no DB needed."""

    def _make_client(self) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        client.has_couchdb = False
        client.get_tasks.return_value = [
            {"_id": "t1", "title": "T1", "note": "n", "dueDate": "2026-04-21"}
        ]
        client.get_due_items.return_value = [
            {"_id": "t2", "title": "T2", "dueDate": "2026-04-20"}
        ]
        client.get_projects.return_value = [
            {"_id": "p1", "title": "Proj", "type": "project", "note": "pnote"}
        ]
        client.get_categories.return_value = [
            {"_id": "c1", "title": "Cat", "note": "cnote"}
        ]
        client.get_labels.return_value = [
            {"_id": "l1", "title": "urgent", "color": "#f00"}
        ]
        client.get_goals.return_value = [
            {"_id": "g1", "title": "Goal", "note": "gnote"}
        ]
        client.get_done_items.return_value = [
            {"_id": "d1", "title": "Done", "doneAt": 1000}
        ]
        return client

    def test_apply_fields_none_returns_all(self):
        items = [{"_id": "x", "title": "T", "note": "n"}]
        assert apply_fields(items, None) == items

    def test_apply_fields_projects_keys(self):
        items = [{"_id": "x", "title": "T", "note": "n"}]
        result = apply_fields(items, ["title"])
        assert set(result[0].keys()) == {"_id", "title"}

    def test_apply_fields_silently_drops_missing(self):
        items = [{"_id": "x", "title": "T"}]
        result = apply_fields(items, ["_id", "nonexistent"])
        assert "nonexistent" not in result[0]
        assert "_id" in result[0]

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_get_tasks_fields(self, mock_create):
        mock_create.return_value = self._make_client()
        result = asyncio.run(get_tasks(fields=["title"]))
        assert result.success
        # result.data is list[CleanTask] — projection removes dueDate before task processing
        assert len(result.data) >= 1
        task = result.data[0]
        assert task.title == "T1"
        assert task.due_date is None  # dueDate projected away by fields=["title"]

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_get_categories_fields(self, mock_create):
        mock_create.return_value = self._make_client()
        result = asyncio.run(get_categories(fields=["title"]))
        assert result.success
        assert len(result.data) >= 1
        assert set(result.data[0].keys()) == {"_id", "title"}

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_get_labels_fields(self, mock_create):
        mock_create.return_value = self._make_client()
        result = asyncio.run(get_labels(fields=["title"]))
        assert result.success
        labels = result.data["labels"]
        assert len(labels) >= 1
        assert set(labels[0].keys()) == {"_id", "title"}

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_get_goals_fields(self, mock_create):
        mock_create.return_value = self._make_client()
        result = asyncio.run(get_goals(fields=["title"]))
        assert result.success
        goals = result.data["goals"]
        assert len(goals) >= 1
        assert set(goals[0].keys()) == {"_id", "title"}

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_get_completed_tasks_for_date_fields(self, mock_create):
        mock_create.return_value = self._make_client()
        result = asyncio.run(get_completed_tasks_for_date(date="2026-04-21", fields=["title"]))
        assert result.success
        items = result.data["all_completed"]
        assert len(items) >= 1
        assert set(items[0].keys()) == {"_id", "title"}


class TestGetChildTasksTypeSplit:
    """Regression tests for the category-leaks-into-tasks bug.

    Before the fix: items with type='category' were classified as tasks
    because the filter was `!= 'project'` instead of `not in ('project', 'category')`.
    Plain tasks (no type field) should get type='task' injected.
    """

    def _make_client(self, children: list) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        # Exercise the DB path — find_docs returns the same children the REST path would
        client.has_couchdb = True
        client.find_docs.return_value = {"docs": children, "bookmark": None}
        return client

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_category_child_does_not_appear_in_tasks(self, mock_create: MagicMock) -> None:
        children = [
            {"_id": "t1", "title": "A task"},
            {"_id": "c1", "title": "A category", "type": "category"},
        ]
        mock_create.return_value = self._make_client(children)

        result = asyncio.run(get_child_tasks_tool("parent1"))

        data = result.data
        task_ids = [t["_id"] for t in data["tasks"]]
        category_ids = [c["_id"] for c in data["categories"]]
        assert "c1" not in task_ids
        assert "c1" in category_ids
        assert "t1" in task_ids

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_task_without_type_gets_type_injected(self, mock_create: MagicMock) -> None:
        children = [{"_id": "t1", "title": "A task"}]
        mock_create.return_value = self._make_client(children)

        result = asyncio.run(get_child_tasks_tool("parent1"))

        task = result.data["tasks"][0]
        assert task["type"] == "task"

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_counts_are_correct(self, mock_create: MagicMock) -> None:
        children = [
            {"_id": "t1", "title": "Task"},
            {"_id": "p1", "title": "Project", "type": "project"},
            {"_id": "c1", "title": "Category", "type": "category"},
        ]
        mock_create.return_value = self._make_client(children)

        result = asyncio.run(get_child_tasks_tool("parent1"))

        data = result.data
        assert data["task_count"] == 1
        assert data["project_count"] == 1
        assert data["category_count"] == 1
        assert data["total_children"] == 3


class TestGetChildTasksFieldProjection:
    """fields=[...] must reach CouchDB find_docs (server-side projection).

    Regression for the bug where get_child_tasks returned full documents on the
    wire even with fields=[...] passed, while query_docs trimmed them. The
    response must also no longer contain the redundant ``all_children`` key.
    """

    def _make_client(
        self, children: list, has_couchdb: bool = True
    ) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        client.has_couchdb = has_couchdb
        client.find_docs.return_value = {"docs": children, "bookmark": None}
        client.get_children.return_value = children
        return client

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_non_recursive_passes_fields_to_find_docs(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.return_value = self._make_client(
            [{"_id": "t1", "title": "A"}]
        )
        asyncio.run(get_child_tasks_tool("p1", fields=["title"]))

        kwargs = mock_create.return_value.find_docs.call_args.kwargs
        assert set(kwargs["fields"]) >= {"_id", "type", "title"}

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_recursive_passes_fields_to_find_docs(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.return_value = self._make_client([])
        asyncio.run(
            get_child_tasks_tool("p1", recursive=True, fields=["title"])
        )

        kwargs = mock_create.return_value.find_docs.call_args.kwargs
        assert set(kwargs["fields"]) >= {"_id", "type", "title"}

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_no_fields_means_no_projection(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.return_value = self._make_client([{"_id": "t1"}])
        asyncio.run(get_child_tasks_tool("p1"))

        kwargs = mock_create.return_value.find_docs.call_args.kwargs
        assert kwargs.get("fields") is None

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_rest_fallback_trims_via_apply_fields(
        self, mock_create: MagicMock
    ) -> None:
        children = [{"_id": "t1", "title": "A", "note": "long body"}]
        mock_create.return_value = self._make_client(
            children, has_couchdb=False
        )
        result = asyncio.run(get_child_tasks_tool("p1", fields=["title"]))

        task = result.data["tasks"][0]
        assert "note" not in task
        assert task.get("title") == "A"

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_response_no_longer_contains_all_children(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.return_value = self._make_client([{"_id": "t1"}])
        result = asyncio.run(get_child_tasks_tool("p1"))
        assert "all_children" not in result.data

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_recursive_response_no_longer_contains_all_children(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.return_value = self._make_client([])
        result = asyncio.run(get_child_tasks_tool("p1", recursive=True))
        assert "all_children" not in result.data


class TestGetChildTasksDoneFilter:
    """Default-exclude done items; opt-in via include_done=True.

    Aligns get_child_tasks with the project-wide convention used by
    query_docs, search, and analytics.
    """

    def _make_client(
        self, children: list, has_couchdb: bool = True
    ) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        client.has_couchdb = has_couchdb
        client.find_docs.return_value = {"docs": children, "bookmark": None}
        client.get_children.return_value = children
        return client

    _NOT_DONE_OR = [{"done": {"$exists": False}}, {"done": {"$ne": True}}]

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_default_excludes_done_via_selector(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.return_value = self._make_client([])
        asyncio.run(get_child_tasks_tool("p1"))

        selector = mock_create.return_value.find_docs.call_args.kwargs["selector"]
        assert selector.get("$or") == self._NOT_DONE_OR

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_include_done_true_drops_selector(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.return_value = self._make_client([])
        asyncio.run(get_child_tasks_tool("p1", include_done=True))

        selector = mock_create.return_value.find_docs.call_args.kwargs["selector"]
        assert "$or" not in selector
        assert "done" not in selector

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_recursive_default_threads_done_filter(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.return_value = self._make_client([])
        asyncio.run(get_child_tasks_tool("p1", recursive=True))

        selector = mock_create.return_value.find_docs.call_args.kwargs["selector"]
        assert selector.get("$or") == self._NOT_DONE_OR

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_recursive_include_done_omits_filter(
        self, mock_create: MagicMock
    ) -> None:
        mock_create.return_value = self._make_client([])
        asyncio.run(get_child_tasks_tool("p1", recursive=True, include_done=True))

        selector = mock_create.return_value.find_docs.call_args.kwargs["selector"]
        assert "$or" not in selector
        assert "done" not in selector

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_rest_fallback_default_filters_done_client_side(
        self, mock_create: MagicMock
    ) -> None:
        children = [
            {"_id": "t1", "title": "open"},
            {"_id": "t2", "title": "completed", "done": True},
        ]
        mock_create.return_value = self._make_client(children, has_couchdb=False)

        result = asyncio.run(get_child_tasks_tool("p1"))

        task_ids = [t["_id"] for t in result.data["tasks"]]
        assert task_ids == ["t1"]

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_rest_fallback_include_done_keeps_done(
        self, mock_create: MagicMock
    ) -> None:
        children = [
            {"_id": "t1", "title": "open"},
            {"_id": "t2", "title": "completed", "done": True},
        ]
        mock_create.return_value = self._make_client(children, has_couchdb=False)

        result = asyncio.run(get_child_tasks_tool("p1", include_done=True))

        task_ids = sorted(t["_id"] for t in result.data["tasks"])
        assert task_ids == ["t1", "t2"]


class TestDeleteDocumentTool:
    """Unit tests for the delete_document MCP tool safety pre-flight logic.

    These tests exercise the three-tier classification (task / container /
    internal doc) without making any live API calls.
    """

    def _make_client(
        self, doc: dict, children: list | None = None
    ) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        client.get_document.return_value = doc
        client.get_children.return_value = children if children is not None else []
        client.delete_document.return_value = {}
        return client

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_task_is_deleted(self, mock_create: MagicMock) -> None:
        """Plain tasks (db=Tasks, no container type) should be deleted immediately."""
        doc = {"_id": "t1", "db": "Tasks", "title": "Buy milk"}
        client = self._make_client(doc)
        mock_create.return_value = client

        result = asyncio.run(delete_document_tool("t1"))

        assert result.success is True
        assert result.data["deleted_title"] == "Buy milk"
        assert result.data["deleted_type"] == "task"
        client.delete_document.assert_called_once_with("t1")
        client.get_children.assert_not_called()

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_non_empty_project_is_blocked(self, mock_create: MagicMock) -> None:
        """Projects with children must be blocked; delete_document must not be called."""
        doc = {"_id": "p1", "type": "project", "title": "My Project"}
        children = [{"_id": "t1", "title": "Child task"}]
        client = self._make_client(doc, children)
        mock_create.return_value = client

        result = asyncio.run(delete_document_tool("p1"))

        assert result.success is False
        assert "1" in result.summary.text  # child count present in message
        client.delete_document.assert_not_called()

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_non_empty_category_is_blocked(self, mock_create: MagicMock) -> None:
        """Categories with children must be blocked; delete_document must not be called."""
        doc = {"_id": "c1", "type": "category", "title": "Work"}
        children = [{"_id": "t2", "title": "Sub-task"}, {"_id": "t3", "title": "Another"}]
        client = self._make_client(doc, children)
        mock_create.return_value = client

        result = asyncio.run(delete_document_tool("c1"))

        assert result.success is False
        assert "2" in result.summary.text
        client.delete_document.assert_not_called()

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_empty_project_is_deleted(self, mock_create: MagicMock) -> None:
        """Empty projects (no children) should be allowed through."""
        doc = {"_id": "p2", "type": "project", "title": "Empty Project"}
        client = self._make_client(doc, children=[])
        mock_create.return_value = client

        result = asyncio.run(delete_document_tool("p2"))

        assert result.success is True
        assert result.data["deleted_title"] == "Empty Project"
        assert result.data["deleted_type"] == "project"
        client.delete_document.assert_called_once_with("p2")

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_internal_doc_is_blocked(self, mock_create: MagicMock) -> None:
        """Non-task, non-container documents (Goals, Labels, etc.) must always be blocked."""
        doc = {"_id": "g1", "db": "Goals", "title": "My Goal"}
        client = self._make_client(doc)
        mock_create.return_value = client

        result = asyncio.run(delete_document_tool("g1"))

        assert result.success is False
        assert "Goals" in result.summary.text
        client.delete_document.assert_not_called()
        client.get_children.assert_not_called()


class TestSettersBuilder:
    """Unit tests for build_setters — no API key required."""

    from amazing_marvin_mcp.setters_builder import build_setters
    from amazing_marvin_mcp.models import TaskUpdateRequest

    FIXED_TIME = 1700000000.0
    NOW_MS = 1700000000000

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_title_produces_fieldUpdates_entry(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x", title="Hello")
        setters = build_setters(req)
        keys = [s["key"] for s in setters]
        assert "title" in keys
        assert "fieldUpdates.title" in keys
        assert "updatedAt" in keys

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_note_produces_fieldUpdates_entry(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x", note="some text")
        setters = build_setters(req)
        keys = [s["key"] for s in setters]
        assert "note" in keys
        assert "fieldUpdates.note" in keys

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_parent_id_produces_fieldUpdates_entry(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x", parent_id="proj1")
        setters = build_setters(req)
        keys = [s["key"] for s in setters]
        assert "parentId" in keys
        assert "fieldUpdates.parentId" in keys

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_is_starred_true_writes_tier_1(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x", is_starred=True)
        setters = build_setters(req)
        starred = next(s for s in setters if s["key"] == "isStarred")
        assert starred["val"] == 1

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_is_starred_false_writes_null(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x", is_starred=False)
        setters = build_setters(req)
        starred = next(s for s in setters if s["key"] == "isStarred")
        assert starred["val"] is None

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_is_frogged_true_writes_tier_1(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x", is_frogged=True)
        setters = build_setters(req)
        frogged = next(s for s in setters if s["key"] == "isFrogged")
        assert frogged["val"] == 1

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_is_frogged_false_writes_null(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x", is_frogged=False)
        setters = build_setters(req)
        frogged = next(s for s in setters if s["key"] == "isFrogged")
        assert frogged["val"] is None

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_due_date_produces_fieldUpdates_entry(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x", due_date="2026-12-31")
        setters = build_setters(req)
        keys = [s["key"] for s in setters]
        assert "dueDate" in keys
        assert "fieldUpdates.dueDate" in keys
        fu = next(s for s in setters if s["key"] == "fieldUpdates.dueDate")
        assert fu["val"] == self.NOW_MS

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_none_fields_excluded(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x")  # all optional fields None
        setters = build_setters(req)
        keys = [s["key"] for s in setters]
        # Only updatedAt should be present
        assert keys == ["updatedAt"]

    @patch("amazing_marvin_mcp.setters_builder.time.time", return_value=FIXED_TIME)
    def test_time_estimate_converted_to_ms(self, _mock_time):
        from amazing_marvin_mcp.setters_builder import build_setters
        from amazing_marvin_mcp.models import TaskUpdateRequest

        req = TaskUpdateRequest(item_id="x", time_estimate=1)  # 1 minute
        setters = build_setters(req)
        te = next(s for s in setters if s["key"] == "timeEstimate")
        assert te["val"] == 60_000  # 1 min → 60000 ms


class TestUpdateTaskTool:
    """Unit tests for the update_task MCP tool — no API key required."""

    def _make_client(self) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        client.update_document.return_value = {"_id": "t1"}
        client.has_full_access = True
        return client

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_builds_correct_setters_for_title(self, mock_create: MagicMock) -> None:
        client = self._make_client()
        mock_create.return_value = client

        from amazing_marvin_mcp.main import update_task as update_task_tool

        asyncio.run(update_task_tool("t1", title="New Title"))

        call_args = client.update_document.call_args
        item_id = call_args[0][0]
        setters = call_args[0][1]
        assert item_id == "t1"
        assert isinstance(setters, list)
        keys = [s["key"] for s in setters]
        assert "title" in keys
        assert "updatedAt" in keys

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_only_set_fields_included_in_setters(self, mock_create: MagicMock) -> None:
        client = self._make_client()
        mock_create.return_value = client

        from amazing_marvin_mcp.main import update_task as update_task_tool

        asyncio.run(update_task_tool("t1", note="hello"))

        setters = client.update_document.call_args[0][1]
        keys = [s["key"] for s in setters]
        assert "note" in keys
        assert "title" not in keys

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_raises_when_no_full_access_token(self, mock_create: MagicMock) -> None:
        client = MagicMock(spec=MarvinAPIClient)
        client.update_document.side_effect = ValueError(
            "Full-access token not configured. Set AMAZING_MARVIN_FULL_ACCESS_TOKEN."
        )
        mock_create.return_value = client

        from amazing_marvin_mcp.main import update_task as update_task_tool

        result = asyncio.run(update_task_tool("t1", title="x"))
        assert result.success is False


class TestNewApiMethods:
    """Unit tests for the 9 new api.py methods — no live API calls."""

    BASE_URL = "https://serv.amazingmarvin.com/api"

    def _client(self) -> MarvinAPIClient:
        return MarvinAPIClient(api_key="key")

    def _mock_response(self, payload: Any, status: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        resp.content = b"x"
        resp.json.return_value = payload
        resp.raise_for_status.return_value = None
        return resp

    @patch("requests.get")
    def test_get_habits_calls_correct_endpoint(self, mock_get: MagicMock):
        mock_get.return_value = self._mock_response([{"_id": "h1"}])
        result = self._client().get_habits()
        mock_get.assert_called_once_with(
            f"{self.BASE_URL}/habits", headers={"X-API-Token": "key"}
        )
        assert result == [{"_id": "h1"}]

    @patch("requests.get")
    def test_get_habit_passes_id_as_query_param(self, mock_get: MagicMock):
        mock_get.return_value = self._mock_response({"_id": "h1"})
        self._client().get_habit("h1")
        mock_get.assert_called_once_with(
            f"{self.BASE_URL}/habit?id=h1", headers={"X-API-Token": "key"}
        )

    @patch("requests.post")
    def test_update_habit_posts_habit_data(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({})
        self._client().update_habit({"habitId": "h1", "action": "record"})
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/updateHabit",
            headers={"X-API-Token": "key"},
            json={"habitId": "h1", "action": "record"},
        )

    @patch("requests.post")
    def test_add_event_posts_event_data(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"_id": "e1"})
        self._client().add_event({"title": "Meeting", "start": "2026-04-16T09:00:00"})
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/addEvent",
            headers={"X-API-Token": "key"},
            json={"title": "Meeting", "start": "2026-04-16T09:00:00"},
        )

    @patch("requests.get")
    def test_get_today_time_blocks_without_date(self, mock_get: MagicMock):
        mock_get.return_value = self._mock_response([])
        self._client().get_today_time_blocks()
        mock_get.assert_called_once_with(
            f"{self.BASE_URL}/todayTimeBlocks", headers={"X-API-Token": "key"}
        )

    @patch("requests.get")
    def test_get_today_time_blocks_with_date(self, mock_get: MagicMock):
        mock_get.return_value = self._mock_response([])
        self._client().get_today_time_blocks("2026-04-16")
        mock_get.assert_called_once_with(
            f"{self.BASE_URL}/todayTimeBlocks?date=2026-04-16",
            headers={"X-API-Token": "key"},
        )

    @patch("requests.post")
    def test_set_reminders_wraps_in_reminders_key(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({})
        reminders = [{"itemId": "t1", "time": 900}]
        self._client().set_reminders(reminders)
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/reminder/set",
            headers={"X-API-Token": "key"},
            json={"reminders": reminders},
        )

    @patch("requests.post")
    def test_delete_reminders_wraps_in_reminderIds_key(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({})
        self._client().delete_reminders(["r1", "r2"])
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/reminder/delete",
            headers={"X-API-Token": "key"},
            json={"reminderIds": ["r1", "r2"]},
        )

    @patch("requests.post")
    def test_spend_reward_points_posts_correctly(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({})
        self._client().spend_reward_points(50, "2026-04-16")
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/spendRewardPoints",
            headers={"X-API-Token": "key"},
            json={"points": 50, "date": "2026-04-16"},
        )

    @patch("requests.post")
    def test_unclaim_reward_points_posts_correctly(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({})
        self._client().unclaim_reward_points("t1", "2026-04-16")
        mock_post.assert_called_once_with(
            f"{self.BASE_URL}/unclaimRewardPoints",
            headers={"X-API-Token": "key"},
            json={"itemId": "t1", "date": "2026-04-16"},
        )


class TestNewMcpTools:
    """Unit tests for the new MCP tools — no API key required."""

    def _make_client(self) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        return client

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_get_habits_tool_returns_list(self, mock_create: MagicMock) -> None:
        from amazing_marvin_mcp.main import get_habits as get_habits_tool

        client = self._make_client()
        client.get_habits.return_value = [{"_id": "h1", "title": "Exercise"}]
        mock_create.return_value = client

        result = asyncio.run(get_habits_tool())
        assert result.success is True
        assert result.data["habits"] == [{"_id": "h1", "title": "Exercise"}]

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_record_habit_tool_sends_record_action(self, mock_create: MagicMock) -> None:
        from amazing_marvin_mcp.main import record_habit as record_habit_tool

        client = self._make_client()
        client.update_habit.return_value = {}
        mock_create.return_value = client

        asyncio.run(record_habit_tool("h1"))
        client.update_habit.assert_called_once_with({"habitId": "h1", "action": "record"})

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_record_habit_tool_includes_value_when_set(self, mock_create: MagicMock) -> None:
        from amazing_marvin_mcp.main import record_habit as record_habit_tool

        client = self._make_client()
        client.update_habit.return_value = {}
        mock_create.return_value = client

        asyncio.run(record_habit_tool("h1", value=5000))
        client.update_habit.assert_called_once_with(
            {"habitId": "h1", "action": "record", "value": 5000}
        )

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_undo_habit_tool_sends_undo_action(self, mock_create: MagicMock) -> None:
        from amazing_marvin_mcp.main import undo_habit as undo_habit_tool

        client = self._make_client()
        client.update_habit.return_value = {}
        mock_create.return_value = client

        asyncio.run(undo_habit_tool("h1"))
        client.update_habit.assert_called_once_with({"habitId": "h1", "action": "undo"})

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_add_event_tool_converts_minutes_to_ms(self, mock_create: MagicMock) -> None:
        from amazing_marvin_mcp.main import add_event as add_event_tool

        client = self._make_client()
        client.add_event.return_value = {"_id": "e1"}
        mock_create.return_value = client

        asyncio.run(add_event_tool("Meeting", "2026-04-16T09:00:00", 30))
        client.add_event.assert_called_once_with(
            {"title": "Meeting", "start": "2026-04-16T09:00:00", "length": 1_800_000}
        )

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_set_reminders_tool_passes_through(self, mock_create: MagicMock) -> None:
        from amazing_marvin_mcp.main import set_reminders as set_reminders_tool

        client = self._make_client()
        client.set_reminders.return_value = {}
        mock_create.return_value = client

        # Canonical reminder shape: reminderId (not itemId), Unix epoch seconds
        # for time, plus type/title/snooze/autoSnooze/canTrack.
        reminders = [{
            "reminderId": "t1",
            "time": 1_750_000_000,
            "type": "T",
            "title": "Sample task",
            "snooze": 600,
            "autoSnooze": 300,
            "canTrack": True,
        }]
        asyncio.run(set_reminders_tool(reminders))
        client.set_reminders.assert_called_once_with(reminders)

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_delete_reminders_tool_passes_through(self, mock_create: MagicMock) -> None:
        from amazing_marvin_mcp.main import delete_reminders as delete_reminders_tool

        client = self._make_client()
        client.delete_reminders.return_value = {}
        mock_create.return_value = client

        asyncio.run(delete_reminders_tool(["r1", "r2"]))
        client.delete_reminders.assert_called_once_with(["r1", "r2"])


class TestDescribeDocType:
    """Unit tests for describe_doc_type and DOC_TYPE_SCHEMAS.

    describe_doc_type is only registered with DB creds. These tests verify
    the schema dict directly (no DB needed) plus confirm the tool is absent
    without creds.
    """

    def test_describe_doc_type_not_registered_without_db_creds(self):
        import asyncio
        from amazing_marvin_mcp.main import mcp
        tools = asyncio.run(mcp.list_tools())
        names = [t.name for t in tools]
        assert "describe_doc_type" not in names

    def test_all_doc_types_in_schemas(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS, VALID_DOC_TYPES
        assert set(DOC_TYPE_SCHEMAS.keys()) == VALID_DOC_TYPES
        assert len(DOC_TYPE_SCHEMAS) == 15

    def test_each_schema_has_required_keys(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS
        required = {"fields", "applicable_filters", "not_applicable", "gotchas", "examples"}
        for doc_type, schema in DOC_TYPE_SCHEMAS.items():
            missing = required - set(schema.keys())
            assert not missing, f"{doc_type} schema missing: {missing}"

    def test_tasks_schema_has_core_fields(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS
        fields = DOC_TYPE_SCHEMAS["Tasks"]["fields"]
        for key in ("_id", "db", "title", "done", "doneAt", "dueDate", "day",
                    "isStarred", "isFrogged", "labelIds", "parentId", "note", "timeEstimate"):
            assert key in fields, f"Tasks schema missing field: {key}"

    def test_categories_schema_mentions_note_gotcha(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS
        gotchas = " ".join(DOC_TYPE_SCHEMAS["Categories"]["gotchas"])
        assert "note" in gotchas.lower()
        assert "rest" in gotchas.lower() or "/categories" in gotchas.lower()

    def test_tasks_schema_lists_is_frogged_as_applicable(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS
        assert "is_frogged" in DOC_TYPE_SCHEMAS["Tasks"]["applicable_filters"]

    def test_categories_schema_lists_priority_as_applicable(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS
        assert "priority" in DOC_TYPE_SCHEMAS["Categories"]["applicable_filters"]

    def test_tasks_schema_lists_priority_as_not_applicable(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS
        not_applicable = " ".join(DOC_TYPE_SCHEMAS["Tasks"]["not_applicable"])
        assert "priority" in not_applicable

    def test_categories_schema_lists_is_frogged_as_applicable(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS
        # is_frogged was widened to apply to Categories (projects can be frogged)
        assert "is_frogged" in DOC_TYPE_SCHEMAS["Categories"]["applicable_filters"]
        assert "is_starred" in DOC_TYPE_SCHEMAS["Categories"]["applicable_filters"]

    def test_tasks_gotchas_mention_isStarred_number_storage(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS
        gotchas = " ".join(DOC_TYPE_SCHEMAS["Tasks"]["gotchas"])
        assert "isStarred" in gotchas
        assert "number" in gotchas.lower() or "1/2/3" in gotchas

    def test_each_schema_has_at_least_one_example(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS
        for doc_type, schema in DOC_TYPE_SCHEMAS.items():
            assert schema["examples"], f"{doc_type} has no examples"

    def test_doc_type_literal_matches_schema_keys(self):
        from amazing_marvin_mcp.doc_types import DOC_TYPE_SCHEMAS, DocType
        import typing
        valid = set(typing.get_args(DocType))
        assert valid == set(DOC_TYPE_SCHEMAS.keys())


class TestBuildSelector:
    """Unit tests for build_selector — pure Python, no I/O.

    Covers each row of the filter dispatch table plus mixed-type gotchas
    and per-doc_type validation.
    """

    from amazing_marvin_mcp.db_filters import build_selector

    def _get_frags(self, selector: dict) -> list[dict]:
        """Extract fragment list from $and selector, or wrap single selector."""
        if "$and" in selector:
            return selector["$and"]
        return [selector]

    def _has_frag(self, selector: dict, key: str, val: Any = None) -> bool:
        frags = self._get_frags(selector)
        for f in frags:
            if key in f:
                return val is None or f[key] == val
        return False

    def _get_frag(self, selector: dict, key: str) -> Any:
        for f in self._get_frags(selector):
            if key in f:
                return f[key]
        return None

    # --- doc_type always present ---

    def test_doc_type_always_in_selector(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks")
        assert self._has_frag(sel, "db", "Tasks")

    def test_single_fragment_not_wrapped_in_and(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Labels", include_deleted=True)
        assert "db" in sel
        assert "$and" not in sel

    # --- soft-delete exclusion ---

    def test_include_deleted_false_adds_deletedAt_not_exists(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks")
        assert self._has_frag(sel, "deletedAt", {"$exists": False})

    def test_include_deleted_true_omits_deletedAt_fragment(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", include_deleted=True)
        frags = self._get_frags(sel)
        assert not any("deletedAt" in f for f in frags)

    # --- completion exclusion ---

    _NOT_DONE_FRAG = {
        "$or": [{"done": {"$exists": False}}, {"done": {"$ne": True}}]
    }

    def test_include_done_false_adds_not_done_or_for_tasks(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks")
        assert self._NOT_DONE_FRAG in self._get_frags(sel)

    def test_include_done_false_adds_not_done_or_for_categories(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Categories")
        assert self._NOT_DONE_FRAG in self._get_frags(sel)

    def test_include_done_false_adds_not_done_or_for_goals(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Goals")
        assert self._NOT_DONE_FRAG in self._get_frags(sel)

    def test_include_done_false_matches_docs_missing_done_field(self):
        # Regression: Mango {"done": {"$ne": True}} alone excludes docs without
        # a `done` field at all (CouchDB quirk). Imported tasks have no `done`,
        # so the OR-with-$exists wrapper is required to surface them.
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks")
        frags = self._get_frags(sel)
        done_frags = [f for f in frags if "$or" in f and any(
            "done" in clause for clause in f["$or"]
        )]
        assert len(done_frags) == 1
        assert {"done": {"$exists": False}} in done_frags[0]["$or"]

    def test_include_done_true_omits_done_fragment_for_goals(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Goals", include_done=True)
        frags = self._get_frags(sel)
        assert not any("done" in f for f in frags)

    def test_include_done_false_omitted_for_habits(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Habits")
        frags = self._get_frags(sel)
        assert not any("done" in f for f in frags)

    def test_include_done_true_omits_done_fragment(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", include_done=True)
        frags = self._get_frags(sel)
        assert not any("done" in f for f in frags)

    # --- label filters ---

    def test_label_ids_uses_elemMatch_in(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", label_ids=["id1", "id2"])
        assert self._has_frag(sel, "labelIds", {"$elemMatch": {"$in": ["id1", "id2"]}})

    def test_exclude_label_ids_uses_not_elemMatch(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", exclude_label_ids=["id3"])
        assert self._has_frag(sel, "labelIds", {"$not": {"$elemMatch": {"$in": ["id3"]}}})

    def test_both_label_ids_and_exclude_coexist(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", label_ids=["a"], exclude_label_ids=["b"])
        frags = self._get_frags(sel)
        assert any(f.get("labelIds") == {"$elemMatch": {"$in": ["a"]}} for f in frags)
        assert any(f.get("labelIds") == {"$not": {"$elemMatch": {"$in": ["b"]}}} for f in frags)

    # --- has_* existence filters ---

    def test_has_due_date_true(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", has_due_date=True)
        v = self._get_frag(sel, "dueDate")
        assert v["$exists"] is True
        assert None in v["$nin"]
        assert "" in v["$nin"]

    def test_has_due_date_false(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", has_due_date=False)
        or_frags = [f["$or"] for f in self._get_frags(sel) if "$or" in f]
        due_or = [
            o for o in or_frags
            if any("dueDate" in clause for clause in o)
        ]
        assert due_or, f"Expected an $or with a dueDate clause; got {or_frags}"
        keys = [list(clause.keys())[0] for clause in due_or[0]]
        assert "dueDate" in keys

    def test_has_note_true(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", has_note=True)
        v = self._get_frag(sel, "note")
        assert v is not None and v["$exists"] is True

    def test_has_note_false(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", has_note=False)
        frags = self._get_frags(sel)
        assert any("$or" in f for f in frags)

    def test_has_time_estimate_true(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", has_time_estimate=True)
        v = self._get_frag(sel, "timeEstimate")
        assert v is not None and v["$exists"] is True

    def test_has_time_estimate_false(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", has_time_estimate=False)
        frags = self._get_frags(sel)
        assert any("$or" in f for f in frags)

    def test_has_scheduled_day_true_excludes_unassigned(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", has_scheduled_day=True)
        v = self._get_frag(sel, "day")
        assert "unassigned" in v["$nin"]

    def test_has_scheduled_day_false_includes_unassigned_in_empties(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", has_scheduled_day=False)
        # Look for $or fragment that includes unassigned
        frags = self._get_frags(sel)
        or_frags = [f["$or"] for f in frags if "$or" in f]
        found_unassigned = any(
            "unassigned" in clause.get("day", {}).get("$in", [])
            for or_clause in or_frags
            for clause in or_clause
        )
        assert found_unassigned

    # --- date range filters ---

    def test_due_exact(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", due="2026-04-21")
        assert self._has_frag(sel, "dueDate", "2026-04-21")

    def test_due_range_after_only(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", due_after="2026-04-01")
        v = self._get_frag(sel, "dueDate")
        assert v["$gte"] == "2026-04-01"
        assert "$lte" not in v

    def test_due_range_before_only(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", due_before="2026-04-30")
        v = self._get_frag(sel, "dueDate")
        assert v["$lte"] == "2026-04-30"
        assert "$gte" not in v

    def test_due_range_both(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", due_after="2026-04-01", due_before="2026-04-30")
        v = self._get_frag(sel, "dueDate")
        assert v["$gte"] == "2026-04-01"
        assert v["$lte"] == "2026-04-30"

    def test_scheduled_exact(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", scheduled="2026-04-21")
        assert self._has_frag(sel, "day", "2026-04-21")

    def test_scheduled_range(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", scheduled_after="2026-04-01", scheduled_before="2026-04-07")
        v = self._get_frag(sel, "day")
        assert v["$gte"] == "2026-04-01"
        assert v["$lte"] == "2026-04-07"

    def test_done_after_for_tasks_converts_to_epoch_ms(self):
        from amazing_marvin_mcp.db_filters import build_selector
        from amazing_marvin_mcp.db_filters import _date_to_epoch_ms_start
        sel = build_selector("Tasks", done_after="2026-04-14", include_done=True)
        v = self._get_frag(sel, "doneAt")
        expected = _date_to_epoch_ms_start("2026-04-14")
        assert v["$gte"] == expected
        assert isinstance(v["$gte"], int)

    def test_done_before_for_tasks_converts_to_epoch_ms_end_of_day(self):
        from amazing_marvin_mcp.db_filters import build_selector, _date_to_epoch_ms_end
        sel = build_selector("Tasks", done_before="2026-04-14", include_done=True)
        v = self._get_frag(sel, "doneAt")
        assert v["$lte"] == _date_to_epoch_ms_end("2026-04-14")

    def test_done_after_for_categories_uses_string_doneDate(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Categories", done_after="2026-04-14", include_done=True)
        v = self._get_frag(sel, "doneDate")
        assert v["$gte"] == "2026-04-14"

    # --- structural filters ---

    def test_parent_id_appended(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", parent_id="proj123")
        assert self._has_frag(sel, "parentId", "proj123")

    def test_parent_id_unassigned(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", parent_id="unassigned")
        assert self._has_frag(sel, "parentId", "unassigned")

    def test_project_type_project(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Categories", project_type="project")
        assert self._has_frag(sel, "type", "project")

    def test_project_type_category(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Categories", project_type="category")
        frags = self._get_frags(sel)
        or_frags = [f["$or"] for f in frags if "$or" in f]
        # Should have an $or containing type-not-project logic
        assert or_frags

    # --- boolean flags ---

    def test_is_starred_true_uses_in_pattern(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", is_starred=True)
        v = self._get_frag(sel, "isStarred")
        assert "$in" in v
        assert set(v["$in"]) == {True, 1, 2, 3}

    def test_is_starred_false_uses_or_pattern(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", is_starred=False)
        frags = self._get_frags(sel)
        or_frags = [f["$or"] for f in frags if "$or" in f]
        assert any(
            any("isStarred" in clause for clause in or_clause)
            for or_clause in or_frags
        )

    def test_is_frogged_true_tasks_only(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", is_frogged=True)
        v = self._get_frag(sel, "isFrogged")
        assert v is not None and "$in" in v
        assert set(v["$in"]) == {True, 1, 2, 3}

    def test_priority_low_for_categories(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Categories", priority="low")
        assert self._has_frag(sel, "priority", "low")

    def test_priority_mid_not_medium(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Categories", priority="mid")
        assert self._has_frag(sel, "priority", "mid")

    # --- contains ---

    def test_contains_builds_title_note_regex_or(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", contains="refactor")
        frags = self._get_frags(sel)
        or_frags = [f["$or"] for f in frags if "$or" in f]
        assert any(
            any("title" in clause for clause in or_clause)
            and any("note" in clause for clause in or_clause)
            for or_clause in or_frags
        )

    def test_contains_is_case_insensitive(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", contains="Hello")
        frags = self._get_frags(sel)
        or_frags = [f["$or"] for f in frags if "$or" in f]
        assert any(
            any("(?i)" in clause.get("title", {}).get("$regex", "") for clause in or_clause)
            for or_clause in or_frags
        )

    def test_contains_escapes_special_regex_chars(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Tasks", contains="hello.world+")
        or_frags = [f["$or"] for f in self._get_frags(sel) if "$or" in f]
        title_or = [
            o for o in or_frags
            if any("title" in clause for clause in o)
        ]
        assert title_or, "Expected an $or with a title regex clause"
        regex = title_or[0][0]["title"]["$regex"]
        # Special chars should be escaped so they don't act as regex operators
        assert r"\." in regex
        assert r"\+" in regex

    # --- per-doc_type validation ---

    def test_is_frogged_works_for_categories(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Categories", is_frogged=True)
        v = self._get_frag(sel, "isFrogged")
        assert v is not None and "$in" in v
        assert set(v["$in"]) == {True, 1, 2, 3}

    def test_is_starred_works_for_categories(self):
        from amazing_marvin_mcp.db_filters import build_selector
        sel = build_selector("Categories", is_starred=True)
        v = self._get_frag(sel, "isStarred")
        assert v is not None and "$in" in v
        assert set(v["$in"]) == {True, 1, 2, 3}

    def test_is_frogged_raises_for_non_tasks_or_categories(self):
        from amazing_marvin_mcp.db_filters import build_selector
        with pytest.raises(ValueError, match="Tasks/Categories-only"):
            build_selector("Habits", is_frogged=True)

    def test_is_starred_raises_for_habits(self):
        from amazing_marvin_mcp.db_filters import build_selector
        with pytest.raises(ValueError, match="Tasks/Categories-only"):
            build_selector("Habits", is_starred=True)

    def test_priority_raises_for_tasks(self):
        from amazing_marvin_mcp.db_filters import build_selector
        with pytest.raises(ValueError, match="Categories-only"):
            build_selector("Tasks", priority="high")

    def test_priority_error_mentions_is_starred_alternative(self):
        from amazing_marvin_mcp.db_filters import build_selector
        with pytest.raises(ValueError, match="is_starred"):
            build_selector("Tasks", priority="low")

    def test_project_type_raises_for_tasks(self):
        from amazing_marvin_mcp.db_filters import build_selector
        with pytest.raises(ValueError, match="Categories-only"):
            build_selector("Tasks", project_type="project")


class TestQueryDocsTool:
    """Unit tests for execute_query_docs orchestration — mocked api_client.

    Tests the full pipeline: validation, label resolution, selector building,
    find_docs invocation, and response shaping.
    """

    DB_LABELS = [
        {"_id": "lbl_urgent", "title": "urgent"},
        {"_id": "lbl_later", "title": "later"},
        {"_id": "lbl_waiting", "title": "waiting"},
    ]
    SAMPLE_DOCS = [
        {"_id": "t1", "title": "Task One", "db": "Tasks"},
        {"_id": "t2", "title": "Task Two", "db": "Tasks"},
    ]

    def _make_client(
        self,
        docs: list | None = None,
        bookmark: str | None = None,
    ) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        client.get_labels.return_value = self.DB_LABELS
        envelope = {"docs": docs if docs is not None else self.SAMPLE_DOCS}
        if bookmark:
            envelope["bookmark"] = bookmark
        client.find_docs.return_value = envelope
        return client

    def _run(self, client: MagicMock, **kwargs) -> StandardResponse:
        from amazing_marvin_mcp.query import execute_query_docs
        defaults = dict(
            doc_type="Tasks",
            fields=None,
            labels=None,
            exclude_labels=None,
            include_done=False,
            include_deleted=False,
            has_due_date=None,
            has_note=None,
            has_time_estimate=None,
            has_scheduled_day=None,
            contains=None,
            due=None,
            due_before=None,
            due_after=None,
            scheduled=None,
            scheduled_before=None,
            scheduled_after=None,
            done_after=None,
            done_before=None,
            parent_id=None,
            project_type=None,
            is_starred=None,
            is_frogged=None,
            priority=None,
            sort_by=None,
            sort_desc=False,
            limit=500,
            bookmark=None,
            debug=False,
        )
        defaults.update(kwargs)
        import asyncio
        return asyncio.run(execute_query_docs(client, **defaults))

    # --- basic success ---

    def test_returns_docs_on_success(self):
        client = self._make_client()
        result = self._run(client)
        assert result.success is True
        assert result.data["count"] == 2
        assert len(result.data["docs"]) == 2

    def test_calls_find_docs_once(self):
        client = self._make_client()
        self._run(client)
        client.find_docs.assert_called_once()

    # --- field projection passthrough ---

    def test_fields_passed_to_find_docs(self):
        client = self._make_client()
        self._run(client, fields=["title", "dueDate"])
        call_kwargs = client.find_docs.call_args.kwargs
        assert call_kwargs["fields"] == ["title", "dueDate"]

    def test_fields_returned_in_response_data(self):
        client = self._make_client()
        result = self._run(client, fields=["title"])
        assert "fields_returned" in result.data
        assert "_id" in result.data["fields_returned"]

    def test_fields_none_not_in_response_data(self):
        client = self._make_client()
        result = self._run(client)
        assert "fields_returned" not in result.data

    # --- label resolution ---

    def test_label_resolves_to_id_before_find_docs(self):
        client = self._make_client()
        self._run(client, labels=["urgent"])
        client.get_labels.assert_called_once()
        call_kwargs = client.find_docs.call_args.kwargs
        selector = call_kwargs["selector"]
        # The selector (possibly nested in $and) must contain labelIds with the ID
        import json
        serialized = json.dumps(selector)
        assert "lbl_urgent" in serialized

    def test_unknown_label_returns_empty_success_with_message(self):
        client = self._make_client()
        result = self._run(client, labels=["nonexistent"])
        assert result.success is True
        assert result.data["count"] == 0
        assert "nonexistent" in result.summary.text
        client.find_docs.assert_not_called()

    def test_unknown_label_message_lists_available_labels(self):
        client = self._make_client()
        result = self._run(client, labels=["ghost"])
        assert "urgent" in result.summary.text or "later" in result.summary.text

    def test_exclude_labels_resolved_to_ids(self):
        client = self._make_client()
        self._run(client, exclude_labels=["later"])
        import json
        selector = client.find_docs.call_args.kwargs["selector"]
        assert "lbl_later" in json.dumps(selector)

    def test_unknown_exclude_label_returns_empty(self):
        client = self._make_client()
        result = self._run(client, exclude_labels=["phantom"])
        assert result.success is True
        assert result.data["count"] == 0
        client.find_docs.assert_not_called()

    def test_label_resolution_calls_get_labels_once_for_both(self):
        client = self._make_client()
        self._run(client, labels=["urgent"], exclude_labels=["later"])
        client.get_labels.assert_called_once()

    def test_no_labels_does_not_call_get_labels(self):
        client = self._make_client()
        self._run(client)
        client.get_labels.assert_not_called()

    # --- XOR validation ---

    def test_due_and_due_before_raises_validation_error(self):
        client = self._make_client()
        result = self._run(client, due="2026-04-21", due_before="2026-04-30")
        assert result.success is False
        assert "due_before" in result.summary.text or "range" in result.summary.text
        client.find_docs.assert_not_called()

    def test_due_and_due_after_raises_validation_error(self):
        client = self._make_client()
        result = self._run(client, due="2026-04-21", due_after="2026-04-01")
        assert result.success is False
        client.find_docs.assert_not_called()

    def test_scheduled_and_scheduled_before_raises(self):
        client = self._make_client()
        result = self._run(client, scheduled="2026-04-21", scheduled_before="2026-04-30")
        assert result.success is False
        client.find_docs.assert_not_called()

    # --- unknown doc_type ---

    def test_unknown_doc_type_returns_error(self):
        client = self._make_client()
        result = self._run(client, doc_type="NotADocType")
        assert result.success is False
        assert "NotADocType" in result.summary.text
        client.find_docs.assert_not_called()

    # --- per-doc_type validation via build_selector ---

    def test_priority_on_tasks_returns_error(self):
        client = self._make_client()
        result = self._run(client, doc_type="Tasks", priority="high")
        assert result.success is False
        assert "Categories-only" in result.summary.text or "is_starred" in result.summary.text
        client.find_docs.assert_not_called()

    def test_is_frogged_on_habits_returns_error(self):
        client = self._make_client()
        result = self._run(client, doc_type="Habits", is_frogged=True)
        assert result.success is False
        client.find_docs.assert_not_called()

    # --- shortcoming #2 smoke: Categories + fields ---

    def test_categories_with_note_field(self):
        cat_docs = [
            {"_id": "c1", "title": "Work", "note": "Main work category"},
            {"_id": "c2", "title": "Personal", "note": ""},
        ]
        client = self._make_client(docs=cat_docs)
        result = self._run(
            client,
            doc_type="Categories",
            fields=["_id", "title", "note"],
        )
        assert result.success is True
        assert result.data["count"] == 2
        call_kwargs = client.find_docs.call_args.kwargs
        assert call_kwargs["selector"].get("db") == "Categories" or (
            any(f.get("db") == "Categories" for f in call_kwargs["selector"].get("$and", []))
        )

    # --- Tasks post-filter for type field ---

    def test_tasks_post_filter_removes_project_and_category_docs(self):
        mixed = [
            {"_id": "t1", "title": "Task", "db": "Tasks"},
            {"_id": "p1", "title": "Project", "db": "Tasks", "type": "project"},
            {"_id": "c1", "title": "Category", "db": "Tasks", "type": "category"},
        ]
        client = self._make_client(docs=mixed)
        result = self._run(client, doc_type="Tasks")
        ids = [d["_id"] for d in result.data["docs"]]
        assert "t1" in ids
        assert "p1" not in ids
        assert "c1" not in ids

    def test_categories_doc_type_no_post_filter(self):
        cat_docs = [
            {"_id": "c1", "db": "Categories", "type": "category"},
            {"_id": "p1", "db": "Categories", "type": "project"},
        ]
        client = self._make_client(docs=cat_docs)
        result = self._run(client, doc_type="Categories")
        assert result.data["count"] == 2

    # --- sort ---

    def test_sort_by_passed_to_find_docs(self):
        client = self._make_client()
        self._run(client, sort_by="dueDate")
        call_kwargs = client.find_docs.call_args.kwargs
        assert call_kwargs["sort"] == [{"dueDate": "asc"}]

    def test_sort_desc_inverts_direction(self):
        client = self._make_client()
        self._run(client, sort_by="doneAt", sort_desc=True)
        call_kwargs = client.find_docs.call_args.kwargs
        assert call_kwargs["sort"] == [{"doneAt": "desc"}]

    def test_no_sort_by_passes_none(self):
        client = self._make_client()
        self._run(client)
        call_kwargs = client.find_docs.call_args.kwargs
        assert call_kwargs["sort"] is None

    # --- pagination ---

    def test_bookmark_passed_to_find_docs(self):
        client = self._make_client()
        self._run(client, bookmark="tok_abc")
        call_kwargs = client.find_docs.call_args.kwargs
        assert call_kwargs["bookmark"] == "tok_abc"

    def test_bookmark_in_response_when_result_equals_limit(self):
        docs = [{"_id": f"t{i}"} for i in range(10)]
        client = self._make_client(docs=docs, bookmark="next_tok")
        result = self._run(client, limit=10)
        assert result.data.get("bookmark") == "next_tok"

    def test_bookmark_in_response_when_post_filtered_below_limit(self):
        # Regression for the raw_count fix: envelope fills the limit exactly, but
        # post-filtering removes type=project/category docs so len(docs) < limit.
        # The bookmark must still be forwarded because more pages exist upstream.
        docs = [{"_id": f"t{i}"} for i in range(8)] + [
            {"_id": "p1", "type": "project"},
            {"_id": "c1", "type": "category"},
        ]
        client = self._make_client(docs=docs, bookmark="next_tok")
        result = self._run(client, doc_type="Tasks", limit=10)
        assert result.data.get("bookmark") == "next_tok"
        assert result.data["count"] == 8  # post-filter dropped the 2 non-tasks

    def test_no_bookmark_in_response_when_result_under_limit(self):
        docs = [{"_id": "t1"}]
        client = self._make_client(docs=docs, bookmark="tok")
        result = self._run(client, limit=500)  # 1 < 500, so no bookmark
        assert "bookmark" not in result.data

    # --- query_docs NOT registered without DB creds ---

    def test_query_docs_not_registered_without_db_creds(self):
        import asyncio
        from amazing_marvin_mcp.main import mcp
        tools = asyncio.run(mcp.list_tools())
        names = [t.name for t in tools]
        assert "query_docs" not in names


class TestSearchMatcher:
    """Unit tests for search_matcher — pure Python, no I/O."""

    def test_single_token_substring(self):
        from amazing_marvin_mcp.search_matcher import matches
        assert matches("budget", ["Q1 budget review"]) is True
        assert matches("budget", ["Q1 review"]) is False

    def test_case_insensitive(self):
        from amazing_marvin_mcp.search_matcher import matches
        assert matches("BUDGET", ["q1 budget review"]) is True
        assert matches("budget", ["Q1 BUDGET REVIEW"]) is True

    def test_multi_token_implicit_and(self):
        from amazing_marvin_mcp.search_matcher import matches
        # Both tokens hit different haystacks — still matches (any-haystack per token).
        assert matches("Q1 budget", ["Q1 plan", "budget allocation"]) is True
        # Missing one token — no match.
        assert matches("Q1 budget", ["Q1 plan"]) is False

    def test_quoted_phrase_case_sensitive_if_uppercase(self):
        from amazing_marvin_mcp.search_matcher import matches
        # Quoted phrase with uppercase letter is case-sensitive.
        assert matches('"Q1"', ["Q1 review"]) is True
        assert matches('"Q1"', ["q1 review"]) is False

    def test_quoted_phrase_case_insensitive_if_lowercase(self):
        from amazing_marvin_mcp.search_matcher import matches
        assert matches('"hello"', ["Hello world"]) is True
        assert matches('"hello"', ["HELLO world"]) is True

    def test_diacritic_insensitive(self):
        from amazing_marvin_mcp.search_matcher import matches
        assert matches("cafe", ["Café meeting"]) is True
        assert matches("café", ["cafe meeting"]) is True
        assert matches("naive", ["A naïve assumption"]) is True

    def test_empty_query_returns_false(self):
        from amazing_marvin_mcp.search_matcher import matches
        assert matches("", ["anything"]) is False
        assert matches("   ", ["anything"]) is False

    def test_none_or_empty_haystacks_skipped(self):
        from amazing_marvin_mcp.search_matcher import matches
        assert matches("budget", [None, "", "budget plan"]) is True
        assert matches("budget", [None, ""]) is False

    def test_tokenize_query_separates_phrases_and_tokens(self):
        from amazing_marvin_mcp.search_matcher import tokenize_query
        ci, cs = tokenize_query('Q1 budget "exact phrase" "Title"')
        assert "q1" in ci
        assert "budget" in ci
        assert "exact phrase" in ci  # all-lowercase quoted phrase
        assert "Title" in cs  # uppercase quoted phrase is case-sensitive

    def test_longest_token_picks_longest(self):
        from amazing_marvin_mcp.search_matcher import longest_token
        # 'budget' (6) and 'review' (6) tie; either is acceptable.
        assert longest_token("Q1 budget review") in {"budget", "review"}
        # Single distinctly-longest token.
        assert longest_token("Q1 documentation") == "documentation"
        assert longest_token("budget") == "budget"
        assert longest_token("") is None
        assert longest_token("   ") is None


class TestSearchDocsOrchestration:
    """Unit tests for execute_search_docs — mocked api_client, no DB env required."""

    def _make_client(self, *responses) -> MagicMock:
        """Build a client whose find_docs returns the given envelopes in sequence."""
        client = MagicMock()
        client.find_docs.side_effect = list(responses)
        return client

    def _run(self, client: MagicMock, **kwargs) -> StandardResponse:
        from amazing_marvin_mcp.search import execute_search_docs
        defaults = dict(
            doc_types=["Tasks", "Categories"],
            search_notes=True,
            search_subtasks=True,
            include_done=False,
            include_deleted=False,
            fields=None,
            limit=100,
        )
        defaults.update(kwargs)
        return execute_search_docs(client, **defaults)

    def test_title_match(self):
        client = self._make_client(
            {"docs": [{"_id": "t1", "db": "Tasks", "title": "Q1 budget review", "updatedAt": 1000}]},
            {"docs": []},  # Categories
            {"docs": []},  # Tasks subtask scan
        )
        r = self._run(client, query="budget")
        assert r.success
        assert r.data["count"] == 1
        assert r.data["docs"][0]["_id"] == "t1"

    def test_subtask_match(self):
        client = self._make_client(
            {"docs": []},  # Tasks title-prefilter — no hits
            {"docs": []},  # Categories
            {"docs": [{
                "_id": "t2", "db": "Tasks", "title": "Q1 Plan",
                "subtasks": {"s1": {"title": "Review budget"}},
                "updatedAt": 2000,
            }]},
        )
        r = self._run(client, query="budget")
        assert r.data["count"] == 1
        assert r.data["docs"][0]["_id"] == "t2"

    def test_multi_token_and(self):
        # Mango pre-filter returns docs containing 'budget' (the longest token).
        # Python post-filter discards docs that don't also contain 'Q1'.
        client = self._make_client(
            {"docs": [
                {"_id": "a", "db": "Tasks", "title": "Q1 budget", "updatedAt": 5000},
                {"_id": "b", "db": "Tasks", "title": "budget Q2", "updatedAt": 4000},
            ]},
            {"docs": []},
            {"docs": []},
        )
        r = self._run(client, query="Q1 budget")
        assert [d["_id"] for d in r.data["docs"]] == ["a"]

    def test_empty_query_returns_validation_error(self):
        client = self._make_client()
        r = self._run(client, query="")
        assert r.success is False
        assert "query is required" in r.summary.text

    def test_unknown_doc_type_returns_validation_error(self):
        client = self._make_client()
        r = self._run(client, query="x", doc_types=["Bogus"])
        assert r.success is False
        assert "Bogus" in r.summary.text

    def test_search_notes_false_excludes_note_haystack(self):
        # The note contains 'budget' but title doesn't. With search_notes=False,
        # the post-filter should reject it.
        client = self._make_client(
            {"docs": [{
                "_id": "t3", "db": "Tasks", "title": "Q1 review",
                "note": "Allocate budget for Q1", "updatedAt": 1000,
            }]},
            {"docs": []},
            {"docs": []},
        )
        r = self._run(client, query="budget", search_notes=False)
        assert r.data["count"] == 0

    def test_fields_projection_limits_response_keys(self):
        client = self._make_client(
            {"docs": [{
                "_id": "t1", "db": "Tasks", "title": "budget review",
                "note": "extra", "updatedAt": 1000, "createdAt": 500,
            }]},
            {"docs": []},
            {"docs": []},
        )
        r = self._run(client, query="budget", fields=["title"])
        keys = set(r.data["docs"][0].keys())
        assert keys == {"_id", "db", "title"}  # _id and db always retained

    def test_sort_by_updatedAt_desc(self):
        client = self._make_client(
            {"docs": [
                {"_id": "old", "db": "Tasks", "title": "budget v1", "updatedAt": 100},
                {"_id": "new", "db": "Tasks", "title": "budget v2", "updatedAt": 9000},
            ]},
            {"docs": []},
            {"docs": []},
        )
        r = self._run(client, query="budget")
        assert [d["_id"] for d in r.data["docs"]] == ["new", "old"]

    def test_limit_clamped_to_500(self):
        client = self._make_client(
            {"docs": []}, {"docs": []}, {"docs": []},
        )
        r = self._run(client, query="x", limit=10000)
        # Should not raise and should still succeed. Limit is internal; not visible
        # here, but the call should complete.
        assert r.success


class TestSearchDocsRegistration:
    """search_docs is only registered when CouchDB credentials are present."""

    def test_search_docs_not_registered_without_db_creds(self):
        import asyncio
        from amazing_marvin_mcp.main import mcp
        tools = asyncio.run(mcp.list_tools())
        names = [t.name for t in tools]
        assert "search_docs" not in names


class TestCouchDBAccess:
    """Unit tests for CouchDB/Cloudant integration — no live API calls.

    Covers: has_couchdb property, find_docs URL/auth/body/fields,
    _id auto-inclusion, _ensure_indexes idempotency and partial failure.
    """

    DB_URI = "https://account.cloudant.com"
    DB_NAME = "amarvin"
    DB_USER = "user"
    DB_PASS = "pass"

    def _full_client(self) -> MarvinAPIClient:
        return MarvinAPIClient(
            api_key="key",
            db_uri=self.DB_URI,
            db_name=self.DB_NAME,
            db_user=self.DB_USER,
            db_password=self.DB_PASS,
        )

    def _partial_client(self, **override) -> MarvinAPIClient:
        kwargs = dict(
            api_key="key",
            db_uri=self.DB_URI,
            db_name=self.DB_NAME,
            db_user=self.DB_USER,
            db_password=self.DB_PASS,
        )
        kwargs.update(override)
        return MarvinAPIClient(**kwargs)

    def _mock_response(self, payload: Any, status: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        resp.content = b"x"
        resp.json.return_value = payload
        resp.raise_for_status.return_value = None
        return resp

    # --- has_couchdb property ---

    def test_has_couchdb_true_when_all_four_present(self):
        assert self._full_client().has_couchdb is True

    def test_has_couchdb_false_without_uri(self):
        assert self._partial_client(db_uri=None).has_couchdb is False

    def test_has_couchdb_false_without_name(self):
        assert self._partial_client(db_name=None).has_couchdb is False

    def test_has_couchdb_false_without_user(self):
        assert self._partial_client(db_user=None).has_couchdb is False

    def test_has_couchdb_false_without_password(self):
        assert self._partial_client(db_password=None).has_couchdb is False

    def test_has_couchdb_false_when_all_missing(self):
        assert MarvinAPIClient(api_key="key").has_couchdb is False

    # --- find_docs raises when not configured ---

    def test_find_docs_raises_without_credentials(self):
        client = MarvinAPIClient(api_key="key")
        with pytest.raises(ValueError, match="AMAZING_MARVIN_DB"):
            client.find_docs({"db": "Tasks"})

    # --- find_docs: correct URL, auth, body ---

    @patch("requests.post")
    def test_find_docs_posts_to_correct_url(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client._indexes_ensured = True  # skip index creation for this test
        client.find_docs({"db": "Tasks"})
        call_url = mock_post.call_args[0][0]
        assert call_url == f"{self.DB_URI}/{self.DB_NAME}/_find"

    @patch("requests.post")
    def test_find_docs_uses_basic_auth(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client.find_docs({"db": "Tasks"})
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["auth"] == (self.DB_USER, self.DB_PASS)

    @patch("requests.post")
    def test_find_docs_body_contains_selector_and_limit(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client._indexes_ensured = True
        selector = {"db": "Tasks", "done": {"$ne": True}}
        client.find_docs(selector, limit=100)
        body = mock_post.call_args.kwargs["json"]
        assert body["selector"] == selector
        assert body["limit"] == 100

    @patch("requests.post")
    def test_find_docs_default_limit_is_500(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client.find_docs({"db": "Tasks"})
        body = mock_post.call_args.kwargs["json"]
        assert body["limit"] == 500

    # --- find_docs: fields handling ---

    @patch("requests.post")
    def test_find_docs_id_always_included_in_fields(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client.find_docs({"db": "Tasks"}, fields=["title", "dueDate"])
        body = mock_post.call_args.kwargs["json"]
        assert "_id" in body["fields"]
        assert "title" in body["fields"]
        assert "dueDate" in body["fields"]

    @patch("requests.post")
    def test_find_docs_fields_sorted(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client.find_docs({"db": "Tasks"}, fields=["title", "_id", "dueDate"])
        body = mock_post.call_args.kwargs["json"]
        assert body["fields"] == sorted(body["fields"])

    @patch("requests.post")
    def test_find_docs_no_fields_key_when_none(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client.find_docs({"db": "Tasks"})
        body = mock_post.call_args.kwargs["json"]
        assert "fields" not in body

    # --- find_docs: optional body keys ---

    @patch("requests.post")
    def test_find_docs_includes_sort_when_provided(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client._indexes_ensured = True
        sort = [{"dueDate": "asc"}]
        client.find_docs({"db": "Tasks"}, sort=sort)
        body = mock_post.call_args.kwargs["json"]
        assert body["sort"] == sort

    @patch("requests.post")
    def test_find_docs_includes_bookmark_when_provided(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client.find_docs({"db": "Tasks"}, bookmark="tok123")
        body = mock_post.call_args.kwargs["json"]
        assert body["bookmark"] == "tok123"

    @patch("requests.post")
    def test_find_docs_no_sort_key_when_none(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = self._full_client()
        client.find_docs({"db": "Tasks"})
        body = mock_post.call_args.kwargs["json"]
        assert "sort" not in body
        assert "bookmark" not in body

    # --- find_docs: return value ---

    @patch("requests.post")
    def test_find_docs_returns_full_envelope(self, mock_post: MagicMock):
        docs = [{"_id": "t1", "title": "Task 1"}]
        envelope = {"docs": docs, "bookmark": "next_page"}
        mock_post.return_value = self._mock_response(envelope)
        client = self._full_client()
        client._indexes_ensured = True
        result = client.find_docs({"db": "Tasks"})
        assert result["docs"] == docs
        assert result["bookmark"] == "next_page"

    # --- find_docs: trailing slash stripped from db_uri ---

    @patch("requests.post")
    def test_find_docs_strips_trailing_slash_from_uri(self, mock_post: MagicMock):
        mock_post.return_value = self._mock_response({"docs": []})
        client = MarvinAPIClient(
            api_key="key",
            db_uri=f"{self.DB_URI}/",  # trailing slash
            db_name=self.DB_NAME,
            db_user=self.DB_USER,
            db_password=self.DB_PASS,
        )
        client.find_docs({"db": "Tasks"})
        call_url = mock_post.call_args[0][0]
        assert "//" not in call_url.replace("https://", "")


class TestDailyProductivityDbFastPath:
    """Unit tests for the CouchDB fast-path in _get_daily_productivity_db."""

    TODAY = "2026-04-22"

    def _today_ms(self) -> tuple[int, int]:
        from datetime import datetime, timedelta, timezone
        today_dt = datetime.strptime(self.TODAY, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start = int(today_dt.timestamp() * 1000)
        end = int((today_dt + timedelta(days=1)).timestamp() * 1000) - 1
        return start, end

    def _make_client(self, docs: list) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        client.has_couchdb = True
        client.find_docs.return_value = {"docs": docs}
        client.get_projects.return_value = [{"_id": "p1", "title": "P"}]
        client.get_goals.return_value = [{"_id": "g1", "title": "G"}]
        return client

    def test_selector_structure(self):
        client = self._make_client([])
        _get_daily_productivity_db(client, self.TODAY)

        selector = client.find_docs.call_args.kwargs["selector"]
        assert selector["db"] == "Tasks"
        assert selector["deletedAt"] == {"$exists": False}
        assert "$or" in selector
        or_clauses = selector["$or"]
        assert len(or_clauses) == 3
        clause_keys = [set(c.keys()) for c in or_clauses]
        assert {"day"} in clause_keys
        assert any("dueDate" in keys for keys in clause_keys)
        assert any("doneAt" in keys for keys in clause_keys)

    def test_partitioning(self):
        today_start_ms, _ = self._today_ms()
        mid_day_ms = today_start_ms + 3_600_000  # 1 hour into today

        docs = [
            {"_id": "sched", "db": "Tasks", "day": self.TODAY, "done": False},
            {"_id": "over", "db": "Tasks", "dueDate": "2026-04-01", "done": False},
            {"_id": "done", "db": "Tasks", "done": True, "doneAt": mid_day_ms},
            {"_id": "unrelated", "db": "Tasks", "day": "2026-01-01", "done": False},
        ]
        client = self._make_client(docs)
        result = _get_daily_productivity_db(client, self.TODAY)

        assert result["scheduled_today"] == 1
        assert result["overdue_items"] == 1
        assert result["completed_today"] == 1

    def test_api_calls_and_efficiency(self):
        client = self._make_client([])
        result = _get_daily_productivity_db(client, self.TODAY)

        assert result["api_calls_made"] == 3
        assert "CouchDB" in result["efficiency_note"]

    def test_find_docs_and_rest_calls_exactly_once(self):
        client = self._make_client([])
        _get_daily_productivity_db(client, self.TODAY)

        client.find_docs.assert_called_once()
        client.get_projects.assert_called_once()
        client.get_goals.assert_called_once()


class TestGetAllChildrenDb:
    """Unit tests for the BFS CouchDB fast-path in _get_all_children_db."""

    def _make_client(self, side_effect) -> MagicMock:
        client = MagicMock(spec=MarvinAPIClient)
        client.has_couchdb = True
        client.find_docs.side_effect = side_effect
        return client

    def test_bfs_calls_find_docs_per_depth_level(self):
        """3 find_docs calls for a tree with 3 BFS levels: root→[c1,c2], c1→[g1], c1_g1→[]."""
        child1 = {"_id": "c1", "title": "Child1", "type": "project"}
        child2 = {"_id": "c2", "title": "Child2", "type": "category"}
        grandchild1 = {"_id": "g1", "title": "Grandchild1", "type": "project"}

        def side_effect(selector=None, fields=None, limit=None):
            frontier = selector["parentId"]["$in"]
            if "root" in frontier:
                return {"docs": [child1, child2]}
            if "c1" in frontier or "c2" in frontier:
                return {"docs": [grandchild1]}
            return {"docs": []}

        client = self._make_client(side_effect)
        result = _get_all_children_db(client, "root")

        assert client.find_docs.call_count == 3
        assert {d["_id"] for d in result} == {"c1", "c2", "g1"}

    def test_selector_includes_deleted_filter(self):
        def side_effect(selector=None, fields=None, limit=None):
            return {"docs": []}

        client = self._make_client(side_effect)
        _get_all_children_db(client, "root")

        selector = client.find_docs.call_args.kwargs["selector"]
        assert selector["deletedAt"] == {"$exists": False}

    def test_seen_ids_prevents_duplicates(self):
        """A doc returned twice by the mock appears only once in the result."""
        child1 = {"_id": "c1", "title": "Child1", "type": "project"}
        grandchild1 = {"_id": "g1", "title": "Grandchild"}

        def side_effect(selector=None, fields=None, limit=None):
            frontier = selector["parentId"]["$in"]
            if "root" in frontier:
                return {"docs": [child1]}
            if "c1" in frontier:
                return {"docs": [grandchild1, grandchild1]}  # duplicate
            return {"docs": []}

        client = self._make_client(side_effect)
        result = _get_all_children_db(client, "root")

        ids = [d["_id"] for d in result]
        assert ids.count("g1") == 1

    def test_forwards_fields_with_id_and_type_always_included(self):
        """fields=[...] must reach find_docs with _id and type forced in."""

        def side_effect(selector=None, fields=None, limit=None):
            return {"docs": []}

        client = self._make_client(side_effect)
        _get_all_children_db(client, "root", fields=["title"])

        kwargs = client.find_docs.call_args.kwargs
        assert set(kwargs["fields"]) >= {"_id", "type", "title"}

    def test_no_fields_forwards_none_projection(self):
        def side_effect(selector=None, fields=None, limit=None):
            return {"docs": []}

        client = self._make_client(side_effect)
        _get_all_children_db(client, "root")

        kwargs = client.find_docs.call_args.kwargs
        assert kwargs.get("fields") is None

    def test_default_selector_excludes_done(self):
        def side_effect(selector=None, fields=None, limit=None):
            return {"docs": []}

        client = self._make_client(side_effect)
        _get_all_children_db(client, "root")

        selector = client.find_docs.call_args.kwargs["selector"]
        assert selector.get("$or") == [
            {"done": {"$exists": False}},
            {"done": {"$ne": True}},
        ]

    def test_include_done_omits_done_filter(self):
        def side_effect(selector=None, fields=None, limit=None):
            return {"docs": []}

        client = self._make_client(side_effect)
        _get_all_children_db(client, "root", include_done=True)

        selector = client.find_docs.call_args.kwargs["selector"]
        assert "done" not in selector
        assert "$or" not in selector


class TestCreateProjectParentId:
    """parent_id passthrough on create_project / create_project_with_tasks."""

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_create_project_passes_parent_id(self, mock_create: MagicMock) -> None:
        client = MagicMock(spec=MarvinAPIClient)
        client.create_project.return_value = {"_id": "p1", "title": "Test"}
        mock_create.return_value = client
        asyncio.run(create_project_tool(title="Test", parent_id="cat_123"))
        payload = client.create_project.call_args[0][0]
        assert payload["parentId"] == "cat_123"
        assert payload["title"] == "Test"
        assert payload["type"] == "project"

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_create_project_omits_parent_id_when_none(self, mock_create: MagicMock) -> None:
        client = MagicMock(spec=MarvinAPIClient)
        client.create_project.return_value = {"_id": "p1"}
        mock_create.return_value = client
        asyncio.run(create_project_tool(title="Test"))
        payload = client.create_project.call_args[0][0]
        assert "parentId" not in payload

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_create_project_with_tasks_propagates_parent_id(self, mock_create: MagicMock) -> None:
        client = MagicMock(spec=MarvinAPIClient)
        client.create_project.return_value = {"_id": "p1"}
        client.create_task.return_value = {"_id": "t1"}
        mock_create.return_value = client
        asyncio.run(
            create_project_with_tasks_tool(
                project_title="Test",
                task_titles=["t1"],
                parent_id="cat_456",
            )
        )
        payload = client.create_project.call_args[0][0]
        assert payload["parentId"] == "cat_456"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestGoalCreateRequest:
    """The document built for /doc/create must be complete — the endpoint
    applies no defaults of its own."""

    def test_defaults_match_a_client_created_goal(self):
        doc = GoalCreateRequest(title="Learn Rust", has_end=False).to_document()

        assert doc["db"] == "Goals"
        assert doc["title"] == "Learn Rust"
        assert doc["status"] == "pending"
        assert doc["parentId"] == "unassigned"
        assert doc["isStarred"] == 0
        assert doc["labelIds"] == []
        assert doc["hideInDayView"] is False
        assert doc["sections"] == [{"_id": "d", "title": ""}]
        assert doc["fieldUpdates"] == {}
        assert isinstance(doc["createdAt"], int)

    def test_id_is_generated_in_marvin_format(self):
        doc = GoalCreateRequest(title="x", has_end=False).to_document()
        assert len(doc["_id"]) == 20
        # The alphabet omits visually ambiguous characters.
        assert not set(doc["_id"]) & set("01IOUVl")

    def test_ids_are_unique(self):
        ids = {
            GoalCreateRequest(title="x", has_end=False).to_document()["_id"]
            for _ in range(50)
        }
        assert len(ids) == 50

    def test_due_date_is_dropped_for_an_ongoing_goal(self):
        doc = GoalCreateRequest(
            title="x", has_end=False, due_date="2026-12-31"
        ).to_document()
        assert doc["dueDate"] is None

    def test_due_date_is_kept_for_a_goal_with_an_end(self):
        doc = GoalCreateRequest(
            title="x", has_end=True, due_date="2026-12-31"
        ).to_document()
        assert doc["dueDate"] == "2026-12-31"

    def test_explicit_sections_win_over_the_default_phase(self):
        doc = GoalCreateRequest(
            title="x", has_end=False, sections=[{"_id": "a", "title": "Phase 1"}]
        ).to_document()
        assert doc["sections"] == [{"_id": "a", "title": "Phase 1"}]

    def test_empty_title_is_rejected(self):
        with pytest.raises(ValidationError):
            GoalCreateRequest(title="", has_end=False)

    def test_has_end_is_required(self):
        with pytest.raises(ValidationError):
            GoalCreateRequest(title="x")

    def test_lifecycle_states_are_not_creatable(self):
        for status in ("active", "done", "completed", "abandoned"):
            with pytest.raises(ValidationError):
                GoalCreateRequest(title="x", has_end=False, status=status)


class TestCreateGoalTool:
    """The tool must confirm the goal exists before reporting success."""

    @staticmethod
    def _client(stored: Any) -> MagicMock:
        client = MagicMock()
        client.create_goal.return_value = {"ok": True}
        client.get_document.return_value = stored
        return client

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_created_goal_is_read_back(self, mock_create: MagicMock) -> None:
        client = self._client({"_id": "placeholder", "title": "Ship it"})
        mock_create.return_value = client

        # The generated ID is only known once the document is built, so mirror
        # it into the read-back stub.
        def create_goal(document: dict[str, Any]) -> dict[str, Any]:
            client.get_document.return_value = {**document, "_rev": "1-abc"}
            return {"ok": True}

        client.create_goal.side_effect = create_goal

        result = asyncio.run(create_goal_tool(title="Ship it", has_end=False))

        sent = client.create_goal.call_args.args[0]
        assert sent["db"] == "Goals"
        assert sent["title"] == "Ship it"
        client.get_document.assert_called_once_with(sent["_id"])
        assert result.data["created_goal"]["_id"] == sent["_id"]
        assert result.success is True
        assert "Created goal: Ship it" in result.summary.text

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_silent_no_op_is_reported_as_an_error(self, mock_create: MagicMock) -> None:
        """A 200 that stores nothing must not be reported as success."""
        client = self._client({})
        mock_create.return_value = client

        result = asyncio.run(create_goal_tool(title="Ship it", has_end=False))

        assert result.success is False
        assert result.summary.status == "error"

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_invalid_status_does_not_reach_the_api(
        self, mock_create: MagicMock
    ) -> None:
        client = self._client({})
        mock_create.return_value = client

        result = asyncio.run(
            create_goal_tool(title="Ship it", has_end=False, status="done")
        )

        assert result.success is False
        client.create_goal.assert_not_called()


class TestRecurringTaskCreateRequest:
    """The calendar fields must follow the anchor, not the caller."""

    @staticmethod
    def _template(**kwargs: Any) -> dict[str, Any]:
        base = {"title": "Inspection", "type": "repeat year", "repeat_start": "2030-01-07"}
        return RecurringTaskCreateRequest(**{**base, **kwargs}).to_document()

    def test_document_matches_a_client_created_template(self):
        doc = self._template(repeat=2, due_in=45)

        assert doc["db"] == "RecurringTasks"
        assert doc["recurringType"] == "project"
        assert doc["type"] == "repeat year"
        assert doc["repeat"] == 2
        assert doc["repeatStart"] == "2030-01-07"
        assert doc["dueIn"] == 45
        assert doc["echoDays"] == 1
        assert doc["onCount"] == 7
        assert doc["offCount"] == 7
        assert doc["customRecurrence"] == ""
        assert doc["limitToWeekdays"] is False
        assert doc["endDate"] is None
        assert doc["sectionId"] is None
        assert doc["fieldUpdates"] == {}
        assert len(doc["_id"]) == 20

    def test_calendar_fields_are_derived_from_the_anchor(self):
        # 2030-01-07 is a Monday; Marvin counts Sunday as 0.
        doc = self._template()
        assert doc["day"] == 1
        assert doc["date"] == 7
        assert doc["weekDays"] == [1]

    def test_sunday_anchor_is_day_zero(self):
        doc = self._template(repeat_start="2030-01-06")
        assert doc["day"] == 0
        assert doc["weekDays"] == [0]

    def test_descendants_are_passed_through(self):
        child = {"title": "Gas test", "db": "Tasks", "done": False, "_id": "undefined"}
        doc = self._template(descendants=[child])
        assert doc["descendants"] == [child]

    def test_unparented_template_lands_in_the_inbox(self):
        assert self._template()["parentId"] == "unassigned"

    def test_unknown_recurrence_type_is_rejected(self):
        with pytest.raises(ValidationError):
            self._template(type="every other tuesday")

    def test_task_templates_are_not_supported_yet(self):
        with pytest.raises(ValidationError):
            self._template(recurring_type="task")

    def test_malformed_anchor_is_rejected(self):
        with pytest.raises(ValueError):
            self._template(repeat_start="07.01.2030")


class TestCreateRecurringTaskTool:
    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_created_template_is_read_back(self, mock_create: MagicMock) -> None:
        client = MagicMock()

        def create(document: dict[str, Any]) -> dict[str, Any]:
            client.get_document.return_value = {**document, "_rev": "1-abc"}
            return {"ok": True}

        client.create_recurring_task.side_effect = create
        mock_create.return_value = client

        result = asyncio.run(
            create_recurring_task_tool(
                title="Inspection",
                recurrence_type="repeat year",
                repeat_start="2030-01-07",
                repeat=2,
            )
        )

        sent = client.create_recurring_task.call_args.args[0]
        assert sent["db"] == "RecurringTasks"
        assert sent["type"] == "repeat year"
        client.get_document.assert_called_once_with(sent["_id"])
        assert result.success is True
        assert "generate button" in result.summary.text

    @patch("amazing_marvin_mcp.main.create_api_client")
    def test_silent_no_op_is_reported_as_an_error(self, mock_create: MagicMock) -> None:
        client = MagicMock()
        client.create_recurring_task.return_value = {"ok": True}
        client.get_document.return_value = {}
        mock_create.return_value = client

        result = asyncio.run(
            create_recurring_task_tool(
                title="Inspection",
                recurrence_type="repeat year",
                repeat_start="2030-01-07",
            )
        )

        assert result.success is False
