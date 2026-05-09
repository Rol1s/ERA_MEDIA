"use client";

import Link from "next/link";
import { Pause, Play, Save, TestTube, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { AgentConfig, AgentTelemetry, api, LLMModel, OrgAgent, SecretsStatus } from "@/lib/api";
import { agentConfigFor, modelLabel, openAISecret, SafeActionButton, Toast } from "@/components/operator";

const groups = [
  { title: "Руководство", names: ["human_owner", "media_director"] },
  { title: "Разведка", names: ["intelligence_director", "world_scout_agent"] },
  { title: "Редакция", names: ["editor_in_chief", "news_editor_agent", "money_editor_agent", "ai_editor_agent", "health_editor_agent", "food_editor_agent"] },
  { title: "Качество", names: ["quality_director", "factcheck_agent", "risk_control_agent"] },
  { title: "Визуал", names: ["creative_director", "visual_agent"] },
  { title: "Дистрибуция", names: ["distribution_director", "publisher_agent"] },
  { title: "Рост", names: ["growth_director", "analytics_agent"] },
];

function dryRunReady(config?: AgentConfig | null, openaiConfigured?: boolean) {
  if (!config?.enabled) return { ok: false, reason: "конфиг выключен" };
  if (config.provider === "mock") return { ok: false, reason: "использует демо-режим" };
  if (config.provider === "openai" && !openaiConfigured) return { ok: false, reason: "OpenAI ключ не добавлен" };
  if (!config.model) return { ok: false, reason: "модель не выбрана" };
  return { ok: true, reason: "готов к dry-run" };
}

export default function AgentsPage() {
  const [telemetry, setTelemetry] = useState<AgentTelemetry[]>([]);
  const [agents, setAgents] = useState<OrgAgent[]>([]);
  const [configs, setConfigs] = useState<AgentConfig[]>([]);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [secrets, setSecrets] = useState<SecretsStatus | null>(null);
  const [drafts, setDrafts] = useState<Record<number, Partial<AgentConfig>>>({});
  const [selected, setSelected] = useState<AgentConfig | null>(null);
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");
  const [busy, setBusy] = useState("");

  const load = async () => {
    const [nextTelemetry, nextAgents, nextConfigs, nextModels, nextSecrets] = await Promise.all([
      api.agentsTelemetry(),
      api.orgAgents(),
      api.agentConfigs(),
      api.llmModels(),
      api.secretsStatus(),
    ]);
    setTelemetry(nextTelemetry);
    setAgents(nextAgents);
    setConfigs(nextConfigs);
    setModels(nextModels);
    setSecrets(nextSecrets);
    setDrafts(Object.fromEntries(nextConfigs.map((item) => [item.id, item])));
    if (selected) setSelected(nextConfigs.find((item) => item.id === selected.id) || null);
  };

  useEffect(() => {
    load().catch((error) => {
      setToast(error.message);
      setToastKind("error");
    });
  }, []);

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

  const telemetryById = useMemo(() => Object.fromEntries(telemetry.map((item) => [item.id, item])), [telemetry]);
  const openaiConfigured = openAISecret(secrets)?.status === "configured";
  const selectedDraft = selected ? drafts[selected.id] || selected : null;
  const selectedAgent = selected ? agents.find((item) => item.id === selected.org_agent_id) : null;
  const modelsForProvider = models.filter((item) => item.provider === (selectedDraft?.provider || "mock") && item.enabled);

  const patch = (id: number, data: Partial<AgentConfig>) => {
    setDrafts((current) => ({ ...current, [id]: { ...current[id], ...data } }));
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Центр управления агентами</h1>
          <p className="page-subtitle">Агенты сгруппированы по редакционной роли. Для dry-run нужны Research, Factcheck, Editor и Chief Editor на OpenAI. Publisher остается выключенным до отдельного этапа публикаций.</p>
        </div>
        <SafeActionButton
          disabledReason={openaiConfigured ? "" : "Сначала добавьте OpenAI ключ в Интеграциях."}
          disabled={busy === "bulk-openai"}
          onClick={() => run("bulk-openai", async () => { await api.configureContentAgentsOpenAI(); }, "Content agents настроены для OpenAI dry-run")}
        >
          Настроить content agents для OpenAI dry-run
        </SafeActionButton>
      </div>

      <section className="agent-groups">
        {groups.map((group) => (
          <div className="panel" key={group.title}>
            <h2>{group.title}</h2>
            <div className="agent-group-grid">
              {group.names.map((name) => {
                const agent = agents.find((item) => item.name === name);
                if (!agent) return null;
                const config = agentConfigFor(name, agents, configs);
                const tele = telemetryById[agent.id];
                const readiness = dryRunReady(config, openaiConfigured);
                const publisherDisabled = agent.name === "publisher_agent";
                return (
                  <article className="agent-card" key={agent.id}>
                    <div className="actions">
                      <span className={`status ${agent.status}`}>{agent.status}</span>
                      <span className={`status ${readiness.ok ? "completed" : "warning"}`}>{readiness.ok ? "dry-run готов" : "не готов"}</span>
                    </div>
                    <h3>{agent.title}</h3>
                    <p className="muted">{agent.role} · {agent.description}</p>
                    <div className="mini-log">
                      <div>Модель: {config ? `${config.provider} / ${modelLabel(models, config.provider, config.model)}` : "конфиг не найден"}</div>
                      <div>Причина: {publisherDisabled ? "Отключен до этапа публикаций" : readiness.reason}</div>
                      <div>Запуски сегодня: {tele?.runs_today ?? 0}</div>
                      <div>Стоимость сегодня: ${Number(tele?.cost_today || 0).toFixed(4)}</div>
                      <div>Последняя ошибка: {tele?.last_error || "нет"}</div>
                    </div>
                    <div className="actions">
                      <button className="btn secondary" disabled={!config} onClick={() => config && setSelected(config)}>Настроить</button>
                      <SafeActionButton
                        className="btn secondary"
                        disabledReason={!config ? "Конфиг не найден." : publisherDisabled ? "Publisher отключен до этапа публикаций." : ""}
                        disabled={busy === `test-${config?.id}`}
                        onClick={() => config && run(`test-${config.id}`, async () => { await api.testAgentConfig(config.id); }, "Тест агента выполнен")}
                      >
                        <TestTube size={16} /> Тест
                      </SafeActionButton>
                      <button className="btn secondary" disabled={busy === `pause-${agent.id}` || publisherDisabled} onClick={() => run(`pause-${agent.id}`, async () => {
                        if (agent.status === "paused" || agent.status === "disabled") await api.resumeOrgAgent(agent.id);
                        else await api.pauseOrgAgent(agent.id);
                      })}>
                        {agent.status === "paused" ? <Play size={16} /> : <Pause size={16} />} {agent.status === "paused" ? "Возобновить" : "Пауза"}
                      </button>
                      <Link className="btn secondary" href={`/agents/${agent.id}`}>Детали</Link>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        ))}
      </section>

      {selected && selectedDraft ? (
        <>
          <button className="drawer-backdrop" aria-label="Закрыть настройки агента" onClick={() => setSelected(null)} />
          <aside className="side-drawer">
            <div className="section-title">
              <div>
                <h2>{selectedAgent?.title || "Агент"}</h2>
                <p className="muted">Настройка модели, бюджета и лимитов для ручного dry-run.</p>
              </div>
              <button className="btn secondary" onClick={() => setSelected(null)}><X size={16} /></button>
            </div>
            <div className="form-grid compact">
              <label>Провайдер модели
                <select className="select" value={selectedDraft.provider || "mock"} onChange={(event) => patch(selected.id, { provider: event.target.value, model: event.target.value === "mock" ? "mock" : "" })}>
                  <option value="mock">демо-режим</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="gemini">Gemini</option>
                </select>
              </label>
              <label>Модель
                <select className="select" value={selectedDraft.model || ""} onChange={(event) => patch(selected.id, { model: event.target.value })}>
                  <option value="">Выберите модель</option>
                  {modelsForProvider.map((model) => <option key={model.id} value={model.model}>{model.label}</option>)}
                </select>
              </label>
              <label>Запусков в день<input data-testid="agent-max-runs" className="input" type="number" value={selectedDraft.max_runs_per_day ?? 1} onChange={(event) => patch(selected.id, { max_runs_per_day: Number(event.target.value) })} /></label>
              <label>Таймаут, сек<input className="input" type="number" value={selectedDraft.timeout_seconds ?? 30} onChange={(event) => patch(selected.id, { timeout_seconds: Number(event.target.value) })} /></label>
              <label>Бюджет, USD<input className="input" type="number" step="0.1" value={selectedDraft.daily_budget_usd ?? 0} onChange={(event) => patch(selected.id, { daily_budget_usd: Number(event.target.value) })} /></label>
              <label>Лимит токенов<input className="input" type="number" value={selectedDraft.daily_token_limit ?? 0} onChange={(event) => patch(selected.id, { daily_token_limit: Number(event.target.value) })} /></label>
            </div>
            <label>Системная инструкция<textarea className="textarea tall" value={selectedDraft.system_prompt || ""} onChange={(event) => patch(selected.id, { system_prompt: event.target.value })} /></label>
            <div className="actions">
              <button data-testid="agent-save-config" className="btn" disabled={busy === "save-config"} onClick={() => run("save-config", async () => { await api.updateAgentConfig(selected.id, selectedDraft); }, "Конфиг сохранен")}>
                <Save size={16} /> Сохранить
              </button>
              <button className="btn secondary" disabled={busy === "test-config"} onClick={() => run("test-config", async () => { await api.testAgentConfig(selected.id); }, "Тест выполнен")}>
                <TestTube size={16} /> Тест агента
              </button>
            </div>
          </aside>
        </>
      ) : null}

      <Toast message={toast} kind={toastKind} />
    </>
  );
}

