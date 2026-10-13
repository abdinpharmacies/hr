---
name: flutter-sqflite3
description: Use package:sqlite3 for direct SQLite persistence in Flutter/Dart. Covers setup, native-assets/hooks, database paths and lifecycle, synchronous SQL, prepared statements, parameter binding, ResultSet/cursors, transactions, schema and migrations, SQLite types, foreign keys, indexes, concurrency, performance, web/WASM, encryption options, testing, and data-layer integration.
---

# Flutter sqlite3 Skill

Use this skill whenever a Flutter/Dart task explicitly chooses `package:sqlite3`, asks for direct SQLite bindings, or requires implementing/debugging an existing `sqlite3` data layer.

This skill is **sqlite3-specific**. Do not silently replace it with `sqflite`, Drift, Isar, Hive, SharedPreferences, Secure Storage, or another persistence technology. If the project is using another persistence technology, follow that technology's skill instead.

`package:sqlite3` is a low-level SQLite binding. It intentionally exposes SQL and SQLite concepts instead of providing the higher-level CRUD helpers and async API found in `sqflite`. Keep that distinction explicit when designing the data layer.

## Core principles

- Keep SQLite/sqlite3 implementation details in the **data/local/persistence layer**, not in widgets, views, or Cubit/BLoC.
- Prefer a repository/data-source boundary when the application architecture already uses repositories or when the persistence implementation may change.
- Keep schema and SQL centralized. Do not scatter table/column names across presentation code.
- Treat migrations as application code. Never delete the user's database as a shortcut for a schema change unless destructive reset is explicitly required and approved.
- Use bound parameters for values. Never interpolate untrusted/user-controlled values into SQL.
- Prefer prepared statements for repeated execution or hot paths.
- Design indexes from actual query patterns; do not index every column.
- Map `Row`/`ResultSet` data into typed Dart models at the data boundary.
- Do not put credentials, tokens, or other secrets into ordinary SQLite simply because the database is local. Use an appropriate secure/encrypted storage strategy when required.
- Remember that native `sqlite3` calls are synchronous. Do not perform large/expensive queries on the Flutter UI isolate when that can block rendering or interaction.

## 1. Verify the project and dependency version first

Before adding or updating `sqlite3`:

1. Inspect the existing `pubspec.yaml` and persistence dependencies.
2. Check the project's Flutter/Dart SDK constraints.
3. Prefer:

```bash
flutter pub add sqlite3
```

4. Verify the resolved version with `flutter pub deps` or the lockfile instead of inventing or blindly pinning a version.

As of 2026-09-19, the latest stable release listed on pub.dev is `sqlite3 3.6.0`, whose minimum Dart SDK is 3.10. Do not hardcode this version into a project without checking the project's SDK constraints and the package resolver.

### Important v3 migration rule

For `sqlite3` 3.x:

- Do **not** add `sqlite3_flutter_libs` for the normal setup.
- Do **not** keep old `open.overrideFor` / old Flutter-specific SQLite loader workarounds unless the project has a verified, version-specific reason.
- `sqlite3` 3.x uses Dart/Flutter hooks and native assets to bundle SQLite by default.
- If upgrading a v2 project, remove obsolete `sqlite3_flutter_libs` dependencies and update web WASM assets/setup as required.

`sqlite3_flutter_libs` is obsolete for `sqlite3` 3.x and its current package release is only kept to avoid old transitive dependency issues. Follow the project's actual resolved package version and upgrade notes when migrating an existing app.

## 2. Native setup

For native Flutter/Dart platforms, import:

```dart
import 'package:sqlite3/sqlite3.dart';
```

Then open a file-backed database with:

```dart
final db = sqlite3.open(databasePath);
```

Or use an in-memory database for temporary/testing scenarios:

```dart
final db = sqlite3.openInMemory();
```

The package bundles SQLite for supported native platforms through hooks by default, so a normal `sqlite3` 3.x setup should not require manually installing a system SQLite library or adding `sqlite3_flutter_libs`.

### Choosing the database path

`sqlite3` itself accepts a path; it does not provide `sqflite`'s `getDatabasesPath()` API.

