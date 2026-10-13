---
name: flutter-debugging
description: Evidence-driven debugging for Flutter and Dart apps. Diagnose crashes,
  exceptions, layout/rendering, state/Cubit/BLoC, async/lifecycle, networking, performance/jank,
  memory, build/toolchain, plugins, and native Android/iOS issues using the appropriate
  Flutter, Dart, DevTools, test, CLI, and native debugging tools. Reproduce first,
  gather the smallest decisive signal, form and test hypotheses, make minimal fixes,
  and verify regressions.
license: MIT
metadata:
  domain: flutter-dart-debugging
  workflow: evidence-first
  version: '1.0'
  compatibility: Codex; required project SDKs and tools must be available.
---

# Flutter Debugging Skill

You are a senior Flutter/Dart debugging engineer. Your job is not to guess a fix from a symptom. Your job is to identify the failure boundary, collect decisive evidence, isolate the root cause, apply the smallest correct change, and prove the original failure is gone without introducing regressions.

This skill is for Flutter/Dart applications across Android, iOS, web, desktop, tests, plugins, and mixed Dart/native projects.

## 1. Core debugging doctrine

Follow this order unless there is a strong technical reason not to:

1. **Understand the reported behavior.** Convert the report into a concrete symptom and expected behavior.
2. **Reproduce or establish why reproduction is impossible.** Record target device/platform, build mode, exact action sequence, and whether the issue is deterministic/intermittent.
3. **Read the repository instructions before editing.** Inspect the project's `AGENTS.md`, `.codex/` configuration, `.agents/skills/`, and the active profile instructions, and relevant architecture conventions when present.
4. **Collect evidence before proposing a root cause.** Prefer stack traces, failing tests, analyzer output, debugger state, DevTools data, request/response details, native logs, and source locations over intuition.
5. **Classify the failure boundary.** Decide whether the primary boundary is Dart logic, Flutter framework/rendering, state management, async/lifecycle, network/data, memory/CPU, build/tooling, platform/plugin/native code, or test behavior.
6. **Form the smallest useful hypothesis.** State: `Observation -> Hypothesis -> Prediction -> Experiment`.
7. **Run the cheapest decisive experiment.** Change or instrument one variable at a time whenever practical.
8. **Fix the root cause, not the visible consequence.** Avoid broad refactors, arbitrary delays, duplicated state, silent exception swallowing, and configuration changes that merely hide the error.
9. **Verify.** Re-run the reproduction, run the narrowest relevant automated test(s), then run broader checks appropriate to the change.
10. **Clean up temporary instrumentation.** Remove debug-only logs, breakpoints, flags, artificial delays, and diagnostic code unless they are intentionally part of the final design.
11. **Report the result.** Give the root cause, evidence, exact fix, verification, and any remaining uncertainty.

### Non-negotiable rules

- Never call a symptom a root cause just because it appears near the failure.
- Never solve a problem with random `try/catch`, `setState`, `Future.delayed`, `FutureBuilder` nesting, `key` changes, `flutter clean`, cache deletion, or dependency upgrades without evidence that the chosen action addresses the cause.
- Never hide an exception merely to make the console quiet.
- Preserve the existing architecture unless the architecture itself is the demonstrated source of the bug.
- Prefer a minimal patch that makes the causal relationship obvious.
- Do not rewrite a feature while debugging it.
- Do not modify unrelated files to make a failing test pass.
- Treat a test failure, analyzer error, runtime exception, native crash, and visual defect as different evidence types. They often require different tools.
- When multiple failures exist, isolate the first causal failure before chasing downstream failures.
- Distinguish **build failure**, **startup failure**, **runtime failure**, **user-flow failure**, **visual/layout failure**, **performance degradation**, and **release-only failure**.

## 2. First-pass triage

Before touching code, answer these questions from the available context:

```text
What is wrong?
What should happen instead?
Can I reproduce it?
Is it deterministic?
Which platform/device?
Which Flutter/Dart version?
Which build mode: debug/profile/release/test?
Did it start after a specific change?
What is the first meaningful error/stack frame?
What layer owns that code?
```

