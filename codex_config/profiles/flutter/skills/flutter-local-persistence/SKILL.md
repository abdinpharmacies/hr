---
name: flutter-local-persistence
description: 'Choose and architect local persistence for Flutter apps: decide whether
  persistence is needed, choose the right storage technology, separate secrets/preferences/files/cache/data,
  and design feature-oriented local data-source abstractions and DI boundaries.'
---

# Flutter Local Persistence

## Purpose

Use this skill when a Flutter task involves local persistence, offline data, caching, local databases, secrets, preferences, files, or choosing a local storage technology.

The goal is to choose the smallest suitable persistence solution for the actual requirements. Do not force one database on the whole application.

A single Flutter application may legitimately use multiple persistence mechanisms.

Example:

```text
flutter_secure_storage
        ↓
   tokens / secrets

shared_preferences
        ↓
   small settings

Drift
        ↓
   structured offline data

filesystem + path_provider
        ↓
   documents / media / generated files
```

---

# 1. Start with the data, not the database

Before choosing a technology, inspect:

- existing persistence code
- `pubspec.yaml`
- supported Flutter platforms
- data size and growth
- relationships between records
- query requirements
- transactions
- migrations/schema evolution
- reactive/watch requirements
- offline-first requirements
- cache vs source-of-truth behavior
- existing DI and repository patterns

Do not introduce a new storage package when the repository already has a suitable solution unless the requirement justifies it.

Do not invent package versions. Verify the package and compatible version before adding a dependency.

---

# 2. Decide whether a database is needed

Do not use a database automatically.

A simpler mechanism is usually enough when data is small and simple, with no meaningful relationships, complex queries, transactions, or schema evolution.

Use:

```text
simple setting/value
    → shared_preferences

small secret
    → flutter_secure_storage

file/blob
    → filesystem + path_provider

structured/queryable application data
    → local database
```

`shared_preferences` is intended for simple key-value persistence, not critical data or large relational datasets. For new code, its newer `SharedPreferencesAsync` or `SharedPreferencesWithCache` APIs should be considered instead of the legacy API.

`flutter_secure_storage` is specifically for sensitive key-value data using platform secure-storage mechanisms; do not use it as a general-purpose database.

`path_provider` provides platform-specific filesystem locations; it is a filesystem-path utility, not a database.

---

# 3. One project may use multiple persistence mechanisms

This is allowed and often appropriate.

Example:

```text
Auth secrets       → flutter_secure_storage
App preferences    → shared_preferences
Offline app data   → Drift
Downloaded files   → filesystem
```

Do not consolidate everything into one database merely to reduce the number of packages.

Do not add several databases without a clear responsibility for each one.

The correct design is the smallest set of mechanisms whose responsibilities are explicit.

---

# 4. Local database selection

## Relational / SQLite

### Drift

Use Drift when the feature needs structured relational persistence such as:

- multiple related tables
- joins
- filtering and ordering
- transactions
- schema migrations
- type-safe queries
- generated database code
- reactive query streams

Drift is a reactive SQLite-based persistence library and currently supports Android, iOS, Linux, macOS, Windows, and Web.

Practical fit:

```text
relational + query-heavy + durable local data
                    ↓
                  Drift
```

Do not use Drift only because it is popular. Verify that its relational/query capabilities are useful for the feature.

### sqflite

Use sqflite when the project explicitly wants direct SQLite access, raw SQL, or already has sqflite-based code.

It supports transactions, batches, query helpers, and database version management. Its main package targets Android, iOS, and macOS; additional desktop and experimental Web support use separate packages.

Do not replace Drift with sqflite without a concrete requirement.

### sqlite3

Use when low-level SQLite/FFI control is explicitly required.

This is a lower-level choice; do not select it as the default application abstraction without a reason.

### Floor

Use when the project already uses Floor or specifically needs its Room-like, SQL-centric SQLite abstraction.

Verify its current maintenance and platform support before introducing it.

---

## NoSQL / key-value / document

### Hive CE

For new projects, evaluate `hive_ce` rather than assuming the original `hive` package.

Use it when data is naturally key-value/object-oriented and the feature benefits from a simple persistence API.

Current Hive CE documentation describes a pure-Dart key-value database with mobile, desktop, browser, and WASM support, plus generated adapters and isolate support.

Good fit:

```text
simple local objects / key-value persistence
                    ↓
                 hive_ce
```