In Flutter, obtain an application-owned directory with the project's filesystem/path package, commonly `path_provider`, then build the final path with `package:path/path.dart`:

```dart
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

final directory = await getApplicationSupportDirectory();
final databasePath = p.join(directory.path, 'app.db');
final db = sqlite3.open(databasePath);
```

Choose the directory according to the app's lifecycle and platform requirements. Do not put a writable production database in the project bundle or another non-persistent asset location.

### Database lifecycle

A database is a native resource. Close it when the owning resource/lifecycle genuinely ends:

```dart
db.close();
```

Do not repeatedly open/close the same database for every CRUD operation. Prefer a long-lived database owner in the data layer, and make ownership explicit so the database is not closed while statements/cursors are still in use.

Prefer `close()` in current `sqlite3` APIs. Older examples may use `dispose()`; `dispose()` is deprecated on current common database/statement APIs.

## 3. Execute SQL directly

`sqlite3` exposes direct SQL execution:

```dart
db.execute('''
  CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL
  ) STRICT
''');
```

Use `execute()` for statements where result rows are not needed, such as `CREATE`, `ALTER`, `INSERT`, `UPDATE`, and `DELETE`.

For reads:

```dart
final result = db.select(
  'SELECT id, name, age FROM users WHERE age >= ?',
  [18],
);
```

`select()` prepares the SQL and returns a `ResultSet` containing all selected rows.

Do not confuse `sqlite3`'s direct API with `sqflite`'s async API. A call such as `db.select(...)` is synchronous on native platforms.

## 4. Parameter binding and SQL safety

Always bind **values** instead of constructing SQL with string interpolation or concatenation.

Good:

```dart
final result = db.select(
  'SELECT * FROM users WHERE id = ? AND name = ?',
  [userId, name],
);
```

Bad:

```dart
final result = db.select(
  'SELECT * FROM users WHERE id = $userId AND name = \'$name\'',
);
```

Binding parameters protects value positions from SQL injection and lets SQLite handle the value type correctly.

Current `sqlite3` parameter binding supports values such as:

- `int`
- `BigInt` where supported by the current platform/package mode
- `double`
- `String`
- `List<int>` for BLOB data
- `null`

Prefer `Uint8List` for binary values when appropriate.

### Parameters are for values, not SQL identifiers

Do not try to bind table names, column names, sort-direction keywords, or SQL syntax as normal parameters.

If dynamic identifiers are required, validate them against a fixed allowlist and quote them correctly for SQLite. Never pass arbitrary user input directly into an identifier position.

## 5. Prepared statements

Use `prepare()` when the same SQL statement is executed repeatedly or when explicit statement lifecycle matters:

```dart
final statement = db.prepare(
  'INSERT INTO users (name, age) VALUES (?, ?)',
);

try {
  statement.execute(['Mohamed', 23]);
  statement.execute(['Ali', 25]);
} finally {
  statement.close();
}
```

Prepared statements are especially useful for loops, bulk inserts, hot queries, and repeated parameterized operations.

Current `sqlite3` also supports named-parameter binding through the `StatementParameters` API when that makes the SQL easier to maintain:

```dart
final statement = db.prepare('''
  SELECT id, name
  FROM users
  WHERE age >= :minAge AND name LIKE :pattern
''');

try {
  final rows = statement.selectWith(
    StatementParameters.named({
      'minAge': 18,
      'pattern': 'M%',
    }),
  );
} finally {
  statement.close();
}
```

Do not copy deprecated API examples such as `executeMap` / `selectMap` into new code when the current package provides `executeWith` / `selectWith` and `StatementParameters`.

### Statement lifecycle

Close prepared statements when they are no longer needed:

```dart
statement.close();
```

Do not retain a prepared statement after its owning database has been closed.

If a prepared statement is reused, understand its reset/re-execution semantics and keep its ownership local and explicit.

## 6. Reading rows

A normal `db.select()` returns a `ResultSet`.

`ResultSet` stores the full result set in memory and provides `Row` objects. A `Row` behaves like a map keyed by column name:

```dart
final result = db.select(
  'SELECT id, name, age FROM users ORDER BY id',
);

for (final row in result) {
  print(row['id']);
  print(row['name']);
  print(row['age']);
}
```