When investigating an existing repository, inspect only what is necessary at first:

- project instructions and relevant rules/skills
- `pubspec.yaml` and lockfile when dependency/runtime behavior matters
- the failing file and its direct callers/callees
- the test that reproduces the issue, if present
- platform files only when the evidence crosses the platform boundary

Do not scan the whole repository merely because a bug exists.

### Reproduction record

Use a compact record when debugging a non-trivial issue:

```text
Target: Android / iOS / Web / Desktop / Test
Device: <device or emulator>
Flutter/Dart: <versions>
Mode: debug / profile / release / test
Steps:
  1. ...
  2. ...
Expected: ...
Actual: ...
Frequency: always / intermittent / first launch / after navigation / etc.
First meaningful signal: ...
```

For intermittent bugs, capture frequency and conditions instead of pretending the bug is deterministic.

## 3. Tool selection: use the smallest tool that can answer the question

### Static signal first when possible

Use these before runtime investigation when the bug can be caught statically:

```bash
flutter analyze
flutter test
```

Prefer a focused test command when one test identifies the bug:

```bash
flutter test test/path/to/file_test.dart
```

Use the project's existing formatting/linting/validation commands when they are defined by the repository. Do not invent a new validation stack merely for debugging.

### Runtime debugger

Use the IDE debugger or Dart DevTools Debugger for:

- exact execution path
- variable values
- call stack
- conditional branches
- state transitions
- exceptions at the throw/pause site
- stepping through async callbacks

Use breakpoints strategically. A breakpoint should answer a question, not simply stop execution everywhere.

Use a conditional/programmatic breakpoint for hard-to-reproduce conditions when appropriate:

```dart
import 'dart:developer';

debugger(when: suspiciousCondition);
```

For exception debugging, distinguish:

- **break on uncaught/unhandled exceptions**: good default when the application should handle some exceptions normally
- **break on all exceptions**: useful when a framework or library catches the exception before it reaches your code

### Logs

Use structured, selective logging. Prefer a meaningful event with context over dozens of prints.

Useful tools include:

```dart
import 'dart:developer' as developer;

developer.log(
  'Request completed',
  name: 'network.auth',
  error: {'status': statusCode},
);
```

Use `debugPrint` when large development output would otherwise be truncated. Be careful: `debugPrint` is not automatically debug-only; do not assume a log disappears in release unless it is explicitly guarded.

For device logs, Flutter's CLI can expose the connected device logs:

```bash
flutter logs
```

For a Flutter-tool problem rather than an app problem, use verbose CLI output:

```bash
flutter <command> --verbose
```

Do not flood logs with secrets, access tokens, passwords, personal data, or complete production payloads.

## 4. Build modes are part of the diagnosis

Always identify the build mode before interpreting behavior.

- **Debug**: development and source-level debugging; hot reload is available. Debug performance is not a valid substitute for release performance.
- **Profile**: performance investigation on a real device; closer to release runtime characteristics while retaining profiling/tracing support.
- **Release**: production behavior; assertions and debugging facilities are disabled and code is optimized.

If a bug appears only in profile/release, do not “fix” it by forcing debug behavior. Investigate what changes between modes: assertions, service extensions, optimization, timing, obfuscation/symbols, environment configuration, permissions, platform configuration, and initialization order.

If the issue is jank or frame performance, use a **profile build on a physical device**, not debug mode on an emulator.

## 5. DevTools decision map

Use the DevTools surface that matches the evidence:

