# Screen Input Model

When a screen collects user input across multiple widgets, create a dedicated
input model and pass it down. Widgets update the model directly. Do not scatter
field state across the view.

## Structure

- File: `lib/features/{feature}/presentation/{feature}_input.dart`
- Class: `{Feature}Input` with mutable fields, sensible defaults, and named
  update methods.
- The view owns one instance; child widgets receive `input` as a constructor
  parameter.
- On submit, pass the whole input to the cubit or use case.

## Input Model

```dart
class OnboardingInput {
  OnboardingInput({
    this.selectedGoalId = 'general_fitness',
    this.availabilityDays = 3,
  });

  String selectedGoalId;
  int availabilityDays;

  void selectGoal(String goalId) => selectedGoalId = goalId;

  void selectAvailabilityDays(int days) => availabilityDays = days;

  String get planId => 'plan_${selectedGoalId}_${availabilityDays}d';
}
```

## View Owns The Model

```dart
class _OnboardingViewState extends State<OnboardingView> {
  final OnboardingInput _input = OnboardingInput();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        OnboardingGoalSection(input: _input),
        OnboardingAvailabilitySection(input: _input),
        OnboardingBottomBar(
          input: _input,
          onContinue: () => context.read<BuildWorkoutPlanCubit>().build(_input),
        ),
      ],
    );
  }
}
```

## Widget Updates The Model

```dart
onTap: () {
  widget.input.selectGoal(widget.goals[i].id);
  setState(() => _selectedGoalIndex = i);
},
```

## Avoid

Do not scatter field state across the view and rebuild it separately on submit:

```dart
String _selectedGoalId = 'general_fitness';
int _availabilityDays = 3;

selectedGoalId: _selectedGoalId,
onGoalSelected: (id) => setState(() => _selectedGoalId = id),
```

## Guidelines

- Use `setState` only for local UI state (e.g. the selection index used for
  rendering); the input model is the source of truth for submitted values.
- Add derived getters on the input model when multiple fields combine into one
  value.
- Keep update methods named after the user action (`selectGoal`,
  `selectAvailabilityDays`).
