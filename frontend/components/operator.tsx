"use client";

import Link from "next/link";
import { AlertCircle, CheckCircle2, Circle, Info, ShieldCheck } from "lucide-react";
import type React from "react";
import type { AgentConfig, AgentTelemetry, Integration, LLMModel, OrgAgent, Post, SecretsStatus, SystemSettings, Topic } from "@/lib/api";

export const statusRu: Record<string, string> = {
  mock: "демо-режим",
  dry_run: "тестовый реальный запуск",
  live: "боевой режим",
  configured: "настроено",
  missing: "не добавлено",
  failed: "ошибка",
  disabled: "выключено",
  ready: "готово",
  backlog: "бэклог",
  in_progress: "в работе",
  review: "на проверке",
  waiting_human: "ждет человека",
  completed: "завершено",
  cancelled: "отменено",
  needs_review: "ждет проверки",
  approved: "одобрено",
  rejected: "отклонено",
};

const contentRuntime = [
  { title: "Research Agent", orgName: "world_scout_agent" },
  { title: "Factcheck Agent", orgName: "factcheck_agent" },
  { title: "Editor Agent", orgName: "editor_in_chief" },
  { title: "Chief Editor Agent", orgName: "editor_in_chief" },
];

export function ru(value?: string | null) {
  if (!value) return "не задано";
  return statusRu[value] || value;
}

export function openAISecret(secrets?: SecretsStatus | null) {
  return secrets?.providers.find((item) => item.provider === "openai") || null;
}

export function providerModel(integrations: Integration[], provider: string) {
  return integrations.find((item) => item.provider === provider)?.config_json?.model || "";
}

export function modelLabel(models: LLMModel[], provider: string, model: string) {
  const found = models.find((item) => item.provider === provider && item.model === model);
  return found ? found.label : model || "модель не выбрана";
}

export function agentConfigFor(runtimeOrgName: string, agents: OrgAgent[], configs: AgentConfig[]) {
  const agent = agents.find((item) => item.name === runtimeOrgName);
  return agent ? configs.find((item) => item.org_agent_id === agent.id) || null : null;
}

export function contentAgentRows(agents: OrgAgent[], configs: AgentConfig[], openaiConfigured: boolean) {
  return contentRuntime.map((item) => {
    const config = agentConfigFor(item.orgName, agents, configs);
    const ready = !!config?.enabled && config.provider === "openai" && !!config.model && openaiConfigured;
    const reason = ready
      ? "готов к тестовому реальному запуску"
      : !openaiConfigured
        ? "OpenAI ключ не добавлен"
        : !config?.enabled
          ? "конфиг выключен"
          : config?.provider !== "openai"
            ? `использует ${ru(config?.provider)}`
            : "модель не выбрана";
    return { ...item, config, ready, reason };
  });
}

export function dryRunBlockReason(args: {
  settings?: SystemSettings | null;
  secrets?: SecretsStatus | null;
  agents: OrgAgent[];
  configs: AgentConfig[];
  stats?: Record<string, number>;
  topic?: Topic | null;
}) {
  const openai = openAISecret(args.secrets);
  const openaiConfigured = openai?.status === "configured";
  if (args.settings?.system_mode !== "dry_run") return "Система сейчас в демо-режиме. Переключите режим на dry_run.";
  if (!openaiConfigured) return "OpenAI ключ не добавлен.";
  const notReady = contentAgentRows(args.agents, args.configs, openaiConfigured).filter((item) => !item.ready);
  if (notReady.length) return notReady[0].reason;
  if (args.stats && Number(args.stats.budget_remaining || 0) <= 0) return "Дневной бюджет исчерпан.";
  if (args.topic && !args.topic.url) return "У темы нет URL источника.";
  if (args.topic?.paywall_or_blocked_detected || args.topic?.status === "blocked_source") return "Источник закрыт, paywall или требует входа. Такой материал не используется.";
  if (args.topic?.status === "duplicate") return "Это дубль уже найденного материала.";
  if (args.topic?.extraction_status === "too_short") return "Извлечённый текст слишком короткий для качественного dry-run.";
  return "";
}

