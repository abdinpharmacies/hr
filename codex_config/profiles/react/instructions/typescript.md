# TypeScript

- TypeScript-first for all new code; avoid `any` and avoid silencing strict-mode errors with casts.
- Use `interface` for props and object shapes, `type` for unions and derived types.
- Type event handlers, refs, and hook return values explicitly; don't leak implicit types across boundaries.
- Prefer `as const` for static configuration and discriminated unions for complex state over nullable fields.
- Keep types colocated with usage; extract shared types to dedicated files only when reused.
- Never guess package versions or typings; verify against documentation before adding anything new.