# Architecture Review Checklist

## Dependency Management

- Are dependencies one directional?
- Are circular dependencies present?
- Are projects tightly coupled?

## Modularity

- Are components clearly separated?
- Are responsibilities well defined?

## Maintainability

- Are projects too large?
- Is documentation available?
- Can components be tested independently?

## Layering

- What layers does the code actually have? Infer them from folder and
  project names (e.g. `Api`, `Domain`, `Infrastructure`, `ui`, `core`),
  not from a textbook pattern.
- Do dependencies point one way between those layers (e.g. UI → domain,
  never domain → UI)?
- Name any edge in the graph that points the wrong way.
