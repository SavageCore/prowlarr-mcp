# AGENTS.md — prowlarr-mcp

MCP server exposing [Prowlarr](https://github.com/Prowlarr/Prowlarr)'s API v1
(REST) as tools so an LLM can manage indexers, applications, download clients,
indexer proxies, notifications, tags, and custom filters, plus run cross-indexer
searches and issue system commands. Unlike tracearr-mcp, **Prowlarr has a full
read/write surface** — many tools create, update, delete, or trigger actions.
Uses FastMCP, `uv` for deps.

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
- This server is not yet deployed to the Proxmox host or the christopfarr project copy. When it is, follow the pattern in the other `-mcp` servers: push tags, sync the project copy, then `ssh root@192.168.50.3 -- 'cd /root/prowlarr-mcp && git fetch origin && git reset --hard origin/main && uv tool install --force .'`.

## Read/write notes
The Prowlarr API is not read-only: every tool is NOT marked read-only. Conventions:
- GET tools: `readOnlyHint=True`.
- DELETE tools and `/system/shutdown` + `/system/restart`: `destructiveHint=True`.
- POST/PUT tools (create/update/test/action/command): no hints (state-changing but non-destructive).
- Auth is the `X-Api-Key` header. `build_client` targets the server root; `_req`
  prefixes `/api/v1` to relative paths, and `/api` + `/ping` are used verbatim.
Keep the whole server in `prowlarr_mcp.py` unless it outgrows it; add tools one per endpoint with the `prowlarr_` prefix.
