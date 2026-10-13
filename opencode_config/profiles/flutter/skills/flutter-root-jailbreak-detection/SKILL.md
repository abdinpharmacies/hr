---
name: flutter-root-jailbreak-detection
description: Design, implement, review, and test layered root/jailbreak and mobile-runtime resilience in Flutter apps using OWASP MASVS/MASTG/MASWE, Android Play Integrity and Keystore Key Attestation, Apple App Attest/DeviceCheck, native platform checks, anti-debugging, runtime-hooking/tool detection, runtime integrity, obfuscation, backend enforcement, and false-positive-aware response strategies. Use for security hardening, threat modeling, architecture, implementation, code review, and authorized security testing of Flutter Android/iOS applications.
compatibility: Requires a Flutter Android/iOS application when implementation is requested. Prefer official platform security APIs and current vendor documentation; verify package/API availability and versions before adding dependencies.
metadata:
  domain: mobile-security
  framework: flutter
  standards: OWASP-MASVS-MASTG-MASWE
  platforms: android-ios
---

# Flutter Root / Jailbreak Detection & Mobile Resilience

## Mission

Act as a mobile application security engineer focused on **root/jailbreak detection and layered runtime resilience for Flutter Android/iOS apps**.

Do not treat this topic as a single boolean `isRooted` / `isJailbroken` feature. Design a defense-in-depth system that combines:

1. Local environment signals.
2. Anti-debugging signals.
3. Runtime-hooking / instrumentation signals.
4. Runtime code/memory integrity checks where justified.
5. App integrity and device attestation.
6. Server-side verification and enforcement for sensitive actions.
7. Obfuscation and separation of security-critical logic.
8. Proportional responses and false-positive handling.
9. Repeatable static and dynamic security testing.

The goal is to **raise attacker cost and protect high-value operations**, not to promise unbypassable client-side detection.

OWASP explicitly treats root/jailbreak detection as a bypassable resilience control and recommends layered checks, distribution near sensitive operations, multiple signal types, backend validation, proportional responses, and ongoing testing. See MASVS-RESILIENCE, MASWE-0051, MASTG-KNOW-0027, MASTG-KNOW-0084, and MASTG-BEST-0030.

## Core security principles

### 1. Never claim certainty from one signal

A local check is a **risk signal**, not cryptographic proof.

Avoid architectures such as:

```text
startup -> isRooted() -> if true exit app
```

Prefer:

```text
                 ┌─ local environment signals
                 ├─ anti-debugging
Request/action ──┼─ runtime/hooking signals
                 ├─ app/device attestation
                 └─ server-side policy
                         ↓
                  risk / trust decision
                         ↓
          allow / step-up / restrict / deny
```

### 2. Assume the client can be modified

On a rooted/jailbroken device, an attacker may hook Dart/native code, modify return values, hide artifacts, instrument processes, patch memory, or bypass a centralized gate.

Therefore:

- Never make the server trust a client-reported `isRooted == false`.
- Never place the final authorization decision for a high-value server action only in Flutter/Dart.
- Never embed server secrets, attestation verification secrets, or trust decisions that must remain confidential in the client.
- Treat client detection as telemetry / a defense signal and use platform-backed attestation plus backend enforcement for high-value actions.

### 3. Match controls to the threat model

Before coding, determine:

- What asset is being protected?
- Is the threat theft of local data, fraud, automation, cheating, credential abuse, license bypass, or transaction tampering?
- Which actions are high value?
- Is the app distributed through Google Play, App Store, enterprise channels, sideloading, or multiple channels?
- Does the backend exist and can it enforce decisions?
- What user populations must continue to work: enterprise, custom ROM, beta, security research, unsupported devices, non-Google devices?
- What is the acceptable false-positive rate?
- What is the operational response when an attestation service is unavailable?

Do not add expensive RASP-style controls merely because they are available.

### 4. Prefer layered controls over signature lists

Known paths, package names, process names, ports, or strings are useful signals but fragile. Attackers can rename, hide, hook, or patch them.

Combine different classes of evidence and implement some checks in platform-native code rather than putting the entire security mechanism in Dart.

### 5. Protect sensitive operations, not only startup

A one-time startup check is easy to bypass after initialization.

Repeat or checkpoint relevant controls around sensitive actions such as:

- authentication/session establishment
- token issuance or refresh
- payment approval
- transfers or withdrawals
- premium-content authorization
- high-value game actions
- key use
- privileged API calls
- account recovery
- sensitive data export