Prefer explicit column lists over `SELECT *` when you do not need all columns, especially in larger queries or when schema evolution is expected.

### Mapping rows to typed models

Keep the raw SQLite row at the data boundary:

```dart
class UserModel {
  final int id;
  final String name;
  final int age;

  const UserModel({
    required this.id,
    required this.name,
    required this.age,
  });

  factory UserModel.fromRow(Row row) {
    return UserModel(
      id: row['id'] as int,
      name: row['name'] as String,
      age: row['age'] as int,
    );
  }
}
```

Then:

```dart
final users = [
  for (final row in db.select('SELECT id, name, age FROM users'))
    UserModel.fromRow(row),
];
```

Do not expose `Row`, `ResultSet`, or `CommonDatabase` to Cubits/views unless the project's architecture explicitly treats them as its public data abstraction.

### Large result sets

`ResultSet` materializes the complete result into memory. For large result sets, prefer a cursor/iterator approach where practical rather than loading every row at once.

Prepared statements expose cursor-oriented APIs such as `selectCursor()`. Use them when processing rows incrementally can reduce memory pressure.

Example pattern:

```dart
final statement = db.prepare('SELECT id, name FROM users ORDER BY id');

try {
  final cursor = statement.selectCursor();

  while (cursor.moveNext()) {
    final row = cursor.current;
    // Process one row at a time.
  }
} finally {
  statement.close();
}
```

Keep the database, statement, and cursor alive for the whole iteration and close them in the correct ownership order.

## 7. Inserts, updates, deletes, and result metadata

For an insert:

```dart
db.execute(
  'INSERT INTO users (name, age) VALUES (?, ?)',
  ['Mohamed', 23],
);
final id = db.lastInsertRowId;
```

For updates/deletes:

```dart
db.execute(
  'UPDATE users SET age = ? WHERE id = ?',
  [24, userId],
);
final updatedRows = db.updatedRows;
```

`lastInsertRowId` reports the most recent successful insert rowid on that database connection. `updatedRows` reports the number of rows changed by the most recent `INSERT`, `UPDATE`, or `DELETE` statement.

Do not assume `updatedRows` represents a cumulative count across several statements.

## 8. Transactions

`package:sqlite3` exposes SQLite directly; use SQLite transaction statements explicitly when an operation must be atomic:

```dart
try {
  db.execute('BEGIN');

  db.execute(
    'INSERT INTO orders (id, user_id) VALUES (?, ?)',
    [orderId, userId],
  );

  db.execute(
    'INSERT INTO order_items (order_id, product_id) VALUES (?, ?)',
    [orderId, productId],
  );

  db.execute('COMMIT');
} catch (_) {
  if (!db.autocommit) {
    db.execute('ROLLBACK');
  }
  rethrow;
}
```

Use the connection's `autocommit` state when diagnosing or deciding whether rollback is still needed.

### Transaction rules

- Keep the transaction short.
- Do not perform network calls, user interaction, delays, or unrelated expensive work while a write transaction is open.
- Do not assume `BEGIN` transactions can nest. SQLite uses `SAVEPOINT` / `RELEASE` for nested transactional scopes.
- Use `BEGIN IMMEDIATE` deliberately when the operation should acquire the write transaction up front and the concurrency model calls for it.
- Do not catch an error and silently continue as though the transaction is still known to be in a clean state. Decide explicitly whether to roll back or commit.

SQLite allows multiple simultaneous readers from separate connections but only one simultaneous writer. Long-running writers increase lock contention and can produce `SQLITE_BUSY` conditions.

## 9. Schema design

Design the relational schema before writing repository methods.

Prefer:

- `INTEGER PRIMARY KEY` for integer identifiers when that matches the domain.
- `NOT NULL` where null is not semantically valid.
- `UNIQUE` constraints for real uniqueness rules.
- foreign keys for relationships.
- indexes based on actual query patterns.
- `CHECK` constraints for simple invariants that belong in the database.
- `STRICT` tables when the project's schema/SQLite version supports and benefits from them.

Example:

