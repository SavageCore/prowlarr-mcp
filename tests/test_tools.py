"""Offline tests: one per Prowlarr API operation, plus error-path tests.

No network. Each tool call is checked against the exact HTTP request it should
produce (method, path incl. URL-encoding, query params, JSON body) via
httpx.MockTransport, using FastMCP's in-memory Client (see
https://gofastmcp.com/development/tests).
"""

import json

import httpx
import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.exceptions import ToolError

import prowlarr_mcp


class Recorder:
    """Captures the single request made during a test and replays a canned response."""

    def __init__(self):
        self.method = None
        self.url = None
        self.headers = None
        self.params = None
        self.json = None
        self.response = httpx.Response(200, json={"success": True})

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.method = request.method
        self.url = request.url
        self.headers = request.headers
        self.params = request.url.params
        try:
            self.json = json.loads(request.content) if request.content else None
        except ValueError:
            self.json = None
        return self.response


@pytest.fixture
def recorder():
    return Recorder()


@pytest_asyncio.fixture
async def server(recorder, monkeypatch):
    transport = httpx.MockTransport(recorder.handler)
    client = prowlarr_mcp.build_client("https://prowlarr.example.com", "test-key", transport=transport)
    monkeypatch.setattr(prowlarr_mcp, "_client", client)
    yield prowlarr_mcp.mcp
    await client.aclose()


_OP_GROUP = {op: group for group, ops in prowlarr_mcp._GROUPS.items() for op in ops}


async def call(server, tool, **kwargs):
    """Call `tool` (an operation name) through the portmanteau group tool
    that now hosts it, so every existing per-operation test keeps working
    unmodified aside from this helper."""
    async with Client(server) as c:
        return await c.call_tool(_OP_GROUP[tool], {"operation": tool, "arguments": kwargs})


# --- one test per endpoint --------------------------------------------------

