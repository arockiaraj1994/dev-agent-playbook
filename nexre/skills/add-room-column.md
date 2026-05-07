---
title: Add Room column — NexRe
description: Playbook for safely adding a new column to an existing Room entity.
triggers: [add column, add field to database, add database column, extend room entity, new db field]
see_also: [pattern:repository, language:kotlin/anti-patterns]
---

# Skill: Add Room column — NexRe

**Warning:** Room schema changes on existing entities require a migration. Skipping the migration causes an `IllegalStateException` crash on upgrade for existing users.

## Steps

1. **Add the field to the entity** — `data/local/entity/<Name>Entity.kt`
   ```kotlin
   @ColumnInfo(name = "my_new_column") val myNewField: String = "",
   ```
   Use a default value in the entity constructor so that the migration can supply it.

2. **Bump the database version** — `data/local/NexReDatabase.kt`
   ```kotlin
   @Database(entities = [...], version = 3)   // was 2
   ```

3. **Write a migration** — in `DatabaseModule.kt` or a dedicated `Migrations.kt` file:
   ```kotlin
   val MIGRATION_2_3 = object : Migration(2, 3) {
       override fun migrate(db: SupportSQLiteDatabase) {
           db.execSQL("ALTER TABLE links ADD COLUMN my_new_column TEXT NOT NULL DEFAULT ''")
       }
   }
   ```
   - Use `ALTER TABLE ... ADD COLUMN` — SQLite does not support other ALTER TABLE forms.
   - Match the column name exactly as in `@ColumnInfo(name = ...)`.
   - Use the correct SQLite type: `TEXT`, `INTEGER`, `REAL`, `BLOB`.
   - `NOT NULL DEFAULT` is required for non-nullable Kotlin types.

4. **Register the migration** — in `DatabaseModule.kt`:
   ```kotlin
   Room.databaseBuilder(context, NexReDatabase::class.java, "nexre.db")
       .addMigrations(MIGRATION_1_2, MIGRATION_2_3)   // add new one
       .build()
   ```

5. **Add the field to the domain model** — `domain/model/Link.kt` (if it belongs in the domain model).

6. **Update repository mapping** — `data/repository/LinkRepositoryImpl.kt`
   - Add the field in `toLink(lwt: LinkWithTags): Link` and `toEntity(link: Link): LinkEntity`.

7. **Update DAOs** if new queries reference the field.

8. **Build and test migration manually**
   - Install the old version of the app on an emulator.
   - Install the new version over it (without uninstalling).
   - Verify the app opens without crashing and existing data is intact.

## Constraints

- Never change an existing `@ColumnInfo(name = ...)` value without a migration.
- Never rename or delete a column — add migrations for renames (add new column, copy data, drop old) or just leave the old column and ignore it.
- Never use `fallbackToDestructiveMigration()` in production code — it deletes all user data.
- If the new column replaces existing logic (e.g., a denormalized field), update all callers atomically in the same PR.
