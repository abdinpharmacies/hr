# Sales Chatter WhatsApp dual-channel planning handoff

Saved: 2026-11-05
Workspace: `/opt/odoo19/worktrees/callcenter19`
Branch at review: `callcenter19`
Status: Diagnosis and proposed plan complete; implementation not started.

## Resume instructions

The user requested saving this progress and continuing with a **new refactor plan in a new session**. Start with planning, not implementation. Re-read applicable AGENTS.md instructions and current source before proposing changes.

- The user reports that WhatsApp credentials are configured and `ab_whatsapp_api` is working. This was not independently verified with live API calls.
- Keep `ab_whatsapp_api` source files unchanged. Companion-addon runtime extensions are a proposal to assess in the next refactor plan, not an implemented or activated change.
- Preserve the existing Telegram channel, shared PIN-agent access, protected employee audit attribution, separate Orders, and branch/company isolation.
- Do not change delivery switches, send test messages, resend old messages, upgrade databases, or restart services as part of resuming planning.
- The earlier `docs/sales-operations-whatsapp-next-plan.md` contains superseded proposals to edit the owner addon and use claims. This handoff supersedes those proposals; the earlier file remains historical evidence.
- The working tree already contained unrelated modifications and untracked addons. Preserve them. No application source changes were made during this diagnosis or handoff save.

## Progress and evidence

Completed: source inspection of WhatsApp contacts/messages/service/controller, Chatter conversation linking and composer restrictions, the generic WhatsApp account adapter, and the previous integration plan; review of accessible official Meta material.

Not performed: implementation, database migrations, install/upgrade tests, browser validation, exploit tests, live provider tests, or rollout. Source findings are not proof of the deployed runtime state. The next session must verify the actual runtime/addons selection before implementation or validation.

Open decisions for the new refactor plan:

1. Define the companion addon's exact ownership and supported extension points while preserving owner source files.
2. Resolve how signature checks, direct ORM restrictions, archival protection and durable sends cover every active entry point, including the administrator dashboard.
3. Confirm the configured API version, BSUID/contact-information support and payload schemas; some detailed Meta endpoints returned HTTP 429 during research.
4. Define explicit business-number/company/intake-branch mapping, ambiguous contact resolution, historical-message provenance and backfill cutover rules.
5. Select the bounded first pilot and rollback criteria after reviewing the implementation proposal; no live activation is authorized by this saved plan.

## Saved plan

The following records the completed planning review. Statements about no project-file changes refer to that review; this subsequent save adds only this Markdown handoff.

Yes—we can bring WhatsApp into the same Chatter, with **one customer entry and Telegram/WhatsApp icons that switch between separate conversations**. The recommended approach is a companion integration addon, keeping `ab_whatsapp_api` source files unchanged.

This was a planning-only review. No project files, configuration, databases, delivery switches, or running services were changed, and no customer messages were sent.

**Contact sharing and resuming the flow**

We can reuse the customer-matching and order workflow, but WhatsApp needs its own identity handling.

| Situation | Recommended behavior |
|---|---|
| Telegram customer shares their own contact | Retain the existing Telegram verification and matching process. |
| WhatsApp provides a phone-bearing sender identity | Use authenticated sender evidence to find candidate CRM customers. Avoid an unnecessary contact-sharing step. |
| WhatsApp exposes a business-scoped user ID without a phone | Preserve that identifier; request contact information when supported and needed for matching. |
| Customer sends someone else’s contact card | Treat it as supplied contact information, not proof of the sender’s identity. |
| Matching remains ambiguous | Let an authorized agent select or create the CRM customer; never merge automatically by name. |