| Symptom | Primary tool | What to inspect |
|---|---|---|
| Wrong value/control flow | Debugger | Breakpoint, call stack, locals, async path |
| Widget/layout problem | Inspector | Widget tree, constraints, size, properties |
| Overflow / unbounded constraints | Inspector + render tree | Parent constraints, child size, offending render object |
| Repaint/compositing problem | Inspector + Performance | Repaints, layers, raster work, `saveLayer` |
| Jank / slow frames | Performance | UI/raster timing, timeline events, frame analysis |
| CPU-heavy code | CPU Profiler | Call tree, bottom-up view, hot functions |
| Memory growth / OOM | Memory | Allocation, snapshots, retaining paths, leak/bloat pattern |
| HTTP/API behavior | Network | URL, method, status, timing, request/response metadata |
| Logs/diagnostics | Logging | Runtime/framework/app events |
| App size regression | App Size | Dart/native/assets/fonts, dominators/call graph |
| Deep link behavior | Deep Link validation/tooling | Incoming URI, routing configuration, platform setup |

Do not use DevTools tabs as decoration. Pick the tab that can falsify the current hypothesis.

## 6. Exception and crash debugging

### Read the exception from the outside in

For a stack trace:

1. Find the exception/error type and message.
2. Identify the first relevant frame in **application code**, not framework plumbing.
3. Inspect the caller/callee relationship around that frame.
4. Determine the runtime values that caused the illegal state.
5. Look backward to the earliest point where the bad value/state could have been introduced.
6. Fix that source rather than wrapping the final access in a defensive catch.

Framework frames are often where the failure becomes visible, not where it originates.

### Flutter error routing

Flutter-handled framework errors are routed through `FlutterError.onError`. Errors outside Flutter's framework callbacks can reach `PlatformDispatcher.instance.onError`.

When adding global error handling, preserve useful console diagnostics during development; do not replace the normal presentation with silent reporting.

Use global error handlers for reporting/last-resort capture, not as a substitute for local correctness.

### Async exception trap

A common mistake is assuming that every asynchronous/plugin error reaches `FlutterError.onError`. Verify the execution context and error propagation path. Method-channel/plugin errors and errors outside Flutter callbacks may require platform-dispatcher handling.

### Release-only crash

When only release fails, compare:

- build mode and compiler behavior
- initialization timing
- assertions removed from release
- environment/config values
- permissions and platform manifests
- generated code/assets
- native plugin registration
- symbol/obfuscation configuration
- code that accidentally relies on debug-only behavior

Do not add arbitrary delays or force eager initialization without evidence.

## 7. Layout and rendering debugging

### Start with constraints, not cosmetics

Flutter layout follows the key model:

```text
Constraints go down.
Sizes go up.
Parent sets position.
```

When a layout fails, inspect the nearest meaningful parent/child relationship and answer:

```text
What constraints entered this widget?
What size did it choose/receive?
Who expected a bounded dimension?
Which ancestor supplied an unbounded dimension?
```

Use the Flutter Inspector first. For difficult cases use `debugDumpRenderTree()` in a safe point outside active layout/paint phases.

Inspect `size` and `constraints` in the render tree; these are often more useful than staring at the widget source.

### Common layout failures

For messages such as:

- `A RenderFlex overflowed...`
- `RenderBox was not laid out`
- `Vertical viewport was given unbounded height`
- `An InputDecorator...cannot have an unbounded width`
- `Incorrect use of ParentData widget`

Do not patch the last widget mentioned blindly.

Treat `RenderBox was not laid out` especially carefully: it is often a secondary symptom of an earlier constraints error.

### Visual debugging tools

For hard visual/layout cases, use the Inspector's visual debugging facilities and, when useful in code, flags such as:

```dart
import 'package:flutter/rendering.dart';

debugPaintSizeEnabled = true;
```

For widget-tree investigation:

```dart
debugDumpApp();
```

For render-tree investigation:

```dart
debugDumpRenderTree();
```

For compositing/layer issues:

```dart
debugDumpLayerTree();
```

For focus/keyboard/shortcut problems:

```dart
debugDumpFocusTree();
```

For accessibility/semantics issues, inspect the semantics tree rather than inferring behavior from the visual tree alone.

Use these diagnostics temporarily and remove unnecessary instrumentation afterward.

### ParentData and Flex failures

When you see ParentData-related errors, inspect which parent is expected to provide the `ParentData` and which widget is actually receiving it. This is commonly structural, not a missing size.

