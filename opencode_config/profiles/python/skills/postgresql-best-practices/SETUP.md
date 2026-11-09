# PostgreSQL MCP setup for the OpenCode Odoo profile

The Odoo/Python profile has a `postgres-mcp` entry in `opencode_config/profiles/python/opencode.jsonc`. It is disabled and has no database credentials. The skills and reference pages work without it.

To use connected diagnostics, first create a dedicated PostgreSQL role limited to the intended database with read-only privileges. Configure a saved connection profile with `--access-mode ro` and a verified TLS connection. Keep passwords in the operating-system keyring rather than commands, configuration files, or prompts.

```sh
npx -y @microsoft/postgres-mcp@0.2.0 connection add my-database \
  "host=db.example.com user=agent_user dbname=app sslmode=verify-full" \
  --access-mode ro
npx -y @microsoft/postgres-mcp@0.2.0 connection set-password my-database
```

After reviewing the [server usage and security guide](https://github.com/microsoft/postgres-mcp/blob/main/USAGE.md), set `enabled` to `true` only for `mcp.postgres-mcp` in the Odoo/Python profile. Start a new OpenCode Odoo session, select the saved connection, and verify the role and database before querying. The configured server disables working-directory access and telemetry; it must not be used to write Odoo business data or to connect to B-Connect/E-Plus SQL Server.

To remove access, disable the server entry, disconnect the profile, and remove the saved connection with `npx -y @microsoft/postgres-mcp@0.2.0 connection remove my-database`.
