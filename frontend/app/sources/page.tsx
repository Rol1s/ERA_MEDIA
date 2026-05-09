"use client";

import Link from "next/link";
import { Activity, DownloadCloud, Plus, Save, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Toast } from "@/components/operator";
import { api, Channel, Source } from "@/lib/api";

const errorText = (error: unknown) => error instanceof Error ? error.message : "Действие не выполнено";

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Partial<Source>>>({});
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();
  const [fetchResult, setFetchResult] = useState<Record<string, any> | null>(null);
  const [form, setForm] = useState({ name: "", url: "", type: "rss", language: "ru", trust_score: 0.7, channel_ids: [] as number[] });

  const load = async () => {
    const [nextSources, nextChannels] = await Promise.all([api.sources(), api.channels()]);
    setSources(nextSources);
    setChannels(nextChannels);
    setDrafts(Object.fromEntries(nextSources.map((source) => [source.id, source])));
  };

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.name.trim() || !form.url.trim()) {
      setToast({ message: "Укажите название и URL источника.", kind: "error" });
      return;
    }
    try {
      await api.createSource({ ...form, status: "active", requires_review: true });
      setForm({ name: "", url: "", type: "rss", language: "ru", trust_score: 0.7, channel_ids: [] });
      await load();
      setToast({ message: "Источник добавлен.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const patchDraft = (id: number, data: Partial<Source>) => {
    setDrafts((current) => ({ ...current, [id]: { ...current[id], ...data } }));
  };

  const toggleChannel = (source: Source, channelId: number) => {
    const current = drafts[source.id]?.channel_ids || [];
    const next = current.includes(channelId) ? current.filter((id) => id !== channelId) : [...current, channelId];
    patchDraft(source.id, { channel_ids: next });
  };

  const saveSource = async (source: Source) => {
    const draft = drafts[source.id] || source;
    if (!String(draft.url || "").trim()) {
      setToast({ message: "Источник без URL нельзя сохранить: pipeline должен понимать, откуда взята тема.", kind: "error" });
      return;
    }
    try {
      await api.updateSource(source.id, draft);
      await load();
      setToast({ message: "Источник сохранён. Событие записано в активность.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const healthCheck = async (source: Source) => {
    try {
      await api.healthCheckSource(source.id);
      await load();
      setToast({ message: "Проверка источника выполнена.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const fetchSource = async (source: Source) => {
    try {
      const result = await api.fetchSource(source.id, source.type === "rss" ? 5 : 1);
      setFetchResult(result.result);
      await load();
      setToast({ message: `Сбор завершён: найдено ${result.result.fetched_count}, тем создано ${result.result.topics_created}, дублей ${result.result.duplicates}.`, kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const deleteSource = async (source: Source) => {
    if (!window.confirm(`Удалить источник "${source.name}"? Связанные посты и темы не удаляются.`)) return;
    try {
      await api.deleteSource(source.id);
      await load();
      setToast({ message: "Источник удалён.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Источники</h1>
          <p className="page-subtitle">Разрешённые источники для тем. Неактивные и отключённые источники не должны использоваться в сборе и pipeline.</p>
        </div>
      </div>
      <Toast message={toast?.message} kind={toast?.kind} />
      <section className="panel">
        <h2>Добавить источник</h2>
        <p className="muted">Источник используется для анализа и краткого пересказа с добавленной ценностью. Не публикуйте большие фрагменты чужого текста.</p>
        <form className="form-grid" onSubmit={submit}>
          <input className="input" placeholder="Название" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="input" placeholder="RSS или URL" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
          <select className="select" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} aria-label="Тип источника">
            <option value="rss">RSS</option>
            <option value="website">Сайт</option>
            <option value="manual_url">Ручной URL</option>
            <option value="api_placeholder">API placeholder</option>
            <option value="ladder_optional">Ladder optional</option>
          </select>
          <input className="input" aria-label="Доверие" type="number" min="0" max="1" step="0.05" value={form.trust_score} onChange={(e) => setForm({ ...form, trust_score: Number(e.target.value) })} />
          <button className="btn" type="submit" disabled={!form.name.trim() || !form.url.trim()} title={!form.name.trim() || !form.url.trim() ? "Укажите название и URL." : undefined}>
            <Plus size={16} /> Добавить источник
          </button>
        </form>
      </section>
      {fetchResult ? (
        <section className="panel">
          <h2>Результат последнего сбора</h2>
          <div className="metric-grid">
            <div className="metric-card"><span>Найдено</span><strong>{fetchResult.fetched_count}</strong></div>
            <div className="metric-card"><span>Извлечено</span><strong>{fetchResult.extracted_count}</strong></div>
            <div className="metric-card"><span>Тем создано</span><strong>{fetchResult.topics_created}</strong></div>
            <div className="metric-card"><span>Дубли</span><strong>{fetchResult.duplicates}</strong></div>
            <div className="metric-card"><span>Блокировано</span><strong>{fetchResult.blocked}</strong></div>
            <div className="metric-card"><span>Ошибки</span><strong>{fetchResult.failed}</strong></div>
          </div>
          {fetchResult.last_error ? <p className="muted">Ошибка: {fetchResult.last_error}</p> : null}
          <Link className="btn secondary" href="/source-items">Открыть материалы</Link>
        </section>
      ) : null}
      <section className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Источник</th>
              <th>Каналы</th>
              <th>Тип и доверие</th>
              <th>Проверка</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => {
              const draft = drafts[source.id] || source;
              return (
                <tr key={source.id}>
                  <td>
                    <input className="input" value={draft.name || ""} onChange={(e) => patchDraft(source.id, { name: e.target.value })} />
                    <input className="input" value={draft.url || ""} onChange={(e) => patchDraft(source.id, { url: e.target.value })} />
                    {source.is_demo ? <span className="status">demo</span> : null}
                    {source.last_error ? <div className="muted">Ошибка: {source.last_error}</div> : null}
                  </td>
                  <td>
                    <div className="check-list">
                      {channels.map((channel) => (
                        <label key={channel.id}>
                          <input type="checkbox" checked={(draft.channel_ids || []).includes(channel.id)} onChange={() => toggleChannel(source, channel.id)} />
                          {channel.name}
                        </label>
                      ))}
                    </div>
                  </td>
                  <td>
                    <select className="select" value={draft.type || "rss"} onChange={(e) => patchDraft(source.id, { type: e.target.value })}>
                      <option value="rss">RSS</option>
                      <option value="website">Сайт</option>
                      <option value="manual_url">Ручной URL</option>
                      <option value="api_placeholder">API placeholder</option>
                      <option value="ladder_optional">Ladder optional</option>
                    </select>
                    <input className="input" type="number" min="0" max="1" step="0.05" value={draft.trust_score || 0} onChange={(e) => patchDraft(source.id, { trust_score: Number(e.target.value) })} />
                    <label><input type="checkbox" checked={!!draft.requires_review} onChange={(e) => patchDraft(source.id, { requires_review: e.currentTarget.checked })} /> Требует проверки</label>
                  </td>
                  <td>
                    <span className={`status ${source.health_status}`}>{source.health_status || "не проверялся"}</span>
                    <div className="muted">{source.last_checked_at ? new Date(source.last_checked_at).toLocaleString("ru-RU") : "ещё не проверялся"}</div>
                    <div className="muted">Материалы: {source.items_count || 0}, валидные: {source.valid_items_count || 0}, дубли: {source.duplicate_items_count || 0}, ошибки: {source.failed_items_count || 0}</div>
                    {draft.type === "ladder_optional" ? <div className="muted">Ladder только для открытого публичного контента. Нельзя использовать для обхода платного или закрытого доступа.</div> : null}
                  </td>
                  <td>
                    <select className="select" value={draft.status || "active"} onChange={(e) => patchDraft(source.id, { status: e.target.value })}>
                      <option value="active">активен</option>
                      <option value="paused">на паузе</option>
                      <option value="disabled">отключён</option>
                    </select>
                  </td>
                  <td>
                    <div className="actions">
                      <button className="btn" onClick={() => saveSource(source)}><Save size={16} /> Сохранить</button>
                      <button className="btn secondary" onClick={() => fetchSource(source)} disabled={source.status !== "active" || source.type === "ladder_optional"} title={source.type === "ladder_optional" ? "Ladder отключён по умолчанию и не используется для обхода ограничений." : undefined}><DownloadCloud size={16} /> Fetch now</button>
                      <button className="btn secondary" onClick={() => healthCheck(source)}><Activity size={16} /> Проверить</button>
                      <Link className="btn secondary" href={`/source-items?source_id=${source.id}`}>Материалы</Link>
                      <button className="btn danger" onClick={() => deleteSource(source)}><Trash2 size={16} /> Удалить</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!sources.length ? <p className="muted">Источников пока нет. Добавьте первый источник с URL.</p> : null}
      </section>
    </>
  );
}
