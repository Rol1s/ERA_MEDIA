"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Toast } from "@/components/operator";
import { ActivityEvent, api, OrgAgent } from "@/lib/api";

const errorText = (error: unknown) => error instanceof Error ? error.message : "Действие не выполнено";

function entityLink(event: ActivityEvent) {
  if (!event.entity_id) return null;
  if (event.entity_type === "post") return <Link href="/posts">пост #{event.entity_id}</Link>;
  if (event.entity_type === "topic") return <Link href="/topics">тема #{event.entity_id}</Link>;
  if (event.entity_type === "task") return <Link href="/logs">задача #{event.entity_id}</Link>;
  if (event.entity_type === "routine") return <Link href="/routines">регламент #{event.entity_id}</Link>;
  if (event.entity_type === "issue") return <Link href="/issues">issue #{event.entity_id}</Link>;
  if (event.entity_type === "integration") return <Link href="/integrations">интеграция #{event.entity_id}</Link>;
  return <span>{event.entity_type} #{event.entity_id}</span>;
}

export default function ActivityPage() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [agents, setAgents] = useState<OrgAgent[]>([]);
  const [filters, setFilters] = useState({ eventType: "", agentId: "", entityType: "" });
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();

  const load = async () => {
    const [nextEvents, nextAgents] = await Promise.all([
      api.activity({
        eventType: filters.eventType || undefined,
        agentId: filters.agentId ? Number(filters.agentId) : undefined,
        entityType: filters.entityType || undefined
      }),
      api.orgAgents()
    ]);
    setEvents(nextEvents);
    setAgents(nextAgents);
  };

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
    const timer = setInterval(load, 10000);
    const source = new EventSource("/api/events/stream");
    source.addEventListener("activity_event_created", load);
    source.onerror = () => source.close();
    return () => {
      clearInterval(timer);
      source.close();
    };
  }, []);

  const eventTypes = useMemo(() => Array.from(new Set(events.map((event) => event.event_type))).sort(), [events]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Активность</h1>
          <p className="page-subtitle">Хронология действий людей, агентов, настроек, расходов и safety-событий. Секреты здесь не должны отображаться.</p>
        </div>
      </div>
      <Toast message={toast?.message} kind={toast?.kind} />
      <section className="panel toolbar">
        <select className="select" value={filters.eventType} onChange={(e) => setFilters({ ...filters, eventType: e.target.value })}>
          <option value="">Все события</option>
          {eventTypes.map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
        <select className="select" value={filters.agentId} onChange={(e) => setFilters({ ...filters, agentId: e.target.value })}>
          <option value="">Все агенты</option>
          {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.title}</option>)}
        </select>
        <select className="select" value={filters.entityType} onChange={(e) => setFilters({ ...filters, entityType: e.target.value })}>
          <option value="">Все сущности</option>
          <option value="post">Посты</option>
          <option value="topic">Темы</option>
          <option value="task">Задачи</option>
          <option value="issue">Issues</option>
          <option value="integration">Интеграции</option>
          <option value="routine">Регламенты</option>
          <option value="org_agent">Агенты</option>
        </select>
        <button className="btn" onClick={() => load().then(() => setToast({ message: "Фильтр применён.", kind: "success" })).catch((error) => setToast({ message: errorText(error), kind: "error" }))}>Применить</button>
      </section>
      <section className="panel">
        <div className="activity-feed">
          {events.map((event) => (
            <article className="activity-item" key={event.id}>
              <span className="status">{event.event_type}</span>
              <strong>{event.message}</strong>
              <p className="muted">{new Date(event.created_at).toLocaleString("ru-RU")} / {event.actor_type} / {entityLink(event)}</p>
            </article>
          ))}
          {!events.length ? <p className="muted">Событий по выбранному фильтру нет.</p> : null}
        </div>
      </section>
    </>
  );
}