This distinction matters now: Meta’s June 2026 developer material describes usernames, **business-scoped user IDs (BSUIDs)** and a **REQUEST_CONTACT_INFO** feature. Therefore, copying Telegram’s phone-sharing implementation directly would be incomplete. Availability and exact payload handling must be checked against your configured account/API version before implementation. [Meta developer briefing](https://developers.meta.com/resources/videos/whatsapp-usernames/)

Once matched, the agent can resume the existing CRM/OMS flow. Switching channels must not create another order, resend anything, or change an existing order’s originating channel.

**What the source review confirmed**

- **The contact duplication is architectural:** WhatsApp stores `ab.whatsapp.contact`; Chatter uses CRM customers and channel identities. The WhatsApp record should remain as the channel record, linked to the CRM customer—not deleted to remove the duplicate display. Its current identifier is globally unique, without company/branch ownership fields. [Contact model](/opt/odoo19/worktrees/callcenter19/ab_whatsapp_api/models/whatsapp_contact.py:5)
- **Channel navigation already exists**, but it groups conversations only when they share the same CRM customer. WhatsApp replies are explicitly deferred, and the composer is Telegram-only. Adding an icon alone will not enable WhatsApp. [Workspace backend](/opt/odoo19/worktrees/callcenter19/ab_crm_sales_workspace/models/workspace.py:491), [composer](/opt/odoo19/worktrees/callcenter19/ab_crm_sales_workspace/static/src/workspace.xml:41)
- **Identity compatibility needs work:** the WhatsApp service strips identifiers to digits, while ingestion expects phone-style `wa_id/from` values. It also lacks dedicated parsing for incoming contact-card messages. [Service normalization](/opt/odoo19/worktrees/callcenter19/ab_whatsapp_api/models/whatsapp_service.py:62), [ingestion](/opt/odoo19/worktrees/callcenter19/ab_whatsapp_api/models/whatsapp_service.py:1390)

The following are source-confirmed activation risks, not executed exploit results:

| Priority | Finding and required correction |
|---|---|
| P1 | Public webhook POST processing has no signature check in the controller; the public ingestion method also lacks a caller check before elevated writes. Authenticate ingress and prevent direct ORM bypass before trusting identity or receipt evidence. [Controller](/opt/odoo19/worktrees/callcenter19/ab_whatsapp_api/controllers/main.py:32) |
| P1 | Existing service APIs are administrator-only, while contacts lack tenant scope. Add narrow PIN-authorized bridge operations and explicit company/branch/account mappings; do not grant agents administrator access. [Access check](/opt/odoo19/worktrees/callcenter19/ab_whatsapp_api/models/whatsapp_service.py:28) |
| P1 | Ingestion creates records without provider-message deduplication; outbound text calls Meta before saving the message. Add durable send intents, concurrent deduplication and uncertain-outcome handling. [Send path](/opt/odoo19/worktrees/callcenter19/ab_whatsapp_api/models/whatsapp_service.py:1086) |
| P1 | Contact deletion physically removes the contact and cascades its messages. Chatter must archive locally and protect linked history from destructive source operations. [Delete method](/opt/odoo19/worktrees/callcenter19/ab_whatsapp_api/models/whatsapp_service.py:772), [message relation](/opt/odoo19/worktrees/callcenter19/ab_whatsapp_api/models/whatsapp_message.py:17) |

**Proposed migration and dual-channel plan**

1. **Establish the integration boundary.**  
   Add `ab_crm_whatsapp_workspace`, depending explicitly on the workspace and `ab_whatsapp_api`. Keep WhatsApp credentials, provider operations and canonical messages with the existing owner. The bridge owns CRM links, scoped projections and staff actions. Do not activate the generic gateway as a second WhatsApp sender. Reuse the working Meta number/app setup; this is a workspace integration, not a phone-number migration.

2. **Map contacts and history without sending.**  
   Inventory the installed version, configured API version, business-number ownership and existing data without exposing credentials. Create explicit company/branch/account mappings. Link existing WhatsApp records to CRM customers through reviewed identity matches. Keep ambiguous matches and records with missing account evidence unresolved. Preserve master customers, verified identities, historical orders and accepted snapshots.

   Import or project history with stable source links and account-scoped provider message IDs. Retain original timestamps; old history must not trigger fresh alerts or reopen a messaging window. Historical records cannot acquire authenticated provenance retroactively.

3. **Enable channel-icon navigation.**  
   Show one customer entry with Telegram and WhatsApp conversation selectors. Each stream retains its own messages, unread state, alerts, reply targets and unsent draft. Make the selected channel clear beside the composer. Contacts without a valid channel conversation remain visible with a simple sending explanation. Preserve shared PIN-agent access, hidden employee attribution and separate Orders.

4. **Add the live-operation safeguards through the companion layer.**  
   Use supported Odoo model/controller extensions and, where appropriate, authenticated ingress controls. Cover signature verification, account validation, direct-RPC restrictions, media authorization, deduplication, history protection and a durable outgoing queue. Preserve identifiers as opaque values; keep normalized phone numbers separately.

   **Keeping the owner’s files unchanged still requires extending some runtime behavior.** A display-only bridge cannot repair its exposed ingestion or destructive operations. If those paths cannot be guarded through the companion layer, live activation remains gated; the read-only integration is the first deliverable.

5. **Pilot WhatsApp replies alongside Telegram.**  
   Start with text replies for one explicitly mapped intake scope. Validate the PIN employee, Odoo user, company, branch, conversation and sender account on every action. Store the outgoing intent before dispatch; uncertain sends must not be blindly retried.

   Enforce the customer-service window from authenticated inbound timestamps. WhatsApp permits non-template replies within 24 hours of a customer message; outside that window, use an approved template with explicit agent action and applicable opt-in checks. Sending a template alone must not be treated as a customer reply. [WhatsApp messaging policy](https://whatsappbusiness.com/policy/)

   Reuse one bubble/footer across attempts. Display Delivered/Read only from authenticated WhatsApp receipts; employee reads remain separate. Keep Telegram’s current capability limits. Add media, reactions and contact-information requests only after their individual paths pass validation.

6. **Expand after acceptance, with a reversible rollback.**  
   During the pilot, make Chatter the designated staff sending surface. Any continued sending from the administrator dashboard must share the same controls to avoid conflicting dispatches. Rollback disables bridge sending and synchronization while retaining mappings, history and uncertain intents; it never replays queued messages automatically.

**Acceptance gates**

Before activation, verify:

- Two authorized PIN agents can use both channels without claiming; forged, expired and cross-company/branch requests fail.
- The same customer appears once; ambiguous phones, shared numbers and phone-hidden identities do not cause incorrect merges.
- Duplicate/reordered webhooks, delayed receipts and send timeouts do not duplicate bubbles or messages.
- Channel switching preserves drafts and targets; alert navigation opens the correct stream and latest pending customer message.
- Historical backfill does not reset service windows or flood notifications.
- Archival preserves messages, identities, orders and audit evidence.
- English, both Arabic catalogs, RTL and mobile layouts work; isolated targeted install/upgrade checks pass, including the applicable `--dev=xml` checks.
- `ab_whatsapp_api` source remains unchanged and only the intended transport sends WhatsApp messages.

The earlier plan’s owner-file edits and claim workflow should be superseded by this companion-addon/shared-access design. I have left that plan file untouched.

Some detailed Meta developer endpoints returned HTTP 429 during review. The current Meta briefing and WhatsApp policy were accessible; exact BSUID/contact-request schemas and your account’s feature availability remain implementation prerequisites.