export function SafeActionButton({
  disabledReason,
  children,
  className = "btn",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { disabledReason?: string }) {
  const disabled = !!disabledReason || props.disabled;
  return (
    <span className="button-with-reason">
      <button {...props} className={className} disabled={disabled} title={disabledReason || props.title}>
        {children}
      </button>
      {disabledReason ? <small>{disabledReason}</small> : null}
    </span>
  );
}

export function Toast({ message, kind = "info" }: { message?: string; kind?: "info" | "error" | "success" }) {
  if (!message) return null;
  return <div className={`toast ${kind}`}>{message}</div>;
}

function ReadinessIcon({ ok, warn }: { ok: boolean; warn?: boolean }) {
  if (ok) return <CheckCircle2 size={18} />;
  if (warn) return <AlertCircle size={18} />;
  return <Circle size={18} />;
}

export function SystemReadinessPanel({
  settings,
  secrets,
  integrations,
  agents,
  configs,
  stats,
}: {
  settings?: SystemSettings | null;
  secrets?: SecretsStatus | null;
  integrations: Integration[];
  agents: OrgAgent[];
  configs: AgentConfig[];
  stats?: Record<string, number>;
}) {
  const openai = openAISecret(secrets);
  const openaiConfigured = openai?.status === "configured";
  const rows = contentAgentRows(agents, configs, openaiConfigured);
  const allAgentsReady = rows.every((item) => item.ready);
  const budgetReady = Number(stats?.budget_remaining ?? settings?.global_daily_budget_usd ?? 0) > 0;
  const max = secrets?.providers.find((item) => item.provider === "max");
  const publisher = agents.find((item) => item.name === "publisher_agent");
  const publishingOff = !settings?.global_publishing_enabled && publisher?.status === "disabled";
  const safe = publishingOff && !settings?.global_routines_enabled && settings?.system_mode !== "live";
  const model = providerModel(integrations, "openai");

  const checks = [
    {
      ok: settings?.system_mode === "dry_run",
      warn: settings?.system_mode === "mock",
      label: `Режим: ${ru(settings?.system_mode)}`,
      text: settings?.system_mode === "dry_run" ? "Реальные LLM-вызовы разрешены только вручную." : "Для реального теста переключите dry_run.",
      href: "/",
    },
    {
      ok: openaiConfigured,
      label: openaiConfigured ? `OpenAI ключ добавлен: ${openai?.masked_value}` : "OpenAI ключ не добавлен",
      text: openaiConfigured ? "Сырой ключ не отдается во frontend." : "Добавьте ключ в Интеграциях.",
      href: "/integrations",
    },
    {
      ok: !!openai?.last_success_at,
      warn: openai?.status === "failed",
      label: openai?.last_success_at ? "Проверка OpenAI прошла" : "OpenAI еще не проверен",
      text: openai?.last_error || "Проверьте ключ после перехода в dry_run.",
      href: "/integrations",
    },
    {
      ok: allAgentsReady,
      label: allAgentsReady ? "Content agents готовы" : "Content agents не готовы",
      text: allAgentsReady ? `Все используют OpenAI ${model || ""}.` : rows.find((item) => !item.ready)?.reason || "Нужно настроить агентов.",
      href: "/agents",
    },
    {
      ok: budgetReady,
      label: budgetReady ? "Бюджет доступен" : "Бюджет исчерпан",
      text: `Остаток: $${Number(stats?.budget_remaining ?? 0).toFixed(2)}.`,
      href: "/costs",
    },
    {
      ok: !settings?.global_publishing_enabled,
      label: "Публикация наружу выключена",
      text: "MAX public publishing в этом шаге недоступен.",
      href: "/channels",
    },
    {
      ok: publisher?.status === "disabled",
      label: "Publisher Agent выключен",
      text: "Отключен до этапа публикаций.",
      href: "/agents",
    },
    {
      ok: max?.status === "configured",
      warn: true,
      label: max?.status === "configured" ? "MAX токен сохранен" : "MAX не подключен",
      text: "Даже при подключении публичная публикация заблокирована.",
      href: "/integrations",
    },
    {
      ok: safe,
      label: safe ? "Безопасное состояние" : "Проверьте стоп-краны",
      text: safe ? "Live, routines и Publisher не включены." : "Нужно выключить публикацию, routines или Publisher.",
      href: "/",
    },
  ];

  return (
    <section className="panel readiness-panel" id="readiness">
      <div className="section-title">
        <div>
          <h2>Готовность системы</h2>
          <p className="muted">Что уже готово для dry-run и что блокирует следующий шаг.</p>
        </div>
        <ShieldCheck size={22} />
      </div>
      <div className="readiness-grid">
        {checks.map((check) => (
          <Link href={check.href} className={`readiness-item ${check.ok ? "ok" : check.warn ? "warn" : "bad"}`} key={check.label}>
            <ReadinessIcon ok={check.ok} warn={check.warn} />
            <span>
              <strong>{check.label}</strong>
              <small>{check.text}</small>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function EmptyHint({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty-hint">
      <Info size={18} />
      <span>{children}</span>
    </div>
  );
}

export function postBadge(post: Post) {
  if (post.generation_mode === "dry_run") return "DRY RUN / ТРЕБУЕТ ПРОВЕРКИ";
  if (post.generation_mode === "live") return "LIVE";
  return "MOCK / НЕ ДЛЯ ПУБЛИКАЦИИ";
}