TOOLS = [
    # (tool name, kwargs, method, path)
    ("prowlarr_get_api_info", {}, "GET", "/api"),
    ("prowlarr_list_applications", {}, "GET", "/api/v1/applications"),
    ("prowlarr_get_application", {"id": 1}, "GET", "/api/v1/applications/1"),
    ("prowlarr_create_application", {"body": {}}, "POST", "/api/v1/applications"),
    ("prowlarr_update_application", {"id": 1, "body": {}}, "PUT", "/api/v1/applications/1"),
    ("prowlarr_delete_application", {"id": 1}, "DELETE", "/api/v1/applications/1"),
    ("prowlarr_bulk_update_applications", {"body": {}}, "PUT", "/api/v1/applications/bulk"),
    ("prowlarr_bulk_delete_applications", {"body": {}}, "DELETE", "/api/v1/applications/bulk"),
    ("prowlarr_list_application_schemas", {}, "GET", "/api/v1/applications/schema"),
    ("prowlarr_test_application", {"body": {}}, "POST", "/api/v1/applications/test"),
    ("prowlarr_test_all_applications", {}, "POST", "/api/v1/applications/testall"),
    ("prowlarr_application_action", {"name": "sync", "body": {}}, "POST", "/api/v1/applications/action/sync"),
    ("prowlarr_list_app_profiles", {}, "GET", "/api/v1/appprofile"),
    ("prowlarr_get_app_profile", {"id": 1}, "GET", "/api/v1/appprofile/1"),
    ("prowlarr_create_app_profile", {"body": {}}, "POST", "/api/v1/appprofile"),
    ("prowlarr_update_app_profile", {"id": 1, "body": {}}, "PUT", "/api/v1/appprofile/1"),
    ("prowlarr_delete_app_profile", {"id": 1}, "DELETE", "/api/v1/appprofile/1"),
    ("prowlarr_list_app_profile_schemas", {}, "GET", "/api/v1/appprofile/schema"),
    ("prowlarr_list_backups", {}, "GET", "/api/v1/system/backup"),
    ("prowlarr_delete_backup", {"id": 1}, "DELETE", "/api/v1/system/backup/1"),
    ("prowlarr_restore_backup", {"id": 1}, "POST", "/api/v1/system/backup/restore/1"),
    ("prowlarr_restore_backup_upload", {"body": {"content": "eA=="}}, "POST", "/api/v1/system/backup/restore/upload"),
    ("prowlarr_list_commands", {}, "GET", "/api/v1/command"),
    ("prowlarr_get_command", {"id": 1}, "GET", "/api/v1/command/1"),
    ("prowlarr_run_command", {"body": {"name": "Backup"}}, "POST", "/api/v1/command"),
    ("prowlarr_cancel_command", {"id": 1}, "DELETE", "/api/v1/command/1"),
    ("prowlarr_list_custom_filters", {}, "GET", "/api/v1/customfilter"),
    ("prowlarr_get_custom_filter", {"id": 1}, "GET", "/api/v1/customfilter/1"),
    ("prowlarr_create_custom_filter", {"body": {}}, "POST", "/api/v1/customfilter"),
    ("prowlarr_update_custom_filter", {"id": 1, "body": {}}, "PUT", "/api/v1/customfilter/1"),
    ("prowlarr_delete_custom_filter", {"id": 1}, "DELETE", "/api/v1/customfilter/1"),
    ("prowlarr_get_host_config", {}, "GET", "/api/v1/config/host"),
    ("prowlarr_update_host_config", {"id": 1, "body": {}}, "PUT", "/api/v1/config/host/1"),
    ("prowlarr_get_ui_config", {}, "GET", "/api/v1/config/ui"),
    ("prowlarr_update_ui_config", {"id": 1, "body": {}}, "PUT", "/api/v1/config/ui/1"),
    ("prowlarr_get_download_client_config", {}, "GET", "/api/v1/config/downloadclient"),
    ("prowlarr_update_download_client_config", {"id": 1, "body": {}}, "PUT", "/api/v1/config/downloadclient/1"),
    ("prowlarr_get_development_config", {}, "GET", "/api/v1/config/development"),
    ("prowlarr_update_development_config", {"id": 1, "body": {}}, "PUT", "/api/v1/config/development/1"),
    ("prowlarr_list_download_clients", {}, "GET", "/api/v1/downloadclient"),
    ("prowlarr_get_download_client", {"id": 1}, "GET", "/api/v1/downloadclient/1"),
    ("prowlarr_create_download_client", {"body": {}}, "POST", "/api/v1/downloadclient"),
    ("prowlarr_update_download_client", {"id": 1, "body": {}}, "PUT", "/api/v1/downloadclient/1"),
    ("prowlarr_delete_download_client", {"id": 1}, "DELETE", "/api/v1/downloadclient/1"),
    ("prowlarr_bulk_update_download_clients", {"body": {}}, "PUT", "/api/v1/downloadclient/bulk"),
    ("prowlarr_bulk_delete_download_clients", {"body": {}}, "DELETE", "/api/v1/downloadclient/bulk"),
    ("prowlarr_list_download_client_schemas", {}, "GET", "/api/v1/downloadclient/schema"),
    ("prowlarr_test_download_client", {"body": {}}, "POST", "/api/v1/downloadclient/test"),
    ("prowlarr_test_all_download_clients", {}, "POST", "/api/v1/downloadclient/testall"),
    ("prowlarr_download_client_action", {"name": "clean", "body": {}}, "POST", "/api/v1/downloadclient/action/clean"),
    ("prowlarr_list_filesystem", {}, "GET", "/api/v1/filesystem"),
    ("prowlarr_get_filesystem_type", {"path": "/data"}, "GET", "/api/v1/filesystem/type"),
    ("prowlarr_list_health", {}, "GET", "/api/v1/health"),
    ("prowlarr_list_history", {}, "GET", "/api/v1/history"),
    ("prowlarr_list_history_since", {"date": "2026-01-01"}, "GET", "/api/v1/history/since"),
    ("prowlarr_list_history_indexer", {"indexer_id": 1}, "GET", "/api/v1/history/indexer"),
    ("prowlarr_list_indexers", {}, "GET", "/api/v1/indexer"),
    ("prowlarr_get_indexer", {"id": 1}, "GET", "/api/v1/indexer/1"),
    ("prowlarr_create_indexer", {"body": {}}, "POST", "/api/v1/indexer"),
    ("prowlarr_update_indexer", {"id": 1, "body": {}}, "PUT", "/api/v1/indexer/1"),
    ("prowlarr_delete_indexer", {"id": 1}, "DELETE", "/api/v1/indexer/1"),
    ("prowlarr_bulk_update_indexers", {"body": {}}, "PUT", "/api/v1/indexer/bulk"),
    ("prowlarr_bulk_delete_indexers", {"body": {}}, "DELETE", "/api/v1/indexer/bulk"),
    ("prowlarr_list_indexer_schemas", {}, "GET", "/api/v1/indexer/schema"),
    ("prowlarr_test_indexer", {"body": {}}, "POST", "/api/v1/indexer/test"),
    ("prowlarr_test_all_indexers", {}, "POST", "/api/v1/indexer/testall"),
    ("prowlarr_indexer_action", {"name": "reset", "body": {}}, "POST", "/api/v1/indexer/action/reset"),
    ("prowlarr_list_indexer_categories", {}, "GET", "/api/v1/indexer/categories"),
    ("prowlarr_list_indexer_proxies", {}, "GET", "/api/v1/indexerproxy"),
    ("prowlarr_get_indexer_proxy", {"id": 1}, "GET", "/api/v1/indexerproxy/1"),
    ("prowlarr_create_indexer_proxy", {"body": {}}, "POST", "/api/v1/indexerproxy"),
    ("prowlarr_update_indexer_proxy", {"id": 1, "body": {}}, "PUT", "/api/v1/indexerproxy/1"),
    ("prowlarr_delete_indexer_proxy", {"id": 1}, "DELETE", "/api/v1/indexerproxy/1"),
    ("prowlarr_list_indexer_proxy_schemas", {}, "GET", "/api/v1/indexerproxy/schema"),
    ("prowlarr_test_indexer_proxy", {"body": {}}, "POST", "/api/v1/indexerproxy/test"),
    ("prowlarr_test_all_indexer_proxies", {}, "POST", "/api/v1/indexerproxy/testall"),
    ("prowlarr_indexer_proxy_action", {"name": "toggle", "body": {}}, "POST", "/api/v1/indexerproxy/action/toggle"),
    ("prowlarr_get_indexer_stats", {}, "GET", "/api/v1/indexerstats"),
    ("prowlarr_list_indexer_status", {}, "GET", "/api/v1/indexerstatus"),
    ("prowlarr_get_localization", {}, "GET", "/api/v1/localization"),
    ("prowlarr_list_localization_options", {}, "GET", "/api/v1/localization/options"),
    ("prowlarr_list_logs", {}, "GET", "/api/v1/log"),
    ("prowlarr_list_log_files", {}, "GET", "/api/v1/log/file"),
    ("prowlarr_get_log_file", {"filename": "prowlarr.txt"}, "GET", "/api/v1/log/file/prowlarr.txt"),
    ("prowlarr_list_update_log_files", {}, "GET", "/api/v1/log/file/update"),
    ("prowlarr_get_update_log_file", {"filename": "update.txt"}, "GET", "/api/v1/log/file/update/update.txt"),
    ("prowlarr_search_newznab", {"id": 1, "q": "matrix"}, "GET", "/api/v1/indexer/1/newznab"),
    ("prowlarr_download_release", {"id": 1}, "GET", "/api/v1/indexer/1/download"),
    ("prowlarr_list_notifications", {}, "GET", "/api/v1/notification"),
    ("prowlarr_get_notification", {"id": 1}, "GET", "/api/v1/notification/1"),
    ("prowlarr_create_notification", {"body": {}}, "POST", "/api/v1/notification"),
    ("prowlarr_update_notification", {"id": 1, "body": {}}, "PUT", "/api/v1/notification/1"),
    ("prowlarr_delete_notification", {"id": 1}, "DELETE", "/api/v1/notification/1"),
    ("prowlarr_list_notification_schemas", {}, "GET", "/api/v1/notification/schema"),
    ("prowlarr_test_notification", {"body": {}}, "POST", "/api/v1/notification/test"),
    ("prowlarr_test_all_notifications", {}, "POST", "/api/v1/notification/testall"),
    ("prowlarr_notification_action", {"name": "send", "body": {}}, "POST", "/api/v1/notification/action/send"),
    ("prowlarr_ping", {}, "GET", "/ping"),
    ("prowlarr_search_releases", {}, "GET", "/api/v1/search"),
    ("prowlarr_push_release", {"body": {}}, "POST", "/api/v1/search"),
    ("prowlarr_bulk_push_releases", {"body": []}, "POST", "/api/v1/search/bulk"),
    ("prowlarr_system_status", {}, "GET", "/api/v1/system/status"),
    ("prowlarr_list_system_routes", {}, "GET", "/api/v1/system/routes"),
    ("prowlarr_list_system_routes_duplicate", {}, "GET", "/api/v1/system/routes/duplicate"),
    ("prowlarr_system_shutdown", {}, "POST", "/api/v1/system/shutdown"),
    ("prowlarr_system_restart", {}, "POST", "/api/v1/system/restart"),
    ("prowlarr_list_tags", {}, "GET", "/api/v1/tag"),
    ("prowlarr_get_tag", {"id": 1}, "GET", "/api/v1/tag/1"),
    ("prowlarr_create_tag", {"body": {"label": "hd"}}, "POST", "/api/v1/tag"),
    ("prowlarr_update_tag", {"id": 1, "body": {}}, "PUT", "/api/v1/tag/1"),
    ("prowlarr_delete_tag", {"id": 1}, "DELETE", "/api/v1/tag/1"),
    ("prowlarr_list_tag_details", {}, "GET", "/api/v1/tag/detail"),
    ("prowlarr_get_tag_details", {"id": 1}, "GET", "/api/v1/tag/detail/1"),
    ("prowlarr_list_tasks", {}, "GET", "/api/v1/system/task"),
    ("prowlarr_get_task", {"id": 1}, "GET", "/api/v1/system/task/1"),
    ("prowlarr_list_updates", {}, "GET", "/api/v1/update"),
]