```sql
CREATE TABLE breeds (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE dogs (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  age INTEGER NOT NULL CHECK (age >= 0),
  breed_id INTEGER,
  FOREIGN KEY (breed_id) REFERENCES breeds(id) ON DELETE SET NULL
) STRICT;

CREATE INDEX idx_dogs_breed_id ON dogs(breed_id);
```

Do not add `AUTOINCREMENT` automatically. SQLite's `INTEGER PRIMARY KEY` already provides automatic rowid assignment; `AUTOINCREMENT` has additional semantics and overhead and should only be used for a verified requirement.

## 10. Foreign keys

SQLite foreign-key enforcement must be treated as an explicit database configuration concern. Do not assume that declaring a `FOREIGN KEY` guarantees enforcement in every connection configuration.

When the application's schema relies on foreign-key enforcement, enable it for the connection and verify the behavior:

```dart
db.execute('PRAGMA foreign_keys = ON');
```

Do this during database initialization before operations whose correctness depends on the constraint.

Use schema-level actions such as `ON DELETE CASCADE`, `ON DELETE SET NULL`, or `ON DELETE RESTRICT` when those semantics accurately represent the domain. Do not duplicate referential cleanup logic across multiple repositories when the database can safely enforce it.

## 11. SQLite types and Dart mapping

SQLite has storage classes rather than a Dart-style type system.

Typical mapping:

| Dart value | SQLite storage | Notes |
|---|---|---|
| `int` | `INTEGER` | 64-bit signed integer semantics on native SQLite bindings |
| `double` | `REAL` | Floating-point values |
| `String` | `TEXT` | Text values |
| `Uint8List` / `List<int>` | `BLOB` | Binary data |
| `null` | `NULL` | Only when the column permits null |

Do not assume SQLite has dedicated boolean or DateTime storage classes.

### bool

Store boolean state consistently, commonly as `INTEGER` `0` / `1`:

```sql
is_completed INTEGER NOT NULL DEFAULT 0 CHECK (is_completed IN (0, 1))
```

Mapping:

```dart
'is_completed': task.isCompleted ? 1 : 0,
```

```dart
taskCompleted: (row['is_completed'] as int) == 1,
```

### DateTime

Choose one representation per project, for example:

- `INTEGER` milliseconds since epoch, or
- `TEXT` ISO-8601 representation.

Be consistent across schema, query code, serialization, and tests.

### Enums

Do not rely on Dart enum ordinals as a long-lived database contract unless the ordering is deliberately frozen. Prefer stable strings or explicitly assigned integer values.

## 12. Migrations

`package:sqlite3` exposes SQLite directly, so schema-version management is an application responsibility. A common approach is to use SQLite's `PRAGMA user_version`.

Read the version:

```dart
final version = db.userVersion;
```

Set it after successfully applying an incremental migration:

```dart
db.userVersion = 2;
```

Use incremental migrations instead of rebuilding the database from scratch:

```dart
void migrate(Database db) {
  final oldVersion = db.userVersion;

  if (oldVersion < 2) {
    db.execute('ALTER TABLE users ADD COLUMN email TEXT');
  }

  if (oldVersion < 3) {
    db.execute('CREATE INDEX idx_users_email ON users(email)');
  }

  db.userVersion = 3;
}
```

### Make migrations atomic

Schema changes that must succeed together should run inside a transaction:

```dart
try {
  db.execute('BEGIN');

  final oldVersion = db.userVersion;

  if (oldVersion < 2) {
    db.execute('ALTER TABLE users ADD COLUMN email TEXT');
  }

  if (oldVersion < 3) {
    db.execute('CREATE INDEX idx_users_email ON users(email)');
  }

  db.userVersion = 3;
  db.execute('COMMIT');
} catch (_) {
  if (!db.autocommit) {
    db.execute('ROLLBACK');
  }
  rethrow;
}
```

Never set the final schema version before all required changes have succeeded.

Do not skip intermediate migrations. If a user is upgrading from version 1 to version 3, code must correctly apply the 1→2 and 2→3 changes in order.

For complex migrations involving data transformation, split structural and data changes clearly and test old-schema fixtures.

## 13. Indexes and query performance

