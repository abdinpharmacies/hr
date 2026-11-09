# Plain text diagrams

Use a fenced `text` block so spaces and alignment survive. Draw with ordinary characters: `+--+` boxes, `|` vertical edges, `-->` arrows, and `/` or `\` branches. This is a finished chat-readable diagram, not source awaiting Mermaid rendering.

Keep the main path left to right or top to bottom. Use short labels, named edge actions and enough spacing to see branches. Aim for at most 80 columns; split a large graph into focused views rather than shrinking labels or drawing crossing lines. Do not use a directory tree to stand in for interactions.

Example notation only, not a default system architecture:

```text
+--------+   request   +-----------+   read   +----------+
| Client | ---------->| App logic | -------->| Database |
+--------+            +-----------+          +----------+
                            |
                            | event
                            v
                      +-----------+
                      | Consumer  |
                      +-----------+
```

Use Arabic prose around the diagram. If mixed Arabic/Latin text disrupts monospace alignment, use short English component names in the diagram with an Arabic key below it; preserve actual identifiers. Label proposals and uncertain edges. Check every arrow direction against the traced flow. For paired outputs, use the same names and semantics in the image.