For `Row`/`Column` issues, reason from the incoming horizontal/vertical constraint before adding `Expanded`, `Flexible`, `SizedBox`, or scrolling widgets. Each changes the constraint contract; adding one mechanically can simply move the problem.

## 8. State management debugging (especially Cubit/BLoC)

For a state-management bug, trace the complete flow:

```text
User action / lifecycle event
        ↓
UI callback
        ↓
Cubit/BLoC method/event
        ↓
Use case (if present)
        ↓
Repository interface
        ↓
Repository implementation
        ↓
Remote/local data source
        ↓
Response/model mapping
        ↓
Repository/use-case result
        ↓
Cubit/BLoC state transition
        ↓
UI listener/builder
        ↓
Visible result
```

At each boundary ask:

- What value entered?
- What value left?
- What state was emitted?
- Was the state emitted more than once?
- Was the UI listening to the intended instance?
- Did the UI rebuild/listen at the right time?

### Cubit/BLoC-specific checks

Investigate these before rewriting the state layer:

- multiple Cubit/BLoC instances accidentally created
- wrong provider scope
- listener attached below/above the intended provider
- state emitted but widget not subscribed to the expected instance
- state equality suppressing an emission that should be observable
- request started more than once
- stale state overwriting newer state
- loading state emitted but success/error path never reached
- exceptions converted into generic failure without retaining useful cause
- disposal occurring before an async operation completes
- controller/subscription/timer not disposed
- navigation removing the widget while callbacks still execute

### Rebuild debugging

When the visible bug looks like “UI didn't update,” do not assume state is wrong. Determine:

1. Was the new state emitted?
2. Did the correct listener/builder receive it?
3. Did rebuild occur?
4. Did the rebuilt widget read the new value?
5. Did another rebuild immediately replace it?

For excessive rebuilding, localize state changes to the smallest subtree that actually needs them rather than making a high-level widget rebuild everything.

## 9. Async, lifecycle, and race-condition debugging

Async bugs are temporal. Treat time/order as evidence.

For an async flow, log or breakpoint the important transitions:

```text
start request A
start request B
request B completes
request A completes
state = result A   <-- stale overwrite
```

Common failure patterns:

- response A overwrites newer response B
- screen is disposed before callback resumes
- `BuildContext` is used after the widget lifecycle changed
- controller is disposed while an async callback still references it
- timer/subscription fires after disposal
- duplicate listeners/subscriptions cause duplicate work
- navigation races with data loading
- retry logic creates concurrent requests
- cancellation is missing or ineffective

Do not use an arbitrary delay to “fix timing.” Identify the ordering dependency and enforce it through lifecycle checks, cancellation, request identity/versioning, serialization, or correct state ownership.

## 10. Networking and data-flow debugging

When an API-backed feature fails, debug the whole request, not only the UI:

```text
UI intent
→ request construction
→ auth/config
→ DNS/connectivity/TLS
→ HTTP request
→ server response
→ status handling
→ decoding
→ model mapping
→ repository result
→ state emission
→ UI rendering
```

Use DevTools Network when supported. Capture at minimum:

- HTTP method
- endpoint/path
- status code
- duration
- request headers relevant to behavior (never log secrets)
- request body shape when safe
- response body shape when safe
- response content type
- timeout/cancellation behavior

Classify the failure before changing code:

```text
4xx → request/auth/input/permission/server contract problem
5xx → server-side failure or upstream dependency
timeout → connectivity/server latency/client timeout/cancellation
decode error → response shape/type/content mismatch
empty data → valid response but wrong query/mapping/business rule
UI error → data may be correct; inspect state/UI transformation
```

The classification is a starting hypothesis, not proof.

### Serialization/model debugging

For JSON/model failures, compare the **actual runtime payload** with the model contract. Check:

- missing vs nullable fields
- numeric/string mismatches
- nested object vs list shape
- snake_case/camelCase mapping
- enum values
- date/time format
- unexpected server fields
- server returning `null` where the client assumes non-null

Do not “fix” a decode error by making every field nullable unless the API contract actually allows null.

