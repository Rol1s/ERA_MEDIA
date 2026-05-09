"use client";

import { CheckCircle2, PlugZap, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, AgentConfig, Integration, LLMModel, OrgAgent, SecretStatus, SecretsStatus, SystemSettings } from "@/lib/api";
import { modelLabel, SafeActionButton, SystemReadinessPanel, Toast } from "@/components/operator";

const providers = [
  { key: "openai", name: "OpenAI", secret: "OPENAI_API_KEY", primary: true },
  { key: "anthropic", name: "Anthropic", secret: "ANTHROPIC_API_KEY", primary: false },
  { key: "gemini", name: "Gemini", secret: "GEMINI_API_KEY", primary: false },
  { key: "max", name: "MAX", secret: "MAX_BOT_TOKEN", primary: false },
] as const;

function secretText(secret?: SecretStatus) {
  if (!secret || secret.status === "missing" || secret.status === "disabled") return "Ключ отсутствует";
  return secret.masked_value || "Ключ сохранен";
}

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [secrets, setSecrets] = useState<SecretsStatus | null>(null);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [agents, setAgents] = useState<OrgAgent[]>([]);
  const [configs, setConfigs] = useState<AgentConfig[]>([]);
  const [secretInputs, setSecretInputs] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");
  const [busy, setBusy] = useState("");

  const load = async () => {
    const [nextIntegrations, nextSecrets, nextSettings, nextModels, nextAgents, nextConfigs] = await Promise.all([
      api.integrations(),
      api.secretsStatus(),
      api.settings(),
      api.llmModels(),
      api.orgAgents(),
      api.agentConfigs(),
    ]);
    setIntegrations(nextIntegrations);
    setSecrets(nextSecrets);
    setSettings(nextSettings);
    setModels(nextModels);
    setAgents(nextAgents);
    setConfigs(nextConfigs);
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

  const secretMap = useMemo(() => Object.fromEntries((secrets?.providers || []).map((item) => [item.provider, item])), [secrets]);
  const integrationMap = useMemo(() => Object.fromEntries(integrations.map((item) => [item.provider, item])), [integrations]);
  const openaiModel = integrationMap.openai?.config_json?.model || "";

  const saveModel = async (integration: Integration, model: string) => {
    await api.updateIntegration(integration.id, { config_json: { ...(integration.config_json || {}), model } });
  };

  const renderProvider = (provider: (typeof providers)[number]) => {
    const secret = secretMap[provider.key] as SecretStatus | undefined;
    const integration = integrationMap[provider.key] as Integration | undefined;
    const inputKey = `${provider.key}:${provider.secret}`;
    const model = integration?.config_json?.model || "";
    const selectedModel = models.find((item) => item.provider === provider.key && item.model === model);
    const modelOptions = models.filter((item) => item.provider === provider.key && item.enabled);
    const isEditing = editing[inputKey] || secret?.status !== "configured";
    const canTest = secret?.status === "configured" || secret?.status === "failed";
    const testBlocked = settings?.system_mode === "mock" ? "Переключите систему в dry_run для проверки реального провайдера." : !canTest ? "Сначала добавьте ключ." : "";

    return (
      <article className={`row-card ${provider.primary ? "primary-card" : ""}`} key={provider.key}>
        <div className="section-title">
          <div>
            <h3>{provider.name}</h3>
            <p className="muted">{provider.key === "max" ? "Токен можно сохранить, но публикация наружу остается выключенной." : "Ключ хранится только на backend в зашифрованном виде."}</p>
          </div>
          <span className={`status ${secret?.status || "missing"}`}>{secret?.status === "configured" ? "настроено" : "не настроено"}</span>
        </div>

        <div className="wizard-grid">
          <div>
            <section className="wizard-section">
              <h4>1. Ключ</h4>
              <p><strong>{secretText(secret)}</strong></p>
              <p className="muted">После сохранения полный ключ больше не показывается.</p>
              {!secrets?.storage_ready ? <p className="error-panel panel">{secrets?.storage_error}</p> : null}
              {isEditing ? (
                <input
                  className="input"
                  type="password"
                  autoComplete="new-password"
                  placeholder={secret?.status === "configured" ? "Вставьте новый ключ для замены" : "Вставьте ключ"}
                  value={secretInputs[inputKey] || ""}
                  onChange={(event) => setSecretInputs((current) => ({ ...current, [inputKey]: event.target.value }))}
                />
              ) : null}
              <div className="actions">
                {!isEditing ? (
                  <button className="btn" onClick={() => setEditing((current) => ({ ...current, [inputKey]: true }))}>Заменить ключ</button>
                ) : (
                  <SafeActionButton
                    disabledReason={!secrets?.storage_ready ? secrets?.storage_error : !(secretInputs[inputKey] || "").trim() ? "Вставьте ключ перед сохранением." : ""}
                    disabled={busy === `save-${inputKey}`}
                    onClick={() => run(`save-${inputKey}`, async () => {
                      await api.saveSecret(provider.key, provider.secret, secretInputs[inputKey]);
                      setSecretInputs((current) => ({ ...current, [inputKey]: "" }));
                      setEditing((current) => ({ ...current, [inputKey]: false }));
                    }, "Ключ сохранен. Поле очищено.")}
                  >
                    {secret?.status === "configured" ? "Сохранить замену" : "Добавить ключ"}
                  </SafeActionButton>
                )}
                <SafeActionButton
                  className="btn danger"
                  disabledReason={secret?.status !== "configured" && secret?.status !== "failed" ? "Ключ уже отсутствует." : ""}
                  disabled={busy === `delete-${inputKey}`}
                  onClick={() => run(`delete-${inputKey}`, async () => { await api.deleteSecret(provider.key, provider.secret); }, "Ключ удален")}
                >
                  <Trash2 size={16} /> Удалить ключ
                </SafeActionButton>
              </div>
            </section>

            {provider.key !== "max" && integration ? (
              <section className="wizard-section">
                <h4>2. Модель</h4>
                <select className="select" value={model} onChange={(event) => run(`model-${provider.key}`, async () => saveModel(integration, event.target.value), "Модель сохранена")}>
                  <option value="">Выберите модель</option>
                  {modelOptions.map((item) => <option key={item.id} value={item.model}>{item.label}</option>)}
                </select>
                <div className="mini-log">
                  <div>Выбрано: {modelLabel(models, provider.key, model)}</div>
                  <div>Стоимость: ${selectedModel?.input_cost_per_1m ?? 0}/1M input, ${selectedModel?.output_cost_per_1m ?? 0}/1M output</div>
                  <div>Структурированный ответ: {selectedModel?.supports_json_schema ? "поддерживается" : "не отмечен"}</div>
                </div>
              </section>
            ) : null}
          </div>

          <div>
            <section className="wizard-section">
              <h4>3. Проверка</h4>
              <p className="muted">Запускает маленький structured output test. В mock-режиме реальные вызовы заблокированы.</p>
              <div className="mini-log">
                <div>Последняя проверка: {secret?.last_test_at ? new Date(secret.last_test_at).toLocaleString("ru-RU") : "не было"}</div>
                <div>Последний успех: {secret?.last_success_at ? new Date(secret.last_success_at).toLocaleString("ru-RU") : "не было"}</div>
                <div>Ошибка: {secret?.last_error || "нет"}</div>
              </div>
              <SafeActionButton
                className="btn secondary"
                disabledReason={testBlocked}
                disabled={busy === `test-${inputKey}`}
                onClick={() => run(`test-${inputKey}`, async () => { await api.testSecret(provider.key, provider.secret); }, "Проверка прошла")}
              >
                <PlugZap size={16} /> Проверить ключ
              </SafeActionButton>
            </section>

            {provider.key === "openai" ? (
              <section className="wizard-section">
                <h4>4. Использовать в агентах</h4>
                <p className="muted">Настроит Research, Factcheck, Editor и Chief Editor на выбранную модель OpenAI. Publisher останется выключенным.</p>
                <ul>
                  <li>Research Agent</li>
                  <li>Factcheck Agent</li>
                  <li>Editor Agent</li>
                  <li>Chief Editor Agent</li>
                </ul>
                <SafeActionButton
                  disabledReason={secret?.status !== "configured" ? "Сначала добавьте OpenAI ключ." : !openaiModel ? "Сначала выберите модель OpenAI." : ""}
                  disabled={busy === "bulk-openai"}
                  onClick={() => run("bulk-openai", async () => { await api.configureContentAgentsOpenAI(openaiModel); }, "Content agents настроены для OpenAI dry-run")}
                >
                  <CheckCircle2 size={16} /> Применить OpenAI к content agents
                </SafeActionButton>
              </section>
            ) : null}
          </div>
        </div>
      </article>
    );
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Интеграции</h1>
          <p className="page-subtitle">Здесь оператор добавляет ключ, выбирает модель, проверяет structured output и применяет OpenAI к агентам. Полные секреты никогда не возвращаются в интерфейс.</p>
        </div>
        <span className={`status ${settings?.system_mode === "dry_run" ? "active" : "warning"}`}>{settings?.system_mode || "загрузка"}</span>
      </div>

      <section className="post-grid">
        {providers.map(renderProvider)}
      </section>

      <SystemReadinessPanel settings={settings} secrets={secrets} integrations={integrations} agents={agents} configs={configs} stats={{}} />
      <Toast message={toast} kind={toastKind} />
    </>
  );
}
