"use client";

import Link from "next/link";
import { Bot, CheckCircle2, FileText, PlugZap, PlusCircle, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, AgentConfig, Integration, LLMModel, OperatingLoopRun, OrgAgent, Post, SecretsStatus, SystemSettings, Topic } from "@/lib/api";
import { contentAgentRows, dryRunBlockReason, modelLabel, openAISecret, providerModel, SafeActionButton, SystemReadinessPanel, Toast } from "@/components/operator";

export default function DashboardPage() {
  const [stats, setStats] = useState<Record<string, number>>({});
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [secrets, setSecrets] = useState<SecretsStatus | null>(null);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [agents, setAgents] = useState<OrgAgent[]>([]);
  const [configs, setConfigs] = useState<AgentConfig[]>([]);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loopRun, setLoopRun] = useState<OperatingLoopRun | null>(null);
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");
  const [busy, setBusy] = useState("");

  const load = async () => {
    const [nextStats, nextSettings, nextSecrets, nextIntegrations, nextAgents, nextConfigs, nextModels, nextTopics, nextPosts, latestLoop] = await Promise.all([
      api.dashboard(),
      api.settings(),
      api.secretsStatus(),
      api.integrations(),
      api.orgAgents(),
      api.agentConfigs(),
      api.llmModels(),
      api.topics(),
      api.posts(),
      api.latestOperatingLoop(),
    ]);
    setStats(nextStats);
    setSettings(nextSettings);
    setSecrets(nextSecrets);
    setIntegrations(nextIntegrations);
    setAgents(nextAgents);
    setConfigs(nextConfigs);
    setModels(nextModels);
    setTopics(nextTopics);
    setPosts(nextPosts);
    setLoopRun(latestLoop);
  };

  useEffect(() => {
    load().catch((error) => {
      setToast(error.message);
      setToastKind("error");
    });
  }, []);

  const run = async (label: string, action: () => Promise<void>) => {
    setBusy(label);
    setToast("");
    try {
      await action();
      setToast("Готово");
      setToastKind("success");
      await load();
    } catch (error: any) {
      setToast(error.message || "Не удалось выполнить действие");
      setToastKind("error");
    } finally {
      setBusy("");
    }
  };

  const openai = openAISecret(secrets);
  const openaiModel = providerModel(integrations, "openai");
  const openaiReady = openai?.status === "configured" && !!openai.last_success_at;
  const rows = contentAgentRows(agents, configs, openai?.status === "configured");
  const agentsReady = rows.every((item) => item.ready);
  const readyTopics = topics.filter((topic) => topic.url && topic.status !== "rejected").length;
  const latestDryRun = posts.find((post) => post.generation_mode === "dry_run");
  const waitingReview = posts.filter((post) => post.status === "needs_review").length;
  const mockPosts = posts.filter((post) => post.generation_mode === "mock").length;
  const notPublishable = posts.filter((post) => !post.publishable).length;
  const dryRunReason = dryRunBlockReason({ settings, secrets, agents, configs, stats });
  const firstReadyTopic = topics.find((topic) => topic.url && topic.status !== "rejected");

  const cards = useMemo(() => [
    {
      title: "Подключить LLM",
      icon: PlugZap,
      lines: [
        openai?.status === "configured" ? `OpenAI ключ: ${openai.masked_value}` : "OpenAI ключ не добавлен",
        openaiModel ? `Модель: ${modelLabel(models, "openai", openaiModel)}` : "Модель не выбрана",
        openai?.last_success_at ? "Проверка ключа прошла" : "Ключ еще не проверен",
        openaiReady ? "Dry-run готов по ключу" : "Нужно добавить или проверить ключ",
      ],
      actions: (
        <>
          <Link className="btn" href="/integrations">Открыть интеграции</Link>
          <SafeActionButton
            className="btn secondary"
            disabledReason={settings?.system_mode === "mock" ? "Проверка реального провайдера доступна только в dry_run." : openai?.status !== "configured" ? "Сначала добавьте OpenAI ключ." : ""}
            disabled={busy === "test-openai"}
            onClick={() => run("test-openai", async () => { await api.testSecret("openai", "OPENAI_API_KEY"); })}
          >
            Проверить OpenAI
          </SafeActionButton>
        </>
      ),
    },
    {
      title: "Подготовить агентов",
      icon: Bot,
      lines: rows.map((row) => `${row.title}: ${row.ready ? "готов" : row.reason}`),
      actions: (
        <>
          <Link className="btn" href="/agents">Настроить агентов</Link>
          <SafeActionButton
            className="btn secondary"
            disabledReason={openai?.status !== "configured" ? "Сначала добавьте OpenAI ключ." : !openaiModel ? "Сначала выберите модель OpenAI." : ""}
            disabled={busy === "bulk-openai"}
            onClick={() => run("bulk-openai", async () => { await api.configureContentAgentsOpenAI(openaiModel); })}
          >
            Применить OpenAI
          </SafeActionButton>
        </>
      ),
    },
    {
      title: "Создать тему",
      icon: PlusCircle,
      lines: [
        `Тем сегодня: ${stats.topics_found_today || 0}`,
        `Готовы к dry-run: ${readyTopics}`,
        "Для dry-run нужен URL источника",
      ],
      actions: (
        <>
          <Link className="btn" href="/topics#create-topic">Создать тему</Link>
          <Link className="btn secondary" href="/topics">Открыть темы</Link>
        </>
      ),
    },
    {
      title: "Сгенерировать dry-run пост",
      icon: Sparkles,
      lines: [
        latestDryRun ? `Последний dry-run: пост #${latestDryRun.id}` : "Dry-run постов еще нет",
        `Остаток бюджета: $${Number(stats.budget_remaining || 0).toFixed(2)}`,
        dryRunReason || "Система готова к ручному dry-run",
      ],
      actions: (
        <SafeActionButton
          className="btn"
          disabledReason={dryRunReason || (!firstReadyTopic ? "Нет темы с URL источника." : "")}
          disabled={busy === "dry-run"}
          onClick={() => run("dry-run", async () => { if (firstReadyTopic) await api.generateDryRun(firstReadyTopic.id); })}
        >
          Запустить dry-run
        </SafeActionButton>
      ),
    },
    {
      title: "Проверить пост",
      icon: FileText,
      lines: [
        `Ждут проверки: ${waitingReview}`,
        latestDryRun ? `Последний dry-run: #${latestDryRun.id}` : "Dry-run пока нет",
        `Mock постов: ${mockPosts}`,
        `Нельзя публиковать: ${notPublishable}`,
      ],
      actions: <Link className="btn" href="/posts">Открыть очередь проверки</Link>,
    },
  ], [openai, openaiModel, models, openaiReady, rows, stats, readyTopics, latestDryRun, waitingReview, mockPosts, notPublishable, dryRunReason, firstReadyTopic, busy, settings]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Панель оператора</h1>
          <p className="page-subtitle">Что делать дальше: подключить модель, подготовить агентов, создать тему, запустить dry-run и проверить пост. Публикация в MAX выключена.</p>
        </div>
        <span className={`status ${settings?.system_mode === "mock" ? "warning" : "active"}`}>{settings ? settings.system_mode : "загрузка"}</span>
      </div>

      <section className="panel">
        <div className="section-title">
          <div>
            <h2>Что делать дальше</h2>
            <p className="muted">Пять рабочих шагов для безопасной генерации dry-run поста.</p>
          </div>
        </div>
      </section>

      <section className="operator-grid">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <article className="operator-card" key={card.title}>
              <Icon size={24} />
              <h3>{card.title}</h3>
              <div className="mini-log">
                {card.lines.map((line) => <div key={line}>{line}</div>)}
              </div>
              <div className="actions">{card.actions}</div>
            </article>
          );
        })}
      </section>

      <SystemReadinessPanel settings={settings} secrets={secrets} integrations={integrations} agents={agents} configs={configs} stats={stats} />

      <section className="stats">
        <div className="stat"><div className="stat-label">Backend</div><div className="stat-value">OK</div><p className="muted">API и база отвечают</p></div>
        <div className="stat"><div className="stat-label">Посты сегодня</div><div className="stat-value">{stats.posts_generated_today || 0}</div><p className="muted">mock/dry-run/live разделены</p></div>
        <div className="stat"><div className="stat-label">Стоимость сегодня</div><div className="stat-value">${Number(stats.cost_today || settings?.daily_usage?.cost || 0).toFixed(4)}</div><p className="muted">лимит ${settings?.global_daily_budget_usd ?? 2}</p></div>
        <div className="stat"><div className="stat-label">Токены сегодня</div><div className="stat-value">{stats.daily_tokens_used || settings?.daily_usage?.tokens || 0}</div><p className="muted">лимит {settings?.global_daily_token_limit ?? 100000}</p></div>
      </section>

      <section className="panel">
        <div className="section-title">
          <div>
            <h2>CEO Operating Loop</h2>
            <p className="muted">Планирование Kanban работает безопасно даже когда глобальные агенты выключены. Контентные агенты, LLM и публикации не запускаются автоматически.</p>
          </div>
          <CheckCircle2 size={22} />
        </div>
        <div className="actions">
          <button className="btn" disabled={busy === "daily-plan"} onClick={() => run("daily-plan", async () => { setLoopRun(await api.runOperatingLoop("create_daily_plan")); })}>Создать план дня</button>
          <button className="btn secondary" disabled={busy === "kanban"} onClick={() => run("kanban", async () => { setLoopRun(await api.runOperatingLoop("refresh_kanban")); })}>Обновить Kanban</button>
          <button className="btn secondary" disabled={busy === "blockers"} onClick={() => run("blockers", async () => { setLoopRun(await api.runOperatingLoop("check_blockers")); })}>Проверить блокировки</button>
        </div>
        {loopRun ? <div className="mini-log">Последний запуск #{loopRun.id}: создано {loopRun.issues_created}, обновлено {loopRun.issues_updated}. Следующее действие: {loopRun.report_json?.next_suggested_action || "не задано"}.</div> : null}
      </section>

      <Toast message={toast} kind={toastKind} />
    </>
  );
}