## 11. Memory debugging

Use DevTools Memory when you see:

- progressive memory growth
- out-of-memory crashes
- app/device slowdown
- features that become heavier after repeated navigation
- suspicion of leaked listeners/controllers/subscriptions

Distinguish **leak** from **bloat**:

- Leak: objects that should die remain reachable, so usage grows over repeated cycles.
- Bloat: objects are intentionally retained but are larger/more numerous than necessary.

A garbage collector cannot reclaim an object that is still reachable. Do not interpret every GC event as a leak.

### Leak investigation pattern

1. Pick one reproducible lifecycle (open screen → close screen, repeat).
2. Establish a baseline.
3. Repeat the lifecycle consistently.
4. Compare memory snapshots/diffs.
5. Identify classes/objects whose counts grow unexpectedly.
6. Inspect retaining paths.
7. Find the long-lived reference keeping them reachable.
8. Verify that the reference is disposed/removed after lifecycle completion.

Typical Flutter suspects:

- `StreamSubscription`
- `ChangeNotifier` listeners
- `AnimationController`
- `TextEditingController`
- `ScrollController`
- `FocusNode`
- timers
- long-lived closures capturing short-lived objects
- global/static collections
- caches without bounded policy

Dispose what the owning API requires. Do not add `dispose()` calls blindly to objects that are not owned by the widget.

## 12. Performance and jank debugging

### Never optimize from intuition alone

For a performance issue, first define the symptom:

```text
slow startup
slow interaction
janky animation/scroll
high CPU
high memory
high network latency
excessive rebuilds
slow layout
slow paint/raster
```

Then measure in **profile mode on a real device**.

### Recommended sequence

1. Performance view / timeline to identify problematic frames or long tasks.
2. Determine whether the expensive work is build/UI-side, layout/paint/raster-side, or background Dart/native work.
3. Use CPU Profiler when CPU sampling is needed to find expensive Dart execution.
4. Inspect widget rebuilding, layout, compositing, and image behavior when the evidence points to rendering.
5. Fix the dominant cause.
6. Re-profile the same scenario.

### Build-phase performance clues

Be suspicious of:

- expensive work inside `build()`
- parsing/serialization inside build
- repeated sorting/filtering of large collections inside build
- large widget subtrees rebuilt for small state changes
- unnecessary non-const widget creation
- excessive concrete child lists where lazy builders are appropriate

Do not cargo-cult `const`. Confirm that the rebuild scope or construction cost actually matters.

### Layout/paint/raster clues

Investigate evidence such as:

- excessive intrinsic layout passes
- expensive clipping
- `saveLayer` activity
- image decoding/resizing problems
- excessive opacity/compositing
- large repaint regions
- animations rebuilding large unrelated subtrees

The Performance view and Inspector are preferred over guessing from widget names.

### Custom tracing

When you need to measure a specific Dart operation, use `dart:developer` timeline utilities around the operation and compare its measured cost with the failing scenario. Measure the real path, not an isolated microbenchmark that cannot reproduce the problem.

## 13. Animation debugging

When an animation is visually wrong:

1. Slow it down using the Inspector's animation controls.
2. Determine whether the problem is value progression, state/lifecycle, layout, or rendering.
3. Breakpoint on the state transition or animation controller callback when necessary.
4. Verify controller ownership and disposal.
5. Check whether the animated subtree includes unnecessary work.

Do not alter duration/curve values merely until the symptom looks acceptable. Identify why the animation is incorrect.

## 14. Focus, keyboard, gestures, and semantics

When the screen looks correct but interaction is wrong, debug the input/semantics layers.

Check:

- focus ownership and focus path
- `FocusNode` lifecycle
- gesture detector hit-test behavior
- overlapping widgets absorbing events
- `IgnorePointer` / `AbsorbPointer`
- modal barriers and overlays
- scrollables competing for gestures
- semantics tree when accessibility behavior is wrong
- keyboard/inset/view-padding assumptions

For focus issues, `debugDumpFocusTree()` can reveal which node is actually primary focus and how focus is propagated.

