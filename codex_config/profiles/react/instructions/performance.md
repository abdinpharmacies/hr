# Performance

- Eliminate waterfalls first: run independent async work with `Promise.all()` and defer awaits until the point of use.
- Keep the initial bundle lean: import directly (avoid barrel files) and dynamically import heavy or rarely-used components.
- Defer third-party scripts (analytics, logging, chat) until after hydration.
- Keep input responsive with `useDeferredValue` or `startTransition` for non-urgent updates.
- Derive state during render rather than syncing it through `useEffect`.
- Memoize only when a profile shows meaningful render cost; avoid premature optimization.
- Hoist static objects (Intl formatters, RegExps, constants) out of render and loops.
- When a decision needs detail or Next.js specifics, load the `react-best-practices` skill instead of approximating.