Do not use it as a substitute for relational queries when relationships, joins, or complex SQL-style operations are central to the feature.

### Isar-family options

Isar-style databases can fit async NoSQL workloads that need collections, indexes, queries, transactions, or watchers.

Verify the exact maintained package before use. Current ecosystem options include `isar_community`; its documented capabilities include indexes, queries, ACID semantics, multi-isolate support, and watchers.

Do not assume the original `isar` package and current community forks have identical maintenance or platform characteristics.

### Sembast

Use when a document-oriented / key-value embedded store fits the data and a simple Dart-centric design is preferred.

Current Sembast supports Flutter/Dart VM and Web through `sembast_web`.

---

# 5. Specialized databases

Use specialized databases only when a concrete requirement benefits from them.

### ObjectBox

Consider for high-performance object persistence and specialized offline-first requirements.

Current Flutter package support includes Android, iOS, Linux, macOS, and Windows. Verify product, licensing, and sync requirements before adopting it.

### Realm

Realm can still be used as a local database, but do not design around Atlas Device Sync. MongoDB/Realm announced deprecation of Atlas Device Sync and the related SDKs in September 2024; the current package documentation warns about this.

### Couchbase Lite

Consider for specialized embedded-document, peer-to-peer, sync, or vector-search requirements.

### Mimir

Treat as a specialized option for reactive NoSQL/full-text workloads. Verify maturity and current support before introducing it.

### flutter_local_db

Treat as a specialized option. Its current package uses Rust + LMDB via FFI and provides a simple key-value API; its documented limitations include no complex query/index system and no automatic migration system.

---

# 6. Decision matrix

Use this as a heuristic, not an automatic rule.

| Requirement | Typical fit |
|---|---|
| Secret / credential | `flutter_secure_storage` |
| Tiny primitive setting | `shared_preferences` |
| File / media / export | filesystem + `path_provider` |
| Simple key-value/object persistence | `hive_ce` |
| Document-oriented local persistence | Sembast or another suitable document store |
| Relational data, joins, filtering, transactions | Drift |
| Direct raw SQLite control | sqflite / sqlite3 |
| Specialized high-performance object persistence | ObjectBox / maintained Isar-family option |
| Specialized embedded sync/document workload | Couchbase Lite or another suitable product |
| Specialized full-text/reactive workload | Mimir, after current verification |

---

# 7. Abstraction strategy

## Generic database abstraction: optional, not default

The following pattern can be used when a project explicitly benefits from a technology-independent database boundary:

```dart
abstract interface class LocalDatabase {
  Future<void> save<T>(T data);

  Future<T?> get<T>(String id);

  Future<void> delete<T>(String id);

  Future<List<T>> getAll<T>();
}
```

A concrete implementation could be:

```dart
class DriftLocalDatabase implements LocalDatabase {
  // Drift implementation
}
```

or:

```dart
class HiveLocalDatabase implements LocalDatabase {
  // Hive CE implementation
}
```

Dependency injection can choose the implementation:

```dart
final LocalDatabase localDatabase =
    DriftLocalDatabase(...);
```

This can allow the implementation technology to change without exposing it to the rest of the application.

### Important limitation

Do not create this abstraction automatically.

A generic interface such as:

```text
save<T>()
get<T>()
delete<T>()
getAll<T>()
```

can be too weak to represent the capabilities that make a technology appropriate. For example, Drift is relational and query-oriented, while Hive CE is key-value/object-oriented.

If the generic interface forces the application to throw away joins, filtering, transactions, reactive queries, indexing, or other real feature requirements, do not use that abstraction.

---

# 8. Preferred abstraction: feature-oriented local data source

Prefer an abstraction based on what the feature needs.

Example:

```dart
abstract interface class UserLocalDataSource {
  Future<UserModel?> getUser();
  Future<void> saveUser(UserModel user);
  Future<void> clearUser();
}
```

Implementations can vary:

```text
UserLocalDataSource
       │
       ├── HiveUserLocalDataSource
       │
       └── DriftUserLocalDataSource
```

Another example:

```dart
abstract interface class NotesLocalDataSource {
  Future<List<NoteModel>> getNotes();
  Future<NoteModel?> getNote(String id);
  Future<void> saveNotes(List<NoteModel> notes);
  Future<void> deleteNote(String id);
}
```

Then:

