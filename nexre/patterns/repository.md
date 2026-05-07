---
title: Repository pattern — NexRe
description: How repositories, DAOs, and domain interfaces are structured in NexRe.
tags: [repository, room, dao, kotlin, clean-architecture]
see_also: [pattern:usecase, skill:add-room-column]
---

# Pattern: Repository — NexRe

**Use this when:** adding a new data operation, a new query, or a new domain entity.

## Structure

```
domain/repository/LinkRepository.kt        ← interface (domain layer)
data/local/dao/LinkDao.kt                  ← Room DAO
data/local/entity/LinkEntity.kt            ← @Entity
data/local/entity/LinkWithTags.kt          ← @Relation view
data/repository/LinkRepositoryImpl.kt      ← implements LinkRepository
di/RepositoryModule.kt                     ← binds impl to interface
```

## Canonical example

### Interface (domain layer — no Android imports)
```kotlin
interface LinkRepository {
    fun getLinkById(id: String): Flow<Link?>
    suspend fun saveLink(link: Link, tagSource: String = "KEYWORD")
    suspend fun deleteLink(id: String)
}
```

### DAO (data layer)
```kotlin
@Dao
interface LinkDao {
    @Query("SELECT * FROM links WHERE id = :id")
    fun getLinkById(id: String): Flow<LinkWithTags?>

    @Upsert
    suspend fun upsertLink(link: LinkEntity)

    @Query("DELETE FROM links WHERE id = :id")
    suspend fun deleteLink(id: String)
}
```

### Implementation
```kotlin
@Singleton
class LinkRepositoryImpl @Inject constructor(
    private val linkDao: LinkDao,
    private val tagDao: TagDao,
) : LinkRepository {

    override fun getLinkById(id: String) =
        linkDao.getLinkById(id).map { it?.let(::toLink) }

    override suspend fun saveLink(link: Link, tagSource: String) {
        linkDao.upsertLink(toEntity(link))
        // ... tag cross-ref logic
    }

    override suspend fun deleteLink(id: String) = linkDao.deleteLink(id)

    private fun toLink(lwt: LinkWithTags): Link = Link(/* map fields */)
    private fun toEntity(link: Link): LinkEntity = LinkEntity(/* map fields */)
}
```

### DI binding
```kotlin
@Module @InstallIn(SingletonComponent::class)
abstract class RepositoryModule {
    @Binds abstract fun bindLinkRepository(impl: LinkRepositoryImpl): LinkRepository
}
```

## Key rules

- The interface lives in `domain/` — zero Android/Room imports.
- The implementation lives in `data/repository/` and is `@Singleton`.
- Observable queries return `Flow<...>`, mutations are `suspend`.
- Mapping between `LinkEntity`/`LinkWithTags` and `Link` domain model happens inside the repository impl (`toLink`, `toEntity`) — never in the DAO or use case.
- Tags are managed via `LinkTagCrossRef` — when saving a link, always call `deleteLinkTags(id)` then re-insert the new refs to keep them in sync.
- Use `runCatching { SomeEnum.valueOf(str) }.getOrDefault(fallback)` when mapping string columns to enums.
