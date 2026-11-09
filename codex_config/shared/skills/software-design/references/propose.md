# Propose a design or better split

Identify the decision, constraints and current friction. When code exists, inspect only the affected feature and its direct dependencies first. For a new idea, design from stated requirements and mark assumptions; do not fabricate an existing implementation.

Recommend the smallest separation that improves a concrete concern: ownership, state consistency, testability, change isolation, failure handling or measured cost. Keeping the present design is a valid result. Do not introduce a repository, service, queue or abstraction merely because a pattern normally contains one.

For each proposed part state its responsibility, inputs/outputs, state or data owner, dependencies and errors. In client code distinguish presentation, state transitions, side effects and data access according to the project's existing framework. Explain event direction and response/state updates; a folder tree alone does not explain runtime behavior.

Compare a credible alternative when it helps the decision, including keeping the current implementation. Explain benefits, added complexity and conditions that would change the recommendation. Do not promise faster execution from structural cleanup alone.

Read [Diagrams](diagrams.md) to show the proposal. Use separate current/proposed views only when both help; a greenfield proposal needs no fictional before view. Keep stable names across views. Finish with a short migration order and validation criteria when modifying existing software is relevant. Implement only within the user's existing authorization.
