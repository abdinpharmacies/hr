# Ownership and Optional Dependencies

Required cross-module fields create registry dependencies: declare their owning
modules in `depends`, including `ab_hr` for its models/fields. Use manifest
dependencies or deliberate `auto_install` for installation relationships, never
Python auto-install calls. Keep groups and group memberships in security XML/CSV.

For a truly optional integration, avoid unconditional relational fields or
XML references to an absent model. Use a separately scoped integration addon or
an existing runtime-availability pattern. A runtime lookup must handle absence;
`env['missing.model']` alone does not make a dependency optional.

The source's `@api.constrains('store_ids')` example checks writes only and is not
a substitute for read/search/field security. Do not silently allow access when a
user lacks a branch mapping. Apply server-side restrictions across public
methods, headers and lines, and check intended manager/admin roles first.

Preserve existing XML IDs, native model names and ownership. Do not use `env.ref()`
to create records owned by another module. New module/model names use the
project's underscore convention. New frontend code uses module-scoped classes,
components and templates; no unrelated shared-component changes or full overrides.

Use XML IDs for stable configured-record references instead of hardcoded numeric
database IDs. This does not prohibit normal ORM record IDs or traceable external
transaction identifiers. Do not rename existing XML IDs without explicit approval.

For SEO, `ab_website_sale_product` owns source product/template/image/stock sync.
Use the SEO skill to define the approved-content publishing handoff.
