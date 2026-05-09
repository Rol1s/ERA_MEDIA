"use client";

import Link from "next/link";
import { ArrowLeft, Pause, Play, Save, TestTube } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { AgentConfig, AgentDetail, api, LLMModel, PromptTemplate } from "@/lib/api";

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const [agentId, setAgentId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [draft, setDraft] = useState<Partial<AgentConfig> | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    params.then((value) => setAgentId(Number(value.id)));
  }, [params]);

  const load = async (id = agentId) => {
    if (!id) return;
    const [nextDetail, nextModels, nextTemplates] = await Promise.all([api.agentDetail(id), api.llmModels(), api.promptTemplates()]);
    setDetail(nextDetail);
    setModels(nextModels);
    setTemplates(nextTemplates);
    setDraft(nextDetail.config || null);
  };

  useEffect(() => {
    load();
  }, [agentId]);

  const modelsForProvider = useMemo(
    () => models.filter((model) => model.provider === (draft?.provider || "mock") && model.enabled),
    [models, draft?.provider]
  );

  const patch = (data: Partial<AgentConfig>) => setDraft((current) => ({ ...(current || {}), ...data }));

  const run = async (key: string, action: () => Promise<void>) => {
    setLoading(key);
    setMessage("");
    try {
      await action();
      setMessage("Готово");
    } catch (error: any) {
      setMessage(error.message || "Ошибка");
    } finally {
      setLoading(null);
    }
  };

  if (!detail || !draft) {
    return <section className="panel">Загружаю агента...</section>;
  }

  return (
    <>
      <div className="page-head">
        <div>
          <Link href="/agents" className="btn secondary"><ArrowLeft size={16} /> Назад</Link>
          <h1 className="page-title">{detail.agent.title}</h1>
          <p className="page-subtitle">{detail.agent.name} / {detail.agent.role} / {detail.agent.status}</p>
        </div>
        <div className="actions">
          <button className={detail.agent.status === "idle" ? "btn danger" : "btn"} disabled={loading === "status"} onClick={() => run("status", async () => { await api.setOrgAgentStatus(detail.agent.id, detail.agent.status === "idle" ? "paused" : "idle"); await load(detail.agent.id); })}>
            {detail.agent.status === "idle" ? <Pause size={16} /> : <Play size={16} />}
            {detail.agent.status === "idle" ? "Пауза" : "Возобновить"}
          </button>
        </div>
      </div>

      {message ? <section className="panel">{message}</section> : null}

      <section className="stats">
        <div className="stat"><div className="stat-label">Запуски сегодня</div><div className="stat-value">{detail.telemetry?.runs_today ?? 0}</div></div>
        <div className="stat"><div className="stat-label">Success rate</div><div className="stat-value">{Math.round((detail.telemetry?.success_rate || 0) * 100)}%</div></div>
        <div className="stat"><div className="stat-label">Токены</div><div className="stat-value">{detail.budget_usage.tokens}</div></div>
        <div className="stat"><div className="stat-label">Расход</div><div className="stat-value">${Number(detail.budget_usage.cost || 0).toFixed(4)}</div></div>
      </section>

      <section className="panel">
        <h2>Готовность provider</h2>
        <div className="actions">
          <span className={detail.provider_readiness?.ready_for_mock ? "status" : "status danger"}>Mock: {detail.provider_readiness?.ready_for_mock ? "готов" : "не готов"}</span>
          <span className={detail.provider_readiness?.ready_for_dry_run ? "status" : "status danger"}>Dry-run: {detail.provider_readiness?.ready_for_dry_run ? "готов" : "не готов"}</span>
          <span className="status">{detail.provider_readiness?.provider || "mock"}/{detail.provider_readiness?.model || "mock"}</span>
        </div>
        <p className="muted">Env: {detail.provider_readiness?.required_env || "не требуется"} / {detail.provider_readiness?.env_key_present ? "найден" : "отсутствует"}</p>
        <p className="muted">{detail.provider_readiness?.reason}</p>
      </section>

      <section className="panel">
        <h2>Конфигурация агента</h2>
        <div className="form-grid">
          <label>Agent name<input className="input" value={detail.agent.name} disabled /></label>
          <label>org_agent_id<input className="input" value={detail.agent.id} disabled /></label>
          <label>Status<input className="input" value={detail.agent.status} disabled /></label>
          <label>Provider
            <select className="select" value={draft.provider || "mock"} onChange={(event) => patch({ provider: event.target.value, model: event.target.value === "mock" ? "mock" : draft.model })}>
              <option value="mock">mock</option>
              <option value="openai">openai</option>
              <option value="anthropic">anthropic</option>
              <option value="gemini">gemini</option>
              <option value="local_ollama_optional">local_ollama_optional</option>
            </select>
          </label>
          <label>Model
            <select className="select" value={draft.model || "mock"} onChange={(event) => patch({ model: event.target.value })}>
              {modelsForProvider.map((model) => <option key={model.id} value={model.model}>{model.label}</option>)}
              {!modelsForProvider.length ? <option value={draft.model || "mock"}>{draft.model || "mock"}</option> : null}
            </select>
          </label>
          <label>Temperature<input className="input" type="number" step="0.1" value={draft.temperature ?? 0.2} onChange={(event) => patch({ temperature: Number(event.target.value) })} /></label>
          <label>max_tokens<input className="input" type="number" value={draft.max_tokens ?? 800} onChange={(event) => patch({ max_tokens: Number(event.target.value) })} /></label>
          <label>prompt_template_id
            <select className="select" value={draft.prompt_template_id || ""} onChange={(event) => patch({ prompt_template_id: Number(event.target.value) || null })}>
              <option value="">auto: active template for {detail.agent.role}</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  #{template.id} {template.name} v{template.version} / {template.agent_type} / {template.status}
                </option>
              ))}
            </select>
          </label>
          <label>daily_budget_usd<input className="input" type="number" step="0.01" value={draft.daily_budget_usd ?? 0} onChange={(event) => patch({ daily_budget_usd: Number(event.target.value) })} /></label>
          <label>daily_token_limit<input className="input" type="number" value={draft.daily_token_limit ?? 0} onChange={(event) => patch({ daily_token_limit: Number(event.target.value) })} /></label>
          <label>max_runs_per_day<input data-testid="agent-max-runs" className="input" type="number" value={draft.max_runs_per_day ?? 1} onChange={(event) => patch({ max_runs_per_day: Number(event.target.value) })} /></label>
          <label>timeout_seconds<input className="input" type="number" value={draft.timeout_seconds ?? 30} onChange={(event) => patch({ timeout_seconds: Number(event.target.value) })} /></label>
        </div>
        <label className="control-line"><span>enabled</span><input type="checkbox" checked={!!draft.enabled} onChange={(event) => patch({ enabled: event.currentTarget.checked })} /></label>
        <label>system_prompt<textarea className="textarea tall" value={draft.system_prompt || ""} onChange={(event) => patch({ system_prompt: event.target.value })} /></label>
        <label>tools_json<textarea className="textarea" value={JSON.stringify(draft.tools_json || [], null, 2)} onChange={(event) => { try { patch({ tools_json: JSON.parse(event.target.value) }); } catch { undefined; } }} /></label>
        <div className="actions">
          <button data-testid="agent-save-config" className="btn" disabled={loading === "save" || !draft.id} onClick={() => run("save", async () => { await api.updateAgentConfig(draft.id!, draft); await load(detail.agent.id); })}><Save size={16} /> Сохранить</button>
          <button data-testid="agent-test-config" className="btn secondary" disabled={loading === "test" || !draft.id} onClick={() => run("test", async () => { const result = await api.testAgentConfig(draft.id!); setMessage(result.ok ? `Тест успешен: ${result.result.provider}/${result.result.model}` : result.error); await load(detail.agent.id); })}><TestTube size={16} /> Тест агента</button>
        </div>
      </section>

      <section className="panel">
        <h2>Активный prompt template</h2>
        {detail.prompt_template ? <pre className="json-box">{JSON.stringify(detail.prompt_template, null, 2)}</pre> : <p className="muted">Активный prompt template не найден.</p>}
      </section>

      <section className="panel table-wrap">
        <h2>Последние agent_runs</h2>
        <table><thead><tr><th>ID</th><th>Agent</th><th>Task</th><th>Status</th><th>Provider</th><th>Tokens</th><th>Error</th></tr></thead><tbody>
          {detail.recent_agent_runs.map((run) => <tr key={run.id}><td>{run.id}</td><td>{run.agent_name}</td><td>{run.task_type}</td><td>{run.status}</td><td>{run.provider}/{run.model}</td><td>{run.tokens_input + run.tokens_output}</td><td>{run.error_message}</td></tr>)}
        </tbody></table>
      </section>

      <section className="panel table-wrap">
        <h2>Issues и решения</h2>
        <table><thead><tr><th>Issue</th><th>Status</th><th>Result</th></tr></thead><tbody>
          {detail.recent_issues.map((issue) => <tr key={issue.id}><td>{issue.title}</td><td>{issue.status}</td><td>{issue.result_summary}</td></tr>)}
        </tbody></table>
        <div className="mini-log">{detail.recent_decision_logs.map((item) => <div key={item.id}><strong>{item.decision}</strong>: {item.reason}</div>)}</div>
      </section>

      <section className="panel">
        <h2>Активность</h2>
        <div className="activity-feed">{detail.recent_activity.map((event) => <article className="activity-item" key={event.id}><strong>{event.event_type}</strong><p>{event.message}</p></article>)}</div>
      </section>
    </>
  );
}
