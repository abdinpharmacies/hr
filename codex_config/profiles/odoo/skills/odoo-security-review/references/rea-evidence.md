# REA handoff for Odoo security review

Load the independent `reverse-engineer-anything` skill only for a specific gap in deployed-client evidence: an unexpected request, shipped Owl/JavaScript asset, portal interaction, or changed frontend behavior. Use the available browser/capture or JavaScript analysis tools; ordinary source inspection does not require REA.

Record the deployment/asset identity, observed actor and company/branch, relevant request or asset location, coverage, and redacted evidence. Trace the observation to its controller or public method and the actual model operations. Review `sudo()` scope, explicit ACLs, record rules, field groups, and cross-company/branch relations with the existing permission architecture.

If active validation is requested, use the agreed environment and designated accounts/records. Check the expected allow/deny behavior for normal-user, portal/public, and cross-company cases that apply. A hidden button, client domain, recorded response, or static asset alone cannot establish the current server policy. Missing source or test access remains a limitation. Review does not authorize database mutation or expanding tests to every discovered endpoint.

Return the evidence to the security review's finding format, include the smallest fix, and rerun the relevant normal-user test when fixes are in scope. Do not replace this workflow with a generic mobile pentest or claim that REA performs an ORM security audit. Its MCP runtime remains separately installed and disabled pending approval.
