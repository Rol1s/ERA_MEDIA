"use client";

import { useEffect, useState } from "react";
import { SafeActionButton, ru } from "@/components/operator";
import { api, Goal, OrgAgent } from "@/lib/api";

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [agents, setAgents] = useState<OrgAgent[]>([]);

  useEffect(() => {
    Promise.all([api.goals(), api.orgAgents()]).then(([nextGoals, nextAgents]) => {
      setGoals(nextGoals);
      setAgents(nextAgents);
    });
  }, []);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Цели</h1>
          <p className="page-subtitle">Операционные цели CEO loop: выпуск, качество, риск, расходы и поиск тем. В этом шаге цели читаются агентами, но редактирование целей пока закрыто.</p>
        </div>
        <SafeActionButton className="btn secondary" disabledReason="Создание и редактирование целей будет отдельным небольшим шагом. Сейчас цели используются CEO loop как read-only ориентиры.">Создать цель</SafeActionButton>
      </div>
      <section className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Цель</th>
              <th>Владелец</th>
              <th>Метрика</th>
              <th>Прогресс</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {goals.map((goal) => {
              const pct = goal.target_value ? Math.min(100, Math.round((goal.current_value / goal.target_value) * 100)) : 0;
              return (
                <tr key={goal.id}>
                  <td><strong>{goal.title}</strong><div className="muted">{goal.description}</div></td>
                  <td>{agents.find((agent) => agent.id === goal.owner_agent_id)?.title || "Не назначен"}</td>
                  <td>{goal.target_metric}</td>
                  <td>{goal.current_value} / {goal.target_value}<div className="progress"><span style={{ width: `${pct}%` }} /></div></td>
                  <td><span className={`status ${goal.status}`}>{ru(goal.status)}</span></td>
                  <td>
                    <div className="actions">
                      <SafeActionButton className="btn secondary" disabledReason="Backend endpoint для ручного обновления цели пока не реализован. Кнопка намеренно выключена, чтобы не создавать no-op.">Обновить прогресс</SafeActionButton>
                      <SafeActionButton className="btn secondary" disabledReason="Pause/achieve/fail для целей пока read-only.">Изменить статус</SafeActionButton>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!goals.length ? <p className="muted">Целей пока нет. CEO loop может работать, но без явных целевых ориентиров.</p> : null}
      </section>
    </>
  );
}
