"use client";

import Link from "next/link";
import { Check } from "lucide-react";
import { useEffect, useState } from "react";
import { SafeActionButton, Toast, ru } from "@/components/operator";
import { api, NotificationItem } from "@/lib/api";

function hrefFor(item: NotificationItem) {
  if (item.entity_type === "post") return "/posts";
  if (item.entity_type === "topic") return "/topics";
  if (item.entity_type === "integration") return "/integrations";
  if (item.entity_type === "issue") return "/issues";
  if (item.entity_type === "routine") return "/routines";
  return "/activity";
}

const errorText = (error: unknown) => error instanceof Error ? error.message : "Действие не выполнено";

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();

  const load = async () => {
    const [next, count] = await Promise.all([api.notifications(), api.unreadNotifications()]);
    setItems(next);
    setUnread(count.unread);
  };

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
    const timer = setInterval(load, 10000);
    const source = new EventSource("/api/events/stream");
    source.addEventListener("notification_count", (event) => setUnread(Number((event as MessageEvent).data || 0)));
    source.addEventListener("activity_event_created", load);
    source.onerror = () => source.close();
    return () => {
      clearInterval(timer);
      source.close();
    };
  }, []);

  const markRead = async (item: NotificationItem) => {
    try {
      await api.markNotificationRead(item.id);
      await load();
      setToast({ message: "Уведомление помечено прочитанным.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Уведомления</h1>
          <p className="page-subtitle">Review, ошибки, бюджет, интеграции и действия, где нужен человек. Непрочитано: {unread}</p>
        </div>
      </div>
      <Toast message={toast?.message} kind={toast?.kind} />
      <section className="panel">
        <div className="activity-feed">
          {items.map((item) => (
            <article className="activity-item" key={item.id}>
              <span className={`status ${item.severity}`}>{item.severity}</span>
              <strong>{item.title}</strong>
              <p>{item.message}</p>
              <p className="muted">{new Date(item.created_at).toLocaleString("ru-RU")} / {ru(item.status)} / <Link href={hrefFor(item)}>{item.entity_type} #{item.entity_id || ""}</Link></p>
              <div className="actions">
                {item.status === "unread" ? (
                  <button className="btn secondary" onClick={() => markRead(item)}><Check size={16} /> Прочитано</button>
                ) : null}
                <Link className="btn secondary" href={hrefFor(item)}>Открыть связанную сущность</Link>
                <SafeActionButton className="btn secondary" disabledReason="Архивация уведомлений пока не имеет backend endpoint. Кнопка выключена, чтобы не быть no-op.">Архивировать</SafeActionButton>
              </div>
            </article>
          ))}
          {!items.length ? <p className="muted">Уведомлений пока нет.</p> : null}
        </div>
      </section>
    </>
  );
}
