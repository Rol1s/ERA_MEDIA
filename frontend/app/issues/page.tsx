"use client";

import { CheckCircle, GitBranch, PauseCircle, Save, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, Issue, IssueDetail, OrgAgent } from "@/lib/api";
import { Toast } from "@/components/operator";

const columns = [
  { key: "backlog", title: "Бэклог" },
  { key: "ready", title: "Готово к работе" },
  { key: "in_progress", title: "В работе" },
  { key: "review", title: "На проверке" },
  { key: "waiting_human", title: "Ждет человека" },
  { key: "completed", title: "Завершено" },
  { key: "failed", title: "Ошибка" },
];

const moves: Record<string, string[]> = {
  backlog: ["ready", "cancelled"],
  ready: ["in_progress", "cancelled"],
  in_progress: ["review", "waiting_human", "failed", "cancelled"],
  review: ["waiting_human", "completed", "failed", "cancelled"],
  waiting_human: ["in_progress", "completed", "cancelled"],
  completed: [],
  failed: [],
  cancelled: [],
};

const statusLabel: Record<string, string> = {
  backlog: "в бэклог",
  ready: "готово",
  in_progress: "в работу",
  review: "на проверку",
  waiting_human: "ждет человека",
  completed: "завершить",
  failed: "ошибка",
  cancelled: "отменить",
};

const progressText = (issue: Issue) => {
  if (!issue.target_metric) return "цель не задана";
  if (issue.target_value <= 0) return `${issue.target_metric}: все`;
  return `${issue.target_metric}: ${issue.current_value}/${issue.target_value}`;
};

