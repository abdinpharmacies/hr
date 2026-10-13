# Jaspr Web Integration (`bloc_signals_jaspr`)

`bloc_signals_jaspr` provides Jaspr web component state binding for `BlocSignal` and `CubitSignal` containers, with platform-specific APIs that must be checked against the installed package.

---

## ⚡ Core Jaspr Components

| Component | Usage & Description |
| :--- | :--- |
| **`BlocSignalProvider<T>`** | Provides a `BlocSignal` or `CubitSignal` instance down the Jaspr component tree via `InheritedComponent`. Supports `lazy:` creation and `.value` injection. |
| **`MultiBlocSignalProvider`** | Combines multiple `BlocSignalProvider` instances into a single linear component hierarchy. |
| **`BlocSignalBuilder<T, S>`** | Rebuilds Jaspr components dynamically whenever container state updates with optional `buildWhen` filtering and automatic subscription teardown. |
| **`BlocSignalListener<T, S>`** | Fires side-effect callbacks (such as notifications or JS interop calls) on state updates with optional `listenWhen` predicate filtering and automatic provider swap rebinding. |
| **`BlocSignalConsumer<T, S>`** | Combines `BlocSignalBuilder` and `BlocSignalListener`, supporting both `buildWhen` and `listenWhen`. |
| **`BlocSignalSelector<T, S, V>`** | Subscribes to fine-grained computed state slices and rebuilds only when selection changes. |
| **`MultiBlocSignalListener`** | Combines multiple `BlocSignalListener` instances cleanly with dynamic list literals. |

---

## 💡 BuildContext Extensions

- **`context.read<T>()`**: Reads container instance without registering a component rebuild dependency.
- **`context.watch<T>()`**: Listens to provider updates and rebuilds component on container reference swap.
- **`context.select<T, R>(selector)`**: Subscribes to a computed state derivation and marks component dirty only when selection changes. Registers an inherited dependency (`listen: true`) so provider container swaps automatically rebind the subscription even above `const` component subtrees.
- **`context.value<T, S>()`**: Watches state emissions on `T` and returns current value `S`, registering an element rebuild dependency for component `build()` methods.
- **`context.state<T, S>()`**: Looks up container `T` and returns underlying `ReadonlySignal<S>` without registering an element rebuild dependency, ideal for `computed()` or `effect()` signal graphs.

---

## 🛡️ Best Practices & Anti-Patterns

### 1. Prefer Declarative Builders Over Raw `.subscribe()` in `StatefulComponent`
* **Anti-Pattern (Double `setState` & Unhandled Subscriptions)**:
  ```dart
  // ❌ AVOID: Double-triggering setState and unhandled subscription closures
  @override
  void initState() {
    super.initState();
    _bloc.state.subscribe((val) {
      if (mounted) setState(() {}); // Fires redundant setState alongside onClick
    });
  }
  ```
  Calling `_bloc.state.subscribe(...)` manually inside `initState` causes:
  1. **Double Re-renders**: UI handlers (like `onClick`) calling `setState()` alongside `_bloc.add()` trigger two back-to-back framework rebuild passes on every event.
  2. **Batch UI Thrashing**: High-frequency loops or benchmarks (for example 1,000 events) force 1,000 individual `setState()` calls during the loop.
  3. **Resource Retain**: The subscription handle returned by `.subscribe()` must be captured and cancelled in `dispose()`.

* **Idiomatic Approach**:
  Use `BlocSignalBuilder` or `BlocSignalBuilder.value` to let the framework manage subscription lifecycle and dirty flags automatically:
  ```dart
  // ✅ RECOMMENDED: Declarative binding with automatic lifecycle teardown
  @override
  Component build(BuildContext context) {
    return BlocSignalBuilder<CounterCubit, int>(
      builder: (context, count) => h1([Component.text('Count: $count')]),
    );
  }
  ```

### 2. Fine-Grained Reactive Updates with `BlocSignalSelector`
Use `BlocSignalSelector` when child components only need to re-render when a specific slice of the container state changes:
```dart
// Rebuilds ONLY when the derived doubled count changes
BlocSignalSelector<CounterBloc, int, int>(
  selector: (state) => state * 2,
  builder: (context, doubled) => span([Component.text('Doubled: $doubled')]),
)
```

---

## Jaspr ownership and hydration

Place providers above the components that read them. A callback created with the outer
build context cannot read a provider that is only returned below that context; extract
the consuming controls into a descendant component or use the package's supported builder.
In static/server mode, keep the provider and consuming UI inside the appropriate `@client`
boundary. Create request-specific state per request, and serialize only public initial values.
Close owned containers and dispose effects using the installed binding's lifecycle contract.
