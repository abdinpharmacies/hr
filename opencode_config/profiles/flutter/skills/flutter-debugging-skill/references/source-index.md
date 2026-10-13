# Flutter Debugging Skill — Source Index

This skill was designed after reviewing the current OpenCode skill documentation plus Flutter/Dart debugging documentation and supplementary technical material.

## OpenCode

- Agent Skills: https://opencode.ai/docs/skills
- OpenCode v2 Skills: https://opencode.ai/v2/docs/skills

Key requirements used by this skill:
- A skill is a directory containing `SKILL.md`.
- `SKILL.md` starts with YAML frontmatter.
- `name` and `description` are required.
- The skill is loaded on demand by the native skill mechanism.
- Supporting files can live beside `SKILL.md` and are read when needed.

## Flutter official documentation

- Debug Flutter apps: https://docs.flutter.dev/testing/debugging
- Debug Flutter apps from code: https://docs.flutter.dev/testing/code-debugging
- Handling errors in Flutter: https://docs.flutter.dev/testing/errors
- Common Flutter errors: https://docs.flutter.dev/testing/common-errors
- Flutter's build modes: https://docs.flutter.dev/testing/build-modes
- Flutter and Dart DevTools: https://docs.flutter.dev/tools/devtools
- DevTools debugger: https://docs.flutter.dev/tools/devtools/debugger
- Flutter Inspector: https://docs.flutter.dev/tools/devtools/inspector
- Performance view: https://docs.flutter.dev/tools/devtools/performance
- CPU profiler: https://docs.flutter.dev/tools/devtools/cpu-profiler
- Memory view: https://docs.flutter.dev/tools/devtools/memory
- Network view: https://docs.flutter.dev/tools/devtools/network
- Logging view: https://docs.flutter.dev/tools/devtools/logging
- DevTools CLI: https://docs.flutter.dev/tools/devtools/cli
- Native debugging: https://docs.flutter.dev/testing/native-debugging
- Performance best practices: https://docs.flutter.dev/perf/best-practices
- Rendering performance: https://docs.flutter.dev/perf/rendering-performance
- App size: https://docs.flutter.dev/perf/app-size
- Create useful bug reports: https://docs.flutter.dev/resources/bug-reports
- Dart web debugging: https://dart.dev/web/debugging

## Dart official documentation

- Dart DevTools overview: https://dart.dev/tools/dart-devtools
- Dart tools: https://dart.dev/tools

## Supplementary technical material

- Flutter: Intro to Dart and Flutter DevTools (official Flutter video, Mar 25, 2026):
  https://www.youtube.com/watch?v=CIfLE0CShbg
- Flutter: Dive into DevTools (official Flutter video, Oct 2, 2023):
  https://www.youtube.com/watch?v=_EYk-E29edo
- Flutter blog: New tools for Flutter developers, built in Flutter:
  https://flutter.dev/blog/new-tools-for-flutter-developers-built-in-flutter
- Very Good Ventures: Debugging Flutter WebViews with Browser DevTools (May 13, 2026):
  https://verygood.ventures/blog/how-to-use-browser-dev-tools-with-flutter-webviews/
- Community DevTools guide (used only as supplementary context, not authority):
  https://medium.com/easy-flutter/debugging-with-flutter-devtools-a-comprehensive-guide-301f6da6b9d6

## Version note

The current Flutter documentation page for build modes reports that the documentation reflects Flutter 3.47.2 and was updated May 5, 2026. This skill therefore explicitly requires agents to inspect the repository's actual Flutter/Dart version before relying on version-sensitive behavior.
