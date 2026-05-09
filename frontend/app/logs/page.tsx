"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AgentRun, api, Task } from "@/lib/api";

export default function LogsPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.tasks().then(setTasks);
    api.agentRuns().then(setRuns);
  }, []);

  const visibleRuns = useMemo(() => runs.filter((run) => !filter || run.agent_name.includes(filter) || run.task_type.includes(filter) || run.status.includes(filter)), [runs, filter]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Логи</h1>
          <p className="page-subtitle">Задачи и agent runs: статусы, ошибки, токены, стоимость и связи с темами/постами. Секреты здесь не отображаются.</p>
        </div>
        <Link className="btn secondary" href="/activity">Открыть активность</Link>
      </div>
      <section className="panel toolbar">
        <input className="input" placeholder="Фильтр по агенту, типу или статусу" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </section>
      <section className="panel table-wrap">
        <h2>Задачи</h2>
        <table>
          <thead><tr><th>ID</th><th>Тип</th><th>Статус</th><th>Попытки</th><th>Связи</th><th>Ошибка</th></tr></thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id}>
                <td>{task.id}</td>
                <td>{task.task_type}</td>
                <td><span className={`status ${task.status}`}>{task.status}</span></td>
                <td>{task.attempts}/{task.max_attempts}</td>
                <td className="muted">topic #{task.payload_json?.topic_id || "-"} / post #{task.payload_json?.post_id || "-"}</td>
                <td className="muted">{task.error_message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel table-wrap">
        <h2>Запуски агентов</h2>
        <table>
          <thead><tr><th>ID</th><th>Агент</th><th>Задача</th><th>Статус</th><th>Provider/model</th><th>Токены</th><th>Расход</th><th>Связи</th><th>Ошибка</th></tr></thead>
          <tbody>
            {visibleRuns.map((run) => (
              <tr key={run.id}>
                <td>{run.id}</td>
                <td>{run.agent_name}</td>
                <td>{run.task_type}</td>
                <td><span className={`status ${run.status}`}>{run.status}</span></td>
                <td>{run.provider || "mock"} / {run.model || "mock"}</td>
                <td>{run.tokens_input + run.tokens_output}</td>
                <td>${run.estimated_cost.toFixed(4)}</td>
                <td>topic #{run.input_json?.topic_id || run.output_json?.topic_id || "-"} / post #{run.input_json?.post_id || run.output_json?.post_id || "-"}</td>
                <td className="muted">{run.error_message}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!visibleRuns.length ? <p className="muted">Запусков по фильтру нет.</p> : null}
      </section>
    </>
  );
}
