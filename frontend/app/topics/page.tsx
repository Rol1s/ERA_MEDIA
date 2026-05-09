"use client";

import { FilePlus2, Play, RotateCcw, UserCheck, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { AgentConfig, AgentRun, api, Channel, DecisionLog, ExplainResult, OrgAgent, SecretsStatus, SystemSettings, Topic } from "@/lib/api";
import { dryRunBlockReason, EmptyHint, SafeActionButton, Toast } from "@/components/operator";

export default function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [secrets, setSecrets] = useState<SecretsStatus | null>(null);
  const [agents, setAgents] = useState<OrgAgent[]>([]);
  const [configs, setConfigs] = useState<AgentConfig[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [runs, setRuns] = useState<Record<number, AgentRun[]>>({});
  const [decisions, setDecisions] = useState<Record<number, DecisionLog[]>>({});
  const [explain, setExplain] = useState<Record<number, ExplainResult>>({});
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState({ title: "", url: "", summary: "", raw_text: "", why_this_matters: "", suggested_angle: "" });

  const load = async () => {
    const [nextTopics, nextChannels, nextSettings, nextSecrets, nextAgents, nextConfigs, nextStats] = await Promise.all([
      api.topics(),
      api.channels(),
      api.settings(),
      api.secretsStatus(),
      api.orgAgents(),
      api.agentConfigs(),
      api.dashboard(),
    ]);
    setTopics(nextTopics);
    setChannels(nextChannels);
    setSettings(nextSettings);
    setSecrets(nextSecrets);
    setAgents(nextAgents);
    setConfigs(nextConfigs);
    setStats(nextStats);
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

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await run("create-topic", async () => {
      await api.createTopic({ ...form, status: "new", usefulness_score: 0.65, originality_score: 0.65, final_score: 0.65 });
      setForm({ title: "", url: "", summary: "", raw_text: "", why_this_matters: "", suggested_angle: "" });
    }, "Тема создана");
  };

  const loadWhy = async (topic: Topic) => {
    const [logs, details] = await Promise.all([
      api.decisionLogs({ entityType: "topic", entityId: topic.id }),
      api.explain("topic", topic.id),
    ]);
    setDecisions((current) => ({ ...current, [topic.id]: logs }));
    setExplain((current) => ({ ...current, [topic.id]: details }));
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Темы</h1>
          <p className="page-subtitle">Тема должна иметь источник, понятный угол и канал. Если dry-run недоступен, причина показана прямо на карточке.</p>
        </div>
      </div>

      <section className="panel" id="create-topic">
        <h2>Создать тему вручную</h2>
        <form className="form-grid" onSubmit={submit}>
          <input className="input" required placeholder="Заголовок темы" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          <input className="input" placeholder="URL источника" value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} />
          <textarea className="textarea" placeholder="Краткое описание" value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} />
          <textarea className="textarea" placeholder="Сырой текст или заметки" value={form.raw_text} onChange={(event) => setForm({ ...form, raw_text: event.target.value })} />
          <textarea className="textarea" placeholder="Почему это важно" value={form.why_this_matters} onChange={(event) => setForm({ ...form, why_this_matters: event.target.value })} />
          <textarea className="textarea" placeholder="Предложенный угол" value={form.suggested_angle} onChange={(event) => setForm({ ...form, suggested_angle: event.target.value })} />
          <button className="btn" type="submit" disabled={busy === "create-topic"}><FilePlus2 size={16} /> Создать тему</button>
        </form>
      </section>

      <section className="post-grid">
        {topics.length ? topics.map((topic) => {
          const channelNames = (topic.assigned_channel_ids || []).map((id) => channels.find((item) => item.id === id)?.name || `#${id}`);
          const blocked = dryRunBlockReason({ settings, secrets, agents, configs, stats, topic });
          return (
            <article className="row-card topic-card" key={topic.id}>
              <div className="actions">
                <span className={`status ${topic.status}`}>{topic.status}</span>
                {topic.is_demo ? <span className="status">demo</span> : null}
                <span className={topic.url ? "status completed" : "status warning"}>{topic.url ? "есть источник" : "нет источника"}</span>
                <span className={channelNames.length ? "status completed" : "status warning"}>{channelNames.length ? "канал выбран" : "автовыбор канала"}</span>
                {topic.source_item_id ? <span className="status completed">source item #{topic.source_item_id}</span> : null}
                {topic.paywall_or_blocked_detected ? <span className="status danger">закрытый источник</span> : null}
              </div>
              <h3>{topic.title}</h3>
              <p>{topic.summary || "Описание не заполнено."}</p>
              <div className="mini-log">
                <div>Источник: {topic.url || "не указан"}</div>
                <div>Извлечение: {topic.extraction_status || "ручная тема"} {topic.extraction_error ? `— ${topic.extraction_error}` : ""}</div>
                <div>Текст: {topic.content_length || 0} символов, язык {topic.language || "не определён"}, дата источника {topic.source_published_at ? new Date(topic.source_published_at).toLocaleString("ru-RU") : "не найдена"}</div>
                <div>Канал: {channelNames.join(", ") || "автовыбор"}</div>
                <div>Dry-run: {blocked ? `заблокирован - ${blocked}` : "готов"}</div>
                <div>Оценки: итог {topic.final_score}, свежесть {topic.freshness_score || 0}, релевантность {topic.relevance_score || 0}, доверие {topic.source_trust_score}, риск {topic.risk_score}, полезность {topic.usefulness_score}, оригинальность {topic.originality_score}</div>
                <div>Готовность: {topic.status === "ready_for_dry_run" ? "готово к dry-run" : topic.status === "blocked_source" ? "не использовать: источник закрыт или заблокирован" : topic.status === "duplicate" ? "дубль, новая тема не нужна" : "требует проверки"}</div>
              </div>
              <div><strong>Почему важно:</strong> {topic.why_this_matters || "не заполнено"}</div>
              <div><strong>Угол:</strong> {topic.suggested_angle || "не заполнено"}</div>
              <div className="actions">
                <button className="btn secondary" disabled={busy === `mock-${topic.id}`} onClick={() => run(`mock-${topic.id}`, async () => {
                  const post = await api.generateDraft(topic.id);
                  const nextRuns = await api.agentRuns({ topicId: topic.id });
                  setRuns((current) => ({ ...current, [topic.id]: nextRuns }));
                  setToast(`Mock-черновик #${post.id} отправлен на проверку`);
                })}><Play size={16} /> Run mock draft</button>
                <SafeActionButton
                  disabledReason={blocked}
                  disabled={busy === `dry-${topic.id}`}
                  onClick={() => run(`dry-${topic.id}`, async () => {
                    if (!window.confirm("Запустить реальный OpenAI dry-run? Публикации в MAX не будет.")) return;
                    const post = await api.generateDryRun(topic.id);
                    const nextRuns = await api.agentRuns({ topicId: topic.id });
                    setRuns((current) => ({ ...current, [topic.id]: nextRuns }));
                    setToast(`Dry-run пост #${post.id} создан и ждет проверки`);
                  })}
                >
                  <Play size={16} /> Run real dry-run
                </SafeActionButton>
                <button className="btn secondary" onClick={() => loadWhy(topic)}>Почему?</button>
                {topic.source_item_id ? <a className="btn secondary" href={`/source-items?source_id=${topic.source_id || ""}`}>Материал</a> : null}
                <button className="btn secondary" onClick={() => run(`review-${topic.id}`, async () => { await api.updateTopic(topic.id, { status: "needs_human_review" }); }, "Тема отправлена на проверку")}><UserCheck size={16} /> На проверку</button>
                <button className="btn secondary" onClick={() => run(`logs-${topic.id}`, async () => { const nextRuns = await api.agentRuns({ topicId: topic.id }); setRuns((current) => ({ ...current, [topic.id]: nextRuns })); }, "Логи загружены")}><RotateCcw size={16} /> Логи</button>
                <button className="btn danger" onClick={() => run(`reject-${topic.id}`, async () => { await api.updateTopic(topic.id, { status: "rejected" }); }, "Тема отклонена")}><X size={16} /> Отклонить</button>
              </div>
              {decisions[topic.id]?.length ? <div className="mini-log">{decisions[topic.id].map((item) => <div key={item.id}><strong>{item.decision}</strong>: {item.reason}</div>)}</div> : null}
              {explain[topic.id] ? <details className="mini-log" open><summary>Как это создано?</summary><pre className="json-box">{JSON.stringify(explain[topic.id], null, 2)}</pre></details> : null}
              {runs[topic.id]?.length ? <div className="mini-log">{runs[topic.id].map((run) => <div key={run.id}>{run.agent_name}: {run.status} / {run.provider} / ${Number(run.estimated_cost || 0).toFixed(5)}</div>)}</div> : null}
            </article>
          );
        }) : <EmptyHint>Тем пока нет. Создайте первую тему с URL источника.</EmptyHint>}
      </section>

      <Toast message={toast} kind={toastKind} />
    </>
  );
}
