# Callcenter XML development startup fix

Validated on 2026-11-08 for `ab_crm_sales_workspace` version `19.0.1.13.1`.

The Callcenter restart at 14:37 UTC failed while upgrading the workspace with
`--dev=xml`. Odoo's filesystem view loader concatenated a null XML field text
with its child architecture. All seven compact architectures in
`views/branch_location.xml` reproduced the failure. The reported parent view,
`conversation_identity_review`, was affected through its inherited branch view.

Adding whitespace after the seven architecture field opening tags fixes the
loader without changing the parsed view trees, XML IDs, UI strings or permissions.
A regression test covers the actual Odoo filesystem loader and combined views.

Verification:

- Targeted upgrade of `ab_crm_messaging,ab_crm_sales_workspace` on isolated database
  `crm_branch_final_test_20261108`, with `--dev=xml`: successful.
- Two focused workspace tests: zero failures and zero errors.
- All seven branch views and the reported parent loaded successfully against
  `callcenter` inside an explicitly read-only transaction.
- Parsed XML trees before and after the whitespace fix are identical when blank
  text is removed. Both Arabic catalogs remain unchanged by this fix.
- `git diff --check` passed.
- Temporary validation processes exited successfully; ports 5069, 5072, 5075 and
  5076 were released. The existing PyCharm process continued listening on 4092.

Evidence logs are in `/tmp/callcenter-restart-fix`. The latest 300 runtime log
lines inspected after validation contained no ERROR or CRITICAL entries.
Earlier session-update serialization retries and existing startup warnings are
separate from the reproduced registry-loading failure.

No live database upgrade or server restart was performed. The live module version
was still `19.0.1.13.0` during read-only verification. On the next user-managed
startup, retain the existing configuration and use:

```text
-d callcenter -u ab_crm_messaging,ab_crm_sales_workspace
```
