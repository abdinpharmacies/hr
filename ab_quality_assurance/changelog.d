Area Manager – Read Only: managed branch departments

The existing role now reads visits, sections, lines, and dashboard totals only
for active direct child departments of active departments managed by the user's
active linked employees. Child departments must link to active branch stores.
Parent offices, grandchildren, shared regions, employee reporting ancestry, and
explicit user department assignments do not grant this role additional access.
Missing mappings grant no access. Reports retain the same record-rule scope.

Existing read-only ACLs, chatter/activity restrictions, and manager/admin access
are preserved. Odoo permissions remain additive: assign this as the user's only
QA role for area-only read access. Existing XML IDs and assignments are retained.

Deployment: restart Odoo workers and upgrade only ab_quality_assurance. After HR
manager, employee, department-parent, or store mapping changes, restart all workers
to discard cached rule domains before relying on the changed permissions. Tests
explicitly clear the rule cache; automatic cache revocation is not implemented.
No production upgrade or HR data changes are performed by this source change.

Validation (isolated database): all 13 Area Manager tests passed on fresh install
and on upgrade from the unchanged role. The full QA suite has three pre-existing
failures, reproduced against the unchanged module: standard-management access,
section-manager chatter visibility, and visit department-change section unlink.
