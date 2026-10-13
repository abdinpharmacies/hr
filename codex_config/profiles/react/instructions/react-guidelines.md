# REACT GUIDELINES

## Language & Tooling

- TypeScript-first for new projects.
- Prefer function components and hooks over class components.
- Use modern JSX/ESM conventions consistent with the project's bundler (Vite, Next.js, etc.).

## Component Modeling

- Prefer small, focused components over monolithic ones. Model reusable UI as components, not ad-hoc inline markup.
- Keep component files focused; extract reusable pieces into their own files.
- Use `const`/memoization judiciously; avoid premature optimization.

## State & Effects

- Favor local state and derived values; lift state only when genuinely shared.
- Use hooks correctly (dependencies arrays, cleanup). Avoid `useEffect` for derived state when a direct computation suffices.

## Styling

- Follow the project's established styling approach (CSS modules, Tailwind, CSS-in-JS) rather than introducing a new system.

## Dependencies & Versions

- Never guess package versions. Before adding a package, perform a live web search to retrieve the absolute latest stable version.
- Avoid adding a dependency when platform or existing project utilities suffice.

## Code Quality

- Clean code: single responsibility principle and DRY.
- Use clear, descriptive, accurate naming.

## Comments Rule

- Do NOT add comments to code unless the user explicitly asks.