```dart
class DriftNotesLocalDataSource
    implements NotesLocalDataSource {
}
```

or:

```dart
class HiveNotesLocalDataSource
    implements NotesLocalDataSource {
}
```

The repository depends on the feature abstraction:

```text
Repository
    ↓
NotesLocalDataSource
    ↓
DriftNotesLocalDataSource / HiveNotesLocalDataSource
    ↓
chosen storage technology
```

The repository should not care whether the implementation is Drift, Hive CE, Sembast, or another local store unless that technology is intentionally part of the contract.

---

# 9. Do not create a "God abstraction"

Do not build one giant interface merely to make unrelated database technologies look identical.

Avoid a universal interface containing every possible operation:

```text
save
get
query
watch
join
transaction
batch
paginate
index
sync
...
```

Instead:

- expose only operations the feature needs
- keep implementation-specific behavior inside the local data source
- expose a capability only when the feature actually depends on it

For example, if the feature needs reactive local search, the abstraction may legitimately be:

```dart
abstract interface class NotesLocalDataSource {
  Stream<List<NoteModel>> watchNotes();
  Future<List<NoteModel>> searchNotes(String query);
}
```

Do not degrade a real requirement to `getAll()` just to keep an abstraction generic.

---

# 10. Repository and data-layer boundary

Keep database implementation details in the data layer according to the project's existing architecture.

Typical flow:

```text
Presentation
     ↓
Use case / Repository
     ↓
Feature local data source
     ↓
Database implementation
```

Do not import Drift tables, Hive boxes, SQLite queries, or database-specific types into presentation code merely for convenience.

Do not add extra interfaces solely for theoretical Clean Architecture purity when the repository pattern does not need them.

---

# 11. Dependency injection

Choose the concrete implementation at the composition root / dependency-injection layer.

Conceptually:

```dart
final NotesLocalDataSource notesLocalDataSource =
    DriftNotesLocalDataSource(...);
```

Follow the project's existing DI mechanism.

Do not scatter technology-selection conditionals throughout feature code.

The storage implementation should be selected once and injected downward.

---

# 12. Offline-first and remote backends

Offline-first does not automatically determine the local database.

First identify:

- local source of truth
- cache behavior
- sync direction
- conflict handling
- retries
- connectivity transitions
- IDs / versions / timestamps
- deletion semantics
- partial synchronization
- query requirements

Then select the local database.

The backend technology and local database do not need to match.

Example:

```text
Local  → Drift
Remote → Supabase PostgreSQL
```

The local store and remote backend remain separate architectural concerns.

Do not choose a local database only because the backend uses the same database family.

---

# 13. Cache vs source of truth

Explicitly classify local data as one of these:

### Cache

The local copy can be discarded and recreated from the remote source.

### Source of truth

The application must be able to rely on the local copy as durable application state.

This distinction affects synchronization, deletion, migrations, fallback behavior, and error handling.

Do not call durable application state a "cache" when the app cannot safely reconstruct it from the server.

---

# 14. Platform/Web compatibility

Platform support is part of the database decision.

Before adding a persistence package:

1. inspect the project's target platforms
2. verify current package support
3. verify Web support separately
4. check native/FFI requirements
5. check whether different platform implementations are required

Examples from current package documentation:

- Drift: Android, iOS, Linux, macOS, Windows, Web.
- Hive CE: mobile, desktop, browser, WASM.
- Sembast: Flutter/Dart VM, with Web through `sembast_web`.
- sqflite: Android, iOS, macOS; other targets need additional packages/support.
- ObjectBox: Android, iOS, Linux, macOS, Windows.
- Realm: Android, iOS, Windows, macOS, Linux.

Never assume Web support from the existence of a Dart package alone.

---

# 15. Migrations and generated code

When the chosen technology supports schema/adapters/generation:

- inspect the current package documentation
- follow the project's existing generation commands
- plan migrations before changing persisted structures
- do not invent generated filenames or commands

Consider:

- schema versions
- migrations
- indexes
- constraints
- transactions
- serialization/adapters
- generated code
- backup/upgrade behavior when relevant

Do not add migration machinery to data that is disposable cache unless the product requirements actually need it.

---

# 16. Testing

Test persistence behavior at the appropriate boundary.

### Local data-source tests

Cover meaningful behavior such as:

- save/read
- update
- delete
- queries
- transactions
- serialization/adapters
- migrations

### Repository tests