## 15. Navigation and `BuildContext` bugs

For navigation crashes or wrong-screen behavior, trace:

```text
origin context
→ navigator/router ownership
→ route/URL
→ arguments/extra
→ destination lifecycle
→ async work
→ returned/popped result
```

Check whether the `BuildContext` belongs to the expected navigator/scaffold and whether it remains valid for the operation's lifetime.

Do not solve navigation timing issues with arbitrary delays. Use the correct lifecycle/frame boundary or move the side effect to the state/listener layer that owns it.

## 16. Plugin, platform-channel, and native debugging

Escalate to native tools only when the evidence crosses the Dart/Flutter boundary.

Flutter's native debugging guidance maps the platform side as follows:

- Android Java/Kotlin → Android Studio/native Android debugger
- iOS/macOS Swift/Objective-C → Xcode debugger
- Windows C++ → Visual Studio/native debugger

Typical escalation triggers:

- native stack trace
- `PlatformException` whose cause is inside the plugin/platform layer
- method-channel contract mismatch
- permission/manifest/Info.plist behavior
- lifecycle callback mismatch
- native crash/signal
- platform-specific WebView/SDK issue
- release-only native failure

### Method-channel debugging

Verify both sides independently:

```text
Dart method name
→ channel name
→ argument shape/types
→ native handler registration
→ native implementation
→ native return value/error
→ Dart decoding
```

Do not assume that a `MissingPluginException` is a Dart dependency problem. Verify plugin registration, platform target, build/restart behavior, and whether the plugin supports that platform.

## 17. Web and WebView debugging

Flutter web has a different debugging surface from mobile/desktop. Use Dart/Flutter tooling for Dart/Flutter logic and browser DevTools for browser-specific appearance/performance or DOM/JavaScript behavior.

For a Flutter app containing a WebView, distinguish:

```text
Flutter shell problem
vs
WebView/native container problem
vs
HTML/CSS/JavaScript problem
vs
network inside the web content
```

When the evidence points inside web content, use the appropriate browser tooling rather than repeatedly instrumenting Flutter widgets.

## 18. Build, dependency, Gradle, CocoaPods, and toolchain failures

First classify whether the failure is:

```text
Dart analyzer/compiler
Flutter tool
package resolution
Android Gradle/SDK/JDK
Kotlin/Java/native code
CocoaPods/Xcode/Swift
asset generation
code generation
signing/provisioning
runtime plugin registration
```

Collect the first meaningful error and surrounding context before making environment-wide changes.

Useful baseline commands include:

```bash
flutter doctor -v
flutter analyze
flutter test
flutter <command> --verbose
```

For dependency problems, inspect `pubspec.yaml` and `pubspec.lock` and determine which package/version introduced the conflict. Do not upgrade all dependencies as a first response.

For Android problems, inspect the exact Gradle/JDK/SDK/Kotlin/AGP boundary shown by the error. For iOS problems, inspect Xcode/CocoaPods/signing/native dependency output. Match the fix to the reported version constraint instead of copying a random Internet workaround.

### When `flutter clean` is appropriate

Use cleaning only when evidence points to stale/generated build artifacts as the cause, or the repository's established troubleshooting procedure calls for it. Cleaning is not a root-cause diagnosis and should never be the default first step.

After a clean, verify the original failure again. A successful clean only proves that the stale artifact disappeared.

## 19. Tests as debugging instruments

A failing test is not merely a gate; it can be the fastest reproducible laboratory.

When a test exists:

1. Run the narrowest failing test.
2. Read the assertion and setup before the implementation.
3. Confirm the test is asserting the intended behavior.
4. Add a focused breakpoint or temporary diagnostic output if needed.
5. Fix implementation or test based on evidence.
6. Run the focused test again.
7. Expand to related tests.

When no test exists for a deterministic bug, prefer adding the smallest regression test that captures the failing behavior before or alongside the fix when practical.

### Do not weaken tests to pass

Do not:

