# Newsroom v1: Нерв мира

Дата: 2026-05-12

## Описание продукта

ERA Media Factory v1 — это маленькая AI-редакция для канала «Нерв мира», а не автономный генератор публикаций.

Система помогает выпускающему редактору собрать новостной фон, выбрать темы, получить черновики, проверить смысл и доказательную базу, подготовить медиа и опубликовать пост в MAX вручную. Главный экран сотрудника — `Редактор дня`.

Цель v1: стабилизировать качество контента и не пропускать публикации с плохим смыслом, неподтверждёнными claims или слабой доказательной базой.

## Что включено

- Главный экран сотрудника: `Редактор дня`.
- Новый безопасный pipeline: сбор источников -> радар -> повестка старшего журналиста -> выбор темы человеком -> черновик -> quality loop -> медиа -> MAX-упаковка -> одобрение -> публикация.
- Автоматически запускаются только сбор радара и повестка. Черновики и публикация требуют действия человека.
- Добавлена очередь `Предложенные новости` для материалов от аудитории через Telegram.
- Добавлен Media Producer: сначала ищет preview/официальное изображение в источнике, генерация используется как fallback.
- Добавлена MAX-упаковка: короткий русский текст, без RSS/XML ссылок, с сохраненными кнопками `Предложить новость` и `Подписаться на Нерв мира`.
- Добавлен обязательный Editorial Quality Loop v1: evidence pack, meaning card, claim-check, chief editor decision и publish guards.

## Editorial Quality Loop v1

Перед approval/MAX каждый пост должен пройти:

1. `source/topic`
2. `evidence_pack`
3. `meaning_card`
4. `draft`
5. `claim-check`
6. `chief_editor`
7. `quality_loop`

Хранение v1:

- `posts.structured_outputs_json.source_tiers`
- `posts.structured_outputs_json.evidence_pack`
- `posts.structured_outputs_json.meaning_card`
- `posts.structured_outputs_json.draft_claim_check`
- `posts.structured_outputs_json.chief_editor_v2`
- `posts.structured_outputs_json.quality_loop`

Обязательные guards:

- без `quality_loop.version = "v1"` approval/MAX запрещены;
- если `quality_loop.passed != true`, approval/MAX запрещены;
- если есть `blocking_issues`, approval/MAX запрещены независимо от `quality_score`;
- high-risk/hard-news требует primary source;
- если primary нет, но есть 2+ credible secondary, пост может быть только `needs_human`, не `approved`;
- generated image нельзя подавать как evidence.

Blocking issue codes:

- `missing_primary_source`
- `unsupported_claim`
- `invented_number`
- `invented_date`
- `invented_quote`
- `unsupported_motive`
- `causality_not_supported`
- `responsibility_not_supported`
- `experts_without_source`
- `quality_loop_error`
- `generated_image_as_evidence`
- `high_risk_needs_human`

## Новые API

- `POST /api/editor-day/run-morning-scan`
- `POST /api/editor-day/build-agenda`
- `GET /api/editor-day/today`
- `POST /api/posts/{id}/prepare-media`
- `POST /api/posts/{id}/prepare-max-package`
- `POST /api/posts/{id}/quality-check`
- `POST /api/submissions`
- `GET /api/submissions`
- `POST /api/submissions/{id}/create-topic`
- `POST /api/submissions/{id}/reject`

## Миграция

- `0020_newsroom_v1`
- Добавлены поля медиа и MAX-упаковки в `posts`.
- Добавлена таблица `newsroom_submissions`.

## Safety

- Автопубликация не включалась.
- Publisher Agent не включался.
- MAX публикация остается только по явной кнопке человека.
- Mock/demo контент не получает production-публикацию.
- Ссылки RSS/XML скрываются из публичного текста поста.
- `quality_score` не перебивает blocking issues.
- Ручная правка текста инвалидирует старый quality loop до повторной проверки.

## Smoke

- `make smoke-editor-day`
- `make smoke-media-producer`
- `make smoke-max-packaging`
- `make smoke-owner-bot`
- `make smoke-editorial-quality-loop`

Все smoke-тесты пройдены на VPS после миграции.