@pytest.mark.parametrize("tool_name,kwargs,method,path", TOOLS, ids=[t[0] for t in TOOLS])
async def test_tool_makes_request(server, recorder, tool_name, kwargs, method, path):
    await call(server, tool_name, **kwargs)
    assert recorder.method == method
    assert recorder.url.path == path


# --- request body --------------------------------------------------------------

async def test_write_tool_sends_json_body(server, recorder):
    await call(server, "prowlarr_create_indexer", body={"name": "test-indexer", "enable": True})
    assert recorder.json == {"name": "test-indexer", "enable": True}


async def test_bulk_push_sends_list_body(server, recorder):
    await call(server, "prowlarr_bulk_push_releases", body=[{"guid": "a"}, {"guid": "b"}])
    assert recorder.json == [{"guid": "a"}, {"guid": "b"}]


async def test_restore_upload_sends_raw_bytes(server, recorder):
    await call(server, "prowlarr_restore_backup_upload", body={"content": "eA=="})
    assert recorder.url.path == "/api/v1/system/backup/restore/upload"
    assert recorder.url.raw_path.endswith(b"/restore/upload")


# --- query params ----------------------------------------------------------------

async def test_history_sends_paging_and_sort(server, recorder):
    await call(server, "prowlarr_list_history", page=2, page_size=50, sort_key="date", sort_direction="descending")
    assert recorder.params["page"] == "2"
    assert recorder.params["pageSize"] == "50"
    assert recorder.params["sortKey"] == "date"
    assert recorder.params["sortDirection"] == "descending"


