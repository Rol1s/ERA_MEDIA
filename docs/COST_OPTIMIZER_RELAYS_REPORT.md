# Cost Optimizer and Relay Mode v1

## Что изменилось

- Включен режим `cost_optimized=true`.
- Добавлен отдельный тип каналов `channel_mode=relay`.
- Добавлена страница `/relays` для live-ретрансляторов.
- Добавлен LLM cache: повторный запуск по тому же source item, шагу pipeline и prompt version не тратит OpenAI повторно.
- FT-live переведен в дешевый режим: один LLM-вызов максимум на пост, без полного newsroom quality loop и без генерации картинок.
- Утренняя повестка ограничена top-50 поводами вместо широкого прогона по большому радару.

## Как работает relay

Поток:

`RSS/source item -> dedupe -> source preview media -> one cheap LLM rewrite -> code guard -> MAX package -> publish`

Для relay не запускаются:

- senior agenda;
- полный newsroom quality loop;
- генерация изображений по умолчанию;
- редакционные задачи в общей ленте.

## Защита relay

Автопубликация блокируется, если:

- RSS-анонс слишком бедный;
- тема high-risk;
- в тексте появились числа вне исходного анонса;
- нет source URL;
- MAX-канал не подключен.

High-risk уходит в `needs_human`.

## Financial Times по-русски

Канал переведен в `relay`:

- `channel_mode=relay`
- `relay_mode=multi_source_live`
- источники: FT World, FT Markets, FT Europe, FT Companies, FT US
- auto low-risk включен

## Проверки

Пройдены:

- `smoke-cost-optimizer`
- `smoke-relay-channel`
- `smoke-ft-live-cheap`
- `smoke-daily-package`

## Ожидаемая экономия

- Relay: x3-x5 дешевле, потому что нет полного quality loop и генерации медиа.
- Утренняя повестка: минимум x2 дешевле за счет ограничения top-50.
- Повторные проверки источника дешевле за счет LLM cache.
