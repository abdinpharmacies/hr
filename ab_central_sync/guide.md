# Central inventory setup and testing

Current version: 19.0.5.1.0. Install ab_central_sync on central and ab_branch_sync on branches.

1. On central, open Settings → Users & Companies → Users. Choose the user, grant Inventory Writer in access rights, and assign the branch under Inventory Stores. Save.
2. As that user, generate a standard Odoo API key under Preferences / Account Security. Keep the key private.
3. On branch, open Settings → Branch Synchronization. Enter the Central URL, Central Database, and Inventory Writer API Key. Click Connect to Central. It downloads the initial stock snapshot.
4. Open branch POS. Verify the connection tag and product balance. Submit a bill; its local bill and outgoing journal are retained while central posts its inventory deduction.
5. In Branch Synchronization, open the outgoing operation. Retry immediately checks central and resends when necessary. Repeated retries must show the same central bill without another deduction.
6. With central unreachable after the initial snapshot, submit another bill. The branch POS balance must decrease immediately. Restore central and retry/synchronize; the new snapshot must include the bill exactly once.

Cashier payments stay on the branch. No pairing code or certificate setup is needed. Existing replica identity/store routing must match replicated business data. Unit matching uses ab_product_uom; legacy packaging counts retain their physical-stock meaning.

See [workflow.md](workflow.md) for authentication, scope, snapshots, idempotency, and legacy-operation restrictions.
