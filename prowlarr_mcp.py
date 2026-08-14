"""MCP server exposing Prowlarr's API v1 (https://github.com/Prowlarr/Prowlarr) as tools.

Full API coverage (see README for the operation list), exposed as 10
resource-scoped *portmanteau* tools instead of one tool per operation. Each
portmanteau tool (e.g. prowlarr_indexers, prowlarr_applications) takes an
`operation` enum plus an `arguments` dict; see AGENTS.md for the rationale
(a 100+-tool server blows the MCP context budget on session start).

Auth is the X-Api-Key header -- generate the key in Prowlarr Settings >
General. A group tool is marked readOnlyHint=True only when every operation
in it was originally a GET tool; mixed groups carry no hints. Write
operations take a `body` JSON object; list a resource's schema first to
discover its fields.

Paths given to _req that already start with `/` (like /api and /ping) are used
verbatim against the server root; everything else is prefixed with /api/v1.
Every function below is still a plain async endpoint wrapper - `_GROUPS` near
the bottom buckets them by resource and `_register_group` wraps each bucket
in one dispatching MCP tool; the functions themselves are not tools anymore.
"""

import base64
import inspect
import os
import sys
from typing import Any, Literal
from urllib.parse import quote

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

READONLY = ToolAnnotations(readOnlyHint=True)
DESTRUCTIVE = ToolAnnotations(destructiveHint=True)

# Prowlarr responses are plain JSON. `dict[str, Any]` (not bare `Any`) matters
# here: FastMCP needs a concrete schema to build MCP structured content, and
# skips that step entirely for an `Any` return type -- which silently makes
# Client.call_tool's `.data` come back None for any tool returning a JSON array.
# Verified against fastmcp 3.4.6.
JSONObj = dict[str, Any]
JSONVal = JSONObj | list[Any]

API_V1 = "/api/v1"

mcp = FastMCP("prowlarr-mcp")

_client: httpx.AsyncClient | None = None


def build_client(
    base_url: str, api_key: str | None, transport: httpx.BaseTransport | None = None
) -> httpx.AsyncClient:
    headers = {"X-Api-Key": api_key} if api_key else {}
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"), headers=headers, transport=transport
    )


