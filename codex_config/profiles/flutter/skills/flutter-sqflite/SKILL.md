---
name: flutter-sqflite
description: Use sqflite for SQLite-based local persistence in Flutter. Covers setup,
  database lifecycle, schema design, CRUD, raw SQL, parameter binding, migrations,
  transactions, batches, relationships, indexes, mapping, platform compatibility,
  testing, and safe data-layer integration.
---

# Flutter sqflite Skill

Use this skill whenever a Flutter task explicitly chooses `sqflite`, asks for SQLite persistence through `sqflite`, or requires implementing/debugging an existing `sqflite` data layer.

This skill is **sqflite-specific**. Do not silently replace it with Drift, Isar, Hive, `sqlite3`, SharedPreferences, or Secure Storage. If the project is using another persistence technology, follow that technology's skill instead.

## Core principles

- Keep SQLite/sqflite implementation details in the **data/local/persistence layer**, not in widgets, views, or Cubit/BLoC.
- Prefer a database/repository abstraction at the boundary when the persistence implementation may change or when the project architecture already uses repositories.
- Keep SQL schema knowledge centralized. Do not scatter table/column names across presentation code.
- Treat schema migrations as application code. Never solve a schema change by deleting the user's database unless data loss is explicitly required and approved.
- Use parameter binding for **values**. Never build SQL values with string interpolation.
- Use constraints and indexes deliberately; do not add them blindly.
- Map database rows to typed Dart models at the data boundary.
- Do not put secrets into ordinary SQLite just because it is local persistence. Use the project's secure-storage/encryption strategy for sensitive secrets.

## 1. Verify the project before changing dependencies

Before adding or updating `sqflite`:

1. Inspect the existing `pubspec.yaml` and current persistence dependencies.
2. Check the project's Flutter/Dart SDK constraints.
3. Prefer:

```bash
flutter pub add sqflite path
```

4. Verify the resolved package version rather than inventing or blindly pinning a version.

Compatibility matters: the current latest `sqflite` release may require a newer Dart SDK than the project. For example, `sqflite 2.4.4` requires Dart 3.12, while older 2.4.x releases support older Dart versions. Resolve a compatible version from the project's SDK constraints.

For Android/iOS/macOS, use `sqflite` directly. For Windows/Linux/Dart VM, use the project's required FFI setup (`sqflite_common_ffi`) rather than assuming the regular mobile plugin supports those platforms. Web support is a separate/experimental path and must be verified before implementation.

## 2. Database location and lifecycle

Use `getDatabasesPath()` together with `path.join()` for the default database location:

```dart
final databasesPath = await getDatabasesPath();
final dbPath = join(databasesPath, 'app_database.db');
```

Open the database with `openDatabase()` and a schema `version`.

Typical structure:

```dart
Future<Database> openAppDatabase() async {
  final path = join(await getDatabasesPath(), 'app_database.db');

  return openDatabase(
    path,
    version: 1,
    onCreate: (db, version) async {
      await db.execute('''
        CREATE TABLE users (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          age INTEGER NOT NULL
        )
      ''');
    },
    onUpgrade: (db, oldVersion, newVersion) async {
      // Apply incremental migrations here.
    },
  );
}
```

When database initialization happens before `runApp`, use `WidgetsFlutterBinding.ensureInitialized()` before platform/database calls that need Flutter bindings. Do not add it everywhere without reason.

Prefer one long-lived database connection for the app. Avoid repeatedly opening the same file with independent connections. `sqflite` defaults `singleInstance` to `true` and its documentation recommends keeping a single database reference to reduce locking issues.

Usually there is no need to close the database during normal app lifetime. Close it when the owning lifecycle genuinely ends or when tests need deterministic cleanup.

Do not introduce multiple database instances just to "speed things up". `sqflite` documents synchronization/locking limitations around concurrent access.

## 3. Schema design

Design the relational schema before writing CRUD code.

Prefer:

- singular, stable column names
- `INTEGER PRIMARY KEY` for integer identifiers when appropriate
- `NOT NULL` where null is not semantically valid
- `UNIQUE` for true uniqueness constraints
- explicit foreign keys for relationships
- indexes for real query patterns
- normalized tables when repeated data would otherwise cause inconsistency

Example:

```sql
CREATE TABLE breeds (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE dogs (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  age INTEGER NOT NULL,
  breed_id INTEGER,
  FOREIGN KEY (breed_id) REFERENCES breeds(id)
);

CREATE INDEX idx_dogs_breed_id ON dogs(breed_id);
```

### Foreign keys

SQLite foreign-key enforcement is not something the agent should assume is enabled automatically. Enable it explicitly for the database connection when the schema relies on foreign-key enforcement:

