---
name: jaspr-content-models
description: Add or update typed YAML/JSON content models in Jaspr sites, including jaspr_content and existing dart_mappable pipelines.
---

# Typed Jaspr content

Inspect a real content file, its consumer, existing model conventions, and generation setup.
Keep the project serialization library; do not introduce `dart_mappable` for a simple model
unless it fits the request. Treat external YAML/JSON values as untrusted shapes and validate
required fields, supported URLs, enum values, and optional values at the parsing boundary.
Use immutable typed fields and stable serialized keys. Preserve nullability and defaults.

When `dart_mappable` is already used, follow the existing annotations, mapper parts, mapping
hooks, and generated factory pattern. Reuse project validation helpers if present. Do not
assume `lib/src/models/content`, `content_validation.dart`, or a particular test file exists.
Run the project's generator and never hand-edit generated mappers. Add focused tests for
valid content, invalid fields, and serialization when model behavior changes.

Pass typed models to components instead of scattering unchecked map casts through build
methods. In `jaspr_content`, inspect the current page data API before accessing it. Keep
private server data out of hydration payloads. Follow the active comments policy; imported
website conventions do not require doc comments on every model.