Avoid tight continuous polling that burns battery. Prefer event-driven or checkpoint-based checks, with short periodic checks only during sensitive flows when justified.

---

# Decision tree

Use this decision tree before implementation.

```text
START
 |
 |-- What are you protecting?
 |      |-- Low-risk UX / warning only
 |      |       -> lightweight local signals may be enough
 |      |
 |      |-- Sensitive server action / fraud / valuable resource
 |              -> backend-enforced attestation required
 |
 |-- Platform?
 |      |-- Android
 |      |     |-- Google Play distribution + Play services available?
 |      |     |      -> Play Integrity (prefer Standard requests for on-demand checks)
 |      |     |      -> bind request with requestHash
 |      |     |
 |      |     |-- Need additional hardware-backed key proof?
 |      |     |      -> evaluate Android Keystore Key Attestation
 |      |     |
 |      |     `-- Non-Play / special distribution?
 |      |            -> do not pretend Play Integrity covers every distribution
 |      |            -> evaluate native attestation/Keystore capabilities and business constraints
 |      |
 |      `-- iOS
 |            |-- App Attest supported?
 |            |      -> use DCAppAttestService + server verification
 |            |      -> bind assertions to server challenges / request data
 |            |
 |            `-- App Attest unsupported/unavailable?
 |                   -> fallback gracefully; DeviceCheck can supplement fraud state
 |                   -> do not claim DeviceCheck proves a device is not jailbroken
 |
 |-- Is local compromise detection materially useful?
 |      |-- No -> rely mainly on attestation/backend controls
 |      `-- Yes
 |            -> add multiple platform-specific signals
 |            -> distribute checks around sensitive flows
 |
 |-- Threat includes instrumentation/debugging/hooking?
 |      |-- Yes -> anti-debugging + tool/instrumentation signals
 |      |         + runtime integrity where risk justifies complexity
 |      `-- No  -> keep scope smaller
 |
 |-- Need to raise reverse-engineering cost?
 |      -> release obfuscation + split-debug-info
 |      -> minimize recognizable security-critical names/structures
 |
 `-- What should happen when signals fail?
        |-- Low confidence / weak signal -> observe, challenge, or step-up
        |-- Medium/high risk -> restrict only sensitive action
        `-- Strong server-verified failure -> deny the protected action
```

Do not convert this tree into a universal global app lockout. The correct response depends on the protected asset and threat model.

---

# Recommended architecture

For a Flutter app using clean architecture or MVVM/Cubit, keep presentation independent from mobile-security implementation details.

```text
Flutter UI / Cubit / ViewModel
            |
            v
     SecurityUseCase
            |
            v
  SecurityAssessmentRepository
            |
     +------+-----------------------------+
     |                                    |
     v                                    v
LocalSecuritySignalSource            AttestationSource
     |                                    |
 +---+---+---+                       +----+------+
 |       |   |                       |           |
 v       v   v                       v           v
Root   Debug Hooking            Android       iOS
/JB    / R/E                    Play         App Attest
checks  checks                  Integrity    / DeviceCheck
 |
 v
Native Android / iOS
(Kotlin/Swift, optional C/C++ only when justified)
            |
            v
       Backend API
            |
            v
   Server-side verifier
            |
            v
    Policy / risk decision
```

### Suggested contracts

Keep the Dart layer generic:

```dart
sealed class SecuritySignal {
  const SecuritySignal();
}

final class SecurityAssessment {
  final bool localCompromiseSuspected;
  final Set<SecuritySignalCode> signals;
  final AttestationState attestation;
  final DateTime checkedAt;

  const SecurityAssessment({
    required this.localCompromiseSuspected,
    required this.signals,
    required this.attestation,
    required this.checkedAt,
  });
}

enum SecuritySignalCode {
  rooted,
  jailbroken,
  debuggerAttached,
  instrumentationDetected,
  suspiciousRuntime,
  runtimeIntegrityFailed,
  emulatorOrUntrustedEnvironment,
}

enum AttestationState {
  verified,
  failed,
  unsupported,
  unavailable,
  notChecked,
}

abstract interface class SecurityRepository {
  Future<SecurityAssessment> assess({required SecurityCheckPoint point});
}

