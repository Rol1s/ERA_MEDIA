"use client";

import { CheckCircle2, KeyRound, PlugZap, Radio, RefreshCw, Save, Send, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { SafeActionButton, secretConfigured, Toast } from "@/components/operator";
import { api, Channel, ChannelWorkspace, MaxDiscoveredChat, PlatformChannel, SecretStatus, SecretsStatus } from "@/lib/api";

const MAX_SECRET = "MAX_BOT_TOKEN";

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Действие не выполнено";
}

function formatDate(value?: string | null) {
  if (!value) return "не было";
  return new Date(value).toLocaleString("ru-RU");
}

function chatId(value?: string | number | null) {
  return String(value || "").trim();
}

function platformLabel(platform?: PlatformChannel | null) {
  if (!platform) return "не создано";
  if (platform.status === "connected") return "связь проверена";
  if (platform.status === "failed") return "ошибка проверки";
  return "не проверен";
}

function statusClass(value?: string) {
  if (value === "connected" || value === "active") return "active";
  if (value === "failed") return "failed";
  return "warning";
}

export default function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [platforms, setPlatforms] = useState<PlatformChannel[]>([]);
  const [platformDrafts, setPlatformDrafts] = useState<Record<number, Partial<PlatformChannel>>>({});
  const [secrets, setSecrets] = useState<SecretsStatus | null>(null);
  const [tokenInput, setTokenInput] = useState("");
  const [discoveredChats, setDiscoveredChats] = useState<MaxDiscoveredChat[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<number | null>(null);
  const [workspace, setWorkspace] = useState<ChannelWorkspace | null>(null);
  const [manualUrl, setManualUrl] = useState("");
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();

  const maxSecret = useMemo(
    () => secrets?.providers.find((item) => item.provider === "max") as SecretStatus | undefined,
    [secrets],
  );
  const tokenReady = secretConfigured(maxSecret?.status);
  const platformByChannel = useMemo(() => new Map(platforms.map((item) => [item.channel_id, item])), [platforms]);
  const platformByChat = useMemo(() => new Map(platforms.filter((item) => item.external_chat_id).map((item) => [item.external_chat_id, item])), [platforms]);
  const activeChannels = channels.filter((channel) => channel.status === "active" && channel.channel_mode !== "relay");
  const unboundChats = discoveredChats.filter((chat) => !platformByChat.has(chatId(chat.chat_id)));

  const load = async () => {
    const [nextChannels, nextPlatforms, nextSecrets] = await Promise.all([
      api.channels(),
      api.platformChannels(),
      api.secretsStatus(),
    ]);
    setChannels(nextChannels);
    setPlatforms(nextPlatforms);
    setSecrets(nextSecrets);
    setPlatformDrafts(Object.fromEntries(nextPlatforms.map((item) => [item.id, item])));
    if (selectedChannelId) {
      setWorkspace(await api.channelWorkspace(selectedChannelId));
    }
  };

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
  }, []);

  const run = async (label: string, action: () => Promise<void>, success: string) => {
    setBusy(label);
    setToast(undefined);
    try {
      await action();
      await load();
      setToast({ message: success, kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    } finally {
      setBusy("");
    }
  };

  const openWorkspace = async (channelId: number) => {
    setSelectedChannelId(channelId);
    setBusy(`workspace-${channelId}`);
    try {
      setWorkspace(await api.channelWorkspace(channelId));
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    } finally {
      setBusy("");
    }
  };

  const patchPlatform = (id: number, data: Partial<PlatformChannel>) => {
    setPlatformDrafts((current) => ({ ...current, [id]: { ...current[id], ...data } }));
  };

  const saveToken = async () => {
    await api.saveSecret("max", MAX_SECRET, tokenInput.trim());
    setTokenInput("");
  };

  const savePlatform = async (platform: PlatformChannel) => {
    const draft = platformDrafts[platform.id] || platform;
    await api.updatePlatformChannel(platform.id, {
      external_chat_id: (draft.external_chat_id || "").trim(),
      external_channel_url: (draft.external_channel_url || "").trim(),
      publish_mode: draft.publish_mode || "manual_copy",
      can_publish: draft.can_publish,
      status: draft.status,
    });
  };

  const discoverChats = async () => {
    const result = await api.discoverMaxChats();
    setDiscoveredChats(result.chats || []);
  };

  const startChat = async (chat: MaxDiscoveredChat) => {
    const result = await api.startMaxChannel({ chat_id: chatId(chat.chat_id), title: chat.title || undefined, link: chat.link || undefined });
    setSelectedChannelId(result.channel.id);
    setWorkspace(await api.channelWorkspace(result.channel.id));
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">MAX-каналы</h1>
          <p className="page-subtitle">
            Здесь канал подключается к ERA: бот видит MAX-чат, ты нажимаешь «Начать», и у канала появляется свой радар, темы и посты.
          </p>
        </div>
        <span className="status warning">ручной запуск</span>
      </div>

      <Toast message={toast?.message} kind={toast?.kind} />

      <section className="panel">
        <div className="section-title">
          <div>
            <h2>1. Токен и поиск каналов</h2>
            <p className="muted">Discover только читает список чатов, которые видит бот. Публикация не вызывается.</p>
          </div>
          <span className={`status ${tokenReady ? "active" : "warning"}`}>{tokenReady ? "токен сохранен" : "нужен токен"}</span>
        </div>
        <div className="form-grid">
          <label>
            Текущий статус
            <input className="input" readOnly value={maxSecret?.masked_value || (tokenReady ? "сохранен" : "ключ отсутствует")} />
          </label>
          <label>
            Новый токен
            <input className="input" type="password" autoComplete="new-password" placeholder="MAX_BOT_TOKEN" value={tokenInput} onChange={(event) => setTokenInput(event.target.value)} />
          </label>
        </div>
        <div className="mini-log">
          <div>Последняя проверка: {formatDate(maxSecret?.last_test_at)}</div>
          <div>Последний успех: {formatDate(maxSecret?.last_success_at)}</div>
          <div>Ошибка: {maxSecret?.last_error || "нет"}</div>
        </div>
        <div className="actions">
          <SafeActionButton disabled={busy === "save-token"} disabledReason={!tokenInput.trim() ? "Вставь токен перед сохранением." : ""} onClick={() => run("save-token", saveToken, "MAX-токен сохранен.")}>
            <KeyRound size={16} /> Сохранить токен
          </SafeActionButton>
          <SafeActionButton className="btn secondary" disabled={busy === "test-token"} disabledReason={!tokenReady ? "Сначала сохрани токен." : ""} onClick={() => run("test-token", async () => { await api.testSecret("max", MAX_SECRET); }, "MAX-токен проверен.")}>
            <PlugZap size={16} /> Проверить токен
          </SafeActionButton>
          <SafeActionButton className="btn secondary" disabled={busy === "discover-chats"} disabledReason={!tokenReady ? "Сначала сохрани MAX-токен." : ""} onClick={() => run("discover-chats", discoverChats, "Список MAX-каналов обновлен.")}>
            <Radio size={16} /> Найти каналы бота
          </SafeActionButton>
        </div>
      </section>

      <section className="panel">
        <div className="section-title">
          <div>
            <h2>2. Найденные MAX-каналы</h2>
            <p className="muted">Нажатие «Начать» только создает рабочее место канала. Агенты, LLM и публикация не запускаются.</p>
          </div>
          <span className="status">{discoveredChats.length} найдено</span>
        </div>
        {discoveredChats.length ? (
          <div className="post-grid">
            {discoveredChats.map((chat, index) => {
              const id = chatId(chat.chat_id);
              const bound = platformByChat.get(id);
              const boundChannel = bound ? channels.find((channel) => channel.id === bound.channel_id) : null;
              return (
                <article className="row-card" key={`${id || index}`}>
                  <div className="section-title">
                    <div>
                      <h3>{chat.title || "MAX-канал без названия"}</h3>
                      <p className="muted">chat_id: {id || "не указан"} {chat.link ? `· ${chat.link}` : ""}</p>
                    </div>
                    <span className={`status ${bound ? "active" : "warning"}`}>{bound ? "в ERA" : "новый"}</span>
                  </div>
                  <div className="mini-log">
                    <div>Тип: {chat.type || "unknown"}</div>
                    <div>Статус MAX: {chat.status || "unknown"}</div>
                    <div>Подписчики/участники: {chat.participants_count ?? "не указано"}</div>
                  </div>
                  <div className="actions">
                    {bound && boundChannel ? (
                      <button className="btn secondary" onClick={() => openWorkspace(boundChannel.id)}>Открыть рабочее место</button>
                    ) : (
                      <button className="btn" disabled={!id || busy === `start-${id}`} onClick={() => run(`start-${id}`, async () => startChat(chat), "Канал добавлен в ERA.")}>
                        <CheckCircle2 size={16} /> Начать
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <p className="muted">Нажми «Найти каналы бота», чтобы увидеть MAX-чаты. Если список пустой, добавь бота администратором в канал.</p>
        )}
        {unboundChats.length ? <p className="muted">Новых каналов без рабочей области: {unboundChats.length}</p> : null}
      </section>

      <section className="panel">
        <div className="section-title">
          <div>
            <h2>3. Активные рабочие каналы</h2>
            <p className="muted">Это каналы ERA, привязанные или готовые к привязке к MAX.</p>
          </div>
          <span className="status">{activeChannels.length} активных</span>
        </div>
        <div className="post-grid">
          {activeChannels.map((channel) => {
            const platform = platformByChannel.get(channel.id);
            const draft = platform ? platformDrafts[platform.id] || platform : null;
            return (
              <article className="row-card" key={channel.id}>
                <div className="section-title">
                  <div>
                    <h3>{channel.name}</h3>
                    <p className="muted">{channel.description || "Редакционный канал ERA"}</p>
                  </div>
                  <span className={`status ${statusClass(platform?.status)}`}>{platformLabel(platform)}</span>
                </div>
                <div className="mini-log">
                  <div>Категория: {channel.category || "news"}</div>
                  <div>Постов в день: {channel.posting_frequency_per_day || channel.daily_post_limit || 1}</div>
                  <div>MAX chat_id: {platform?.external_chat_id || "не указан"}</div>
                </div>
                {platform && draft ? (
                  <>
                    <label>
                      MAX chat_id
                      <input className="input" value={draft.external_chat_id || ""} onChange={(event) => patchPlatform(platform.id, { external_chat_id: event.target.value })} />
                    </label>
                    <label>
                      Ссылка на MAX
                      <input className="input" value={draft.external_channel_url || ""} onChange={(event) => patchPlatform(platform.id, { external_channel_url: event.target.value })} />
                    </label>
                  </>
                ) : null}
                <div className="actions">
                  <button className="btn" onClick={() => openWorkspace(channel.id)} disabled={busy === `workspace-${channel.id}`}>Открыть рабочее место</button>
                  {platform ? (
                    <>
                      <button className="btn secondary" disabled={busy === `save-${platform.id}`} onClick={() => run(`save-${platform.id}`, async () => savePlatform(platform), "Настройки MAX сохранены.")}>
                        <Save size={16} /> Сохранить MAX
                      </button>
                      <SafeActionButton className="btn secondary" disabled={busy === `test-${platform.id}`} disabledReason={!tokenReady ? "Сначала сохрани MAX-токен." : !(draft?.external_chat_id || "").trim() ? "Сначала укажи MAX chat_id." : ""} onClick={() => run(`test-${platform.id}`, async () => { await savePlatform(platform); await api.testPlatformChannel(platform.id); }, "Связь с MAX-каналом проверена.")}>
                        <CheckCircle2 size={16} /> Проверить
                      </SafeActionButton>
                    </>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {workspace ? (
        <section className="panel">
          <div className="section-title">
            <div>
              <h2>Рабочее место: {workspace.channel.name}</h2>
              <p className="muted">Радар, темы и посты только этого канала.</p>
            </div>
            <span className={`status ${statusClass(workspace.platform_channel?.status)}`}>{platformLabel(workspace.platform_channel)}</span>
          </div>
          <div className="metric-grid">
            <div className="metric-card"><span>Источники</span><strong>{workspace.stats.active_sources}/{workspace.stats.sources}</strong><small>активные/все</small></div>
            <div className="metric-card"><span>Темы сегодня</span><strong>{workspace.stats.topics_today}</strong><small>всего {workspace.stats.topics}</small></div>
            <div className="metric-card"><span>Черновики</span><strong>{workspace.stats.drafts}</strong><small>нужна проверка</small></div>
            <div className="metric-card"><span>Готово</span><strong>{workspace.stats.approved}</strong><small>approved/final</small></div>
            <div className="metric-card"><span>Опубликовано</span><strong>{workspace.stats.published}</strong><small>MAX/manual</small></div>
          </div>
          <div className="panel">
            <div className="section-title">
              <div>
                <h3>Откуда собираем</h3>
                <p className="muted">{workspace.source_coverage.recommendation}</p>
              </div>
              <span className={`status ${workspace.source_coverage.status === "ok" ? "active" : "warning"}`}>{workspace.source_coverage.status}</span>
            </div>
            <div className="metric-grid">
              <div className="metric-card"><span>Привязано</span><strong>{workspace.source_coverage.total_sources}</strong><small>источников</small></div>
              <div className="metric-card"><span>Активно</span><strong>{workspace.source_coverage.active_sources}</strong><small>можно собирать</small></div>
              <div className="metric-card"><span>Ошибки</span><strong>{workspace.source_coverage.failed_sources}</strong><small>проверить health</small></div>
              <div className="metric-card"><span>Материалы сегодня</span><strong>{workspace.source_coverage.items_today}</strong><small>source items</small></div>
            </div>
            <div className="split-grid">
              <div>
                <h4>Источники канала</h4>
                {workspace.sources.length ? workspace.sources.slice(0, 8).map((source) => (
                  <div className="list-row" key={source.id}>
                    <div>
                      <strong>{source.name}</strong>
                      <p className="muted">{source.type} · {source.language || "lang?"} · {source.status} · {source.health_status || "health?"}</p>
                    </div>
                    <span className={`status ${source.last_error ? "failed" : "active"}`}>{source.last_error ? "ошибка" : "ок"}</span>
                  </div>
                )) : <p className="muted">У канала пока нет источников. Ниже можно привязать подходящие.</p>}
              </div>
              <div>
                <h4>Подходящие источники</h4>
                {workspace.suggested_sources.length ? workspace.suggested_sources.slice(0, 8).map((item) => (
                  <div className="list-row" key={item.source.id}>
                    <div>
                      <strong>{item.source.name}</strong>
                      <p className="muted">fit {Math.round(item.fit_score)} · {item.reason}</p>
                    </div>
                    <button className="btn secondary" disabled={busy === `attach-${item.source.id}`} onClick={() => run(`attach-${item.source.id}`, async () => { await api.attachSourceToChannel(workspace.channel.id, item.source.id); setWorkspace(await api.channelWorkspace(workspace.channel.id)); }, "Источник привязан к каналу.")}>
                      Привязать
                    </button>
                  </div>
                )) : <p className="muted">Нет свободных подходящих источников. Добавь их на странице источников.</p>}
              </div>
            </div>
          </div>
          <div className="actions">
            <button className="btn" disabled={busy === `refresh-${workspace.channel.id}`} onClick={() => run(`refresh-${workspace.channel.id}`, async () => { await api.refreshChannelRadar(workspace.channel.id); setWorkspace(await api.channelWorkspace(workspace.channel.id)); }, "Радар канала обновлен.")}>
              <RefreshCw size={16} /> Обновить радар канала
            </button>
          </div>

          <div className="panel">
            <div className="section-title">
              <div>
                <h3>Забрать новость по ссылке</h3>
                <p className="muted">Zero-token импорт: ERA скачает страницу, извлечет текст, создаст SourceItem/Topic и покажет тему в радаре этого канала.</p>
              </div>
              <span className="status">no LLM</span>
            </div>
            <div className="form-grid">
              <label>
                URL новости
                <input className="input" value={manualUrl} onChange={(event) => setManualUrl(event.target.value)} placeholder="https://..." />
              </label>
              <div className="actions">
                <button className="btn secondary" disabled={!manualUrl.trim() || busy === `ingest-url-${workspace.channel.id}`} onClick={() => run(`ingest-url-${workspace.channel.id}`, async () => {
                  await api.ingestUrlForChannel(workspace.channel.id, { url: manualUrl.trim() });
                  setManualUrl("");
                  setWorkspace(await api.channelWorkspace(workspace.channel.id));
                }, "Ссылка забрана. Тема появится в радаре канала, если текст удалось извлечь.")}>
                  <Sparkles size={16} /> Забрать ссылку
                </button>
              </div>
            </div>
          </div>

          <div className="split-grid">
            <div className="panel">
              <h3>Радар канала</h3>
              {workspace.radar.length ? workspace.radar.slice(0, 10).map((topic) => (
                <div className="list-row" key={topic.id}>
                  <div>
                    <strong>{topic.title}</strong>
                    <p className="muted">{topic.freshness_status || "fresh"} · score {Math.round(topic.final_score || topic.freshness_score || 0)} · {topic.source || "источник"}</p>
                  </div>
                  <button className="btn secondary" disabled={busy === `draft-${topic.id}`} onClick={() => run(`draft-${topic.id}`, async () => { await api.requestDryRun(topic.id, workspace.channel.id); setWorkspace(await api.channelWorkspace(workspace.channel.id)); }, "Генерация поста поставлена в очередь. Смотри Mission Control и Посты.")}>
                    <Sparkles size={16} /> Черновик
                  </button>
                </div>
              )) : <p className="muted">Пока нет тем для этого канала. Обнови радар или привяжи источники.</p>}
            </div>
            <div className="panel">
              <h3>Посты канала</h3>
              {workspace.posts.length ? workspace.posts.slice(0, 10).map((post) => (
                <div className="list-row" key={post.id}>
                  <div>
                    <strong>{post.title}</strong>
                    <p className="muted">post #{post.id} · {post.status} · risk {Math.round(post.risk_score || 0)} · quality {Math.round(post.quality_score || 0)}</p>
                  </div>
                  <div className="actions">
                    <button className="btn secondary" onClick={() => run(`package-${post.id}`, async () => { await api.prepareMaxPackage(post.id); setWorkspace(await api.channelWorkspace(workspace.channel.id)); }, "MAX-упаковка готова.")}>Упаковать</button>
                    <button className="btn secondary" disabled={!workspace.platform_channel?.can_publish || busy === `publish-${post.id}`} onClick={() => {
                      if (!window.confirm("Опубликовать этот пост в MAX сейчас?")) return;
                      run(`publish-${post.id}`, async () => { await api.publishPostToMax(post.id, "Опубликовано вручную из рабочего места канала."); setWorkspace(await api.channelWorkspace(workspace.channel.id)); }, "Пост опубликован в MAX.");
                    }}>
                      <Send size={16} /> MAX
                    </button>
                  </div>
                </div>
              )) : <p className="muted">Постов для этого канала пока нет.</p>}
            </div>
          </div>
        </section>
      ) : null}
    </>
  );
}