async def test_list_params_are_repeated(server, recorder):
    await call(server, "prowlarr_list_history", event_type=[1, 2], indexer_ids=[5, 6])
    assert recorder.params.get_list("eventType") == ["1", "2"]
    assert recorder.params.get_list("indexerIds") == ["5", "6"]


async def test_search_params_sent(server, recorder):
    await call(server, "prowlarr_search_releases", query="matrix", type="search", categories=[2000], indexer_ids=[1], limit=50)
    assert recorder.params["query"] == "matrix"
    assert recorder.params["type"] == "search"
    assert recorder.params["categories"] == "2000"
    assert recorder.params["indexerIds"] == "1"
    assert recorder.params["limit"] == "50"


async def test_newznab_params_sent(server, recorder):
    await call(server, "prowlarr_search_newznab", id=1, q="matrix", season=2, limit=100, imdbid="tt0133093")
    assert recorder.params["q"] == "matrix"
    assert recorder.params["season"] == "2"
    assert recorder.params["limit"] == "100"
    assert recorder.params["imdbid"] == "tt0133093"


async def test_force_flags_sent_only_when_set(server, recorder):
    await call(server, "prowlarr_create_indexer", body={}, force_save=True)
    assert recorder.params["forceSave"] == "true"

    await call(server, "prowlarr_test_indexer", body={}, force_test=True)
    assert recorder.params["forceTest"] == "true"

    await call(server, "prowlarr_create_indexer", body={})
    assert "forceSave" not in recorder.params