enum SecurityCheckPoint {
  sessionStart,
  sensitiveAction,
  privilegedOperation,
  periodicSensitiveFlow,
}
```

Do not expose raw filesystem paths, package signatures, attestation certificates, or internal detection heuristics to widgets unless they are intentionally needed for diagnostics. Prefer stable domain-level results.

### Native boundary

Use Flutter platform integration for security-sensitive native APIs:

- `MethodChannel` is acceptable for small integrations.
- Prefer generated/type-safe Pigeon interfaces for larger cross-platform contracts.
- Keep Android and iOS implementations separate.
- Never make the Dart result itself the trust anchor.

Flutter officially supports platform-specific code using platform channels and Pigeon; Android uses Kotlin/Java and iOS uses Swift/Objective-C.

---

# Android implementation strategy

## Layer A — local root/environment signals

Implement multiple classes of checks. Select only signals relevant to the threat model and current Android versions.

Possible signal classes include:

### Filesystem/artifact checks

Look for indicators associated with elevated privilege or modified environments, such as:

- `su`-related artifacts in known executable locations
- root-management artifacts
- suspicious writable system locations
- known framework/configuration artifacts
- unexpected binaries or files associated with hooking/instrumentation

Do not depend on one fixed path list. Treat path lists as rotating/maintainable indicators.

### System/property/build checks

Inspect platform-exposed information that can indicate:

- unlocked/modified boot state where the relevant API/property is trustworthy enough for the threat model
- test/custom build characteristics
- suspicious build tags/configuration
- emulator indicators

Do not treat emulator detection as proof of compromise. Emulators can be legitimate in development, QA, accessibility, CI, and enterprise environments.

### Privilege/behavior probes

Where safe and justified, test behavior associated with elevated privileges rather than only checking filenames.

Examples of categories:

- whether privileged commands can actually execute
- whether protected areas that should be inaccessible appear writable
- unexpected ability to inspect privileged system state

Avoid destructive commands or irreversible device changes.

### Installed apps / package indicators

Look for known management/instrumentation packages only as supplemental signals.

Do not hard-code a single package list as the security boundary. Package names can change and package visibility is constrained by modern Android behavior.

### Process / socket / library indicators

When justified, inspect safe runtime indicators such as:

- suspicious processes/services
- loaded native libraries
- memory mappings
- Unix sockets / named pipes / ports associated with instrumentation
- thread names or other runtime artifacts

These are indicators, not proof. OWASP specifically documents reverse-engineering tool detection as artifact-based and recommends combining it with runtime integrity, app integrity, anti-debugging, and obfuscation.

## Layer B — anti-debugging

Use platform-native debugging indicators as additional signals.

Examples include:

- Java/Kotlin debugging APIs where appropriate
- native/debug state checks in JNI/native paths when required
- checkpoints during sensitive flows rather than startup-only logic

Anti-debugging must not be treated as a guarantee. Hooking and patching can bypass client checks.

## Layer C — runtime hooking / instrumentation detection

For higher-risk applications, detect evidence of dynamic instrumentation using multiple categories instead of one tool signature.

Possible categories:

- known instrumentation artifacts
- suspicious loaded libraries
- suspicious processes/services
- suspicious sockets/pipes
- memory-map anomalies
- unexpected code-page characteristics
- runtime integrity mismatches

Target behavior categories rather than a permanently fixed list of attacker names.

OWASP's guidance includes Frida, Xposed-like frameworks, and similar artifacts as examples, but the implementation must remain adaptive.

## Layer D — runtime code integrity

When the threat model justifies it, add runtime integrity checks that look for unauthorized modifications to executable code or critical runtime state.

Potential approaches include:

- validating expected code/data regions where feasible
- detecting unexpected loaded executable modules
- integrity checks around sensitive native functions
- detecting suspicious changes to function pointers or critical runtime structures
- comparing measurements against trusted release expectations

Be conservative. Runtime integrity is complex, architecture/ABI dependent, and inherently cat-and-mouse. Do not ship brittle checks without testing across all supported devices and release modes.

## Layer E — Play Integrity

For Google Play distributed apps, use Play Integrity as the backend-trust layer for valuable operations.

### Prefer Standard requests for on-demand sensitive operations

Flow:

```text
Flutter/native client
   |
   | 1. canonicalize protected request
   | 2. SHA-256 -> requestHash
   v
Play Integrity
   |
   | signed/encrypted token
   v
Flutter/native client
   |
   | token
   v
Backend
   |
   | send token to Google Play / decode & verify
   v
Verified verdict
   |
   v