Indexes should follow real access patterns.

Typical candidates include:

- columns frequently filtered in `WHERE` conditions
- foreign-key lookup columns
- common `ORDER BY` patterns
- composite indexes matching recurring multi-column filters

Every index has a storage and write/update cost. Do not add one merely because a column exists.

For performance investigations:

1. Inspect the actual SQL.
2. Check result size and selected columns.
3. Check relevant indexes.
4. Use SQLite query-planning tools such as `EXPLAIN QUERY PLAN`.
5. Measure before and after changes.

Example:

```dart
final plan = db.select('''
  EXPLAIN QUERY PLAN
  SELECT id, name
  FROM users
  WHERE email = ?
''', [email]);
```

Avoid accidental work such as:

- unbounded `SELECT` queries for very large tables
- fetching columns you do not need
- filtering in Dart when SQLite can efficiently filter
- N+1 queries when a join or batched strategy is appropriate
- creating many single-row statements when a prepared statement in a transaction would be more efficient

## 14. Batch writes and repeated operations

There is no `sqflite`-style `Batch` abstraction in the low-level `sqlite3` API. For repeated writes, prefer a prepared statement and, when atomicity matters, a transaction:

```dart
final statement = db.prepare(
  'INSERT INTO users (name, age) VALUES (?, ?)',
);

try {
  db.execute('BEGIN');

  for (final user in users) {
    statement.execute([user.name, user.age]);
  }

  db.execute('COMMIT');
} catch (_) {
  if (!db.autocommit) {
    db.execute('ROLLBACK');
  }
  rethrow;
} finally {
  statement.close();
}
```

Keep the transaction focused and avoid doing unrelated work inside it.

## 15. Synchronous execution and isolates

This is one of the most important differences from `sqflite`.

On native platforms, `package:sqlite3` provides direct synchronous access to SQLite. The package documentation recommends moving substantial database work off the UI isolate when appropriate.

Use an isolate or an appropriate async database wrapper when:

- a query processes a large result set
- a migration is expensive
- bulk import/export is large
- CPU-heavy mapping/transformation accompanies database access
- database work can produce visible frame drops

Do not automatically create an isolate for every tiny query. The point is to avoid blocking the UI isolate with meaningful synchronous work.

When isolates are used, make database ownership explicit. Do not casually share a native database connection between isolates. Each isolate/connection should follow the concurrency model supported by the chosen architecture.

The `sqlite3` ecosystem also provides packages such as `sqlite3_connection_pool` and `sqlite_async` for higher-level asynchronous/isolate-oriented usage. Do not introduce these automatically when the task specifically asks for direct `package:sqlite3` usage; first respect the selected technology and project requirements.

## 16. Concurrency and locking

SQLite permits multiple readers but only one simultaneous writer for a database file. Separate connections/isolates increase the importance of lock handling rather than removing it.

Know the meaning of common errors such as:

- `SQLITE_BUSY`: database/table is locked
- `SQLITE_CONSTRAINT`: constraint violation
- `SQLITE_READONLY`: write attempted against a read-only database
- `SQLITE_CORRUPT`: malformed/corrupt database
- `SQLITE_CANTOPEN`: database could not be opened

Do not hide these errors behind a generic "database failed" message in the data layer. Preserve useful error context and translate it into an application-level failure type where the architecture calls for it.

If lock contention is expected, investigate transaction duration, connection ownership, journal mode, and competing readers/writers before adding retries. Do not add blind retry loops around every SQLite call.

## 17. PRAGMA configuration

Use `PRAGMA` statements deliberately and document why an app requires them.

Examples of legitimate configuration/diagnostic uses include:

```dart
db.execute('PRAGMA foreign_keys = ON');
```

```dart
final journal = db.select('PRAGMA journal_mode');
```

Do not blindly copy a random collection of PRAGMAs from a blog post. Some settings are connection-specific, some affect persistent database state, and some depend on SQLite version or deployment constraints.

When using WAL, test the app's actual connection/concurrency model and platform behavior instead of assuming WAL solves every locking problem.

## 18. Custom SQL functions and collations

The current API can register Dart-backed SQL functions and collations on a database connection:

