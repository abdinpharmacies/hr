# Obfuscation-Safe Code

When writing or modifying code:

- Do not rely on class, function, library, or runtime type names as string values.
- Do not compare `runtimeType.toString()` or other runtime/reflection-derived names against hard-coded strings.
- Do not use class, function, or library names as persisted identifiers.
- Do not use runtime-derived type names for serialization, persistence, routing, cache keys, or API identifiers.
- Prefer type-safe checks or stable, explicit identifiers when a name must be persisted, compared, or serialized.