Backend policy
```

Google's Standard request flow supports binding the integrity token to the request with `requestHash`. The backend must compute/verify the same digest, and Standard requests include replay protections handled by Google Play.

Never send sensitive plaintext inside `requestHash`; hash the relevant canonicalized request data.

### Verify the request before the verdict

The backend must first validate the request-binding data in the decoded verdict before trusting the integrity labels.

Conceptually:

```text
received request
        |
        +--> reconstruct canonical protected fields
        |
        +--> SHA-256
        |
        +--> compare with decoded requestHash
        |
        `--> only then evaluate app/device/account signals
```

### Use the relevant verdict dimensions

Do not reduce Play Integrity to a single `isRooted` approximation.

Relevant signals can include:

- `appIntegrity`
- `deviceIntegrity`
- account/license information
- optional threat/risk verdicts enabled for the application
- device attributes when relevant to your policy

Current Google documentation describes device integrity tiers including `MEETS_BASIC_INTEGRITY`, `MEETS_DEVICE_INTEGRITY`, and `MEETS_STRONG_INTEGRITY`, with materially different guarantees depending on Android version.

Do not hard-code the highest tier as a universal requirement. Google explicitly recommends tiered enforcement because stricter verdicts reduce reachable device coverage.

### Do not cache a sensitive verdict as a permanent pass

Bind the attestation to the protected action and make backend decisions close to the action. Avoid treating an old "good device" token as permanent proof.

### Classic requests

Use Classic requests only when there is a specific reason for their stronger/fresher assessment characteristics and follow Google's current nonce/replay guidance. Do not use Classic requests repeatedly in polling loops.

## Layer F — Android Keystore Key Attestation

Use Android Keystore Key Attestation when the threat model needs a cryptographically verifiable, hardware-backed key property in addition to or instead of other device signals.

Architecture:

```text
Android app
  -> generate hardware-backed key
  -> obtain X.509 attestation chain
  -> send chain to trusted backend
  -> backend validates chain/root/revocation/extensions
  -> backend binds key identity to account/device/session
```

Important rules:

- Verify attestation on a trusted server, not on the potentially compromised device.
- Verify the certificate chain and trust anchor.
- Check revocation status as required by the platform guidance.
- Verify the relevant attestation extension data and expected security properties.
- Do not assume that the leaf certificate is always the trusted source of attestation extension data; follow current Android validation guidance.
- Account for devices without equivalent hardware-backed attestation or with manufacturer-specific trust roots.

Key Attestation proves properties of an attested key and its security environment; it is not a magical universal jailbreak detector.

---

# iOS implementation strategy

## Layer A — local jailbreak signals

Use multiple classes of signals, carefully scoped to the supported iOS versions and distribution model.

Possible categories documented by OWASP include:

### File/directory indicators

Examples may include artifacts commonly associated with jailbreak tooling or package managers.

Important: never treat a single hard-coded path as proof of jailbreak.

### Sandbox boundary probes

Where technically appropriate, detect unexpected access outside the normal app sandbox or unexpected ability to perform operations that a stock app should not be able to perform.

These should be non-destructive and carefully tested for false positives.

### Scheme/application indicators

Where allowed by the platform and privacy rules, supplemental checks for known tooling/application indicators may be useful.

### Runtime behavior

Combine artifact checks with runtime signals instead of relying on static paths alone.

OWASP describes jailbreak detection as a resilience control and specifically warns that it is not effective by itself.

## Layer B — anti-debugging

Use iOS-appropriate native techniques when the threat model requires them.

Consider:

- debugger state
- process execution characteristics
- native security checks around sensitive operations
- runtime checkpoints instead of startup-only checks

Do not use unsupported/private APIs solely to create a stronger-looking detector.

## Layer C — hooking/instrumentation signals

Look for behavioral/runtime indicators of dynamic instrumentation, loaded injected modules, or altered runtime behavior where the current iOS environment exposes reliable evidence.

Do not rely on one list of tool names or library paths.

## Layer D — App Attest

For server-protected actions, App Attest should be a major trust layer where supported.

Official Apple flow:

```text
App
 |
 | generateKey
 v
Secure Enclave-backed key
 |
 | attestKey(clientDataHash)
 v
attestation object
 |
 v
Backend
 |
 | verify certificate/attestation data
 v
store verified public key + device association
 |
 | later
 v
App -> challenge + request data -> generateAssertion()
 |
 v
Backend verifies assertion + challenge + counter + app identity data
```

### Required server properties

The backend should:

1. Issue a fresh server challenge.
2. Bind the challenge to the intended operation/session.
3. Verify the attestation object according to Apple's current validation guide.
4. Verify the application identity information and environment.
5. Store the verified public key for the app/device association.
6. Reject suspicious key reuse/association patterns according to the application's model.
7. For subsequent assertions, verify the signature, request-bound challenge, application identity information, and monotonically increasing counter.
8. Store the latest verified counter and prevent replay.

