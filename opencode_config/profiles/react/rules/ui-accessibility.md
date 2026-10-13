---
description: UI quality and accessibility defaults for React (web) projects.
alwaysApply: true
---
# UI & Accessibility

- Prefer semantic HTML (`<nav>`, `<button>`, `<main>`, `<label>`) over generic `<div>`; never attach click handlers to non-interactive elements.
- Every interactive element needs a visible focus indicator and keyboard handler; form inputs need an associated `<label>` or `aria-label`.
- Provide `alt` text on meaningful images and `alt=""` on decorative ones; specify image dimensions to avoid layout shift.
- Maintain WCAG AA color contrast; never rely on color alone to convey meaning.
- Respect `prefers-reduced-motion`; keep animations short and compositor-friendly (transform/opacity).
- Add state attributes (`aria-current`, `aria-expanded`) where they aid navigation; use `aria-live` sparingly.