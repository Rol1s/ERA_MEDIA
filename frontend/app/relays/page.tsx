"use client";

import { Activity, Clock, Radio, Send, Settings2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, RelayChannel } from "@/lib/api";

function formatDate(value?: string | null) {
  if (!value) return "ещё не было";
  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function runSummary(relay: RelayChannel) {
  const meta = relay.last_run?.metadata || {};
  const published = meta.published?.length || 0;
  const blocked = meta.blocked?.length || 0;
  const calls = meta.llm_calls_count || 0;
  const candidates = meta.candidate_topics_count ?? "?";
  const reason = meta.reason || "";
  if (!relay.last_run?.created_at) return "Проверок ещё не было.";
  if (published === 0 && blocked === 0 && reason) return reason;
  return `Кандидаты: ${candidates}. Опубликовано: ${published}. На ручной проверке: ${blocked}. LLM-вызовы: ${calls}.`;
}

export default function RelaysPage() {
  const [relays, setRelays] = useState<RelayChannel[]>([]);
  const [name, setName] = useState("Financial Times по-русски");
  const [chatId, setChatId] = useState("");
  const [maxUrl, setMaxUrl] = useState("");
  const [sources, setSources] = useState("https://www.ft.com/world?format=rss\nhttps://www.ft.com/markets?format=rss");
  const [limit, setLimit] = useState(5);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const stats = useMemo(() => {
    const active = relays.filter((relay) => relay.status === "active").length;
    const connected = relays.filter((relay) => relay.max.can_publish).length;
    const posts = relays.reduce((sum, relay) => sum + (relay.recent_posts?.length || 0), 0);
    return { active, connected, posts };
  }, [relays]);

  const load = () => api.relays().then(setRelays).catch((error) => setMessage(String(error.message || error)));

  useEffect(() => {
    load();
  }, []);

  const createRelay = async () => {
    setBusy(true);
    setMessage("Создаю ретранслятор...");
    try {
      await api.createRelay({
        name,
        max_chat_id: chatId,
        max_url: maxUrl,
        source_urls: sources.split("\n").map((item) => item.trim()).filter(Boolean),
        max_posts_per_day: limit,
        check_interval_minutes: 5,
        auto_publish_low_risk: false,
      });
      setMessage("Ретранслятор создан.");
      await load();
    } catch (error: any) {
      setMessage(error.message || "Ошибка создания ретранслятора");
    } finally {
      setBusy(false);
    }
  };

  const runRelay = async (id: number) => {
    setBusy(true);
    setMessage("Проверяю источники: если есть новые уникальные новости, подготовлю посты для ручной проверки.");
    try {
      const result = await api.runRelay(id, limit);
      const reason = result.reason ? ` ${result.reason}` : "";
      setMessage(`Готово: подготовлено к публикации ${result.published?.length || 0}, на ручной проверке ${result.blocked?.length || 0}, LLM-вызовов ${result.llm_calls_count || 0}.${reason}`);
      await load();
    } catch (error: any) {
      setMessage(error.message || "Ошибка запуска ретранслятора");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main>
      <div className="page-head">
        <div>
          <h1 className="page-title">Ретрансляции</h1>
          <p className="page-subtitle">
            Отдельные live-каналы: один или несколько источников → короткий русский пост → MAX. Они не засоряют общую редакционную ленту.
          </p>
        </div>
      </div>

      <section className="relay-stats">
        <div className="metric-card">
          <span>Активные</span>
          <strong>{stats.active}</strong>
          <small>проверяются по расписанию</small>
        </div>
        <div className="metric-card">
          <span>MAX подключён</span>
          <strong>{stats.connected}</strong>
          <small>можно публиковать через API</small>
        </div>
        <div className="metric-card">
          <span>Последние посты</span>
          <strong>{stats.posts}</strong>
          <small>показаны ниже для контроля</small>
        </div>
      </section>

      {message ? <div className="notice relay-notice">{message}</div> : null}

      <section className="panel relay-create">
        <div className="relay-section-title">
          <Settings2 size={20} />
          <div>
            <h2>Создать ретранслятор</h2>
            <p>Для канала вроде “Financial Times по-русски”: RSS читается каждые несколько минут, публикуются только новые low-risk материалы.</p>
          </div>
        </div>
        <div className="relay-form-grid">
          <label>
            Название
            <input className="input" value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            MAX chat_id
            <input className="input" value={chatId} onChange={(event) => setChatId(event.target.value)} placeholder="-123456789" />
          </label>
          <label>
            Ссылка на канал MAX
            <input className="input" value={maxUrl} onChange={(event) => setMaxUrl(event.target.value)} placeholder="https://max.ru/..." />
          </label>
          <label>
            Лимит в день
            <input className="input" type="number" min={1} max={30} value={limit} onChange={(event) => setLimit(Number(event.target.value || 1))} />
          </label>
        </div>
        <label className="relay-sources-field">
          RSS/URL источники, по одному на строку
          <textarea className="textarea" value={sources} onChange={(event) => setSources(event.target.value)} rows={5} />
        </label>
        <button className="btn primary" disabled={busy} onClick={createRelay}>Создать ретранслятор</button>
      </section>

      <section className="relay-list">
        {relays.map((relay) => {
          const meta = relay.last_run?.metadata || {};
          return (
            <article className="relay-card" key={relay.id}>
              <div className="relay-card-head">
                <div>
                  <div className="relay-title-line">
                    <Radio size={18} />
                    <h2>{relay.name}</h2>
                  </div>
                  <p>{relay.auto_publish_enabled ? "Автопубликация low-risk включена" : "Ручной режим"} · {relay.relay_mode} · лимит {relay.relay_max_posts_per_day || 5}/день</p>
                </div>
                <span className={`status ${relay.max.can_publish ? "completed" : "warning"}`}>{relay.max.can_publish ? "MAX подключён" : "MAX не подключён"}</span>
              </div>

              <div className="relay-run-box">
                <div>
                  <Clock size={16} />
                  <span>Последняя проверка: {formatDate(relay.last_run?.created_at)}</span>
                </div>
                <strong>{runSummary(relay)}</strong>
              </div>

              <div className="relay-source-grid">
                {relay.sources.map((source) => (
                  <div className="relay-source" key={source.id}>
                    <strong>{source.name}</strong>
                    <span>{source.url}</span>
                  </div>
                ))}
              </div>

              <div className="relay-actions">
                <button className="btn primary" disabled={busy} onClick={() => runRelay(relay.id)}>
                  <Activity size={16} /> Проверить сейчас
                </button>
                {relay.max.url ? (
                  <a className="btn secondary" href={relay.max.url} target="_blank" rel="noreferrer">
                    <Send size={16} /> Открыть канал
                  </a>
                ) : null}
              </div>

              <div className="relay-posts">
                <h3>Последние материалы</h3>
                {relay.recent_posts?.length ? (
                  relay.recent_posts.slice(0, 5).map((post) => (
                    <div className="relay-post-row" key={post.id}>
                      <span>#{post.id}</span>
                      <strong>{post.title}</strong>
                      <em>{post.status}</em>
                    </div>
                  ))
                ) : (
                  <p className="muted">Постов пока нет.</p>
                )}
              </div>

              {meta.blocked?.length ? (
                <div className="relay-blocked">
                  <h3>На ручной проверке</h3>
                  {meta.blocked.slice(0, 3).map((item: any) => (
                    <p key={`${item.topic_id}-${item.post_id || item.title}`}>{item.title}: {item.reason}</p>
                  ))}
                </div>
              ) : null}
            </article>
          );
        })}
      </section>
    </main>
  );
}