```dart
onConfigure: (db) async {
  await db.execute('PRAGMA foreign_keys = ON');
},
```

Do this before schema/mutation logic that depends on enforcement.

For cascading behavior, express the intended behavior in the schema, for example `ON DELETE CASCADE`, rather than manually duplicating referential cleanup throughout repositories.

### Indexes

Add an index when it matches an actual query pattern, commonly:

- frequent equality/range filters in `WHERE`
- join keys / foreign-key lookup columns
- frequent `ORDER BY` patterns
- composite filters that benefit from a composite index

Do not index every column. Indexes consume storage and add write/update cost.

## 4. Supported value mapping

`sqflite`/SQLite persistence should use the supported SQLite storage types:

| Dart value | SQLite storage |
|---|---|
| `int` | `INTEGER` |
| `num` / `double` | `REAL` |
| `String` | `TEXT` |
| `Uint8List` | `BLOB` |
| nullable value | `NULL` when allowed |

SQLite has no dedicated boolean storage class. Store booleans consistently as `INTEGER` `0/1`.

SQLite has no dedicated `DateTime` storage class. Choose one project-wide representation, commonly:

- `INTEGER` Unix/millisecond timestamp, or
- `TEXT` ISO-8601 string.

Do not invent unsupported direct conversions such as inserting a Dart `DateTime` object directly.

Keep conversions at the data boundary:

```dart
class Dog {
  final int id;
  final String name;
  final int age;
  final bool vaccinated;

  const Dog({
    required this.id,
    required this.name,
    required this.age,
    required this.vaccinated,
  });

  Map<String, Object?> toMap() => {
        'id': id,
        'name': name,
        'age': age,
        'vaccinated': vaccinated ? 1 : 0,
      };

  factory Dog.fromMap(Map<String, Object?> map) {
    return Dog(
      id: map['id']! as int,
      name: map['name']! as String,
      age: map['age']! as int,
      vaccinated: (map['vaccinated']! as int) == 1,
    );
  }
}
```

Do not leak `Map<String, Object?>` deep into the presentation layer when the app architecture expects typed models.

sqflite query result maps are read-only. If code must mutate a returned map in memory, copy it first:

```dart
final copy = Map<String, Object?>.from(records.first);
```

## 5. CRUD: choose helpers first

Prefer `insert`, `query`, `update`, and `delete` for ordinary CRUD. They make the intent and argument binding explicit.

### Insert

```dart
final id = await db.insert(
  'dogs',
  dog.toMap(),
);
```

Use `ConflictAlgorithm` only when the conflict semantics are intentional, for example:

```dart
await db.insert(
  'dogs',
  dog.toMap(),
  conflictAlgorithm: ConflictAlgorithm.replace,
);
```

Do not use `replace` as a default "fix duplicate errors" mechanism. Decide whether the application means replace, ignore, abort, fail, or update.

### Query

```dart
final rows = await db.query(
  'dogs',
  columns: ['id', 'name', 'age'],
  where: 'age >= ? AND breed_id = ?',
  whereArgs: [18, breedId],
  orderBy: 'age DESC',
  limit: 50,
);
```

Avoid `SELECT *` in performance-sensitive or large-table queries when only a subset of columns is needed.

### Update

Always constrain updates to the intended rows:

```dart
final count = await db.update(
  'dogs',
  {'age': 42},
  where: 'id = ?',
  whereArgs: [dogId],
);
```

### Delete

Always use a deliberate `where` clause unless deleting all rows is explicitly the operation:

```dart
final count = await db.delete(
  'dogs',
  where: 'id = ?',
  whereArgs: [dogId],
);
```

Never write an accidental unrestricted `update()` or `delete()`.

## 6. Parameterized SQL is mandatory for values

For values, use `whereArgs` with helpers or positional arguments with raw SQL:

```dart
await db.query(
  'users',
  where: 'email = ?',
  whereArgs: [email],
);
```

```dart
await db.rawQuery(
  'SELECT * FROM users WHERE email = ?',
  [email],
);
```

Never do this:

```dart
// WRONG
await db.rawQuery("SELECT * FROM users WHERE email = '$email'");
```

Do not interpolate runtime values into SQL strings.

### Dynamic identifiers are different

SQL parameters are for values, not arbitrary table/column names. If the app needs a dynamic column/order choice, use an allowlist/enum-to-SQL mapping and only then compose the SQL identifier. Never accept arbitrary identifier text from untrusted input.

When a table/column name is a SQLite keyword, escape the identifier correctly. Prefer naming that avoids keywords in the first place.