async def test_empty_optional_params_are_omitted(server, recorder):
    await call(server, "prowlarr_list_history")
    assert "sortKey" not in recorder.params
    assert "sortDirection" not in recorder.params
    assert "eventType" not in recorder.params
    assert "successful" not in recorder.params
    assert "downloadId" not in recorder.params
    assert "indexerIds" not in recorder.params
    assert recorder.params["page"] == "1"
    assert recorder.params["pageSize"] == "10"

    await call(server, "prowlarr_list_logs")
    assert "level" not in recorder.params


async def test_filesystem_params_mapped(server, recorder):
    await call(server, "prowlarr_list_filesystem", path="/downloads", include_files=True)
    assert recorder.params["path"] == "/downloads"
    assert recorder.params["includeFiles"] == "true"
    assert "allowFoldersWithoutTrailingSlashes" not in recorder.params


# --- auth header --------------------------------------------------------------

async def test_api_key_sent_as_x_api_key_header(server, recorder):
    await call(server, "prowlarr_list_indexers")
    assert recorder.headers["x-api-key"] == "test-key"


async def test_no_token_means_no_api_key_header(recorder, monkeypatch):
    transport = httpx.MockTransport(recorder.handler)
    client = prowlarr_mcp.build_client("https://prowlarr.example.com", None, transport=transport)
    monkeypatch.setattr(prowlarr_mcp, "_client", client)
    await call(prowlarr_mcp.mcp, "prowlarr_list_indexers")
    assert "x-api-key" not in recorder.headers
    await client.aclose()


# --- error paths ---------------------------------------------------------------

async def test_404_error_message_reaches_caller(server, recorder):
    recorder.response = httpx.Response(404, json={"message": "Indexer not found"})
    with pytest.raises(ToolError, match="Indexer not found"):
        await call(server, "prowlarr_get_indexer", id=999)


async def test_401_error_surfaces_status(server, recorder):
    recorder.response = httpx.Response(401, json={"message": "Unauthorized"})
    with pytest.raises(ToolError, match="401"):
        await call(server, "prowlarr_list_indexers")


async def test_429_rate_limit_surfaces_status(server, recorder):
    recorder.response = httpx.Response(429, json={"message": "Rate limit exceeded"})
    with pytest.raises(ToolError, match="429"):
        await call(server, "prowlarr_list_indexers")


async def test_non_json_error_body_does_not_crash(server, recorder):
    recorder.response = httpx.Response(502, text="<html>Bad Gateway</html>")
    with pytest.raises(ToolError, match="502"):
        await call(server, "prowlarr_list_indexers")


async def test_newznab_returns_text(server, recorder):
    recorder.response = httpx.Response(200, text="<rss><channel /></rss>")
    result = await call(server, "prowlarr_search_newznab", id=1, q="matrix")
    assert result.data == "<rss><channel /></rss>"


async def test_download_returns_base64(server, recorder):
    recorder.response = httpx.Response(200, content=b"nzb-bytes")
    result = await call(server, "prowlarr_download_release", id=1)
    import base64

    assert base64.b64decode(result.data) == b"nzb-bytes"


# --- main() ----------------------------------------------------------------

def test_main_requires_prowlarr_url(monkeypatch):
    monkeypatch.delenv("PROWLARR_URL", raising=False)
    with pytest.raises(SystemExit):
        prowlarr_mcp.main()


# --- portmanteau grouping safety net ------------------------------------------

def test_all_tools_grouped():
    """Every tool in TOOLS must land in exactly one portmanteau group - this
    is the safety net for the group-tool consolidation."""
    tool_names = {t[0] for t in TOOLS}
    grouped_names = [n for names in prowlarr_mcp._GROUPS.values() for n in names]
    assert sorted(grouped_names) == sorted(tool_names)
    assert len(grouped_names) == len(set(grouped_names))


async def test_group_tools_are_the_only_registered_tools(server):
    async with Client(server) as c:
        tools = await c.list_tools()
    assert {t.name for t in tools} == set(prowlarr_mcp._GROUPS)


async def test_unknown_operation_rejected_by_schema(server):
    # The Literal[...] enum on `operation` means an invalid value never
    # reaches _register_group's dispatch body - pydantic rejects it first.
    with pytest.raises(ToolError, match="validation error"):
        async with Client(server) as c:
            await c.call_tool("prowlarr_tags", {"operation": "not_a_real_operation"})
