"use client";

import Link from "next/link";
import { FilePlus2, RefreshCw, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, Source, SourceItem } from "@/lib/api";
import { Toast } from "@/components/operator";

const statusText: Record<string, string> = {
  fetched: "получено",
  extracted: "извлечено",
  too_short: "слишком коротко",
  blocked: "закрыто/блок",
  failed: "ошибка",
  duplicate: "дубль",
  rejected: "отклонено",
};

export default function SourceItemsPage() {
  const [items, setItems] = useState<SourceItem[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [status, setStatus] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [language, setLanguage] = useState("");
  const [special, setSpecial] = useState("");
  const [openText, setOpenText] = useState<number | null>(null);
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");

  const load = async () => {
    const params = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
    const initialSourceId = params.get("source_id") || sourceId;
    if (initialSourceId && initialSourceId !== sourceId) setSourceId(initialSourceId);
    const [nextItems, nextSources] = await Promise.all([
      api.sourceItems({
        sourceId: initialSourceId ? Number(initialSourceId) : undefined,
        status: status || undefined,
        language: language || undefined,
        duplicate: special === "duplicate" ? true : undefined,
        blocked: special === "blocked" ? true : undefined,
      }),
      api.sources(),
    ]);
    setItems(nextItems);
    setSources(nextSources);
  };

  useEffect(() => {
    load().catch((error) => {
      setToast(error.message);
      setToastKind("error");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, sourceId, language, special]);

  const run = async (action: () => Promise<void>, success: string) => {
    try {
      await action();
      setToast(success);
      setToastKind("success");
      await load();
    } catch (error: any) {
      setToast(error.message || "Действие не выполнено");
      setToastKind("error");
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Материалы источников</h1>
          <p className="page-subtitle">Здесь видно, что система реально получила, извлекла, заблокировала как paywall/login или пометила дублем.</p>
        </div>
      </div>
      <section className="panel">
        <p className="muted">Источник используется для анализа и краткого пересказа с добавленной ценностью. Не публикуйте большие фрагменты чужого текста.</p>
        <div className="actions">
          <select className="select" value={sourceId} onChange={(event) => setSourceId(event.target.value)}>
            <option value="">Все источники</option>
            {sources.map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}
          </select>
          <select className="select" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Все статусы</option>
            {Object.entries(statusText).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
          <select className="select" value={language} onChange={(event) => setLanguage(event.target.value)}>
            <option value="">Любой язык</option>
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
          <select className="select" value={special} onChange={(event) => setSpecial(event.target.value)}>
            <option value="">Все материалы</option>
            <option value="duplicate">Только дубли</option>
            <option value="blocked">Только закрытые/blocked</option>
          </select>
        </div>
      </section>

      <section className="post-grid">
        {items.map((item) => {
          const source = sources.find((entry) => entry.id === item.source_id);
          return (
            <article className="row-card" key={item.id}>
              <div className="actions">
                <span className={`status ${item.extraction_status}`}>{statusText[item.extraction_status] || item.extraction_status}</span>
                <span className={item.paywall_or_blocked_detected ? "status danger" : "status completed"}>{item.paywall_or_blocked_detected ? "paywall/login detected" : "открытый материал"}</span>
                {item.duplicate_of_item_id ? <span className="status warning">дубль #{item.duplicate_of_item_id}</span> : null}
                {item.linked_topic_id ? <span className="status completed">topic #{item.linked_topic_id}</span> : null}
              </div>
              <h3>{item.title || "Без заголовка"}</h3>
              <p>{item.extracted_summary || item.summary || "Описание не извлечено."}</p>
              <div className="mini-log">
                <div>Источник: {source?.name || `#${item.source_id}`}</div>
                <div>URL: <a href={item.url} target="_blank" rel="noreferrer">{item.canonical_url || item.url}</a></div>
                <div>Дата источника: {item.published_at ? new Date(item.published_at).toLocaleString("ru-RU") : "не найдена"}</div>
                <div>Язык: {item.language || "не определён"} / длина: {item.content_length}</div>
                {item.extraction_error ? <div>Причина: {item.extraction_error}</div> : null}
              </div>
              <div className="actions">
                <button className="btn secondary" onClick={() => setOpenText(openText === item.id ? null : item.id)}>Текст</button>
                <button className="btn secondary" disabled={!!item.linked_topic_id || item.extraction_status === "duplicate" || item.paywall_or_blocked_detected} onClick={() => run(async () => { await api.createTopicFromSourceItem(item.id); }, "Тема создана")} title={item.paywall_or_blocked_detected ? "Закрытые/paywall материалы не используются для тем." : undefined}><FilePlus2 size={16} /> Создать тему</button>
                <button className="btn secondary" onClick={() => run(async () => { await api.refetchSourceItem(item.id); }, "Источник перечитан")}><RefreshCw size={16} /> Refetch</button>
                <button className="btn danger" onClick={() => run(async () => { await api.rejectSourceItem(item.id); }, "Материал отклонён")}><X size={16} /> Отклонить</button>
                {item.linked_topic_id ? <Link className="btn secondary" href="/topics">Открыть темы</Link> : null}
              </div>
              {openText === item.id ? <pre className="json-box">{item.extracted_text}</pre> : null}
            </article>
          );
        })}
        {!items.length ? <div className="panel">Материалов пока нет. Откройте “Источники” и нажмите Fetch now у публичного RSS или URL.</div> : null}
      </section>
      <Toast message={toast} kind={toastKind} />
    </>
  );
}
