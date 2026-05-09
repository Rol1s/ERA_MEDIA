"use client";

import Link from "next/link";
import { Pause, Play, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { SafeActionButton, Toast, ru } from "@/components/operator";
import { api, OrgAgent } from "@/lib/api";

const errorText = (error: unknown) => error instanceof Error ? error.message : "Действие не выполнено";

function OrgNode({ agent, agents, selectedId, onSelect }: { agent: OrgAgent; agents: OrgAgent[]; selectedId?: number; onSelect: (agent: OrgAgent) => void }) {
  const children = agents.filter((item) => item.parent_agent_id === agent.id);
  return (
    <div className="org-branch">
      <button className={`org-node status-${agent.status} ${selectedId === agent.id ? "selected" : ""}`} onClick={() => onSelect(agent)}>
        <strong>{agent.title}</strong>
        <span>{agent.name}</span>
        <span className={`status ${agent.status}`}>{ru(agent.status)}</span>
        <small>{agent.responsibilities?.[0]}</small>
        <small>Расход: ${agent.daily_cost_used.toFixed(4)} / ${agent.budget_daily.toFixed(2)}</small>
      </button>
      {children.length ? <div className="org-children">{children.map((child) => <OrgNode key={child.id} agent={child} agents={agents} selectedId={selectedId} onSelect={onSelect} />)}</div> : null}
    </div>
  );
}

export default function OrgPage() {
  const [agents, setAgents] = useState<OrgAgent[]>([]);
  const [selected, setSelected] = useState<OrgAgent | null>(null);
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();

  const load = async () => {
    const items = await api.orgAgents();
    setAgents(items);
    setSelected((current) => current ? items.find((item) => item.id === current.id) || items[0] : items[0]);
  };

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
  }, []);
  const roots = useMemo(() => agents.filter((agent) => !agent.parent_agent_id), [agents]);

  const setStatus = async (agent: OrgAgent, status: string) => {
    try {
      await api.setOrgAgentStatus(agent.id, status);
      await load();
      setToast({ message: `${agent.title}: статус изменён на ${ru(status)}.`, kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Оргструктура</h1>
          <p className="page-subtitle">Кто кому подчиняется, кто проверяет работу и какие права есть у каждого агента. Publisher остаётся выключенным до этапа публикаций.</p>
        </div>
        <button className="btn secondary" onClick={() => load()}><RefreshCcw size={16} /> Обновить</button>
      </div>
      <Toast message={toast?.message} kind={toast?.kind} />
      <section className="org-layout">
        <div className="panel org-chart graph-mode">{roots.map((agent) => <OrgNode key={agent.id} agent={agent} agents={agents} selectedId={selected?.id} onSelect={setSelected} />)}</div>
        <aside className="panel org-detail">
          {selected ? (
            <>
              <h2>{selected.title}</h2>
              <p className="muted">{selected.description}</p>
              {selected.name === "publisher_agent" ? <p className="status failed">Отключён до этапа MAX publishing. Включение заблокировано backend.</p> : null}
              {selected.budget_warning ? <p className="status failed">Бюджет близко к лимиту</p> : null}
              <p><strong>Роль:</strong> {selected.role}</p>
              <p><strong>Проверяет:</strong> {selected.reviewed_by || "Human Owner"}</p>
              <p><strong>Кого курирует:</strong> {selected.supervises?.join(", ") || "никого"}</p>
              <p><strong>Бюджет в день:</strong> ${selected.daily_cost_used.toFixed(4)} / ${selected.budget_daily.toFixed(2)}</p>
              <p><strong>Токены:</strong> {selected.daily_tokens_used} / {selected.token_limit_daily}</p>
              <div className="flag-grid">
                <span className="status">{selected.can_create_tasks ? "может создавать задачи" : "не создаёт задачи"}</span>
                <span className="status">{selected.can_approve_posts ? "может одобрять" : "не одобряет"}</span>
                <span className="status">{selected.can_publish ? "может публиковать" : "не публикует"}</span>
                <span className="status">{selected.can_spend_budget ? "может тратить бюджет" : "без бюджета"}</span>
              </div>
              <h3>Ответственность</h3>
              <ul>{selected.responsibilities.map((item) => <li key={item}>{item}</li>)}</ul>
              <h3>Права</h3>
              <pre className="json-box">{JSON.stringify(selected.permissions_json, null, 2)}</pre>
              <div className="actions">
                <SafeActionButton className={selected.status === "idle" ? "btn danger" : "btn"} disabledReason={selected.name === "publisher_agent" ? "Publisher Agent нельзя включить до MAX publishing step." : ""} onClick={() => setStatus(selected, selected.status === "idle" ? "paused" : "idle")}>
                  {selected.status === "idle" ? <Pause size={16} /> : <Play size={16} />}{selected.status === "idle" ? "Пауза" : "Возобновить"}
                </SafeActionButton>
                <Link className="btn secondary" href="/agents">Открыть настройки агента</Link>
              </div>
            </>
          ) : <p className="muted">Выберите агента в структуре.</p>}
        </aside>
      </section>
    </>
  );
}