Apple documents App Attest specifically as a way for the server to verify that connections come from legitimate instances of the app.

### App Attest limitation

Do **not** describe App Attest as a definitive jailbreak detector. Apple's own documentation states that App Attest cannot definitively pinpoint a device with a compromised operating system.

### DeviceCheck

Use DeviceCheck as a complementary per-device fraud/risk signal when appropriate.

DeviceCheck provides authenticated server-side access to two per-device binary bits and an authenticated device token. It is useful for persistent fraud-state signals but is not a substitute for App Attest or for local jailbreak detection.

### Availability and rollout

Check `isSupported` and handle service failures gracefully. Follow Apple's current recommendations for development, production onboarding, and service errors.

Do not make unsupported devices automatically equivalent to compromised devices.

---

# Cross-platform Flutter integration

## Dart contract

Expose one stable domain API such as:

```dart
abstract interface class MobileSecurityService {
  Future<LocalSecurityAssessment> inspectLocalEnvironment();
  Future<AttestationResult> attestForAction(ProtectedAction action);
}
```

Keep the platform-specific details behind the implementation:

```text
MobileSecurityService
  -> AndroidSecurityService
      -> Kotlin native checks
      -> Play Integrity bridge
      -> optional Keystore attestation

  -> IOSSecurityService
      -> Swift native checks
      -> App Attest bridge
      -> DeviceCheck bridge
```

Do not leak platform-specific enums into UI code unless the product genuinely needs them.

## Platform channel contract

Prefer a small, stable contract:

```text
checkLocalSignals()
prepareAttestation()
attestProtectedRequest(requestBinding)
getCapabilityStatus()
```

Return structured data rather than strings such as:

```json
{
  "compromised": true,
  "signals": ["debugger", "instrumentation"],
  "attestation": "failed",
  "platform": "android"
}
```

The backend must not trust this JSON as proof; it is only local telemetry / a client-side input to the broader flow.

## Isolate security work from presentation

A Cubit/ViewModel can consume `SecurityAssessment`, but should not know:

- root artifact paths
- Play Integrity token decoding
- App Attest CBOR structures
- Keystore X.509 parsing
- jailbreak implementation details

Security implementation belongs in data/platform infrastructure, not widgets.

---

# Backend enforcement architecture

For valuable actions, use the backend as the enforcement point.

```text
Client request
   |
   +-- user/session authentication
   +-- protected request payload
   +-- platform attestation evidence
   +-- request binding / nonce / challenge
   |
   v
Backend
   |
   +--> verify auth
   +--> verify request binding
   +--> verify attestation with Apple/Google/native trust service
   +--> evaluate local-signal telemetry if present
   +--> apply server policy
   |
   v
Action result
```

### Example policy model

Use policy states rather than a universal boolean:

```text
LOW_RISK
  -> allow

LOCAL_SUSPICION_ONLY
  -> allow low-risk features
  -> require step-up for sensitive actions

ATTESTATION_UNAVAILABLE
  -> product/threat-model dependent
  -> retry or restrict only protected actions

ATTESTATION_FAILED / REQUEST_BINDING_FAILED
  -> deny the protected action

MULTIPLE HIGH-CONFIDENCE SIGNALS
  -> restrict sensitive capabilities
  -> surface recovery/support flow
```

Do not create a permanent account ban from one local signal.

---

# False-positive handling

False positives are part of the threat model, not an afterthought.

Potential legitimate cases include:

- custom ROMs
- developer/test devices
- enterprise-managed or unusual device configurations
- emulators used by QA/CI
- unsupported App Attest environments
- Play Integrity verdicts that do not meet a strict tier but are not necessarily evidence of malicious activity
- temporary network/service errors
- outdated device security patches
- devices without equivalent hardware-backed capabilities

### Response rules

1. Distinguish `failed`, `unsupported`, and `unavailable`.
2. Do not map every failure to `compromised = true`.
3. Restrict the smallest sensitive capability needed.
4. Offer step-up authentication or recovery when feasible.
5. Log structured reason codes server-side.
6. Avoid logging raw secrets, full attestation tokens, or unnecessary device-identifying data.
7. Monitor false-positive rates after release.
8. Provide a controlled support/test override only for authorized internal environments; keep such overrides server-side and auditable.

---

# Checkpoint strategy

