---
name: flutter-obfuscation
description: Manage Flutter release obfuscation, split debug information, symbol files,
  crash symbolization, and obfuscation maps. Use when preparing, validating, troubleshooting,
  or documenting an obfuscated Flutter release.
metadata:
  scope: flutter
  category: deployment
  workflow: release
  compatibility: Codex; required project SDKs and tools must be available.
---

# Flutter Obfuscation

Use this skill when working with Flutter release builds that need Dart code obfuscation, symbol preservation, crash symbolization, or obfuscation maps.

This skill covers the **deployment and operational workflow** for Flutter obfuscation.

Do not duplicate or redefine coding rules about runtime names, class names, function names, reflection, serialization identifiers, or other obfuscation-sensitive code patterns. Those concerns are handled by the project's `Obfuscation-Safe Code` rule.

## Core facts

* Flutter obfuscation is supported only for release builds.
* Obfuscation renames symbols in compiled Dart code to make reverse engineering harder.
* Obfuscation does not encrypt application resources.
* Obfuscation does not prevent reverse engineering.
* Obfuscation is not a secret-management mechanism.
* Never treat obfuscation as a replacement for keeping secrets out of the application.
* Flutter web does not support this obfuscation flow. Web release builds are minified instead.
* Supported targets for this obfuscation workflow include:

  * `aar`
  * `apk`
  * `appbundle`
  * `ios`
  * `ios-framework`
  * `ipa`
  * `linux`
  * `macos`
  * `macos-framework`
  * `windows`

Source of truth: Flutter's official obfuscation documentation.

## Before building

First determine the actual release target.

Examples:

```bash
flutter build apk -h
flutter build appbundle -h
flutter build ipa -h
```

Verify that the target exposes both:

```text
--obfuscate
--split-debug-info
```

If those options are unavailable for the target, do not invent an alternative command. Check the installed Flutter version and official Flutter documentation.

## Standard obfuscated release build

Use `--obfuscate` together with `--split-debug-info`.

Example:

```bash
flutter build apk \
  --release \
  --obfuscate \
  --split-debug-info=out/android
```

For an Android App Bundle:

```bash
flutter build appbundle \
  --release \
  --obfuscate \
  --split-debug-info=out/android
```

The exact target and output directory must match the project's release workflow.

Do not assume `apk` when the user is preparing a Play Store release. For Play Store distribution, Flutter documents App Bundle (`appbundle`) as the preferred release format.

## Symbol files are release artifacts

When obfuscation is enabled, Flutter generates symbol information in the directory supplied to `--split-debug-info`.

Treat the generated symbol files as sensitive release artifacts that must be retained for the corresponding release.

Never delete or overwrite the only copy of a release's symbols without ensuring a backup exists.

Recommended organization:

```text
out/
└── symbols/
    ├── 1.0.0/
    │   ├── android/
    │   └── ios/
    └── 1.1.0/
        ├── android/
        └── ios/
```

The exact directory layout may differ by project. The important requirement is that every distributed obfuscated binary remains associated with its matching symbol files.

Record enough release information to identify:

* App version
* Build number
* Target/platform
* Relevant architecture when applicable
* Build variant/flavor when applicable
* Exact symbol files generated for that release

## Symbol-file matching

Use the symbol file that matches the affected build.

For example, an Android arm64 crash requires the corresponding arm64 symbols, such as:

```text
app.android-arm64.symbols
```

Do not use symbols from another release, build variant, platform, or architecture.

If the symbols do not match the binary that produced the crash, do not claim that the resulting symbolized stack trace is reliable.

## Symbolizing an obfuscated stack trace

When given an obfuscated stack trace:

1. Identify the exact release/build that produced it.
2. Locate the matching symbol file.
3. Keep the original stack trace unchanged.
4. Run `flutter symbolize` with the stack trace and matching symbols.

Example:

```bash
flutter symbolize \
  -i <stack-trace-file> \
  -d <obfuscated-symbols-file>
```

Example:

```bash
flutter symbolize \
  -i crash.txt \
  -d out/android/app.android-arm64.symbols
```