```dart
db.createFunction(
  functionName: 'dart_version',
  argumentCount: const AllowedArgumentCount(0),
  function: (args) => 'example',
);
```

Use this only when there is a clear query-level need. Keep such registrations near database initialization so every required connection is configured consistently.

Do not make arbitrary application/business logic dependent on per-connection custom functions without a clear lifecycle and testing strategy.

## 19. SQLite extensions and encryption

`package:sqlite3` can load/use SQLite extensions when supported by the build and platform.

For encrypted databases, current `sqlite3` 3.x supports configurable SQLite builds such as SQLCipher and SQLite3 Multiple Ciphers through hooks/user defines. Do not claim that ordinary SQLite files are encrypted merely because they are stored on a private application directory.

Only introduce an encrypted build after checking the project's platform, CI/build tooling, database migration requirements, and licensing/operational constraints.

Never hard-code encryption keys in source code.

## 20. Web / WASM

`package:sqlite3` supports web through a separate WASM implementation, but web is **not** the same setup as native Flutter.

Native:

```dart
import 'package:sqlite3/sqlite3.dart';

final db = sqlite3.open('app.db');
```

Web:

```dart
import 'package:sqlite3/wasm.dart';
```

A web app needs a compatible `sqlite3.wasm` build and a virtual filesystem strategy because browser code cannot use the host operating system filesystem directly.

For browser persistence, the current package documents VFS options such as `InMemoryFileSystem`, `IndexedDbFileSystem`, and OPFS-oriented implementations. Do not copy native file-path code into a Flutter web target and expect it to work.

When sharing database code across native and web platforms, use the common interfaces where practical:

```dart
import 'package:sqlite3/common.dart';
```

Then use conditional/platform-specific database opening code for the actual native/WASM implementation.

Do not add web setup to a native-only task unless the project targets web.

## 21. Testing

Prefer in-memory databases for isolated database tests:

```dart
final db = sqlite3.openInMemory();
```

This avoids filesystem state leaking between tests and makes schema setup deterministic.

A database test should normally verify:

- schema creation
- migrations from representative old versions
- inserts
- reads and mapping
- updates
- deletes
- uniqueness and foreign-key constraints
- transaction rollback on failure
- transaction commit on success
- index/query behavior where performance is important
- null/type conversion behavior

Always close test databases and statements.

For migration tests, create a database at the old version, insert representative data, run the migration, then assert both schema and data compatibility.

Do not rely only on a test that creates the newest schema from scratch; that misses migration bugs.

## 22. Architecture integration

A clean Flutter data flow can look like:

```text
Presentation
  ↓
Domain repository interface
  ↓
Data repository implementation
  ↓
Local data source / DAO
  ↓
SQLite database owner
  ↓
package:sqlite3
```

The exact layering should follow the project's existing architecture. Do not create artificial layers solely because this skill exists.

Good separation:

```text
lib/features/users/data/local/sqlite_database.dart
lib/features/users/data/local/user_local_data_source.dart
lib/features/users/data/models/user_model.dart
lib/features/users/data/repositories/user_repository_impl.dart
```

The local data source owns SQL and `Row` mapping. The repository coordinates the data source with the rest of the feature. Cubit/BLoC/View code should receive application/domain models, not raw SQLite structures.

## 23. Recommended database owner pattern

A small database owner can centralize opening, configuration, and closing:

```dart
class AppDatabase {
  AppDatabase(this.db);

  final Database db;

  static Future<AppDatabase> open() async {
    final directory = await getApplicationSupportDirectory();
    final path = p.join(directory.path, 'app.db');
    final db = sqlite3.open(path);

    db.execute('PRAGMA foreign_keys = ON');
    _migrate(db);

    return AppDatabase(db);
  }

  void close() => db.close();

  static void _migrate(Database db) {
    final current = db.userVersion;

    if (current < 1) {
      db.execute('''
        CREATE TABLE users (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          age INTEGER NOT NULL
        ) STRICT
      ''');
      db.userVersion = 1;
    }
  }
}
```

Adapt this to the project's initialization lifecycle and migration strategy. Do not blindly copy the directory or schema names.