Cover:

- local/remote coordination
- cache/fallback behavior
- synchronization decisions

### Use-case tests

Test business orchestration, not database internals.

Do not add tests merely to increase file count.

---

# 17. Local-db-architect workflow

When the `local-db-architect` subagent handles a persistence decision, use this order:

```text
1. Inspect repository
       ↓
2. Inspect existing storage + DI
       ↓
3. Classify the data
       ↓
4. Decide whether a DB is actually needed
       ↓
5. Check platform requirements
       ↓
6. Check query / relation / transaction needs
       ↓
7. Check cache vs source-of-truth
       ↓
8. Select the smallest suitable technology
       ↓
9. Decide whether an abstraction is useful
       ↓
10. Define feature local-data-source responsibilities
       ↓
11. Define DI wiring
       ↓
12. Check migrations / testing / failure cases
       ↓
13. Present the architecture decision before implementation
```

If the user already selected the database, do not repeatedly ask for a database choice. Evaluate the choice against the requirements and proceed within the user's constraint unless a genuine architectural contradiction exists.

If the technology choice materially changes the architecture and the user has not chosen one, explain the tradeoff and proposed choice before implementation.

---

# 18. Technology-specific Skills

This Skill is the **selection and architecture layer**. It should not duplicate detailed package APIs.

Keep implementation knowledge in separate Skills:

```text
skills/
├── flutter-local-persistence/
│   └── SKILL.md
├── drift/
│   └── SKILL.md
├── hive-ce/
│   └── SKILL.md
├── isar/
│   └── SKILL.md
├── sembast/
│   └── SKILL.md
├── sqflite/
│   └── SKILL.md
├── objectbox/
│   └── SKILL.md
├── flutter-secure-storage/
│   └── SKILL.md
├── shared-preferences/
│   └── SKILL.md
└── path-provider/
    └── SKILL.md
```

Use this Skill to decide **what** should be used. Load the relevant technology-specific Skill to decide **how** to implement it.

For example:

```text
flutter-local-persistence
        ↓
Requirement analysis
        ↓
choose Drift
        ↓
load drift Skill
        ↓
implement with current Drift API
```

Codex loads skills on demand, and its documented format uses one `SKILL.md` per Skill directory. Keep this Skill focused so unrelated database implementation details are not loaded when they are unnecessary.

---

# References

Use current official/package documentation when implementation details are required:

- Codex skills: https://learn.chatgpt.com/docs/build-skills
- Flutter persistence cookbook: https://docs.flutter.dev/cookbook/persistence
- Drift: https://pub.dev/packages/drift
- sqflite: https://pub.dev/packages/sqflite
- Hive CE: https://pub.dev/packages/hive_ce
- shared_preferences: https://pub.dev/packages/shared_preferences
- flutter_secure_storage: https://pub.dev/packages/flutter_secure_storage
- path_provider: https://pub.dev/packages/path_provider
- Sembast: https://pub.dev/packages/sembast
- ObjectBox: https://pub.dev/packages/objectbox
- Realm: https://pub.dev/packages/realm
- Isar Community: https://pub.dev/packages/isar_community

When this Skill conflicts with current package documentation, prefer the current package documentation and verify the installed project's versions.

# Common mistakes

Avoid:

- using Secure Storage as a general database
- putting large relational data into Shared Preferences
- creating a database when files/preferences are enough
- forcing Drift and Hive into an identical generic CRUD API
- leaking database-specific types into presentation
- choosing by benchmark alone
- ignoring Web/platform support
- adding multiple databases without clear responsibilities
- introducing abstractions before understanding the feature
- changing an established persistence technology without a requirement

---

# Final self-check

Before finalizing a local persistence design:

- [ ] A database is actually needed.
- [ ] Secrets, preferences, files, caches, and application data are distinguished.
- [ ] Multiple mechanisms are used only when responsibilities are clear.
- [ ] The chosen database matches the data and query requirements.
- [ ] Platform/Web support is verified.
- [ ] Existing project patterns are respected.
- [ ] A feature-oriented abstraction is preferred where appropriate.
- [ ] No God abstraction has been introduced.
- [ ] Concrete implementations are wired through the existing DI pattern.
- [ ] Cache vs source-of-truth behavior is explicit.
- [ ] Migration and testing needs are considered.
- [ ] Technology-specific Skills are loaded only for the selected implementation.
