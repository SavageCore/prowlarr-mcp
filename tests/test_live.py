"""Integration tests against a real Prowlarr instance.

Skipped unless PROWLARR_URL and PROWLARR_API_KEY are set. Run with:
    uv run pytest -m integration

The suite is read-only by default and never mutates your instance. Setting
PROWLARR_ALLOW_WRITES=1 additionally runs a scratch Tag create+delete
round-trip (the least-destructive write available).
"""

import os
import time

import pytest
from fastmcp import Client

import prowlarr_mcp

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (os.environ.get("PROWLARR_URL") and os.environ.get("PROWLARR_API_KEY")),
        reason="requires PROWLARR_URL and PROWLARR_API_KEY",
    ),
]


@pytest.fixture(autouse=True)
def configure_client():
    prowlarr_mcp._client = prowlarr_mcp.build_client(os.environ["PROWLARR_URL"], os.environ["PROWLARR_API_KEY"])
    yield
    if prowlarr_mcp._client is not None:
        import asyncio

        asyncio.run(prowlarr_mcp._client.aclose())


async def call(name, **kwargs):
    async with Client(prowlarr_mcp.mcp) as c:
        return await c.call_tool(name, kwargs)


# --- read-only ---------------------------------------------------------------

async def test_ping():
    result = await call("prowlarr_ping")
    assert result.data["status"] == "OK"


async def test_system_status():
    result = await call("prowlarr_system_status")
    assert isinstance(result.data["version"], str)


async def test_list_health():
    result = await call("prowlarr_list_health")
    assert isinstance(result.data, list)


async def test_list_indexers():
    result = await call("prowlarr_list_indexers")
    assert isinstance(result.data, list)


async def test_list_indexer_categories():
    result = await call("prowlarr_list_indexer_categories")
    assert isinstance(result.data, list)
    if result.data:
        assert "id" in result.data[0]


async def test_list_applications():
    result = await call("prowlarr_list_applications")
    assert isinstance(result.data, list)


async def test_list_download_clients():
    result = await call("prowlarr_list_download_clients")
    assert isinstance(result.data, list)


async def test_list_tags():
    result = await call("prowlarr_list_tags")
    assert isinstance(result.data, list)


async def test_search_releases():
    result = await call("prowlarr_search_releases", query="matrix")
    assert isinstance(result.data, list)


async def test_history_when_records_exist():
    result = await call("prowlarr_list_history", page_size=1)
    assert isinstance(result.data, dict)
    assert "records" in result.data or "page" in result.data or "records" in result.data


# --- write (opt-in) ----------------------------------------------------------

async def test_tag_round_trip_when_writes_allowed():
    if os.environ.get("PROWLARR_ALLOW_WRITES") != "1":
        pytest.skip("PROWLARR_ALLOW_WRITES not set to 1")
    label = f"mcp-scratch-{int(time.time())}"
    created = await call("prowlarr_create_tag", body={"label": label})
    assert created.data.get("label") == label

    tag_id = created.data["id"]
    listed = await call("prowlarr_list_tags")
    assert any(tag["id"] == tag_id for tag in listed.data)

    await call("prowlarr_delete_tag", id=tag_id)
    after = await call("prowlarr_list_tags")
    assert all(tag["id"] != tag_id for tag in after.data)
