# Custom Widgets Over Builder Functions

Never create private methods or functions that return `Widget`.

Instead, extract the UI into a named custom widget in its own file.

## Widget Extraction

When a UI section would normally be extracted into a helper function returning `Widget`:

* Create a dedicated custom widget.
* Place the widget in the feature's `widgets/` folder.
* Pass required data and callbacks through constructor parameters.
* Keep parent widgets thin by composing imported widgets.

Example feature structure:

```text
lib/
└── features/
    └── onboarding/
        └── widgets/
            └── onboarding_goal_list.dart
```

---

## Avoid Builder Functions

### Bad

Do not create helper functions that return widgets:

```dart
Widget buildGoalList(
  List<WorkoutGoalModel> goals,
  String languageCode,
) {
  return Column(
    children: [
      for (var i = 0; i < goals.length; i++) ...[
        OnboardingGoalCard(
          goal: goals[i],
          languageCode: languageCode,
          isSelected: i == _selectedGoalIndex,
          onTap: () => setState(
            () => _selectedGoalIndex = i,
          ),
        ),
        const SizedBox(height: 12),
      ],
    ],
  );
}
```

---

## Good

Create a dedicated widget in its own file:

```dart
class OnboardingGoalList extends StatelessWidget {
  const OnboardingGoalList({
    super.key,
    required this.goals,
    required this.languageCode,
    required this.selectedGoalIndex,
    required this.onGoalSelected,
  });

  final List<WorkoutGoalModel> goals;
  final String languageCode;
  final int selectedGoalIndex;
  final ValueChanged<int> onGoalSelected;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (var i = 0; i < goals.length; i++) ...[
          OnboardingGoalCard(
            goal: goals[i],
            languageCode: languageCode,
            isSelected: i == selectedGoalIndex,
            onTap: () => onGoalSelected(i),
          ),
          const SizedBox(height: 12),
        ],
      ],
    );
  }
}
```

The parent widget should then compose the extracted widget:

```dart
OnboardingGoalList(
  goals: goals,
  languageCode: languageCode,
  selectedGoalIndex: _selectedGoalIndex,
  onGoalSelected: (index) {
    setState(() => _selectedGoalIndex = index);
  },
)
```

---

## Parent Widget Responsibility

Keep parent widgets thin.

Parent widgets should:

* Compose imported custom widgets.
* Own the state when appropriate.
* Pass data to child widgets.
* Pass callbacks to child widgets.

Extract reusable or meaningful UI sections into dedicated custom widgets instead of helper functions returning `Widget`.

---

## File Naming

Each custom widget must live in its own file.

Use `snake_case.dart` for the file name.

The file name should match the widget class name.

Example:

```text
onboarding_goal_list.dart
```

```dart
class OnboardingGoalList extends StatelessWidget {
  // ...
}
```

### Naming Rule

```text
Widget Class        → PascalCase
File Name           → snake_case
```

Example:

```text
OnboardingGoalList
        ↓
onboarding_goal_list.dart
```

---

## Summary

```text
Private Widget-returning Function
            ↓
          Avoid
            ↓
Dedicated Custom Widget
            ↓
Separate File
            ↓
Constructor Parameters
            ↓
Parent Composes Widget
```