# prowlarr-mcp

MCP server exposing [Prowlarr](https://github.com/Prowlarr/Prowlarr)'s API v1
(REST) as tools, so an LLM can manage your indexers, applications, download
clients, indexer proxies, notifications, tags, and custom filters — plus run
cross-indexer searches and issue system commands. The full API surface is
covered, **read and write**.

Built with [FastMCP](https://gofastmcp.com).

## Enabling the API on your Prowlarr server

Generate an API key in Prowlarr **Settings > General** (Authentication section).
Every `/api/v1` endpoint requires it, sent as the `X-Api-Key` header.

## Install

Download a wheel from the [latest release](https://github.com/SavageCore/prowlarr-mcp/releases/latest)
and install it as a `uv` tool (no repo checkout needed):

```bash
uv tool install prowlarr_mcp-*.whl
```

This puts a `prowlarr-mcp` command on your PATH. Register it with Claude Code:

```bash
claude mcp add prowlarr \
  --env PROWLARR_URL=http://localhost:9696 \
  --env PROWLARR_API_KEY=<key> \
  -- prowlarr-mcp
```

### From source

```bash
uv sync
cp .env.example .env   # fill in PROWLARR_URL and PROWLARR_API_KEY
```

```bash
claude mcp add prowlarr \
  --env PROWLARR_URL=http://localhost:9696 \
  --env PROWLARR_API_KEY=<key> \
  -- uv run --directory /path/to/prowlarr-mcp prowlarr-mcp
```

## Config

| Env var | Required | Default |
|---|---|---|
| `PROWLARR_URL` | yes | - |
| `PROWLARR_API_KEY` | yes* | none (no auth header sent if unset) |

\* Every API endpoint requires auth; practically you must set it, but the
server still starts without one so errors surface from the API rather than at
startup.

## Tools

One tool per Prowlarr API v1 operation. GET tools are read-only
(`readOnlyHint`), DELETE tools (and system shutdown/restart) are destructive
(`destructiveHint`), and POST/PUT tools create/update/test/trigger actions.

Create/update/test/action tools take a `body` JSON object; fetch a
`list_*_schema` first to see the fields a resource expects. `forceSave` and
`forceTest` query flags are exposed as optional params.

### ApiInfo
| Tool | Endpoint |
|---|---|
| `prowlarr_get_api_info` | `GET /api` |

### Applications
| Tool | Endpoint |
|---|---|
| `prowlarr_list_applications` | `GET /api/v1/applications` |
| `prowlarr_get_application` | `GET /api/v1/applications/{id}` |
| `prowlarr_create_application` | `POST /api/v1/applications` |
| `prowlarr_update_application` | `PUT /api/v1/applications/{id}` |
| `prowlarr_delete_application` | `DELETE /api/v1/applications/{id}` |
| `prowlarr_bulk_update_applications` | `PUT /api/v1/applications/bulk` |
| `prowlarr_bulk_delete_applications` | `DELETE /api/v1/applications/bulk` |
| `prowlarr_list_application_schemas` | `GET /api/v1/applications/schema` |
| `prowlarr_test_application` | `POST /api/v1/applications/test` |
| `prowlarr_test_all_applications` | `POST /api/v1/applications/testall` |
| `prowlarr_application_action` | `POST /api/v1/applications/action/{name}` |

### App Profiles
| Tool | Endpoint |
|---|---|
| `prowlarr_list_app_profiles` | `GET /api/v1/appprofile` |
| `prowlarr_get_app_profile` | `GET /api/v1/appprofile/{id}` |
| `prowlarr_create_app_profile` | `POST /api/v1/appprofile` |
| `prowlarr_update_app_profile` | `PUT /api/v1/appprofile/{id}` |
| `prowlarr_delete_app_profile` | `DELETE /api/v1/appprofile/{id}` |
| `prowlarr_list_app_profile_schemas` | `GET /api/v1/appprofile/schema` |

### Backups
| Tool | Endpoint |
|---|---|
| `prowlarr_list_backups` | `GET /api/v1/system/backup` |
| `prowlarr_delete_backup` | `DELETE /api/v1/system/backup/{id}` |
| `prowlarr_restore_backup` | `POST /api/v1/system/backup/restore/{id}` |
| `prowlarr_restore_backup_upload` | `POST /api/v1/system/backup/restore/upload` |

### Commands
| Tool | Endpoint |
|---|---|
| `prowlarr_list_commands` | `GET /api/v1/command` |
| `prowlarr_get_command` | `GET /api/v1/command/{id}` |
| `prowlarr_run_command` | `POST /api/v1/command` |
| `prowlarr_cancel_command` | `DELETE /api/v1/command/{id}` |

### Custom Filters
| Tool | Endpoint |
|---|---|
| `prowlarr_list_custom_filters` | `GET /api/v1/customfilter` |
| `prowlarr_get_custom_filter` | `GET /api/v1/customfilter/{id}` |
| `prowlarr_create_custom_filter` | `POST /api/v1/customfilter` |
| `prowlarr_update_custom_filter` | `PUT /api/v1/customfilter/{id}` |
| `prowlarr_delete_custom_filter` | `DELETE /api/v1/customfilter/{id}` |

### Config
| Tool | Endpoint |
|---|---|
| `prowlarr_get_host_config` | `GET /api/v1/config/host` |
| `prowlarr_update_host_config` | `PUT /api/v1/config/host/{id}` |
| `prowlarr_get_ui_config` | `GET /api/v1/config/ui` |
| `prowlarr_update_ui_config` | `PUT /api/v1/config/ui/{id}` |
| `prowlarr_get_download_client_config` | `GET /api/v1/config/downloadclient` |
| `prowlarr_update_download_client_config` | `PUT /api/v1/config/downloadclient/{id}` |
| `prowlarr_get_development_config` | `GET /api/v1/config/development` |
| `prowlarr_update_development_config` | `PUT /api/v1/config/development/{id}` |

### Download Clients
| Tool | Endpoint |
|---|---|
| `prowlarr_list_download_clients` | `GET /api/v1/downloadclient` |
| `prowlarr_get_download_client` | `GET /api/v1/downloadclient/{id}` |
| `prowlarr_create_download_client` | `POST /api/v1/downloadclient` |
| `prowlarr_update_download_client` | `PUT /api/v1/downloadclient/{id}` |
| `prowlarr_delete_download_client` | `DELETE /api/v1/downloadclient/{id}` |
| `prowlarr_bulk_update_download_clients` | `PUT /api/v1/downloadclient/bulk` |
| `prowlarr_bulk_delete_download_clients` | `DELETE /api/v1/downloadclient/bulk` |
| `prowlarr_list_download_client_schemas` | `GET /api/v1/downloadclient/schema` |
| `prowlarr_test_download_client` | `POST /api/v1/downloadclient/test` |
| `prowlarr_test_all_download_clients` | `POST /api/v1/downloadclient/testall` |
| `prowlarr_download_client_action` | `POST /api/v1/downloadclient/action/{name}` |

### Filesystem
| Tool | Endpoint |
|---|---|
| `prowlarr_list_filesystem` | `GET /api/v1/filesystem` |
| `prowlarr_get_filesystem_type` | `GET /api/v1/filesystem/type` |

### Health
| Tool | Endpoint |
|---|---|
| `prowlarr_list_health` | `GET /api/v1/health` |

### History
| Tool | Endpoint |
|---|---|
| `prowlarr_list_history` | `GET /api/v1/history` |
| `prowlarr_list_history_since` | `GET /api/v1/history/since` |
| `prowlarr_list_history_indexer` | `GET /api/v1/history/indexer` |

### Indexers
| Tool | Endpoint |
|---|---|
| `prowlarr_list_indexers` | `GET /api/v1/indexer` |
| `prowlarr_get_indexer` | `GET /api/v1/indexer/{id}` |
| `prowlarr_create_indexer` | `POST /api/v1/indexer` |
| `prowlarr_update_indexer` | `PUT /api/v1/indexer/{id}` |
| `prowlarr_delete_indexer` | `DELETE /api/v1/indexer/{id}` |
| `prowlarr_bulk_update_indexers` | `PUT /api/v1/indexer/bulk` |
| `prowlarr_bulk_delete_indexers` | `DELETE /api/v1/indexer/bulk` |
| `prowlarr_list_indexer_schemas` | `GET /api/v1/indexer/schema` |
| `prowlarr_test_indexer` | `POST /api/v1/indexer/test` |
| `prowlarr_test_all_indexers` | `POST /api/v1/indexer/testall` |
| `prowlarr_indexer_action` | `POST /api/v1/indexer/action/{name}` |
| `prowlarr_list_indexer_categories` | `GET /api/v1/indexer/categories` |

### Indexer Proxies
| Tool | Endpoint |
|---|---|
| `prowlarr_list_indexer_proxies` | `GET /api/v1/indexerproxy` |
| `prowlarr_get_indexer_proxy` | `GET /api/v1/indexerproxy/{id}` |
| `prowlarr_create_indexer_proxy` | `POST /api/v1/indexerproxy` |
| `prowlarr_update_indexer_proxy` | `PUT /api/v1/indexerproxy/{id}` |
| `prowlarr_delete_indexer_proxy` | `DELETE /api/v1/indexerproxy/{id}` |
| `prowlarr_list_indexer_proxy_schemas` | `GET /api/v1/indexerproxy/schema` |
| `prowlarr_test_indexer_proxy` | `POST /api/v1/indexerproxy/test` |
| `prowlarr_test_all_indexer_proxies` | `POST /api/v1/indexerproxy/testall` |
| `prowlarr_indexer_proxy_action` | `POST /api/v1/indexerproxy/action/{name}` |

### Indexer Stats / Status
| Tool | Endpoint |
|---|---|
| `prowlarr_get_indexer_stats` | `GET /api/v1/indexerstats` |
| `prowlarr_list_indexer_status` | `GET /api/v1/indexerstatus` |

### Localization
| Tool | Endpoint |
|---|---|
| `prowlarr_get_localization` | `GET /api/v1/localization` |
| `prowlarr_list_localization_options` | `GET /api/v1/localization/options` |

### Logs
| Tool | Endpoint |
|---|---|
| `prowlarr_list_logs` | `GET /api/v1/log` |
| `prowlarr_list_log_files` | `GET /api/v1/log/file` |
| `prowlarr_get_log_file` | `GET /api/v1/log/file/{filename}` |
| `prowlarr_list_update_log_files` | `GET /api/v1/log/file/update` |
| `prowlarr_get_update_log_file` | `GET /api/v1/log/file/update/{filename}` |

### Newznab
| Tool | Endpoint |
|---|---|
| `prowlarr_search_newznab` | `GET /api/v1/indexer/{id}/newznab` |
| `prowlarr_download_release` | `GET /api/v1/indexer/{id}/download` |

### Notifications
| Tool | Endpoint |
|---|---|
| `prowlarr_list_notifications` | `GET /api/v1/notification` |
| `prowlarr_get_notification` | `GET /api/v1/notification/{id}` |
| `prowlarr_create_notification` | `POST /api/v1/notification` |
| `prowlarr_update_notification` | `PUT /api/v1/notification/{id}` |
| `prowlarr_delete_notification` | `DELETE /api/v1/notification/{id}` |
| `prowlarr_list_notification_schemas` | `GET /api/v1/notification/schema` |
| `prowlarr_test_notification` | `POST /api/v1/notification/test` |
| `prowlarr_test_all_notifications` | `POST /api/v1/notification/testall` |
| `prowlarr_notification_action` | `POST /api/v1/notification/action/{name}` |

### Ping / Search
| Tool | Endpoint |
|---|---|
| `prowlarr_ping` | `GET /ping` |
| `prowlarr_search_releases` | `GET /api/v1/search` |
| `prowlarr_push_release` | `POST /api/v1/search` |
| `prowlarr_bulk_push_releases` | `POST /api/v1/search/bulk` |

### System
| Tool | Endpoint |
|---|---|
| `prowlarr_system_status` | `GET /api/v1/system/status` |
| `prowlarr_list_system_routes` | `GET /api/v1/system/routes` |
| `prowlarr_list_system_routes_duplicate` | `GET /api/v1/system/routes/duplicate` |
| `prowlarr_system_shutdown` | `POST /api/v1/system/shutdown` |
| `prowlarr_system_restart` | `POST /api/v1/system/restart` |

### Tags
| Tool | Endpoint |
|---|---|
| `prowlarr_list_tags` | `GET /api/v1/tag` |
| `prowlarr_get_tag` | `GET /api/v1/tag/{id}` |
| `prowlarr_create_tag` | `POST /api/v1/tag` |
| `prowlarr_update_tag` | `PUT /api/v1/tag/{id}` |
| `prowlarr_delete_tag` | `DELETE /api/v1/tag/{id}` |
| `prowlarr_list_tag_details` | `GET /api/v1/tag/detail` |
| `prowlarr_get_tag_details` | `GET /api/v1/tag/detail/{id}` |

### Tasks
| Tool | Endpoint |
|---|---|
| `prowlarr_list_tasks` | `GET /api/v1/system/task` |
| `prowlarr_get_task` | `GET /api/v1/system/task/{id}` |

### Updates
| Tool | Endpoint |
|---|---|
| `prowlarr_list_updates` | `GET /api/v1/update` |

## Development

```bash
make help  # list all commands
```

| Command | Does |
|---|---|
| `make sync` | `uv sync` |
| `make test` | Offline tests - one per endpoint, mocked HTTP |
| `make test-integration` | Tests against the live instance (needs `PROWLARR_URL`/`PROWLARR_API_KEY`) |
| `make build` | Build wheel + sdist into `dist/` |
| `make bump-patch` / `bump-minor` / `bump-major` | Bump the version in `pyproject.toml` + `uv.lock` |
| `make clean` | Remove build artifacts |

The release workflow (`.github/workflows/release.yml`) builds and publishes to
[Releases](https://github.com/SavageCore/prowlarr-mcp/releases) whenever a `v*`
tag is pushed - so the usual flow is `make bump-patch`, commit, then tag and
push.

The integration suite is read-only by default (a plain `make test-integration`
never mutates your instance). Setting `PROWLARR_ALLOW_WRITES=1` additionally
runs a scratch Tag create+delete round-trip.