export default function IssuesPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [agents, setAgents] = useState<OrgAgent[]>([]);
  const [selected, setSelected] = useState<Issue | null>(null);
  const [detail, setDetail] = useState<IssueDetail | null>(null);
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");
  const [busy, setBusy] = useState("");

  const load = async () => {
    const [nextIssues, nextAgents] = await Promise.all([api.issues(), api.orgAgents()]);
    setIssues(nextIssues);
    setAgents(nextAgents);
  };

  useEffect(() => {
    load().catch((error) => {
      setToast(error.message);
      setToastKind("error");
    });
  }, []);

  const byColumn = useMemo(() => {
    const grouped: Record<string, Issue[]> = Object.fromEntries(columns.map((item) => [item.key, []]));
    for (const issue of issues) {
      const key = issue.status === "cancelled" ? "failed" : issue.status;
      (grouped[key] || grouped.backlog).push(issue);
    }
    return grouped;
  }, [issues]);

  const agentTitle = (id?: number | null) => agents.find((agent) => agent.id === id)?.title || "не назначен";

  const run = async (label: string, action: () => Promise<void>, success = "Готово") => {
    setBusy(label);
    setToast("");
    try {
      await action();
      setToast(success);
      setToastKind("success");
      await load();
    } catch (error: any) {
      setToast(error.message || "Не удалось выполнить действие");
      setToastKind("error");
    } finally {
      setBusy("");
    }
  };

  const openIssue = async (issue: Issue) => {
    const nextDetail = await api.issueDetail(issue.id);
    setSelected(nextDetail.issue);
    setDetail(nextDetail);
  };

  const moveIssue = async (issue: Issue, status: string) => {
    await api.updateIssue(issue.id, { status });
    if (selected?.id === issue.id) await openIssue({ ...issue, status });
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Операционный Kanban</h1>
          <p className="page-subtitle">Карточки показывают владельца, проверяющего, следующий шаг, блокировку и связанный пост или тему. Недопустимые переходы блокируются backend state machine.</p>
        </div>
      </div>

      <section className="kanban">
        {columns.map((column) => (
          <div className="kanban-column" key={column.key}>
            <h3>{column.title}</h3>
            {(byColumn[column.key] || []).map((issue) => (
              <article className="kanban-card" key={issue.id}>
                <div className="actions">
                  <span className="status">{issue.issue_type}</span>
                  <span className={`status ${issue.priority}`}>{issue.priority}</span>
                  {issue.blocked_reason ? <span className="status warning">заблокировано</span> : null}
                </div>
                <strong>{issue.title}</strong>
                <p className="muted">{issue.result_summary || issue.description}</p>
                <p className="muted">Владелец: {agentTitle(issue.owner_agent_id)}</p>
                <p className="muted">Проверяет: {agentTitle(issue.reviewer_agent_id)}</p>
                <p className="muted">Связано: тема {issue.related_topic_id || "-"} · пост {issue.related_post_id || "-"}</p>
                <p className="muted">{progressText(issue)}</p>
                <p><strong>Следующее действие:</strong> {issue.next_action || "не задано"}</p>
                {issue.blocked_reason ? <p><strong>Почему стоит:</strong> {issue.blocked_reason}</p> : null}
                {issue.required_human_action ? <p><strong>Нужно от человека:</strong> {issue.required_human_action}</p> : null}
                {issue.sub_issue_count ? <p className="muted">Подзадачи: {issue.sub_issue_count}</p> : null}
                <div className="actions">
                  <button className="btn secondary" data-testid={`issue-open-${issue.id}`} onClick={() => openIssue(issue)}>Открыть</button>
                  {(moves[issue.status] || []).slice(0, 3).map((status) => (
                    <button key={status} data-testid={`issue-move-${issue.id}-${status}`} className="btn secondary" disabled={busy === `${issue.id}-${status}`} onClick={() => run(`${issue.id}-${status}`, async () => moveIssue(issue, status), "Статус обновлен")}>{statusLabel[status] || status}</button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ))}
      </section>

      {selected ? (
        <section className="panel">
          <div className="page-head">
            <div>
              <h2>{selected.title}</h2>
              <p className="muted">{selected.description}</p>
            </div>
            <span className={`status ${selected.status}`}>{statusLabel[selected.status] || selected.status}</span>
          </div>
          <div className="form-grid compact">
            <label>Владелец
              <select className="select" value={selected.owner_agent_id || ""} onChange={(event) => setSelected({ ...selected, owner_agent_id: Number(event.target.value) || null })}>
                <option value="">не назначен</option>
                {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.title}</option>)}
              </select>
            </label>
            <label>Проверяющий
              <select className="select" value={selected.reviewer_agent_id || ""} onChange={(event) => setSelected({ ...selected, reviewer_agent_id: Number(event.target.value) || null })}>
                <option value="">не назначен</option>
                {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.title}</option>)}
              </select>
            </label>
            <label>Приоритет
              <select className="select" value={selected.priority} onChange={(event) => setSelected({ ...selected, priority: event.target.value })}>
                <option value="low">низкий</option><option value="normal">обычный</option><option value="high">высокий</option><option value="urgent">срочный</option>
              </select>
            </label>
          </div>
          <label>Следующее действие<textarea className="textarea" value={selected.next_action || ""} onChange={(event) => setSelected({ ...selected, next_action: event.target.value })} /></label>
          <label>Причина блокировки<textarea className="textarea" value={selected.blocked_reason || ""} onChange={(event) => setSelected({ ...selected, blocked_reason: event.target.value })} /></label>
          <label>Что нужно сделать человеку<textarea className="textarea" value={selected.required_human_action || ""} onChange={(event) => setSelected({ ...selected, required_human_action: event.target.value })} /></label>
          <label>Итог работы<textarea className="textarea" value={selected.result_summary || ""} onChange={(event) => setSelected({ ...selected, result_summary: event.target.value })} /></label>
          <div className="actions">
            <button className="btn" onClick={() => run("save-issue", async () => { await api.updateIssue(selected.id, selected); await openIssue(selected); }, "Задача сохранена")}><Save size={16} /> Сохранить</button>
            <button className="btn secondary" onClick={() => run("sub-issue", async () => { await api.createSubIssue(selected.id, { title: `Подзадача для #${selected.id}`, description: "Ручная делегация", issue_type: selected.issue_type, owner_agent_id: selected.owner_agent_id, reviewer_agent_id: selected.reviewer_agent_id }); await openIssue(selected); }, "Подзадача создана")}><GitBranch size={16} /> Создать подзадачу</button>
            <button className="btn secondary" onClick={() => run("waiting-human", async () => moveIssue(selected, "waiting_human"))}><PauseCircle size={16} /> Ждет человека</button>
            <button className="btn secondary" onClick={() => run("complete", async () => moveIssue(selected, "completed"))}><CheckCircle size={16} /> Завершить</button>
            <button className="btn danger" onClick={() => run("cancel", async () => moveIssue(selected, "cancelled"))}><XCircle size={16} /> Отменить</button>
          </div>
          <h3>Допустимые переходы</h3>
          <div className="actions">
            {(detail?.allowed_transitions || moves[selected.status] || []).map((status) => (
              <button key={status} className="btn secondary" onClick={() => run(`detail-${status}`, async () => moveIssue(selected, status))}>{statusLabel[status] || status}</button>
            ))}
          </div>
          <h3>Дерево задач</h3>
          {detail?.parent ? <div className="mini-log">Parent: #{detail.parent.id} {detail.parent.title}</div> : null}
          {detail?.sub_issues.length ? detail.sub_issues.map((child) => <div key={child.id} className="mini-log">#{child.id} {child.title} <span className={`status ${child.status}`}>{statusLabel[child.status] || child.status}</span> / {progressText(child)}</div>) : <p className="muted">Подзадач пока нет.</p>}
          <h3>Решения и активность</h3>
          {detail?.decision_logs.length ? <div className="mini-log">{detail.decision_logs.map((decision) => <div key={decision.id}><strong>{decision.decision}</strong>: {decision.reason}</div>)}</div> : <p className="muted">Decision logs пока нет.</p>}
          {detail?.activity.length ? <div className="mini-log">{detail.activity.map((event) => <div key={event.id}><strong>{event.event_type}</strong>: {event.message}</div>)}</div> : null}
        </section>
      ) : null}

      <Toast message={toast} kind={toastKind} />
    </>
  );
}