## 24. Common mistakes to prevent

### Do not use `sqlite3_flutter_libs` with normal sqlite3 3.x setup

That package belongs to the old v2 loading model and is obsolete after adopting v3.

### Do not treat synchronous APIs as async

Bad conceptual model:

```dart
final rows = await db.select(...);
```

Native `sqlite3` calls are synchronous. Use the API exactly as exposed by the resolved package version; move expensive work off the UI isolate when needed.

### Do not expose rows everywhere

Bad:

```dart
Widget build(...) {
  final rows = database.select(...);
}
```

Database access belongs in the data layer.

### Do not interpolate values into SQL

Bad:

```dart
db.select('SELECT * FROM users WHERE id = $id');
```

Good:

```dart
db.select('SELECT * FROM users WHERE id = ?', [id]);
```

### Do not forget statement cleanup

Prepared statements hold native resources. Close them when ownership ends.

### Do not load huge result sets blindly

`ResultSet` contains the full result. Use a cursor/iteration approach when the dataset can be large.

### Do not leave migrations implicit

Track schema version explicitly and test every migration path.

### Do not assume foreign keys are enforced

Configure and test foreign-key enforcement for the actual connection.

### Do not overuse transactions

Transactions protect atomicity, but long transactions hold locks and can increase contention.

### Do not blindly copy outdated v2 examples

The package's 3.x API and native asset loading model differ from older articles and snippets. Verify examples against the resolved package documentation.

## 25. Implementation workflow

When asked to implement sqlite3 persistence, follow this order:

1. Inspect the project's Flutter/Dart SDK constraints and existing persistence packages.
2. Verify the resolved `sqlite3` version and platform targets.
3. Inspect the existing architecture before introducing new layers.
4. Decide the database owner and file location.
5. Define schema and constraints.
6. Define schema version and migration strategy.
7. Configure required connection-level settings such as foreign keys.
8. Implement prepared statements / SQL in the local data source.
9. Add typed row-to-model mapping.
10. Add repository integration according to the project architecture.
11. Add tests for CRUD, constraints, rollback, and migrations.
12. Analyze expensive queries and move substantial synchronous work off the UI isolate when required.
13. Run formatter, analyzer, and relevant tests.

Before coding, inspect existing database/schema code and reuse established naming and architecture conventions unless there is a concrete reason to change them.

## 26. Official/source references

Use current primary references before inventing an API or relying on an old snippet:

- OpenCode Skills: https://opencode.ai/docs/skills
- sqlite3 package: https://pub.dev/packages/sqlite3
- sqlite3 API docs: https://pub.dev/documentation/sqlite3/latest/
- sqlite3 examples: https://pub.dev/packages/sqlite3/example
- sqlite3 changelog: https://pub.dev/packages/sqlite3/changelog
- sqlite3 v2 → v3 upgrade notes: https://github.com/simolus3/sqlite3.dart/blob/main/UPGRADING_TO_V3.md
- sqlite3 hooks/native assets: https://github.com/simolus3/sqlite3.dart/blob/main/sqlite3/doc/hook.md
- sqlite3 repository: https://github.com/simolus3/sqlite3.dart
- SQLite transactions: https://www.sqlite.org/lang_transaction.html
- SQLite SELECT: https://www.sqlite.org/lang_select.html
- SQLite prepared statements: https://www.sqlite.org/c3ref/prepare.html

For Flutter-specific storage architecture, use the project's existing Flutter architecture guidance and avoid creating framework-specific abstractions that conflict with the app's conventions.

## 27. Final decision rule

Choose `package:sqlite3` intentionally when the project needs direct SQLite control from Dart and accepts the lower-level, synchronous native API.

Do not choose it merely because "SQLite is fast" or because another SQLite package is unfamiliar.

When the project specifically requires:

- direct SQL control
- prepared statements
- low-level SQLite features
- custom SQLite builds/extensions
- native/WASM common database interfaces

then `sqlite3` is an appropriate fit.

When the task actually requires a higher-level reactive/type-safe ORM, automatic async database execution, or a project-standard abstraction such as Drift, stop using this skill and follow the appropriate persistence technology skill instead.