Avoid a giant `SecurityGate` that runs everything on every screen.

Instead, define checkpoints:

```text
App cold start
    -> lightweight capability discovery

Session establishment
    -> local risk signals + attestation bootstrap

Sensitive action
    -> fresh request-bound attestation
    -> selected local/runtime checks
    -> backend authorization

Long sensitive flow
    -> occasional checkpoint

Background / idle
    -> avoid aggressive polling unless threat model demands it
```

Security checks should be close to the operation they protect. OWASP specifically recommends distributing checks and using checkpoints around sensitive operations.

---

# Obfuscation and release hardening

Flutter's official release obfuscation supports `--obfuscate` and `--split-debug-info` for supported native release targets including Android and iOS.

Use it to raise reverse-engineering cost, not as a substitute for attestation or runtime controls.

Example:

```bash
flutter build appbundle \
  --release \
  --obfuscate \
  --split-debug-info=build/symbols/android
```

and for iOS, use the corresponding supported Flutter build target with the same obfuscation flags.

Operational rules:

- Keep symbol files securely backed up.
- Never ship symbol maps unnecessarily to end users.
- Do not rely on class/function names for security decisions in obfuscated builds.
- Verify security checks in actual release builds; debug/profile behavior can differ.

Flutter's obfuscation renames symbols; it does not make client code impossible to reverse engineer.

---

# Dependency and package selection

A third-party Flutter package may simplify platform integration, but it must not become the security model.

Before adopting a package:

1. Inspect pub.dev and the package repository/current source.
2. Confirm Android/iOS implementations and maintenance status.
3. Read the package's native code, not just the Dart API.
4. Compare its checks against current OWASP guidance.
5. Identify whether it only performs static artifact checks or also uses native/runtime signals.
6. Check release compatibility with the project's current Flutter/Dart/Android/iOS toolchains.
7. Avoid inventing dependency versions; verify the current version at implementation time.
8. Document what the package does **not** protect against.

A package that returns only `bool isJailbroken` should be considered a convenience signal, not a trust anchor.

---

# Testing strategy

Testing must cover clean, modified, unsupported, and adversarial environments.

## Static testing

Use release binaries and inspect for:

- expected security entry points
- native security implementation presence
- references to detection mechanisms
- whether security logic is accidentally excluded from release variants
- whether sensitive constants/secrets are embedded
- whether obfuscation is enabled as expected

Map static tests to relevant OWASP MASTG tests such as:

- MASTG-TEST-0324 — References to Root Detection Mechanisms
- MASTG-TEST-0240 — Jailbreak Detection in Code
- MASTG-TEST-0324/0325 — Android root detection references/runtime use
- relevant anti-debugging/reference tests

## Dynamic testing matrix

At minimum test:

| Environment | Expected purpose |
|---|---|
| Stock physical Android | baseline |
| Stock physical iOS | baseline |
| Emulator/simulator | compatibility + legitimate unsupported case |
| Rooted Android | root signals |
| Jailbroken iOS | jailbreak signals |
| Hidden-root Android | bypass-resistance |
| Instrumented process | hooking detection |
| Debugger attached | anti-debugging |
| Modified/re-signed Android app | app-integrity failure |
| Non-Play install where relevant | distribution policy behavior |
| App Attest unsupported/failing | graceful fallback |
| Play Integrity service/network failure | unavailable path |
| Offline / degraded network | retry/fail policy |
| Release-obfuscated binary | production behavior |

Use only devices, apps, accounts, and test environments you are authorized to analyze.

## Adversarial testing

Test whether an attacker can:

- hook a boolean return value
- bypass a single early-exit gate
- hide known artifacts
- rename a detected binary/tool
- disable one signal and continue
- replay an attestation response
- replay an older valid request
- alter the protected request after attestation
- bypass only the Flutter layer while leaving native checks untouched
- abuse a cached "good" verdict
- downgrade to a weaker environment

The expected result is not "impossible to bypass." The goal is to verify that no single bypass defeats the entire protection strategy and that the backend still protects valuable operations.

## Runtime testing

OWASP recommends combining static identification of security mechanisms with dynamic tests that confirm the mechanisms actually execute at runtime. Use:

- MASTG-TEST-0241 for runtime jailbreak-detection behavior
- MASTG-TEST-0325 for runtime root-detection behavior
- appropriate anti-debugging runtime tests

Do not rely exclusively on automated bypass scripts; OWASP notes that such tooling is not exhaustive.

---

# Security review checklist

Before declaring the implementation complete, verify:

### Architecture

