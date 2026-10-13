# Web behavior

Determine static, server, or client mode before editing entrypoints or browser access.
In SSR/SSG, hydrate the interactive subtree, keep initial markup deterministic, and serialize
only public initial values. Preserve generated initialization and never edit generated options.
Keep server-only and browser-only import graphs compatible; runtime guards alone cannot fix
incompatible imports. Guard browser access in shared code and cancel listeners on disposal.

Use semantic headings, real links, action buttons, form labels, keyboard focus, and useful
alternative text. Keep titles and metadata appropriate to each route. Verify direct deep
links and not-found behavior. Use the existing CSS/Tailwind pipeline and responsive DOM layout.

Use one explicit input model for forms spanning multiple components. The parent owns it,
children call named updates, and submission passes the model to the existing application
flow. Validate inputs and expose errors accessibly. Follow established project patterns
when they already provide a coherent form solution.