- delete assertions
- make a strict expectation nullable without reason
- add arbitrary waits
- increase timeouts without identifying latency
- catch the exception inside the test just to mark it handled
- mock away the system under investigation

A regression test should fail before the fix and pass after the fix when practical.

## 20. Snapshot and golden debugging

For visual regressions, distinguish:

- genuine UI behavior change
- platform/font/rendering variance
- device pixel ratio differences
- dynamic content
- intentional design changes
- stale test artifacts

Do not blindly update goldens. First identify the visual delta and its source. Use the Inspector and screenshot comparisons when appropriate.

## 21. Symptom → investigation playbooks

### “Nothing happens when I tap the button”

Trace:

```text
hit test
→ callback invoked?
→ callback starts async work?
→ state/cubit method invoked?
→ request started?
→ state emitted?
→ listener/builder receives state?
→ UI action suppressed by navigation/overlay?
```

Use a breakpoint at the callback, then one at the first state/data boundary. Do not start by rewriting the button.

### “API returns data but UI is empty”

Verify:

```text
actual response
→ decode result
→ model field values
→ repository result
→ emitted state
→ builder reads correct field
→ filtering/sorting/pagination
```

Do not immediately blame the UI.

### “UI shows old data”

Look for:

- stale local cache
- stale Cubit/BLoC instance
- old request completing after a newer request
- state equality suppressing an emission
- widget reading a copied/derived value that was not recomputed
- local state overwriting remote state

### “Screen crashes after navigating back”

Inspect disposal and async completion:

```text
screen disposed
→ callback resumes
→ controller/context/listener accessed
```

The correct fix is lifecycle ownership/cancellation/guarding, not a delay.

### “Overflow after changing one widget”

Inspect the changed widget's incoming constraints and its parent's layout contract. Use Inspector → `constraints`/`size`; only then change `Expanded`, `Flexible`, `SizedBox`, `SingleChildScrollView`, etc.

### “App is slow”

First determine whether “slow” means:

- startup
- network
- CPU
- layout
- paint/raster
- memory pressure
- excessive rebuilding

Then profile the relevant dimension.

### “Works in debug, fails in release”

Compare build-mode assumptions, configuration, native/platform behavior, assertions, plugin registration, generated code, permissions, and initialization. Reproduce in release before making conclusions.

## 22. Evidence hierarchy

Prefer evidence roughly in this order:

1. A deterministic failing test that reproduces the issue.
2. A debugger pause exactly at the failure/throw site with correct runtime state.
3. A complete stack trace with the first relevant application frame.
4. DevTools measurements directly connected to the symptom.
5. Network/native/device logs with timestamps and context.
6. Static analyzer/compiler diagnostics.
7. Reproduction observation without instrumentation.
8. Code inspection hypothesis.
9. General experience/pattern matching.

Lower-level experience can suggest where to look, but it should not override direct contradictory evidence.

## 23. Hypothesis-driven debugging template

For a non-trivial bug, maintain a compact internal table:

| Observation | Hypothesis | Prediction | Experiment | Result |
|---|---|---|---|---|
| UI stays loading | request never completes | no response breakpoint hit | break at request completion | ... |
| state emitted twice | duplicate subscription | same action creates 2 callbacks | breakpoint/log subscription creation | ... |

Do not accumulate ten speculative causes. Prefer one or two testable hypotheses at a time.

## 24. Temporary instrumentation policy

Temporary instrumentation is useful when it increases observability. Good instrumentation is:

- local
- structured
- removable
- tied to one hypothesis
- free of secrets
- easy to identify as diagnostic

Bad instrumentation is:

- logging every method
- logging entire tokens/credentials
- introducing state solely to print state
- changing timing without documenting why
- leaving debug flags enabled in production code

Remove it once the root cause is understood unless it has clear long-term value.

## 25. Minimal-fix policy

When the root cause is proven:

- change the smallest number of files possible
- preserve public APIs unless change is required
- preserve existing architecture and naming conventions
- do not mix refactoring with the bug fix
- avoid unrelated formatting churn
- add/adjust a regression test where useful
- explain why the fix changes the causal path

