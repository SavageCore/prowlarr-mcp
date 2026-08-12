# AGENTS.md — prowlarr-mcp

MCP server exposing [Prowlarr](https://github.com/Prowlarr/Prowlarr)'s API v1
(REST) as tools so an LLM can manage indexers, applications, download clients,
indexer proxies, notifications, tags, and custom filters, plus run cross-indexer
searches and issue system commands. Unlike tracearr-mcp, **Prowlarr has a full
read/write surface** — many operations create, update, delete, or trigger actions.
Uses FastMCP, `uv` for deps.

Exposed as **10 resource-scoped portmanteau tools**, not one tool per operation — see "Portmanteau registration" below. A prior version registered all 116 operations individually; that blew the MCP context budget (~116 tools × ~250 tokens ≈ 29k tokens just for this one server) and has been retired.

## Testing
- Offline suite: `make test` (or `uv run pytest`)
- Live integration (needs `PROWLARR_URL`/`PROWLARR_API_KEY`): `make test-integration`
- Write integration (scratch Tag round-trip) additionally needs `PROWLARR_ALLOW_WRITES=1`
  so plain `make test-integration` never mutates the instance.

## Release workflow
Always use the `make bump-*` targets to bump the version (`uv version --bump patch|minor|major`), which updates `pyproject.toml` and `uv.lock` together. Do NOT edit the version by hand.

- Bump: `make bump-patch` (or `bump-minor` / `bump-major`)
- Commit message is **just the version**, e.g. `0.1.2` — nothing else.
- Tag it `v<version>` (e.g. `v0.1.2`).
- Push main and the tag:
  ```
  git push origin main
  git push origin v<version>
  ```
- Deploy to the Proxmox host (root SSH key): pull the repo then reinstall the uv tool:
  ```
  ssh root@192.168.50.3 -- 'cd /root/prowlarr-mcp && git fetch origin && git reset --hard origin/main'
  ssh root@192.168.50.3 -- 'cd /root/prowlarr-mcp && uv tool install --force .'
  ```
  The host runs it via `uv tool install` → `/root/.local/bin/prowlarr-mcp` (not from the repo). There is no `/home/savagecore/Documents/christopfarr/mcp/prowlarr-mcp` copy.

## Read/write notes
The Prowlarr API is not read-only: most operations are NOT read-only. Conventions:
- GET operations: originally `readOnlyHint=True` at the individual-function level.
- DELETE operations and `/system/shutdown` + `/system/restart`: originally `destructiveHint=True`.
- POST/PUT operations (create/update/test/action/command): originally no hints (state-changing but non-destructive).
- Auth is the `X-Api-Key` header. `build_client` targets the server root; `_req`
  prefixes `/api/v1` to relative paths, and `/api` + `/ping` are used verbatim.
Keep the whole server in `prowlarr_mcp.py` unless it outgrows it.

## Portmanteau registration — **do not go back to one tool per endpoint**
- `_GROUPS` near the bottom of `prowlarr_mcp.py` buckets every endpoint function into one of 10 resource groups (`prowlarr_indexers`, `prowlarr_applications`, `prowlarr_system`, ...). `_register_tools()` registers exactly one MCP tool per group via `_register_group`, which wraps the group's functions in a single `dispatch(operation, arguments)` closure. The endpoint functions themselves are unchanged — they're plain callables looked up by name via `globals()`, not separately-registered tools.
- `operation` is typed `Literal[<the group's function names>]`, so FastMCP/pydantic validates it against the real operation list before `dispatch` ever runs — an invalid operation never reaches the group tool's body.
- `dispatch`'s return type is `JSONVal | str` (not bare `JSONVal`) because a handful of operations (`prowlarr_get_log_file`, `prowlarr_get_update_log_file`, `prowlarr_search_newznab`, `prowlarr_download_release`) return raw text or base64 rather than decoded JSON — narrowing the union back to `JSONVal` breaks FastMCP's structured-content validation for those.
- Adding a new endpoint: write the function as before (with its own `@mcp.tool`-free `async def prowlarr_<verb>_<resource>(...)`), then add its name to exactly one group in `_GROUPS`. `tests/test_tools.py::test_all_tools_grouped` fails if you forget.
- New resource area big enough to need its own group (rare): add a new `_GROUPS` key. Keep the total group count at or under ~15 — that ceiling is the entire point of this pattern.
- If you're tempted to add a per-endpoint `@mcp.tool` decorator back, don't — every endpoint must be reachable only via its group's `operation` enum. A 116-tool server (one per endpoint) previously cost ~29k tokens of system-prompt budget on every session start; the 10-tool grouped version costs roughly a tenth of that.
- Annotations: a group tool is `readOnlyHint=True` (`READONLY`) only when *every* operation in it was originally GET (tracked in `_register_tools()`'s `readonly_names` set). Mixed groups carry no hints — the original per-operation DESTRUCTIVE distinction is no longer applied at the group level, but stays implicit in each operation line's function name and docstring in the group tool's description.