- [ ] Local detection is modeled as signals, not absolute proof.
- [ ] Presentation does not contain platform security implementation details.
- [ ] Native implementations are separated from Flutter UI.
- [ ] Sensitive server actions are protected by backend policy.

### Android

- [ ] Multiple root/environment signals exist where justified.
- [ ] Detection is not dependent on one package/path/name.
- [ ] Anti-debugging is checkpointed near sensitive flows when justified.
- [ ] Runtime hooking/tool signals exist for higher-risk applications.
- [ ] Runtime integrity is used only when the threat model justifies it.
- [ ] Play Integrity is used for relevant Google Play-distributed sensitive actions.
- [ ] `requestHash` is bound to a canonical protected request.
- [ ] Backend verifies the decrypted Play Integrity verdict.
- [ ] Device/app/account verdicts are interpreted according to current Google documentation.
- [ ] Key Attestation is considered when hardware-backed key proof is required.
- [ ] Key Attestation validation happens on a trusted server.

### iOS

- [ ] Multiple jailbreak signals exist where justified.
- [ ] No single path/package check is the security boundary.
- [ ] App Attest is used for sensitive server interactions when supported.
- [ ] Server issues fresh challenges and verifies request binding.
- [ ] Attestation object is verified server-side according to Apple's guide.
- [ ] Assertion counters are tracked to prevent replay.
- [ ] App Attest `isSupported` and service failures are handled correctly.
- [ ] DeviceCheck is treated as complementary fraud state, not jailbreak proof.

### Release

- [ ] Release build is tested, not only debug/profile.
- [ ] Flutter obfuscation is enabled where appropriate.
- [ ] Symbol files are securely retained.
- [ ] Security checks do not rely on Dart names that will change under obfuscation.

### Operations

- [ ] `failed`, `unsupported`, and `unavailable` states are distinct.
- [ ] False positives have a defined recovery path.
- [ ] High-risk actions have explicit server policy.
- [ ] Security telemetry avoids unnecessary sensitive data.
- [ ] Detection indicators can evolve without a full app rewrite.
- [ ] Security tests run against representative supported OS/device versions.

---

# Anti-patterns to reject

Reject or redesign these implementations:

```dart
if (await isRooted()) {
  exit(0);
}
```

```dart
// Client decides whether a transfer is allowed.
if (!deviceSecurity.isCompromised) {
  api.transferMoney();
}
```

```text
One path exists -> Cydia found -> jailbroken = true
```

```text
One known package found -> rooted = true
```

```text
One startup check -> no more checks
```

```text
Play Integrity token fetched at login -> cached forever
```

```text
App Attest succeeds once -> trust all future requests forever
```

```text
Unsupported attestation -> automatically treat as malicious
```

```text
Obfuscation enabled -> security complete
```

---

# Implementation workflow for the agent

When asked to implement or review this capability, follow this order:

1. **Inspect the project first.** Identify Flutter version, Android/iOS deployment targets, build variants, architecture, backend, distribution channels, current security packages, and release configuration.
2. **Define the threat model.** Identify the protected assets and which operations truly require stronger controls.
3. **Choose the platform trust layer.** Android: Play Integrity and/or Key Attestation as appropriate. iOS: App Attest, with DeviceCheck as a complementary signal where useful.
4. **Design the signal model.** Select multiple local/root/jailbreak, anti-debugging, and instrumentation signals based on the threat model.
5. **Define the backend policy.** Specify exactly what is allowed, restricted, challenged, or denied for each attestation/signal state.
6. **Define the Flutter/native contract.** Keep platform details behind an abstraction and keep UI unaware of implementation details.
7. **Implement the smallest sufficient control set first.** Do not add brittle RASP complexity without a justified security requirement.
8. **Bind attestations to requests/actions.** Prevent replay and tampering using the current platform guidance.
9. **Add release hardening.** Obfuscate and verify release builds, keeping symbols secure.
10. **Test clean and adversarial environments.** Include false-positive and service-unavailable cases.
11. **Review bypass resistance.** Verify that disabling one signal does not defeat backend protection.
12. **Document assumptions and limitations.** State explicitly what the solution detects, what it does not detect, and where vendor capabilities differ.

When modifying existing security code, preserve the project's architecture and existing abstractions unless there is a clear security reason to change them.

---

# Source hierarchy

Prefer sources in this order when resolving security design questions:

