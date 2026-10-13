---
description: Handling assets in Flutter. Applies only to asset-related work.
---
# Flutter Assets

Apply these when working on assets.

- Inspect the project only when asset work actually requires it.
- Use the project's existing asset-generation system when one exists.
- Prefer generated asset references over raw strings when generation is configured.
- Declare new asset directories in `pubspec.yaml`.
- Do not invent an asset generator.
- If no generator exists, do not block unrelated work; ask only if asset generation is actually necessary.