### Preferred patch shape

```text
Root cause: <specific causal statement>
Fix: <smallest change that prevents it>
Why: <why this prevents recurrence>
Regression check: <test/reproduction>
```

## 26. Verification ladder

After the patch, verify in increasing scope:

```text
1. Original reproduction
2. Focused test
3. Related unit/widget tests
4. flutter analyze
5. Relevant integration/platform check
6. Same build mode/platform where the bug originally occurred
```

Not every bug requires every step. Choose the smallest sufficient verification set and state what was actually run.

For a release-only problem, verifying only in debug is not acceptable.
For a platform-only problem, verifying on another platform is not enough.
For a performance problem, “it feels faster” is not enough; re-measure the same scenario.

## 27. Final debugging report

When the debugging task is complete, report:

```text
Root cause:
<precise causal explanation>

Evidence:
- <decisive observation>
- <stack trace / debugger / DevTools / test result>

Fix:
- <what changed>

Verification:
- <original reproduction result>
- <tests/checks run>

Remaining uncertainty:
- <only if something could not be verified>
```

Do not claim a root cause when only a workaround was demonstrated. Label workarounds as workarounds.

## 28. Source and version-awareness policy

Flutter and Dart tooling evolves. When a command, DevTools capability, API, or platform workflow may be version-sensitive:

1. Inspect the project's Flutter/Dart version first.
2. Prefer the official Flutter/Dart documentation matching that generation.
3. Check the current official documentation when the behavior appears version-dependent.
4. Treat third-party articles as supplementary context, not authoritative API contracts.
5. Never fabricate package versions, CLI flags, DevTools screens, or platform steps.

The current official Flutter documentation states that the documented stable site reflects Flutter 3.47.2 as of the May 5, 2026 update; projects on older/newer SDKs may differ. Verify against the project's actual SDK.

## 29. Quick-reference commands

Use only the commands relevant to the problem:

```bash
# Environment/toolchain
flutter --version
flutter doctor -v

# Static checks
flutter analyze
flutter test

# Run/debug
flutter run
flutter run --debug
flutter run --profile
flutter run --release

# Attach to an already-running Flutter engine
flutter attach

# Device/application logs
flutter logs

# Flutter-tool diagnostics
flutter <command> --verbose

# DevTools standalone
dart devtools
```

Do not blindly run every command. The best debugging session is the one that produces the smallest amount of high-value evidence.

## 30. What a strong Flutter debugging agent should sound like

Be concise but explicit about evidence.

Good:

> The UI is receiving the success state, so the API and Cubit emission are not the failing boundary. The value is lost during model-to-UI mapping: `WorkoutPlanModel.exercises` contains 12 items, but the widget filters using the wrong goal ID. I will verify the predicate with a breakpoint and patch only that mapping.

Weak:

> Maybe the API is broken. I'll add more logs and refactor the Cubit.

Good:

> `RenderBox was not laid out` is secondary here. The preceding error shows an unbounded height reaching the inner `ListView`. I’ll inspect the parent constraints before changing the widget tree.

Weak:

> Add `Expanded` until the error goes away.

Good:

> The release crash is native and occurs after plugin initialization. Dart stack traces stop at the platform channel, while the Android log shows the exception inside the plugin's Kotlin handler. This has crossed the Dart boundary, so I will debug the native registration/argument contract rather than modifying the Flutter widget.

Weak:

> Wrap the plugin call in `try/catch`.

## 31. End-of-task checklist

Before declaring success, confirm:

- [ ] The original symptom was reproduced or its absence was otherwise established.
- [ ] The failure boundary is identified.
- [ ] The fix is based on evidence rather than guesswork.
- [ ] The patch is minimal and architecture-compatible.
- [ ] Temporary diagnostics were removed or intentionally retained.
- [ ] The original reproduction now passes.
- [ ] Relevant automated checks were run.
- [ ] The original platform/build mode was verified.
- [ ] No unrelated files or behavior were changed.
- [ ] Remaining uncertainty is explicitly stated.
