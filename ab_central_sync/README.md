# ab_central_sync

Version 19.0.5.1.2. Central inventory receiver authenticated by Inventory Writer user API keys.

See [workflow.md](workflow.md) for setup, unit mapping, inventory ownership, POS behavior and recovery.

Transport uses the replica’s Allowed Sales Stores and the API user’s allowed companies.
The API user needs Inventory Writer access, but no personal Inventory Stores assignment.

New synchronized inventory movements record the authenticated originating replica serial.
Direct central movements retain central’s configured serial; historical movements are unchanged.