## 7. Raw SQL: use it deliberately

Use helpers for simple CRUD. Use `rawQuery`, `rawInsert`, `rawUpdate`, `rawDelete`, or `execute` when you need SQL expressiveness that the helper API does not provide, such as:

- joins
- aggregates
- complex predicates
- subqueries
- schema DDL
- indexes
- PRAGMA statements

Example:

```dart
final rows = await db.rawQuery('''
  SELECT d.id, d.name, b.name AS breed_name
  FROM dogs d
  LEFT JOIN breeds b ON b.id = d.breed_id
  WHERE d.age >= ?
  ORDER BY d.name ASC
''', [minAge]);
```

Keep raw SQL centralized rather than scattering query strings through UI/Cubit code.

## 8. Migrations are incremental

Database `version` drives `onCreate`, `onUpgrade`, and `onDowngrade` callbacks.

`onCreate` is for a brand-new database. Existing installs are migrated through `onUpgrade`/`onDowngrade` as appropriate.

Write migrations incrementally:

```dart
return openDatabase(
  path,
  version: 3,
  onCreate: _createSchema,
  onUpgrade: (db, oldVersion, newVersion) async {
    if (oldVersion < 2) {
      await db.execute(
        'ALTER TABLE dogs ADD COLUMN vaccinated INTEGER NOT NULL DEFAULT 0',
      );
    }

    if (oldVersion < 3) {
      await db.execute(
        'CREATE INDEX idx_dogs_breed_id ON dogs(breed_id)',
      );
    }
  },
);
```

Rules:

- Never assume a user starts from the latest schema.
- Migrate from `oldVersion` toward `newVersion` in order.
- Keep old migrations valid unless the product explicitly performs a destructive reset.
- Put schema changes in migrations, not in random startup code.
- `onCreate` and `onUpgrade` callbacks are already transaction-wrapped by sqflite; do not add a nested transaction there.
- Test upgrades from every supported historical schema version that matters to the application.

For destructive migrations, explicitly preserve data when possible (copy/transform into a replacement table) instead of dropping user data casually.

## 9. Transactions: atomic multi-step changes

Use a transaction when several database operations must succeed or fail together.

```dart
await db.transaction((txn) async {
  final ownerId = await txn.insert('owners', owner.toMap());

  await txn.insert('dogs', {
    ...dog.toMap(),
    'owner_id': ownerId,
  });
});
```

Critical rule: **inside a transaction, use only the `Transaction` object (`txn`) for database operations. Do not call the outer `Database` object (`db`) from the transaction callback.** Doing so can deadlock.

If the transaction callback completes normally, sqflite commits it. If an error escapes the callback, sqflite rolls it back and rethrows the error.

Therefore:

```dart
try {
  await db.transaction((txn) async {
    await txn.update(...);
    await txn.insert(...);
  });
} catch (e) {
  // Transaction has been rolled back if the error escaped the callback.
  rethrow;
}
```

Do not catch and swallow a transaction error unless the intended semantics are to continue and commit the rest of the transaction.

## 10. Batch operations

Use a `Batch` when many independent operations should be sent efficiently together.

```dart
final batch = db.batch();

for (final dog in dogs) {
  batch.insert('dogs', dog.toMap());
}

await batch.commit();
```

If the operation is performance-sensitive and individual results are unnecessary:

```dart
await batch.commit(noResult: true);
```

By default, a batch stops when it encounters an error. `continueOnError: true` changes that behavior and should be used only when partial success is acceptable.

Inside a transaction, use `txn.batch()`. The batch's final durability/commit is tied to the surrounding transaction.

Do not use a batch merely because it is available; choose it for repeated operations or actual batching needs.

## 11. Repository/data-source integration

For a layered Flutter application, prefer a structure similar to:

```text
lib/
└── features/
    └── dogs/
        └── data/
            ├── datasources/
            │   └── dogs_local_datasource.dart
            ├── models/
            │   └── dog_model.dart
            └── repositories/
                └── dogs_repository_impl.dart
```

A local data source should own sqflite-specific operations such as:

- table/column names
- SQL
- `Database` access
- `Map<String, Object?>` conversion
- schema-specific errors

A repository should expose the project's chosen abstraction and should not force presentation code to know SQL.

Do not make a Cubit/BLoC/view call `db.query()` directly.

Whether a separate domain entity/use-case layer is required is an architecture decision outside this skill. If the project already has a `data-flow-architect`/domain skill, follow that decision rather than duplicating domain rules here.

## 12. Error handling

Do not catch every database exception and return an empty list. That hides corruption, schema mistakes, constraint failures, and real bugs.

