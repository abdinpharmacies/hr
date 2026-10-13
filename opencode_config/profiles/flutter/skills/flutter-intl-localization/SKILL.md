name: flutter-intl-localization
description: Sets up Flutter Intl localization with ARB files, generated S class, and a LocaleCubit that rebuilds MaterialApp on language change. Use when localizing the app, adding locales, extracting strings to ARB, wiring language switchers, or when the user mentions Flutter Intl, intl_utils, l10n, or change language.

# Flutter Intl Localization

## Before You Start (Required)

**Do not initialize localization or write code until the user confirms the default language.**

Use AskQuestion (or ask conversationally) with options derived from planned locales. For this project, typical choices are `en` (English) and `ar` (Arabic).

Record the answer and use it for:

* `flutter_intl.main_locale` in `pubspec.yaml`
* Initial `LocaleCubit` state
* `intl_<locale>.arb` main file name (e.g. `intl_en.arb`)

Also confirm which additional locales to add (e.g. `ar`).

## Setup Checklist
```
* [ ] Default language confirmed with user
* [ ] flutter_intl enabled in pubspec.yaml
* [ ] flutter_localizations added
* [ ] lib/l10n/intl_<main>.arb created (+ other locale ARBs)
* [ ] lib/generated/ committed (do not edit manually)
* [ ] LocaleCubit created
* [ ] BuildContext localization extension created
* [ ] BlocProvider + BlocBuilder in main.dart
* [ ] iOS CFBundleLocalizations updated
* [ ] Hardcoded strings migrated to ARB keys
* [ ] Language switcher wired to LocaleCubit
```

---


## 1. pubspec.yaml
Add dependencies:
yaml dependencies:
flutter_localizations:
sdk: flutter
Add Flutter Intl config (use confirmed default as `main_locale`):
```yaml
flutter_intl:
enabled: true
class_name: S
I
main_locale: en # replace with user-confirmed default arb_dir: lib/l10n
output_dir: lib/generated
Run 'flutter pub get`. If generated files are missing, run `dart run intl_utils:generate` or use VS Code command **Flutter Intl: Initialize**.

## 2. ARB Files
- Main file: `lib/l10n/intl_<main_locale>.arb`
- Additional locales: `lib/l10n/intl_<locale>.arb` (e.g. `intl_ar.arb`) - Never edit `lib/generated/` manually - keep generated files in version control
Key naming: `featureScreenElement (e.g. `onboardingContinue`, `splashTagline`).
ICU placeholders, plurals, selects, and formatted values follow Flutter Intl ARB conventions. See [reference.md] (reference.md).


## 3. LocaleCubit
Place under `lib/core/locale/`:
| File | Purpose |
locale_state.dart` | Holds 'Locale' |
|`locale_cubit.dart` | `changeLocale (Locale)` `S.load(locale)` → emit
I
Pattern:
dart
class LocaleState {
const LocaleState({required this.locale}); final Locale locale;
→
}
I
class LocaleCubit extends Cubit<LocaleState> { LocaleCubit({required Locale initialLocale})
: super(LocaleState(locale: initialLocale));
Future<void> changeLocale (Locale locale) async { await S.load(locale);
emit (LocaleState(locale: locale));
}
}
Map UI labels to `Locale` objects (e.g. `'English'` `'Arabic'` → `Locale('ar')`).
+
`Locale('en')`,


## 4. Wire MaterialApp
In `main.dart`:
1. `BlocProvider` at root with `LocaleCubit (initialLocale: Locale('<default>'))`
2. `BlocBuilder<LocaleCubit, LocaleState>` wrapping `MaterialApp` /
`MaterialApp.router`
3. Pass `locale: state. locale to MaterialApp
4. Add delegates and supported locales:
`dart
localizationsDelegates: const [
],
S.delegate,
GlobalMaterialLocalizations.delegate,
GlobalWidgets Localizations.delegate,
GlobalCupertinoLocalizations.delegate,
supportedLocales: S.delegate.supportedLocales,
Rebuild happens automatically when `LocaleCubit' emits a new state.
## 5. iOS
## 5. Wire MaterialApp

In `main.dart`:

1. `BlocProvider` at root with `LocaleCubit(initialLocale: Locale('<default>'))`
2. `BlocBuilder<LocaleCubit, LocaleState>` wrapping `MaterialApp` / `MaterialApp.router`
3. Pass `locale: state.locale` to MaterialApp
4. Add delegates and supported locales:

```dart
localizationsDelegates: const [
  S.delegate,
  GlobalMaterialLocalizations.delegate,
  GlobalWidgetsLocalizations.delegate,
  GlobalCupertinoLocalizations.delegate,
],
supportedLocales: S.delegate.supportedLocales,
```

Rebuild happens automatically when `LocaleCubit` emits a new state.

## 6. iOS

Add to `ios/Runner/Info.plist` — list must match `lib/l10n` locales:

```xml
<key>CFBundleLocalizations</key>
<array>
  <string>en</string>
  <string>ar</string>
</array>
```

## 7. Use Strings in Widgets

```dart
import 'package:cursor_course/core/locale/localization_extension.dart';

Text(context.localize.onboardingContinue)
Text(context.localize.pageHomeWelcome('John'))
```

With context unavailable: `S.current.onboardingContinue` (after `S.load`).

Replace hardcoded strings feature-by-feature. Prefer extracting all user-visible copy from the touched screen.

## 8. Language Switcher

Dropdown (or any switcher) to `LocaleCubit`:

```dart
context.read<LocaleCubit>().changeLocale(const Locale('ar'));
```

Do not keep local `_selectedLanguage` state for locale — read from `context.watch<LocaleCubit>().state.locale` or map cubit locale back to display label.

## Project Conventions

* Cubits live in `lib/core/<feature>/`
* Views stay thin; pass models, not destructured primitives
* Use `const` constructors where possible
* No `TextEditingController` unless programmatic text control is required
* Use generated asset classes, not raw asset paths

## Additional Resources

ARB ICU examples and placeholder meta: [reference.md](reference.md)

