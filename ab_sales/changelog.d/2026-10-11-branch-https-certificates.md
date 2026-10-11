# Branch HTTPS certificate acceptance

## Recent relevant commit (RPC transport excerpt)

- Commit: `146702c86c910cffb750d8611e7339f41424fd37`
- Author: emadco88
- Date: 2026-10-08 01:31:39 +0300
- Original commit subject: ab_sales/ UPD comptability with new ab_branch_api  with duplication prevention
- Route sale submission directly through the branch RPC call and validate the returned branch identity.

Files changed (relevant excerpt):
- `ab_sales/models/ab_sales_branch_rpc_config.py`

## Current changes before commit:

- Accept branch HTTPS certificates automatically for existing and new connections by disabling certificate verification only in the branch RPC request.
- HTTPS encryption remains; CA trust, expiry, and certificate hostname checks are disabled. Branch servers still require a working TLS endpoint.
- Preserve API-key authentication, remote HTTPS enforcement, timeouts, response identity checks, and redirect rejection. Do not suppress TLS warnings globally.
- No user-facing strings changed; neither Arabic translation catalog requires an update.

Files changed:
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/changelog.d/2026-10-11-branch-https-certificates.md`

Validation:
- Executed the actual RPC and URL-validation method bodies in an isolated Python harness against a temporary local HTTPS server: a self-signed, hostname-mismatched certificate is rejected by normal Requests verification and accepted by the updated RPC call.
- HTTP 401/403 still raise access errors; redirects are rejected without following them; remote HTTP URLs are rejected.
- Python syntax passed. No Odoo database upgrade or live service restart performed; restart the call-center Odoo process to load the Python change.