async def _req_raw(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: JSONObj | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    assert _client is not None, "client not configured"
    full = path if path.startswith("/") else f"{API_V1}/{path}"
    r = await _client.request(method, full, params=params, json=body, content=content)
    if r.status_code >= 400:
        msg = _error_message(r)
        raise ToolError(f"Prowlarr API {r.status_code}: {msg}")
    return r


async def _req(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: JSONObj | None = None,
    content: bytes | None = None,
) -> JSONVal:
    r = await _req_raw(method, path, params=params, body=body, content=content)
    if not r.content:
        return {"success": True}
    try:
        return r.json()
    except ValueError:
        return {"content": r.text}


async def _req_text(path: str, params: dict[str, Any] | None = None) -> str:
    r = await _req_raw("GET", path, params=params)
    return r.text


async def _req_b64(path: str, params: dict[str, Any] | None = None) -> str:
    r = await _req_raw("GET", path, params=params)
    return base64.b64encode(r.content).decode("ascii")


def _id(id: int) -> str:
    return quote(str(id))


def _omit(params: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose values are empty/None so the API's defaults apply."""
    return {k: v for k, v in params.items() if v not in ("", None)}


def _error_message(r: httpx.Response) -> str:
    """Extract a human-readable message from a non-2xx response.

    Prowlarr returns validation failures as a JSON array of error objects
    (e.g. [{"propertyName": ..., "errorMessage": ...}]) rather than a single
    {"message": ...} dict, so handle dict, list, and raw text."""
    try:
        data = r.json()
    except ValueError:
        return r.text
    if isinstance(data, dict):
        for key in ("message", "errorMessage", "error"):
            if key in data:
                return str(data[key])
        return str(data)
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, dict):
                prop = item.get("propertyName") or item.get("property")
                err = item.get("errorMessage") or item.get("message")
                if err:
                    lines.append(f"{prop + ': ' if prop else ''}{err}")
            elif item is not None:
                lines.append(str(item))
        return "; ".join(lines) if lines else str(data)
    return str(data)


# --- ApiInfo ------------------------------------------------------------------


async def prowlarr_get_api_info() -> JSONObj:
    """Report the current API version, the API key hash (last 4 chars), and
    deprecated endpoints. Useful for confirming connectivity and version."""
    return await _req("GET", "/api")


# --- Applications --------------------------------------------------------------


async def prowlarr_list_applications() -> JSONVal:
    """List all configured applications (Lidarr/Radarr/Sonarr/Readarr etc.)
    that indexers are synced to."""
    return await _req("GET", "applications")


async def prowlarr_get_application(id: int) -> JSONObj:
    """Get a single application by id."""
    return await _req("GET", f"applications/{_id(id)}")


async def prowlarr_create_application(
    body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Create an application. Pass the full ApplicationResource as body (fetch
    prowlarr_list_application_schemas for available providers and fields).
    force_save bypasses validation."""
    return await _req("POST", "applications", _omit({"forceSave": force_save}), body)


async def prowlarr_update_application(
    id: int, body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Update an application by id. body is the ApplicationResource to save."""
    return await _req(
        "PUT", f"applications/{_id(id)}", _omit({"forceSave": force_save}), body
    )


async def prowlarr_delete_application(id: int) -> JSONObj:
    """Delete an application by id."""
    return await _req("DELETE", f"applications/{_id(id)}")


async def prowlarr_bulk_update_applications(body: JSONObj) -> JSONObj:
    """Bulk-edit applications. body is an ApplicationBulkResource with ids plus
    optional tags/applyTags/enable to apply to all of them."""
    return await _req("PUT", "applications/bulk", body=body)


async def prowlarr_bulk_delete_applications(body: JSONObj) -> JSONObj:
    """Bulk-delete applications. body is an ApplicationBulkResource with ids."""
    return await _req("DELETE", "applications/bulk", body=body)


async def prowlarr_list_application_schemas() -> JSONVal:
    """List application provider schemas (what each application implementation
    accepts). Read this before creating/updating an application."""
    return await _req("GET", "applications/schema")


async def prowlarr_test_application(
    body: JSONObj, force_test: bool | None = None
) -> JSONObj:
    """Test an application connection without saving it. body is the
    ApplicationResource to test. force_test skips the cached-test check."""
    return await _req(
        "POST", "applications/test", _omit({"forceTest": force_test}), body
    )


async def prowlarr_test_all_applications() -> JSONObj:
    """Test every configured application."""
    return await _req("POST", "applications/testall")


async def prowlarr_application_action(name: str, body: JSONObj) -> JSONObj:
    """Run a named action on an application (e.g. sync indexers). body is the
    ApplicationResource to act on."""
    return await _req("POST", f"applications/action/{_id(name)}", body=body)


# --- App Profiles ---------------------------------------------------------------


async def prowlarr_list_app_profiles() -> JSONVal:
    """List app profiles (named groups of applications, added in Prowlarr 1.19+)."""
    return await _req("GET", "appprofile")


async def prowlarr_get_app_profile(id: int) -> JSONObj:
    """Get a single app profile by id."""
    return await _req("GET", f"appprofile/{_id(id)}")


async def prowlarr_create_app_profile(body: JSONObj) -> JSONObj:
    """Create an app profile. body is an AppProfileResource (name, appIds, and
    per-app settings)."""
    return await _req("POST", "appprofile", body=body)


async def prowlarr_update_app_profile(id: int, body: JSONObj) -> JSONObj:
    """Update an app profile by id."""
    return await _req("PUT", f"appprofile/{_id(id)}", body=body)


async def prowlarr_delete_app_profile(id: int) -> JSONObj:
    """Delete an app profile by id."""
    return await _req("DELETE", f"appprofile/{_id(id)}")


async def prowlarr_list_app_profile_schemas() -> JSONVal:
    """List app profile schemas describing the structure of each app profile
    form section."""
    return await _req("GET", "appprofile/schema")


# --- Backups -------------------------------------------------------------------


async def prowlarr_list_backups() -> JSONVal:
    """List scheduled, manual, and update backups available on the server."""
    return await _req("GET", "system/backup")


async def prowlarr_delete_backup(id: int) -> JSONObj:
    """Delete a backup file by id."""
    return await _req("DELETE", f"system/backup/{_id(id)}")


async def prowlarr_restore_backup(id: int) -> JSONObj:
    """Restore a backup by id. Triggers a restore on the next restart."""
    return await _req("POST", f"system/backup/restore/{_id(id)}")


async def prowlarr_restore_backup_upload(body: JSONObj) -> JSONObj:
    """Restore a user-uploaded backup file. body must be
    {"content": "<base64-encoded backup bytes>", "filename": "backup.zip"}."""
    payload = base64.b64decode(body["content"])
    return await _req("POST", "system/backup/restore/upload", content=payload)


# --- Commands -------------------------------------------------------------------


async def prowlarr_list_commands() -> JSONVal:
    """List all tasks currently queued or running."""
    return await _req("GET", "command")


async def prowlarr_get_command(id: int) -> JSONObj:
    """Get a single task by id."""
    return await _req("GET", f"command/{_id(id)}")


async def prowlarr_run_command(body: JSONObj) -> JSONObj:
    """Run a command. body is a CommandResource with a `name` (e.g.
    ApplicationIndexerSync, IndexerRssSync, RefreshIndexerProxy,
    CheckForUpdate, Backup) plus optional command-specific fields."""
    return await _req("POST", "command", body=body)


async def prowlarr_cancel_command(id: int) -> JSONObj:
    """Cancel a queued or running task by id."""
    return await _req("DELETE", f"command/{_id(id)}")


# --- Custom Filters --------------------------------------------------------------


async def prowlarr_list_custom_filters() -> JSONVal:
    """List user-defined custom filters used to narrow indexer search results."""
    return await _req("GET", "customfilter")


async def prowlarr_get_custom_filter(id: int) -> JSONObj:
    """Get a single custom filter by id."""
    return await _req("GET", f"customfilter/{_id(id)}")


async def prowlarr_create_custom_filter(body: JSONObj) -> JSONObj:
    """Create a custom filter. body is a CustomFilterResource with a name,
    label, type (e.g. release), and filters array."""
    return await _req("POST", "customfilter", body=body)


async def prowlarr_update_custom_filter(id: int, body: JSONObj) -> JSONObj:
    """Update a custom filter by id."""
    return await _req("PUT", f"customfilter/{_id(id)}", body=body)


async def prowlarr_delete_custom_filter(id: int) -> JSONObj:
    """Delete a custom filter by id."""
    return await _req("DELETE", f"customfilter/{_id(id)}")


# --- Config: Host / UI / DownloadClient / Development ------------------------------


async def prowlarr_get_host_config() -> JSONObj:
    """Get the host configuration (binding, port, SSL, authentication, API key,
    proxy settings, update/backup settings)."""
    return await _req("GET", "config/host")


async def prowlarr_update_host_config(id: int, body: JSONObj) -> JSONObj:
    """Update the host configuration by id. body is a HostConfigResource."""
    return await _req("PUT", f"config/host/{_id(id)}", body=body)


async def prowlarr_get_ui_config() -> JSONObj:
    """Get the UI configuration (language, theme, first-day-of-week, etc.)."""
    return await _req("GET", "config/ui")


async def prowlarr_update_ui_config(id: int, body: JSONObj) -> JSONObj:
    """Update the UI configuration by id."""
    return await _req("PUT", f"config/ui/{_id(id)}", body=body)


async def prowlarr_get_download_client_config() -> JSONObj:
    """Get the download client config (which clients get grabs from indexers)."""
    return await _req("GET", "config/downloadclient")


async def prowlarr_update_download_client_config(id: int, body: JSONObj) -> JSONObj:
    """Update the download client config by id."""
    return await _req("PUT", f"config/downloadclient/{_id(id)}", body=body)


async def prowlarr_get_development_config() -> JSONObj:
    """Get the development config (debug/logging toggles)."""
    return await _req("GET", "config/development")


async def prowlarr_update_development_config(id: int, body: JSONObj) -> JSONObj:
    """Update the development config by id."""
    return await _req("PUT", f"config/development/{_id(id)}", body=body)


# --- Download Clients --------------------------------------------------------------


async def prowlarr_list_download_clients() -> JSONVal:
    """List all configured download clients."""
    return await _req("GET", "downloadclient")


async def prowlarr_get_download_client(id: int) -> JSONObj:
    """Get a single download client by id."""
    return await _req("GET", f"downloadclient/{_id(id)}")


async def prowlarr_create_download_client(
    body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Create a download client. body is a DownloadClientResource (fetch
    prowlarr_list_download_client_schemas for providers and fields).
    force_save bypasses validation."""
    return await _req("POST", "downloadclient", _omit({"forceSave": force_save}), body)


async def prowlarr_update_download_client(
    id: int, body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Update a download client by id."""
    return await _req(
        "PUT", f"downloadclient/{_id(id)}", _omit({"forceSave": force_save}), body
    )


async def prowlarr_delete_download_client(id: int) -> JSONObj:
    """Delete a download client by id."""
    return await _req("DELETE", f"downloadclient/{_id(id)}")


async def prowlarr_bulk_update_download_clients(body: JSONObj) -> JSONObj:
    """Bulk-edit download clients. body is a DownloadClientBulkResource with
    ids plus optional tags/applyTags/enable."""
    return await _req("PUT", "downloadclient/bulk", body=body)


async def prowlarr_bulk_delete_download_clients(body: JSONObj) -> JSONObj:
    """Bulk-delete download clients. body is a DownloadClientBulkResource."""
    return await _req("DELETE", "downloadclient/bulk", body=body)


async def prowlarr_list_download_client_schemas() -> JSONVal:
    """List download client provider schemas. Read this before creating or
    updating a download client."""
    return await _req("GET", "downloadclient/schema")


async def prowlarr_test_download_client(
    body: JSONObj, force_test: bool | None = None
) -> JSONObj:
    """Test a download client connection without saving it."""
    return await _req(
        "POST", "downloadclient/test", _omit({"forceTest": force_test}), body
    )


async def prowlarr_test_all_download_clients() -> JSONObj:
    """Test every configured download client."""
    return await _req("POST", "downloadclient/testall")


async def prowlarr_download_client_action(name: str, body: JSONObj) -> JSONObj:
    """Run a named action on a download client (e.g. clear failed downloads)."""
    return await _req("POST", f"downloadclient/action/{_id(name)}", body=body)


# --- Filesystem -------------------------------------------------------------------


async def prowlarr_list_filesystem(
    path: str = "",
    include_files: bool | None = None,
    allow_folders_without_trailing_slashes: bool | None = None,
) -> JSONObj:
    """List a directory on the Prowlarr host. path is absolute; empty lists the
    root (drives/mounts). include_files adds files to the listing."""
    return await _req(
        "GET",
        "filesystem",
        _omit(
            {
                "path": path,
                "includeFiles": include_files,
                "allowFoldersWithoutTrailingSlashes": allow_folders_without_trailing_slashes,
            }
        ),
    )


async def prowlarr_get_filesystem_type(path: str) -> JSONObj:
    """Report whether a filesystem path is a file or a directory."""
    return await _req("GET", "filesystem/type", _omit({"path": path}))


# --- Health -----------------------------------------------------------------------


async def prowlarr_list_health() -> JSONVal:
    """List health checks: warnings/errors about indexers, applications,
    download clients, proxies, and system settings."""
    return await _req("GET", "health")


# --- History ----------------------------------------------------------------------


async def prowlarr_list_history(
    page: int = 1,
    page_size: int = 10,
    sort_key: str = "",
    sort_direction: str = "",
    event_type: list[int] | None = None,
    successful: bool | None = None,
    download_id: str = "",
    indexer_ids: list[int] | None = None,
) -> JSONObj:
    """Paged history of grabs and failures. event_type/indexer_ids are lists of
    ints (repeat the param for each). sort_direction is ascending|descending."""
    return await _req(
        "GET",
        "history",
        _omit(
            {
                "page": page,
                "pageSize": page_size,
                "sortKey": sort_key,
                "sortDirection": sort_direction,
                "eventType": event_type,
                "successful": successful,
                "downloadId": download_id,
                "indexerIds": indexer_ids,
            }
        ),
    )


async def prowlarr_list_history_since(date: str, event_type: str = "") -> JSONVal:
    """History records since an ISO date. event_type is a HistoryEventType value
    (e.g. indexerQuery, indexerRss, indexerAuth, indexerInfo, indexerDownload)."""
    return await _req(
        "GET", "history/since", _omit({"date": date, "eventType": event_type})
    )


async def prowlarr_list_history_indexer(
    indexer_id: int | None = None, event_type: str = "", limit: int | None = None
) -> JSONVal:
    """History records for a single indexer, newest first, optionally limited."""
    return await _req(
        "GET",
        "history/indexer",
        _omit({"indexerId": indexer_id, "eventType": event_type, "limit": limit}),
    )


# --- Indexers ----------------------------------------------------------------------


async def prowlarr_list_indexers() -> JSONVal:
    """List all configured indexers with their settings, status, and category
    mappings."""
    return await _req("GET", "indexer")


async def prowlarr_get_indexer(id: int) -> JSONObj:
    """Get a single indexer by id."""
    return await _req("GET", f"indexer/{_id(id)}")


async def prowlarr_create_indexer(
    body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Create an indexer. body is an IndexerResource (fetch
    prowlarr_list_indexer_schemas for the provider definition). force_save
    bypasses validation (e.g. for disabled indexers)."""
    return await _req("POST", "indexer", _omit({"forceSave": force_save}), body)


async def prowlarr_update_indexer(
    id: int, body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Update an indexer by id."""
    return await _req(
        "PUT", f"indexer/{_id(id)}", _omit({"forceSave": force_save}), body
    )


async def prowlarr_delete_indexer(id: int) -> JSONObj:
    """Delete an indexer by id."""
    return await _req("DELETE", f"indexer/{_id(id)}")


async def prowlarr_bulk_update_indexers(body: JSONObj) -> JSONObj:
    """Bulk-edit indexers. body is an IndexerBulkResource with ids plus optional
    tags/applyTags/enable/appProfileId to apply to all of them."""
    return await _req("PUT", "indexer/bulk", body=body)


async def prowlarr_bulk_delete_indexers(body: JSONObj) -> JSONObj:
    """Bulk-delete indexers. body is an IndexerBulkResource with ids."""
    return await _req("DELETE", "indexer/bulk", body=body)


async def prowlarr_list_indexer_schemas() -> JSONVal:
    """List indexer provider schemas (definitions of every supported indexer
    type and its fields). Read this before creating an indexer."""
    return await _req("GET", "indexer/schema")


async def prowlarr_test_indexer(
    body: JSONObj, force_test: bool | None = None
) -> JSONObj:
    """Test an indexer connection without saving it."""
    return await _req("POST", "indexer/test", _omit({"forceTest": force_test}), body)


async def prowlarr_test_all_indexers() -> JSONObj:
    """Test every configured indexer."""
    return await _req("POST", "indexer/testall")


async def prowlarr_indexer_action(name: str, body: JSONObj) -> JSONObj:
    """Run a named action on an indexer (e.g. reset indexer status)."""
    return await _req("POST", f"indexer/action/{_id(name)}", body=body)


async def prowlarr_list_indexer_categories() -> JSONVal:
    """List the default indexer categories (tv, movies, music, books, and
    subcategories) with their ids and parents."""
    return await _req("GET", "indexer/categories")


# --- Indexer Proxies ---------------------------------------------------------------


async def prowlarr_list_indexer_proxies() -> JSONVal:
    """List all configured indexer proxies (HTTP/Socks5 for connecting to
    indexers)."""
    return await _req("GET", "indexerproxy")


async def prowlarr_get_indexer_proxy(id: int) -> JSONObj:
    """Get a single indexer proxy by id."""
    return await _req("GET", f"indexerproxy/{_id(id)}")


async def prowlarr_create_indexer_proxy(
    body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Create an indexer proxy. body is an IndexerProxyResource (fetch
    prowlarr_list_indexer_proxy_schemas for providers). force_save bypasses
    validation."""
    return await _req("POST", "indexerproxy", _omit({"forceSave": force_save}), body)


async def prowlarr_update_indexer_proxy(
    id: int, body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Update an indexer proxy by id."""
    return await _req(
        "PUT", f"indexerproxy/{_id(id)}", _omit({"forceSave": force_save}), body
    )


async def prowlarr_delete_indexer_proxy(id: int) -> JSONObj:
    """Delete an indexer proxy by id."""
    return await _req("DELETE", f"indexerproxy/{_id(id)}")


async def prowlarr_list_indexer_proxy_schemas() -> JSONVal:
    """List indexer proxy provider schemas. Read this before creating or
    updating a proxy."""
    return await _req("GET", "indexerproxy/schema")


async def prowlarr_test_indexer_proxy(
    body: JSONObj, force_test: bool | None = None
) -> JSONObj:
    """Test an indexer proxy connection without saving it."""
    return await _req(
        "POST", "indexerproxy/test", _omit({"forceTest": force_test}), body
    )


async def prowlarr_test_all_indexer_proxies() -> JSONObj:
    """Test every configured indexer proxy."""
    return await _req("POST", "indexerproxy/testall")


async def prowlarr_indexer_proxy_action(name: str, body: JSONObj) -> JSONObj:
    """Run a named action on an indexer proxy (e.g. toggle its status)."""
    return await _req("POST", f"indexerproxy/action/{_id(name)}", body=body)


# --- Indexer Stats / Status ----------------------------------------------------------


async def prowlarr_get_indexer_stats(
    start_date: str = "",
    end_date: str = "",
    indexers: str = "",
    protocols: str = "",
    tags: str = "",
) -> JSONObj:
    """Aggregated query/download statistics per indexer. start_date/end_date are
    ISO dates; indexers/protocols/tags are comma-separated filters (protocols:
    usenet|torrent)."""
    return await _req(
        "GET",
        "indexerstats",
        _omit(
            {
                "startDate": start_date,
                "endDate": end_date,
                "indexers": indexers,
                "protocols": protocols,
                "tags": tags,
            }
        ),
    )


async def prowlarr_list_indexer_status() -> JSONVal:
    """List indexer status records (current failure/backoff state and most
    recent failure per indexer)."""
    return await _req("GET", "indexerstatus")


# --- Localization ---------------------------------------------------------------------


async def prowlarr_get_localization() -> JSONObj:
    """Get the localization string table for the configured UI language."""
    return await _req("GET", "localization")


async def prowlarr_list_localization_options() -> JSONVal:
    """List the available UI languages and their cultures."""
    return await _req("GET", "localization/options")


# --- Logs -----------------------------------------------------------------------------


async def prowlarr_list_logs(
    page: int = 1,
    page_size: int = 10,
    sort_key: str = "",
    sort_direction: str = "",
    level: str = "",
) -> JSONObj:
    """Paged application log. level filters to debug|info|warn|error|fatal
    (default info+)."""
    return await _req(
        "GET",
        "log",
        _omit(
            {
                "page": page,
                "pageSize": page_size,
                "sortKey": sort_key,
                "sortDirection": sort_direction,
                "level": level,
            }
        ),
    )


async def prowlarr_list_log_files() -> JSONVal:
    """List the application log files available for download."""
    return await _req("GET", "log/file")


async def prowlarr_get_log_file(filename: str) -> str:
    """Return the raw contents of an application log file."""
    return await _req_text(f"log/file/{quote(filename)}")


async def prowlarr_list_update_log_files() -> JSONVal:
    """List the update log files available for download."""
    return await _req("GET", "log/file/update")


async def prowlarr_get_update_log_file(filename: str) -> str:
    """Return the raw contents of an update log file."""
    return await _req_text(f"log/file/update/{quote(filename)}")


# --- Newznab ----------------------------------------------------------------------------


async def prowlarr_search_newznab(
    id: int,
    t: str = "",
    q: str = "",
    cat: str = "",
    imdbid: str = "",
    tmdbid: int | None = None,
    tvdbid: int | None = None,
    rid: int | None = None,
    tvmazeid: int | None = None,
    traktid: int | None = None,
    doubanid: int | None = None,
    season: int | None = None,
    ep: str = "",
    album: str = "",
    artist: str = "",
    label: str = "",
    track: str = "",
    year: int | None = None,
    genre: str = "",
    author: str = "",
    title: str = "",
    publisher: str = "",
    limit: int | None = None,
    offset: int | None = None,
    minage: int | None = None,
    maxage: int | None = None,
    minsize: int | None = None,
    maxsize: int | None = None,
    extended: str = "",
    configured: str = "",
    source: str = "",
    host: str = "",
    server: str = "",
) -> str:
    """Query a single indexer in Newznab format and return the raw XML.
    id is the indexer id. t is the newznab request type (search|movie|tvsearch|
    music|book); q is the query term. Returns the XML response as a string."""
    return await _req_text(
        f"indexer/{_id(id)}/newznab",
        _omit(
            {
                "t": t,
                "q": q,
                "cat": cat,
                "imdbid": imdbid,
                "tmdbid": tmdbid,
                "tvdbid": tvdbid,
                "rid": rid,
                "tvmazeid": tvmazeid,
                "traktid": traktid,
                "doubanid": doubanid,
                "season": season,
                "ep": ep,
                "album": album,
                "artist": artist,
                "label": label,
                "track": track,
                "year": year,
                "genre": genre,
                "author": author,
                "title": title,
                "publisher": publisher,
                "limit": limit,
                "offset": offset,
                "minage": minage,
                "maxage": maxage,
                "minsize": minsize,
                "maxsize": maxsize,
                "extended": extended,
                "configured": configured,
                "source": source,
                "host": host,
                "server": server,
            }
        ),
    )


async def prowlarr_download_release(id: int, link: str = "", file: str = "") -> str:
    """Download a release (NZB/torrent) through an indexer. id is the indexer
    id; pass either the download link or the stored file name. Returns the file
    bytes base64-encoded as a string."""
    return await _req_b64(
        f"indexer/{_id(id)}/download", _omit({"link": link, "file": file})
    )


# --- Notifications -----------------------------------------------------------------------


async def prowlarr_list_notifications() -> JSONVal:
    """List all configured notification connections (Discord, Telegram, etc.)."""
    return await _req("GET", "notification")


async def prowlarr_get_notification(id: int) -> JSONObj:
    """Get a single notification by id."""
    return await _req("GET", f"notification/{_id(id)}")


async def prowlarr_create_notification(
    body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Create a notification. body is a NotificationResource (fetch
    prowlarr_list_notification_schemas for providers). force_save bypasses
    validation."""
    return await _req("POST", "notification", _omit({"forceSave": force_save}), body)


async def prowlarr_update_notification(
    id: int, body: JSONObj, force_save: bool | None = None
) -> JSONObj:
    """Update a notification by id."""
    return await _req(
        "PUT", f"notification/{_id(id)}", _omit({"forceSave": force_save}), body
    )


async def prowlarr_delete_notification(id: int) -> JSONObj:
    """Delete a notification by id."""
    return await _req("DELETE", f"notification/{_id(id)}")


async def prowlarr_list_notification_schemas() -> JSONVal:
    """List notification provider schemas. Read this before creating or
    updating a notification."""
    return await _req("GET", "notification/schema")


async def prowlarr_test_notification(
    body: JSONObj, force_test: bool | None = None
) -> JSONObj:
    """Send a test message through a notification connection without saving it."""
    return await _req(
        "POST", "notification/test", _omit({"forceTest": force_test}), body
    )


async def prowlarr_test_all_notifications() -> JSONObj:
    """Send a test message through every configured notification."""
    return await _req("POST", "notification/testall")


async def prowlarr_notification_action(name: str, body: JSONObj) -> JSONObj:
    """Run a named action on a notification (e.g. a custom provider action)."""
    return await _req("POST", f"notification/action/{_id(name)}", body=body)


# --- Ping / Search ------------------------------------------------------------------------


async def prowlarr_ping() -> JSONObj:
    """Liveness probe. Returns {"status": "OK"} when the server is reachable."""
    return await _req("GET", "/ping")


async def prowlarr_search_releases(
    query: str = "",
    type: str = "",
    indexer_ids: list[int] | None = None,
    categories: list[int] | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> JSONVal:
    """Search every (or selected) indexers for releases and return matches.
    query is the search term; type is search|book|movie|audio|tv. indexer_ids
    and categories are lists of ints (repeat the param for each)."""
    return await _req(
        "GET",
        "search",
        _omit(
            {
                "query": query,
                "type": type,
                "indexerIds": indexer_ids,
                "categories": categories,
                "limit": limit,
                "offset": offset,
            }
        ),
    )


async def prowlarr_push_release(body: JSONObj) -> JSONObj:
    """Send a release to the configured download clients. body is a
    ReleaseResource (get one from a prowlarr_search_releases result)."""
    return await _req("POST", "search", body=body)


async def prowlarr_bulk_push_releases(body: list[dict[str, Any]]) -> JSONObj:
    """Send multiple releases to the configured download clients at once. body
    is a list of ReleaseResource objects."""
    return await _req("POST", "search/bulk", body=body)


# --- System ---------------------------------------------------------------------------------


async def prowlarr_system_status() -> JSONObj:
    """Get system status: version, runtime (docker/os), start time, app data
    path, is-mono, migration version, and whether a branch update is pending."""
    return await _req("GET", "system/status")


async def prowlarr_list_system_routes() -> JSONObj:
    """List the API routes the server exposes."""
    return await _req("GET", "system/routes")


async def prowlarr_list_system_routes_duplicate() -> JSONObj:
    """List API routes with duplicate bindings (route conflict diagnostics)."""
    return await _req("GET", "system/routes/duplicate")


async def prowlarr_system_shutdown() -> JSONObj:
    """Shut down the Prowlarr server. Destructive -- the server goes offline."""
    return await _req("POST", "system/shutdown")


async def prowlarr_system_restart() -> JSONObj:
    """Restart the Prowlarr server. Destructive -- the server goes offline
    briefly."""
    return await _req("POST", "system/restart")


# --- Tags --------------------------------------------------------------------------------------


async def prowlarr_list_tags() -> JSONVal:
    """List all tags, usable on indexers, applications, download clients,
    proxies, and notifications."""
    return await _req("GET", "tag")


async def prowlarr_get_tag(id: int) -> JSONObj:
    """Get a single tag by id."""
    return await _req("GET", f"tag/{_id(id)}")


async def prowlarr_create_tag(body: JSONObj) -> JSONObj:
    """Create a tag. body is a TagResource with a `label` (e.g. {"label": "hd"})."""
    return await _req("POST", "tag", body=body)


async def prowlarr_update_tag(id: int, body: JSONObj) -> JSONObj:
    """Update a tag by id."""
    return await _req("PUT", f"tag/{_id(id)}", body=body)


async def prowlarr_delete_tag(id: int) -> JSONObj:
    """Delete a tag by id. Fails if the tag is still in use."""
    return await _req("DELETE", f"tag/{_id(id)}")


async def prowlarr_list_tag_details() -> JSONVal:
    """List tags with the count of indexers, applications, download clients,
    proxies, and notifications using each one."""
    return await _req("GET", "tag/detail")


async def prowlarr_get_tag_details(id: int) -> JSONObj:
    """Get tag details (with usage counts) for a single tag by id."""
    return await _req("GET", f"tag/detail/{_id(id)}")


# --- Tasks -------------------------------------------------------------------------------------


async def prowlarr_list_tasks() -> JSONVal:
    """List all scheduled background tasks (indexer sync, RSS sync, health
    checks, backup) with their next run times."""
    return await _req("GET", "system/task")


async def prowlarr_get_task(id: int) -> JSONObj:
    """Get a single scheduled task by id."""
    return await _req("GET", f"system/task/{_id(id)}")


# --- Updates -----------------------------------------------------------------------------------


async def prowlarr_list_updates() -> JSONVal:
    """List recent releases/updates for Prowlarr (version, release date,
    changes)."""
    return await _req("GET", "update")


# Resource groups for portmanteau registration. Every tool function name
# must appear in exactly one group - see test_all_functions_grouped.
_GROUPS: dict[str, tuple[str, ...]] = {
    "prowlarr_system": (
        "prowlarr_cancel_command",
        "prowlarr_delete_backup",
        "prowlarr_get_api_info",
        "prowlarr_get_command",
        "prowlarr_get_filesystem_type",
        "prowlarr_get_localization",
        "prowlarr_get_log_file",
        "prowlarr_get_task",
        "prowlarr_get_update_log_file",
        "prowlarr_list_backups",
        "prowlarr_list_commands",
        "prowlarr_list_filesystem",
        "prowlarr_list_health",
        "prowlarr_list_localization_options",
        "prowlarr_list_log_files",
        "prowlarr_list_logs",
        "prowlarr_list_system_routes",
        "prowlarr_list_system_routes_duplicate",
        "prowlarr_list_tasks",
        "prowlarr_list_update_log_files",
        "prowlarr_list_updates",
        "prowlarr_restore_backup",
        "prowlarr_restore_backup_upload",
        "prowlarr_run_command",
        "prowlarr_system_restart",
        "prowlarr_system_shutdown",
        "prowlarr_system_status",
    ),
    "prowlarr_applications": (
        "prowlarr_application_action",
        "prowlarr_bulk_delete_applications",
        "prowlarr_bulk_update_applications",
        "prowlarr_create_app_profile",
        "prowlarr_create_application",
        "prowlarr_delete_app_profile",
        "prowlarr_delete_application",
        "prowlarr_get_app_profile",
        "prowlarr_get_application",
        "prowlarr_list_app_profile_schemas",
        "prowlarr_list_app_profiles",
        "prowlarr_list_application_schemas",
        "prowlarr_list_applications",
        "prowlarr_test_all_applications",
        "prowlarr_test_application",
        "prowlarr_update_app_profile",
        "prowlarr_update_application",
    ),
    "prowlarr_indexers": (
        "prowlarr_bulk_delete_indexers",
        "prowlarr_bulk_update_indexers",
        "prowlarr_create_indexer",
        "prowlarr_delete_indexer",
        "prowlarr_get_indexer",
        "prowlarr_get_indexer_stats",
        "prowlarr_indexer_action",
        "prowlarr_list_indexer_categories",
        "prowlarr_list_indexer_schemas",
        "prowlarr_list_indexer_status",
        "prowlarr_list_indexers",
        "prowlarr_test_all_indexers",
        "prowlarr_test_indexer",
        "prowlarr_update_indexer",
    ),
    "prowlarr_config": (
        "prowlarr_create_custom_filter",
        "prowlarr_delete_custom_filter",
        "prowlarr_get_custom_filter",
        "prowlarr_get_development_config",
        "prowlarr_get_download_client_config",
        "prowlarr_get_host_config",
        "prowlarr_get_ui_config",
        "prowlarr_list_custom_filters",
        "prowlarr_update_custom_filter",
        "prowlarr_update_development_config",
        "prowlarr_update_download_client_config",
        "prowlarr_update_host_config",
        "prowlarr_update_ui_config",
    ),
    "prowlarr_download_clients": (
        "prowlarr_bulk_delete_download_clients",
        "prowlarr_bulk_update_download_clients",
        "prowlarr_create_download_client",
        "prowlarr_delete_download_client",
        "prowlarr_download_client_action",
        "prowlarr_get_download_client",
        "prowlarr_list_download_client_schemas",
        "prowlarr_list_download_clients",
        "prowlarr_test_all_download_clients",
        "prowlarr_test_download_client",
        "prowlarr_update_download_client",
    ),
    "prowlarr_indexer_proxies": (
        "prowlarr_create_indexer_proxy",
        "prowlarr_delete_indexer_proxy",
        "prowlarr_get_indexer_proxy",
        "prowlarr_indexer_proxy_action",
        "prowlarr_list_indexer_proxies",
        "prowlarr_list_indexer_proxy_schemas",
        "prowlarr_test_all_indexer_proxies",
        "prowlarr_test_indexer_proxy",
        "prowlarr_update_indexer_proxy",
    ),
    "prowlarr_notifications": (
        "prowlarr_create_notification",
        "prowlarr_delete_notification",
        "prowlarr_get_notification",
        "prowlarr_list_notification_schemas",
        "prowlarr_list_notifications",
        "prowlarr_notification_action",
        "prowlarr_test_all_notifications",
        "prowlarr_test_notification",
        "prowlarr_update_notification",
    ),
    "prowlarr_tags": (
        "prowlarr_create_tag",
        "prowlarr_delete_tag",
        "prowlarr_get_tag",
        "prowlarr_get_tag_details",
        "prowlarr_list_tag_details",
        "prowlarr_list_tags",
        "prowlarr_update_tag",
    ),
    "prowlarr_search": (
        "prowlarr_bulk_push_releases",
        "prowlarr_download_release",
        "prowlarr_ping",
        "prowlarr_push_release",
        "prowlarr_search_newznab",
        "prowlarr_search_releases",
    ),
    "prowlarr_history": (
        "prowlarr_list_history",
        "prowlarr_list_history_indexer",
        "prowlarr_list_history_since",
    ),
}


def _op_line(name: str, fn: Any) -> str:
    """One line of a group tool's description: signature + one-line doc."""
    sig = ", ".join(
        p.name if p.default is inspect.Parameter.empty else f"{p.name}={p.default!r}"
        for p in inspect.signature(fn).parameters.values()
    )
    return f"- {name}({sig}) — {' '.join((fn.__doc__ or '').split())}"


def _register_group(
    group: str, names: tuple[str, ...], ns: dict[str, Any], readonly_names: set[str]
) -> None:
    """Register one dispatching tool that fans out to every function named
    in `names`. The functions themselves are untouched - they're just
    looked up by name instead of each becoming its own tool."""
    fns = {n: ns[n] for n in names}

    async def dispatch(
        operation: str, arguments: JSONObj | None = None
    ) -> JSONVal | str:
        # `| str` covers the handful of operations (log/newznab/download) that
        # return raw text or base64 instead of decoded JSON.
        fn = fns.get(operation)
        if fn is None:
            raise ToolError(
                f"Unknown operation {operation!r} for {group}. Valid: {', '.join(fns)}"
            )
        return await fn(**(arguments or {}))

    dispatch.__annotations__["operation"] = Literal[names]
    ann = READONLY if set(names) <= readonly_names else None
    mcp.add_tool(
        Tool.from_function(
            dispatch,
            name=group,
            description=(
                f"{group.replace('_', ' ')} operations on Prowlarr. Pass `operation` and an "
                f"`arguments` dict matching that operation's parameters.\n\n"
                + "\n".join(_op_line(n, f) for n, f in fns.items())
            ),
            annotations=ann,
        )
    )


def _register_tools() -> None:
    ns = globals()
    readonly_names: set[str] = {
        "prowlarr_download_release",
        "prowlarr_get_api_info",
        "prowlarr_get_app_profile",
        "prowlarr_get_application",
        "prowlarr_get_command",
        "prowlarr_get_custom_filter",
        "prowlarr_get_development_config",
        "prowlarr_get_download_client",
        "prowlarr_get_download_client_config",
        "prowlarr_get_filesystem_type",
        "prowlarr_get_host_config",
        "prowlarr_get_indexer",
        "prowlarr_get_indexer_proxy",
        "prowlarr_get_indexer_stats",
        "prowlarr_get_localization",
        "prowlarr_get_log_file",
        "prowlarr_get_notification",
        "prowlarr_get_tag",
        "prowlarr_get_tag_details",
        "prowlarr_get_task",
        "prowlarr_get_ui_config",
        "prowlarr_get_update_log_file",
        "prowlarr_list_app_profile_schemas",
        "prowlarr_list_app_profiles",
        "prowlarr_list_application_schemas",
        "prowlarr_list_applications",
        "prowlarr_list_backups",
        "prowlarr_list_commands",
        "prowlarr_list_custom_filters",
        "prowlarr_list_download_client_schemas",
        "prowlarr_list_download_clients",
        "prowlarr_list_filesystem",
        "prowlarr_list_health",
        "prowlarr_list_history",
        "prowlarr_list_history_indexer",
        "prowlarr_list_history_since",
        "prowlarr_list_indexer_categories",
        "prowlarr_list_indexer_proxies",
        "prowlarr_list_indexer_proxy_schemas",
        "prowlarr_list_indexer_schemas",
        "prowlarr_list_indexer_status",
        "prowlarr_list_indexers",
        "prowlarr_list_localization_options",
        "prowlarr_list_log_files",
        "prowlarr_list_logs",
        "prowlarr_list_notification_schemas",
        "prowlarr_list_notifications",
        "prowlarr_list_system_routes",
        "prowlarr_list_system_routes_duplicate",
        "prowlarr_list_tag_details",
        "prowlarr_list_tags",
        "prowlarr_list_tasks",
        "prowlarr_list_update_log_files",
        "prowlarr_list_updates",
        "prowlarr_ping",
        "prowlarr_search_newznab",
        "prowlarr_search_releases",
        "prowlarr_system_status",
    }
    for group, names in _GROUPS.items():
        _register_group(group, names, ns, readonly_names)


_register_tools()


def main() -> None:
    global _client
    url = os.environ.get("PROWLARR_URL")
    if not url:
        print(
            "PROWLARR_URL environment variable is required (e.g. http://localhost:9696)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    _client = build_client(url, os.environ.get("PROWLARR_API_KEY"))
    mcp.run()


if __name__ == "__main__":
    main()
