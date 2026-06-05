"use client";

import Link from "next/link";
import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, NewsroomSubmission } from "@/lib/api";
import { Toast } from "@/components/operator";

function ruDate(value?: string | null) {
  if (!value) return "нет";
  return new Date(value).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function SubmissionsPage() {
  const [items, setItems] = useState<NewsroomSubmission[]>([]);
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");

  const load = async () => setItems(await api.submissions());

  useEffect(() => {
    load().catch((error) => {
      setToast(error.message);
      setToastKind("error");
    });
  }, []);

  const run = async (label: string, action: () => Promise<void>, success: string) => {
    setBusy(label);
    setToast("");
    try {
      await action();
      setToast(success);
      setToastKind("success");
      await load();
    } catch (error: any) {
      setToast(error.message || "Действие не выполнено");
      setToastKind("error");
    } finally {
      setBusy("");
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Предложенные новости</h1>
          <p className="page-subtitle">Очередь материалов от аудитории. Сотрудник может превратить предложку в тему или отклонить.</p>
        </div>
        <Link className="btn secondary" href="/director">Редактор дня</Link>
      </div>

      <section className="panel">
        <div className="card-grid">
          {items.map((item) => (
            <article className="topic-card" key={item.id}>
              <span className={`status ${item.status}`}>#{item.id} · {item.status}</span>
              <h3>{item.text.split("\n")[0] || item.url || "Без текста"}</h3>
              <p>{item.text || "Текст не передан"}</p>
              {item.url ? <p><a href={item.url} target="_blank" rel="noreferrer">{item.url}</a></p> : null}
              <small>источник: {item.source} · автор: {item.submitter_name || item.submitter_chat_id || "неизвестно"} · {ruDate(item.created_at)}</small>
              <div className="actions">
                {item.topic_id ? <Link className="btn secondary" href={`/topics?topic_id=${item.topic_id}#topic-${item.topic_id}`}>Открыть тему</Link> : null}
                <button className="btn" disabled={item.status !== "new" || busy === `topic-${item.id}`} onClick={() => run(`topic-${item.id}`, async () => { await api.createSubmissionTopic(item.id); }, "Тема создана")}>
                  <Check size={16} /> Создать тему
                </button>
                <button className="btn danger" disabled={item.status !== "new" || busy === `reject-${item.id}`} onClick={() => run(`reject-${item.id}`, async () => { await api.rejectSubmission(item.id, "Не подходит для выпуска"); }, "Предложка отклонена")}>
                  <X size={16} /> Отклонить
                </button>
              </div>
            </article>
          ))}
          {!items.length ? <p className="muted">Предложек пока нет.</p> : null}
        </div>
      </section>
      <Toast message={toast} kind={toastKind} />
    </>
  );
}
