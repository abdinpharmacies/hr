# Flutter Forms & Input

Apply these when working on forms, text fields, or input handling.

- Prefer managing form state via simple state plus `onChanged` / `onSubmitted`.
- Use `TextEditingController` only when programmatic manipulation is actually required.
- Dispose every controller you create (e.g., in `dispose()`).
- Use `Form` and `TextFormField` validation where appropriate.
