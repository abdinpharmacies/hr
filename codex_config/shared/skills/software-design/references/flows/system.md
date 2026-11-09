# System flow

Use when the user asks how the software works internally, what calls what, where data comes from or goes, or how infrastructure participates. Start from a real entry point and trace the relevant request, event or job through actual components and stores. For each important arrow identify the operation or data, its direction, and whether it is synchronous or asynchronous when known.

Separate clients, application boundaries, persistence, external integrations and background work where they exist. Mark unverified runtime or deployment links instead of drawing them as confirmed. A module or package is not automatically a separately deployed service.

Use the [Understand](../understand.md) guidance for source evidence and [Whole-system coverage](../system-coverage.md) only for whole-system requests. The [accepted usage-flow example](../../assets/usage-flow-reference.png) is not a system-flow reference. Do not infer a system graph from its actor arrows; inspect the implementation.

The system-flow image layout is still open to refinement. Choose a readable technical view for the requested scope without presenting the usage-flow layout as the final system-flow design.