If symbolization produces unexpected or unresolved output, verify the release, target, architecture, and symbol-file match before changing anything else.

## Windows x64

For Windows x64, `--split-debug-info` generates a PDB file rather than a Flutter SYMBOLS file.

Flutter's `flutter symbolize` command does not support PDB files.

For an obfuscated Windows x64 build:

* Preserve the generated PDB file.
* Match it to the exact release/build.
* Use an appropriate Windows debugger such as WinDbg to inspect the obfuscated crash information.

Do not attempt to force a Windows PDB through `flutter symbolize`.

## Artifact isolation

SYMBOLS files and obfuscation maps are build/debug artifacts, not application assets.

- Do not add SYMBOLS files to the Flutter application's `assets`.
- Do not add `map.json` to `pubspec.yaml`.
- Do not copy either artifact into the application's distributable APK, AAB, IPA, or other runtime resources.
- Store them in a separate release-artifact directory outside the application asset tree.
- Preserve them separately for crash investigation and symbol lookup.

## Optional obfuscation map

An obfuscation map can be generated when there is a specific need to inspect the relationship between original names and obfuscated names.

Use:

```bash
flutter build <build-target> \
  --release \
  --obfuscate \
  --split-debug-info=/<symbols-directory> \
  --extra-gen-snapshot-options=--save-obfuscation-map=/<obfuscation-map-file>
```

Example:

```bash
flutter build apk \
  --release \
  --obfuscate \
  --split-debug-info=out/android \
  --extra-gen-snapshot-options=--save-obfuscation-map=out/android/map.json
```

The generated JSON contains mappings between original names and obfuscated names.

Do not generate an obfuscation map by default unless the project or task benefits from having one. The normal release workflow primarily requires the matching symbol files for crash symbolization.

## Release checklist

Before shipping an obfuscated release, verify:

```text
[ ] The build is a release build.
[ ] The selected target supports --obfuscate.
[ ] --split-debug-info is configured.
[ ] The obfuscated binary was successfully generated.
[ ] All generated symbol files were identified.
[ ] Symbols are backed up outside the distributable binary.
[ ] Symbols are associated with the exact app version/build.
[ ] Platform/architecture/variant information is recorded when relevant.
[ ] The release artifact and symbol artifacts can be matched later.
```

## Crash-investigation checklist

When investigating a crash from an obfuscated production build:

```text
[ ] Identify app version.
[ ] Identify build number.
[ ] Identify platform.
[ ] Identify architecture when applicable.
[ ] Identify build variant/flavor when applicable.
[ ] Locate the exact matching symbols.
[ ] Verify the symbols belong to the same binary.
[ ] Run flutter symbolize when the target supports it.
[ ] For Windows x64, use the matching PDB with a Windows debugger.
```

## Project changes

When asked to add obfuscation to an existing project:

1. Inspect the existing release/build configuration before changing it.
2. Prefer the project's established output and release-artifact conventions.
3. Do not hard-code paths that conflict with the existing project structure.
4. Do not modify signing, flavors, CI/CD, or platform configuration unless the task requires it.
5. Do not add unnecessary dependencies for Flutter obfuscation.
6. Do not claim a release is safely reproducible unless the relevant configuration and artifacts have actually been verified.

When CI/CD is involved, ensure the symbol artifacts are preserved as release artifacts and are not lost when the CI job ends.

## What this skill does not cover

This skill does not define:

* How to write obfuscation-safe Dart code.
* How to protect API keys or secrets in application code.
* General application security review.
* General Android signing configuration.
* General iOS signing configuration.
* General Flutter release engineering outside the obfuscation workflow.

Use the dedicated rule or skill for those concerns.

## Official references

Primary Flutter documentation:

* Deployment:
  https://docs.flutter.dev/deployment
* Obfuscate Dart code:
  https://docs.flutter.dev/deployment/obfuscate
* Build and release an Android app:
  https://docs.flutter.dev/deployment/android
* Build modes:
  https://docs.flutter.dev/testing/build-modes

When behavior differs from memory or from this skill, verify against the current official Flutter documentation.