1. **OWASP Mobile Application Security (MASVS / MASTG / MASWE)** for mobile-security principles, testing, resilience, root/jailbreak detection, anti-debugging, hooking, and runtime integrity.
2. **Google Android Developers / Play Integrity documentation** for Android platform attestation behavior, request binding, verdict semantics, errors, and current API requirements.
3. **Android Developers / AOSP security documentation** for Keystore and hardware-backed Key Attestation.
4. **Apple Developer Documentation** for App Attest and DeviceCheck behavior, attestation/assertion validation, counters, challenges, support, and fraud-risk workflows.
5. **Flutter official documentation** for platform channels, Pigeon, release builds, and obfuscation.
6. Current package source/repository and pub.dev metadata only for optional implementation convenience; package behavior must be verified against the primary platform/security sources.

Do not substitute a package README, blog post, Stack Overflow answer, or social-media post for the vendor/OWASP documentation when the two disagree.

---

# Primary references

- OWASP MASTG — Root Detection: https://mas.owasp.org/MASTG-KNOW-0027/
- OWASP MASTG — Jailbreak Detection: https://mas.owasp.org/MASTG/knowledge/ios/MASVS-RESILIENCE/MASTG-KNOW-0084/
- OWASP MASWE — Root/Jailbreak Detection Not Implemented: https://mas.owasp.org/MASWE/MASVS-RESILIENCE/MASWE-0051/
- OWASP MASWE — Device Attestation Not Implemented: https://mas.owasp.org/MASWE/MASVS-RESILIENCE/MASWE-0054/
- OWASP MASWE — Runtime Code Integrity Not Verified: https://mas.owasp.org/MASWE/MASVS-RESILIENCE/MASWE-0058/
- OWASP MASTG Best Practice — Implementing Root Detection: https://mas.owasp.org/MASTG/best-practices/MASTG-BEST-0030/
- OWASP MASTG Best Practice — Hardening Against Runtime Hooking: https://mas.owasp.org/MASTG/best-practices/MASTG-BEST-0041/
- OWASP MASTG Best Practice — Continuous Anti-Debugging Checks: https://mas.owasp.org/MASTG/best-practices/MASTG-BEST-0047/
- OWASP MASTG — Reverse Engineering Tool Detection (Android): https://mas.owasp.org/MASTG/knowledge/android/MASVS-RESILIENCE/MASTG-KNOW-0030/
- OWASP MASTG — Runtime Integrity Verification: https://mas.owasp.org/MASTG-KNOW-0032/
- OWASP MASTG — Android root detection static test: https://mas.owasp.org/MASTG/tests/android/MASVS-RESILIENCE/MASTG-TEST-0324/
- OWASP MASTG — Android root detection runtime test: https://mas.owasp.org/MASTG/tests/android/MASVS-RESILIENCE/MASTG-TEST-0325/
- OWASP MASTG — iOS jailbreak detection runtime test: https://mas.owasp.org/MASTG-TEST-0241/
- Google Android Developers — Play Integrity overview: https://developer.android.com/google/play/integrity
- Google Android Developers — Standard Play Integrity requests: https://developer.android.com/google/play/integrity/standard
- Google Android Developers — Play Integrity verdicts: https://developer.android.com/google/play/integrity/verdicts
- Google Android Developers — Classic Play Integrity requests: https://developer.android.com/google/play/integrity/classic
- Google Android Developers — Hardware-backed Key Attestation: https://developer.android.com/privacy-and-security/security-key-attestation
- Apple Developer — DeviceCheck: https://developer.apple.com/documentation/devicecheck
- Apple Developer — DCAppAttestService: https://developer.apple.com/documentation/devicecheck/dcappattestservice
- Apple Developer — Validating apps that connect to your server: https://developer.apple.com/documentation/devicecheck/validating-apps-that-connect-to-your-server
- Apple Developer — Attestation Object Validation Guide: https://developer.apple.com/documentation/devicecheck/attestation-object-validation-guide
- Apple Developer — Assessing fraud risk: https://developer.apple.com/documentation/devicecheck/assessing-fraud-risk
- Flutter — Platform channels / platform-specific code: https://docs.flutter.dev/platform-integration/platform-channels
- Flutter — Obfuscate Dart code: https://docs.flutter.dev/deployment/obfuscate
- OpenCode — Agent Skills: https://opencode.ai/docs/skills

---

# Final rule

**Root/jailbreak detection is a resilience signal, not a root of trust.** For security-critical actions, combine layered client signals with platform-backed attestation and backend enforcement. Design for bypass attempts, false positives, service failures, evolving attacker indicators, and real production compatibility.
