"use client";

import Link from "next/link";
import { PlugZap, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { SafeActionButton, Toast, ru } from "@/components/operator";
import { api, Channel, PlatformChannel } from "@/lib/api";

const splitList = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);
const errorText = (error: unknown) => error instanceof Error ? error.message : "Действие не выполнено";

export default function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [platforms, setPlatforms] = useState<PlatformChannel[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Partial<Channel>>>({});
  const [platformDrafts, setPlatformDrafts] = useState<Record<number, Partial<PlatformChannel>>>({});
  const [active, setActive] = useState<number | null>(null);
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();

  const load = async () => {
    const [items, platformItems] = await Promise.all([api.channels(), api.platformChannels()]);
    setChannels(items);
    setPlatforms(platformItems);
    setDrafts(Object.fromEntries(items.map((channel) => [channel.id, channel])));
    setPlatformDrafts(Object.fromEntries(platformItems.map((item) => [item.id, item])));
    setActive((current) => current || items[0]?.id || null);
  };

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
  }, []);

  const patchDraft = (id: number, data: Partial<Channel>) => setDrafts((current) => ({ ...current, [id]: { ...current[id], ...data } }));
  const patchPlatform = (id: number, data: Partial<PlatformChannel>) => setPlatformDrafts((current) => ({ ...current, [id]: { ...current[id], ...data } }));

  const saveChannel = async (channel: Channel) => {
    try {
      await api.updateChannel(channel.id, drafts[channel.id] || channel);
      await load();
      setToast({ message: "Канал сохранён. Изменение записано в активность.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const savePlatform = async (platform: PlatformChannel) => {
    try {
      await api.updatePlatformChannel(platform.id, platformDrafts[platform.id] || platform);
      await load();
      setToast({ message: "MAX-настройки канала сохранены. Публикация наружу остаётся выключенной.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const testPlatform = async (platform: PlatformChannel) => {
    try {
      const result = await api.testPlatformChannel(platform.id);
      await load();
      setToast({ message: result.ok ? "Проверка MAX-связи выполнена без публикации." : "Проверка MAX-связи вернула ошибку.", kind: result.ok ? "success" : "error" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const selected = channels.find((channel) => channel.id === active) || channels[0];
  const draft = selected ? drafts[selected.id] || selected : null;
  const platform = selected ? platforms.find((item) => item.channel_id === selected.id) : null;
  const platformDraft = platform ? platformDrafts[platform.id] || platform : null;

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Каналы</h1>
          <p className="page-subtitle">Редакционные профили MVP-каналов. MAX-подключение хранится отдельно, а публичная публикация в этом шаге заблокирована.</p>
        </div>
      </div>
      <Toast message={toast?.message} kind={toast?.kind} />
      <section className="panel">
        <div className="toolbar">
          {channels.map((channel) => (
            <button key={channel.id} className={channel.id === selected?.id ? "btn" : "btn secondary"} onClick={() => setActive(channel.id)}>
              {channel.name}
            </button>
          ))}
        </div>
      </section>
      {selected && draft ? (
        <section className="review-layout">
          <article className="panel">
            <div className="section-title">
              <div>
                <h2>{selected.name}</h2>
                <p className="muted">Готовность: {draft.status === "active" ? "канал активен" : `канал ${ru(draft.status)}`}. Режим публикации: {draft.publish_mode === "manual" ? "только вручную" : draft.publish_mode}.</p>
              </div>
              <span className={`status ${draft.status}`}>{ru(draft.status)}</span>
            </div>
            <div className="form-grid">
              <label>Название<input className="input" value={draft.name || ""} onChange={(e) => patchDraft(selected.id, { name: e.target.value })} /></label>
              <label>Категория<input className="input" value={draft.category || ""} onChange={(e) => patchDraft(selected.id, { category: e.target.value })} /></label>
              <label>Частота в день<input className="input" type="number" value={draft.posting_frequency_per_day || 0} onChange={(e) => patchDraft(selected.id, { posting_frequency_per_day: Number(e.target.value) })} /></label>
              <label>Лимит постов в день<input className="input" type="number" value={draft.daily_post_limit || 0} onChange={(e) => patchDraft(selected.id, { daily_post_limit: Number(e.target.value) })} /></label>
              <label>Порог риска<input className="input" type="number" min="0" max="1" step="0.05" value={draft.risk_threshold || 0} onChange={(e) => patchDraft(selected.id, { risk_threshold: Number(e.target.value) })} /></label>
              <label>Режим публикации<select className="select" value={draft.publish_mode || "manual"} onChange={(e) => patchDraft(selected.id, { publish_mode: e.target.value as Channel["publish_mode"] })}><option value="manual">только вручную</option><option value="semi_auto">после approval</option><option value="auto">auto недоступен</option></select></label>
              <label>Статус<select className="select" value={draft.status || "active"} onChange={(e) => patchDraft(selected.id, { status: e.target.value })}><option value="active">активен</option><option value="paused">на паузе</option><option value="disabled">отключён</option></select></label>
            </div>
            <label>Описание<textarea className="textarea" value={draft.description || ""} onChange={(e) => patchDraft(selected.id, { description: e.target.value })} /></label>
            <label>Тональность<textarea className="textarea" value={draft.tone_of_voice || ""} onChange={(e) => patchDraft(selected.id, { tone_of_voice: e.target.value })} /></label>
            <label>Аудитория<textarea className="textarea" value={draft.audience_description || ""} onChange={(e) => patchDraft(selected.id, { audience_description: e.target.value })} /></label>
            <label>Разрешённые темы<input className="input" value={(draft.topics_allowed || []).join(", ")} onChange={(e) => patchDraft(selected.id, { topics_allowed: splitList(e.target.value) })} /></label>
            <label>Запрещённые темы<input className="input" value={(draft.topics_forbidden || []).join(", ")} onChange={(e) => patchDraft(selected.id, { topics_forbidden: splitList(e.target.value) })} /></label>
            <div className="actions">
              <button className="btn" onClick={() => saveChannel(selected)}><Save size={16} /> Сохранить правила</button>
              <Link className="btn secondary" href={`/topics`}>Темы канала</Link>
              <Link className="btn secondary" href={`/posts`}>Посты канала</Link>
              <Link className="btn secondary" href={`/issues`}>Задачи канала</Link>
            </div>
          </article>
          <aside className="panel">
            <h2>MAX-подключение</h2>
            <p className="muted">Здесь можно проверить привязку, но публичная публикация в MAX остаётся выключенной.</p>
            {platform && platformDraft ? (
              <>
                <div className="actions"><span className={`status ${platform.status}`}>{ru(platform.status)}</span><span className="status">{platform.publish_mode}</span></div>
                <label>MAX chat_id / channel_id<input className="input" value={platformDraft.external_chat_id || ""} onChange={(e) => patchPlatform(platform.id, { external_chat_id: e.target.value })} /></label>
                <label>URL канала<input className="input" value={platformDraft.external_channel_url || ""} onChange={(e) => patchPlatform(platform.id, { external_channel_url: e.target.value })} /></label>
                <label>Режим подготовки<select className="select" value={platformDraft.publish_mode || "manual_copy"} onChange={(e) => patchPlatform(platform.id, { publish_mode: e.target.value as PlatformChannel["publish_mode"] })}><option value="manual_copy">ручное копирование</option><option value="semi_auto_approval">после approval, без автопубликации</option><option value="auto_publish">auto недоступен</option></select></label>
                {platform.last_error ? <p className="muted">Последняя ошибка: {platform.last_error}</p> : null}
                <div className="actions">
                  <button className="btn secondary" onClick={() => savePlatform(platform)}><Save size={16} /> Сохранить MAX</button>
                  <button className="btn secondary" onClick={() => testPlatform(platform)}><PlugZap size={16} /> Проверить связь</button>
                  <SafeActionButton className="btn secondary" disabledReason="Публичная публикация MAX не реализуется в Step 2.7.">Запустить публикацию</SafeActionButton>
                </div>
              </>
            ) : <p className="muted">Для канала ещё нет platform channel записи.</p>}
          </aside>
        </section>
      ) : <section className="panel muted">Каналы не загружены.</section>}
    </>
  );
}
