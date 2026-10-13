---
name: signals-hooks
description: Integrate signals_hooks with flutter_hooks in Flutter projects already using or explicitly adopting these packages.
---

## Project compatibility

Inspect the project SDK constraints, lockfile, imports, and installed package source first. These collected references describe upstream snapshots, not a required version or a migration request. Preserve the existing state-management and routing choices unless the task requests a change. Use only APIs supported by the installed packages; add dependencies with the project package manager instead of copying example version pins. Read only relevant references. In Jaspr, use Dart core or Jaspr bindings, never Flutter widgets, hooks, or routers. Use primary constructors only when the project SDK supports them.


# Reactive State Hooks (`signals_hooks`)

This skill covers orchestrating reactive state signals within `flutter_hooks` codebases utilizing the `signals_hooks` package.

---

## 🚀 Getting Started

```dart
import 'package:flutter/material.dart';
import 'package:flutter_hooks/flutter_hooks.dart';
import 'package:signals_hooks/signals_hooks.dart';

class ExampleWidget extends HookWidget {
  const ExampleWidget({super.key});

  @override
  Widget build(BuildContext context) {
    // 1. Create a reactive signal managed by the widget's hook lifecycle
    final count = useSignal(0);
    
    // 2. Derive a lazy, memoized computed value
    final doubleCount = useComputed(() => count.value * 2);
    
    // 3. Register reactive side effects automatically bound to layout phases
    useSignalEffect(() {
      debugPrint('count changed: $count, double: $doubleCount');
    });

    return Scaffold(
      body: Center(
        child: Text('Count: $count (Double: $doubleCount)'),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => count.value++,
        child: const Icon(Icons.add),
      ),
    );
  }
}
```

> [!TIP]
> All signals, derived computed states, and side effects created inside standard `HookWidget` elements using the `use...` methods automatically teardown and dispose when the widget unmounts. This completely eliminates memory leaks or manual resource disposal.

---

## 📊 Comprehensive Hooks Reference Directory

The following table summarizes all available reactive hooks in the `signals_hooks` package. Click on any hook's name to view its detailed documentation, signature, best practices, and code examples.

| Hook | Return Type | Description | Lifecycle / Teardown Behavior |
| :--- | :--- | :--- | :--- |
| [useSignal](hooks/useSignal.md) | `Signal<T>` | Creates a mutable reactive signal managed by the hook lifecycle. | Disposes the signal on widget unmount. |
| [useComputed](hooks/useComputed.md) | `Computed<T>` | Creates a derived, cached read-only computed signal. | Disposes the computed signal on widget unmount. |
| [useSignalEffect](hooks/useSignalEffect.md) | `void` | Registers a reactive side effect bound to the widget mount lifecycle. | Cancels the effect subscription on widget unmount. |
| [useExistingSignal](hooks/useExistingSignal.md) | `Signal<T>` | Binds an external signal to rebuild when it mutates. | Detaches subscription on unmount (does not dispose signal). |
| [useSignalValue](hooks/useSignalValue.md) | `T` | Directly reads and subscribes to the value of an external signal. | Detaches subscription on unmount (does not dispose signal). |
| [useLazySignal](hooks/useLazySignal.md) | `Signal<T>` | Creates a new lazy Signal initialized late, managed by hook state. | Disposes the lazy signal on widget unmount. |
| [useLinkedSignal](hooks/useLinkedSignal.md) | `LinkedSignal<T>` | Creates a new LinkedSignal that resets its value when its source changes. | Disposes the linked signal on widget unmount. |
| [useFutureSignal](hooks/useFutureSignal.md) | `FutureSignal<T>` | Creates a reactive future signal with auto-disposal and race protection. | Disposes the future signal on widget unmount. |
| [useStreamSignal](hooks/useStreamSignal.md) | `StreamSignal<T>` | Creates a reactive stream signal with key-based resubscription. | Cancels stream subscription and disposes signal on unmount. |
| [useAsyncSignal](hooks/useAsyncSignal.md) | `AsyncSignal<T>` | Wraps an asynchronous task state inside a manageable AsyncSignal. | Disposes the async signal on widget unmount. |
| [useAsyncComputed](hooks/useAsyncComputed.md) | `AsyncSignal<T>` | Creates an async computed signal re-evaluated on dependency change. | Disposes the async signal on widget unmount. |
| [useValueNotifierToSignal](hooks/useValueNotifierToSignal.md) | `Signal<T>` | Bridges a standard Flutter ValueNotifier to a mutable reactive Signal. | Detaches subscription on unmount (does not dispose). |
| [useValueListenableToSignal](hooks/useValueListenableToSignal.md) | `ReadonlySignal<T>` | Bridges a standard Flutter ValueListenable to a read-only Signal. | Detaches subscription on unmount (does not dispose). |
| [useListSignal](hooks/useListSignal.md) | `ListSignal<T>` | Creates a reactive list with deep item-level mutation tracking. | Disposes the list signal on widget unmount. |
| [useSetSignal](hooks/useSetSignal.md) | `SetSignal<T>` | Creates a reactive set with deep element-level mutation tracking. | Disposes the set signal on widget unmount. |
| [useMapSignal](hooks/useMapSignal.md) | `MapSignal<K, V>` | Creates a reactive map with deep key-value mutation tracking. | Disposes the map signal on widget unmount. |
| [useIterableSignal](hooks/useIterableSignal.md) | `IterableSignal<T>` | Creates a reactive iterable with element-level mutation tracking. | Disposes the iterable signal on widget unmount. |
| [useTrackedSignal](hooks/useTrackedSignal.md) | `TrackedSignal<T>` | Creates a tracked signal remembering its historical value state. | Disposes the tracked signal on widget unmount. |
| [useQueueSignal](hooks/useQueueSignal.md) | `QueueSignal<T>` | Creates a reactive queue for FIFO collection management. | Disposes the queue signal on widget unmount. |
| [useChangeStackSignal](hooks/useChangeStackSignal.md) | `ChangeStackSignal<T>` | Creates a change-stack signal for robust undo/redo history tracking. | Disposes the change-stack signal on widget unmount. |

---

## 🧪 Testing State Hooks

To verify hook state components, use `flutter_test` along with a `HookBuilder` to execute the hooks safely under test frameworks:

```dart
testWidgets('useSignal test', (tester) async {
  late Signal<int> state;
  await tester.pumpWidget(
    HookBuilder(builder: (context) {
      state = useSignal(42);
      return Text('$state', textDirection: TextDirection.ltr);
    }),
  );

  expect(state.value, 42);
  expect(find.text('42'), findsOneWidget);

  state.value = 43;
  await tester.pumpAndSettle();

  expect(find.text('43'), findsOneWidget);
});
```
