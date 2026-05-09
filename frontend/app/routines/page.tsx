"use client";

import { FlaskConical, Play, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { SafeActionButton, Toast } from "@/components/operator";
import { api, OrgAgent, Routine, SystemSettings } from "@/lib/api";

const errorText = (error: unknown) => error instanceof Error ? error.message : "Действие не выполнено";

export default function RoutinesPage() {
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [agents, setAgents] = useState<OrgAgent[]>([]);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [drafts, setDrafts] = useState<Record<number, Partial<Routine>>>({});
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();

  const load = async () => {
    const [nextRoutines, nextAgents, nextSettings] = await Promise.all([api.routines(), api.orgAgents(), api.settings()]);
    setRoutines(nextRoutines);
    setAgents(nextAgents);
    setSettings(nextSettings);
    setDrafts(Object.fromEntries(nextRoutines.map((routine) => [routine.id, routine])));
  };

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
  }, []);

  const patchDraft = (id: number, data: Partial<Routine>) => {
    setDrafts((current) => ({ ...current, [id]: { ...current[id], ...data } }));
  };

  const save = async (routine: Routine) => {
    try {
      await api.updateRoutine(routine.id, drafts[routine.id] || routine);
      await load();
      setToast({ message: "Регламент сохранён.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const dryRun = async (routine: Routine) => {
    try {
      await api.dryRunRoutine(routine.id);
      await load();
      setToast({ message: "Dry run регламента выполнен без внешних публикаций.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const runOnce = async (routine: Routine) => {
    try {
      await api.runRoutineOnce(routine.id);
      await load();
      setToast({ message: settings?.global_routines_enabled ? "Разовый запуск поставлен в очередь." : "Запуск заблокирован: глобальные регламенты выключены.", kind: "info" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Регламенты</h1>
          <p className="page-subtitle">Автономные регламенты выключены по умолчанию. Dry run безопасен, а реальный run once заблокирован глобальным стоп-краном, пока routines не включены вручную.</p>
        </div>
      </div>
      <Toast message={toast?.message} kind={toast?.kind} />
      <section className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Регламент</th>
              <th>Владелец</th>
              <th>Cron и лимиты</th>
              <th>Следующий запуск</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {routines.map((routine) => {
              const draft = drafts[routine.id] || routine;
              const runBlocked = !settings?.global_routines_enabled ? "Глобальный переключатель регламентов выключен. Это безопасное состояние Step 2.7." : "";
              return (
                <tr key={routine.id}>
                  <td><strong>{routine.name}</strong><div className="muted">{routine.description}</div><div className="muted">{routine.task_type}</div></td>
                  <td>{agents.find((agent) => agent.id === routine.owner_agent_id)?.title || "Не назначен"}</td>
                  <td>
                    <input className="input" value={draft.cron_schedule || ""} onChange={(e) => patchDraft(routine.id, { cron_schedule: e.target.value })} />
                    <input className="input" aria-label="Максимум запусков в день" type="number" value={draft.max_runs_per_day || 1} onChange={(e) => patchDraft(routine.id, { max_runs_per_day: Number(e.target.value) })} />
                    <input className="input" aria-label="Максимальный бюджет на запуск" type="number" step="0.01" value={draft.max_budget_per_run || 0} onChange={(e) => patchDraft(routine.id, { max_budget_per_run: Number(e.target.value) })} />
                  </td>
                  <td>{routine.next_run_at ? new Date(routine.next_run_at).toLocaleString("ru-RU") : "не запланирован"}</td>
                  <td>
                    <label><input type="checkbox" checked={!!draft.enabled} onChange={(e) => patchDraft(routine.id, { enabled: e.currentTarget.checked })} /> включён локально</label>
                    <div><span className={`status ${routine.enabled ? "completed" : "paused"}`}>{routine.enabled ? "включён" : "выключен"}</span></div>
                    <div className="muted">{routine.last_run_status || "не запускался"}</div>
                  </td>
                  <td>
                    <div className="actions">
                      <button className="btn" onClick={() => save(routine)}><Save size={16} /> Сохранить</button>
                      <button className="btn secondary" onClick={() => dryRun(routine)}><FlaskConical size={16} /> Dry run</button>
                      <SafeActionButton className="btn secondary" disabledReason={runBlocked} onClick={() => runOnce(routine)}><Play size={16} /> Разово</SafeActionButton>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </>
  );
}