Distinguish:

- expected "not found" behavior
- unique/foreign-key constraint violations
- migration/schema failures
- database locked/connection lifecycle problems
- unexpected database exceptions

Translate persistence exceptions at the appropriate application boundary instead of leaking raw SQLite details through the UI.

When debugging a database issue, inspect the actual exception text, SQL, arguments, schema version, and migration path before modifying code.

## 13. Query performance

Before optimizing, identify the actual query pattern.

Good defaults:

- select only required columns
- filter in SQL, not after loading a huge result set into Dart
- paginate or limit large lists
- add indexes that match real filters/sorts/joins
- avoid repeated N+1 queries when a join or batch/transaction is appropriate
- use a transaction for related writes that must be atomic
- use a batch for large repeated write sets

For difficult performance problems, inspect the SQL query plan and schema indexes rather than guessing.

Do not move database work into arbitrary Dart isolates without understanding sqflite's transaction/isolate limitations. Follow the package's documented platform/isolate behavior and the project's concurrency requirements.

## 14. Testing

At minimum, test:

1. database creation from an empty state
2. CRUD behavior
3. serialization/deserialization
4. constraints and relationships
5. migrations between supported schema versions
6. transaction rollback on failure
7. batch behavior when an operation fails
8. important indexes/queries for large datasets when performance matters

Prefer a temporary/test database path or isolated test database so tests do not mutate a developer's real app database.

Use deterministic fixtures and clean up database files after tests.

## 15. Debugging checklist

When sqflite fails:

1. Confirm the actual resolved `sqflite` version and Dart/Flutter SDK compatibility.
2. Confirm the database path.
3. Confirm whether the file is new or an existing database with an older schema version.
4. Log/inspect the schema version and migration branch being executed.
5. Verify table and column names exactly.
6. Verify SQLite-supported value types and nullability.
7. Verify `where` + `whereArgs` pairings and argument order.
8. Check foreign-key enforcement when relationships are involved.
9. For a transaction, confirm every operation uses `txn`, not `db`.
10. For locking problems, look for multiple independently opened database instances or overlapping writes.
11. For slow queries, inspect indexes and query shape before adding application-side work.

Do not "fix" migration bugs by recommending `deleteDatabase()` unless the user explicitly wants a destructive reset and understands the data-loss consequence.

## 16. Platform-specific guidance

### Android / iOS / macOS

Use the normal `sqflite` package unless the project has a specific platform requirement.

### Windows / Linux / Dart VM

Do not assume the normal mobile plugin is sufficient. Use `sqflite_common_ffi` and the project's platform initialization/path strategy when desktop support is required.

### Web

Do not assume normal mobile `sqflite` works on web. The package ecosystem has an experimental web path; verify compatibility and requirements before choosing it for production.

## 17. Do not over-engineer

For a small app, a single database helper/data source plus typed models can be enough.

Do not introduce a custom ORM, repository factory, dependency graph, query abstraction, caching layer, or generic CRUD framework solely because `sqflite` exists.

Add abstraction where it supports the project's architecture, testability, or expected change. Keep SQL explicit when explicit SQL is the simplest correct solution.

## 18. Source-of-truth and research priority

When current package/API behavior matters, prefer these sources in this order:

1. Official Codex skills documentation for Skill structure/discovery.
2. Flutter documentation for Flutter integration and persistence recipes.
3. `sqflite` package API/README/changelog on pub.dev.
4. `tekartik/sqflite` repository documentation for package-specific behavior, migrations, opening, transactions, batches, desktop/FFI, and troubleshooting.
5. Official SQLite documentation for SQL semantics, datatypes, parameters, foreign keys, indexes, and query planning.

Do not invent package APIs, callback signatures, supported platforms, or package versions. If the codebase or dependency graph is ambiguous, inspect the installed/resolved package version and use its API documentation.

## Canonical references

- Codex skills: https://learn.chatgpt.com/docs/build-skills
- Flutter persistence cookbook: https://docs.flutter.dev/cookbook/persistence
- Flutter SQLite recipe: https://docs.flutter.dev/cookbook/persistence/sqlite
- sqflite package: https://pub.dev/packages/sqflite
- sqflite API docs: https://pub.dev/documentation/sqflite/latest/
- sqflite GitHub docs: https://github.com/tekartik/sqflite/tree/master/sqflite/doc
- SQLite datatypes: https://www.sqlite.org/datatype3.html
- SQLite parameters: https://www.sqlite.org/lang_expr.html
- SQLite foreign keys: https://www.sqlite.org/foreignkeys.html
- SQLite query planning: https://www.sqlite.org/queryplanner.html
