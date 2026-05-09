"use client";

import { Archive, Check, Clock, Copy, Save, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, Channel, DecisionLog, ExplainResult, Post } from "@/lib/api";
import { postBadge, SafeActionButton, Toast } from "@/components/operator";

const splitUrls = (value: string) => value.split("\n").map((item) => item.trim()).filter(Boolean);
const cannotPublishReason = (post: Post) => post.non_publishable_reason || post.not_publishable_reason || "Пост нельзя публиковать в текущем режиме.";

const qualityLabels: Record<string, string> = {
  editorial_value_score: "Редакционная ценность",
  factuality_score: "Фактичность",
  clarity_score: "Ясность",
  usefulness_score: "Практическая польза",
  channel_fit_score: "Попадание в канал",
  originality_score: "Оригинальность",
  risk_score: "Риск",
  overall_quality_score: "Итоговое качество",
};

const decisionLabel: Record<string, string> = {
  approve: "одобрено к проверке",
  approve_for_review: "одобрено к ручной проверке",
  rewrite_once: "нужна одна перепись",
  reject: "отклонено",
  waiting_human: "ждёт человека",
};

function listBlock(title: string, items: any[] | undefined) {
  if (!items?.length) return null;
  return (
    <div>
      <strong>{title}</strong>
      <ul className="compact-list">
        {items.map((item, index) => <li key={`${title}-${index}`}>{String(item)}</li>)}
      </ul>
    </div>
  );
}

function QualityPanel({ post }: { post: Post }) {
  const data = post.structured_outputs_json || {};
  const chief = data.chief_editor || {};
  const factcheck = data.factcheck || {};
  const editor = data.editor || {};
  const playbook = data.channel_playbook || {};
  const scores = data.quality_scores || {
    editorial_value_score: chief.editorial_value_score,
    factuality_score: chief.factuality_score,
    clarity_score: chief.clarity_score,
    usefulness_score: chief.usefulness_score,
    channel_fit_score: chief.channel_fit_score,
    originality_score: chief.originality_score,
    risk_score: chief.risk_score ?? post.risk_score,
    overall_quality_score: chief.overall_quality_score ?? post.quality_score,
  };
  const checklist = chief.playbook_checklist || editor.channel_playbook_checklist || {};
  const rewriteHistory = data.rewrite_history || post.version_history || [];

  return (
    <div className="safety-block">
      <h3>Качество и безопасность</h3>
      <div className="score-grid">
        {Object.entries(scores).filter(([, value]) => value !== undefined && value !== null).map(([key, value]) => (
          <div className="score-row" key={key}>
            <span>{qualityLabels[key] || key}</span>
            <strong>{Number(value).toFixed(0)}/100</strong>
          </div>
        ))}
      </div>
      <div>Решение главреда: <strong>{decisionLabel[chief.decision] || chief.decision || "нет данных"}</strong></div>
      <div>Фактчек: <strong>{factcheck.factcheck_result || factcheck.result || "нет данных"}</strong></div>
      <div>Качество источников: {factcheck.source_quality || factcheck.source_check || "не указано"}</div>
      <div>Риск: {Number(post.risk_score || 0).toFixed(0)}/100 — {post.risk_reason || factcheck.risk_notes || "нет пояснения"}</div>
      <div>Качество: {Number(post.quality_score || 0).toFixed(0)}/100 — {post.quality_reason || chief.reason || "нет пояснения"}</div>
      <div>Токены: {post.tokens_input} input / {post.tokens_output} output</div>
      <div>Стоимость: ${Number(post.estimated_cost_usd || 0).toFixed(5)}</div>
      {editor.why_useful ? <div><strong>Почему это полезно:</strong> {editor.why_useful}</div> : null}
      {listBlock("Что человеку проверить перед публикацией", chief.human_check_before_publication)}
      {listBlock("Неподтверждённые утверждения", factcheck.unsupported_claims)}
      {listBlock("Требуемые правки", chief.required_changes)}
      {factcheck.risk_notes ? <div><strong>Риск-заметки:</strong> {factcheck.risk_notes}</div> : null}
      {Object.keys(checklist).length ? (
        <div>
          <strong>Чеклист playbook</strong>
          <ul className="compact-list">
            {Object.entries(checklist).map(([key, value]) => <li key={key}>{value ? "✓" : "!"} {key}</li>)}
          </ul>
        </div>
      ) : null}
      {playbook.required_structure?.length ? listBlock("Структура канала", playbook.required_structure) : null}
      {rewriteHistory.length ? (
        <details>
          <summary>История переписи: {rewriteHistory.length}</summary>
          <pre className="json-box">{JSON.stringify(rewriteHistory, null, 2)}</pre>
        </details>
      ) : null}
    </div>
  );
}

export default function PostsPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Partial<Post>>>({});
  const [decisions, setDecisions] = useState<Record<number, DecisionLog[]>>({});
  const [explain, setExplain] = useState<Record<number, ExplainResult>>({});
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");
  const [busy, setBusy] = useState("");

  const channelById = useMemo(() => new Map(channels.map((item) => [item.id, item])), [channels]);

  const load = async () => {
    const [nextPosts, nextChannels] = await Promise.all([api.posts(), api.channels()]);
    setPosts(nextPosts);
    setChannels(nextChannels);
    setDrafts(Object.fromEntries(nextPosts.map((post) => [post.id, post])));
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

  const patchDraft = (id: number, data: Partial<Post>) => setDrafts((current) => ({ ...current, [id]: { ...current[id], ...data } }));

  const loadWhy = async (post: Post) => {
    const [logs, details] = await Promise.all([
      api.decisionLogs({ entityType: "post", entityId: post.id }),
      api.explain("post", post.id),
    ]);
    setDecisions((current) => ({ ...current, [post.id]: logs }));
    setExplain((current) => ({ ...current, [post.id]: details }));
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Очередь проверки постов</h1>
          <p className="page-subtitle">Здесь редактор читает dry-run результат, видит решения агентов, качество, фактчек, риски и список того, что нужно проверить вручную.</p>
        </div>
      </div>

      <section className="post-grid">
        {posts.map((post) => {
          const draft = drafts[post.id] || post;
          const channel = channelById.get(post.channel_id);
          const disabledReason = !post.publishable ? cannotPublishReason(post) : "Публичная публикация MAX не включена в Step 2.7.";
          return (
            <article className="row-card" key={post.id}>
              <div className="actions">
                <span className={`status ${post.status}`}>{post.status}</span>
                <span className={post.generation_mode === "mock" ? "status danger" : "status warning"}>{postBadge(post)}</span>
                <span className={post.publishable ? "status completed" : "status danger"}>{post.publishable ? "можно публиковать" : "нельзя публиковать"}</span>
                <span className="status">{post.provider || "mock"} / {post.model || "mock"}</span>
                <span className="status">${Number(post.estimated_cost_usd || 0).toFixed(5)}</span>
              </div>

              <div className="review-layout">
                <div>
                  <p className="muted">{channel?.name || `Канал #${post.channel_id}`}</p>
                  <label>Заголовок<input className="input" value={draft.title || ""} onChange={(event) => patchDraft(post.id, { title: event.target.value })} /></label>
                  <label>Текст<textarea className="textarea tall" value={draft.body || ""} onChange={(event) => patchDraft(post.id, { body: event.target.value })} /></label>
                  <label>Источники<textarea className="textarea" value={(draft.source_urls || []).join("\n")} onChange={(event) => patchDraft(post.id, { source_urls: splitUrls(event.target.value) })} /></label>
                  <label>Визуальная идея<textarea className="textarea" value={draft.visual_prompt || ""} onChange={(event) => patchDraft(post.id, { visual_prompt: event.target.value })} /></label>
                  <div className="max-preview"><strong>{draft.title}</strong><p>{draft.body}</p><small>{(draft.source_urls || []).join(" | ")}</small></div>
                </div>
                <aside>
                  <QualityPanel post={post} />
                  <div className="mini-log">
                    <div>Версия prompt: {post.prompt_template_version || "n/a"}</div>
                    <div>Режим генерации: {post.generation_mode}</div>
                    <div>Публикация: {post.publishable ? "разрешена" : "запрещена"}</div>
                    <div>{disabledReason}</div>
                  </div>
                </aside>
              </div>

              <div className="actions">
                <button className="btn" disabled={busy === `save-${post.id}`} onClick={() => run(`save-${post.id}`, async () => { await api.updatePost(post.id, draft); }, "Правки сохранены")}><Save size={16} /> Сохранить правки</button>
                <SafeActionButton className="btn secondary" disabledReason={disabledReason} disabled={busy === `approve-${post.id}`} onClick={() => run(`approve-${post.id}`, async () => { await api.approvePost(post.id); })}><Check size={16} /> Одобрить</SafeActionButton>
                <SafeActionButton className="btn secondary" disabledReason={disabledReason} disabled={busy === `schedule-${post.id}`} onClick={() => run(`schedule-${post.id}`, async () => { await api.schedulePost(post.id); })}><Clock size={16} /> Запланировать</SafeActionButton>
                <button className="btn secondary" disabled={busy === `rewrite-${post.id}`} onClick={() => run(`rewrite-${post.id}`, async () => { await api.rewritePost(post.id, ["make_more_useful"]); }, "Запрошена перепись")}><Sparkles size={16} /> Переписать</button>
                <button className="btn secondary" onClick={() => loadWhy(post)}>Как это создано?</button>
                <button className="btn secondary" onClick={async () => { await navigator.clipboard?.writeText(`${draft.title}\n\n${draft.body}`); setToast("Текст скопирован"); setToastKind("success"); }}><Copy size={16} /> Копировать</button>
                <button className="btn danger" disabled={busy === `reject-${post.id}`} onClick={() => run(`reject-${post.id}`, async () => { await api.rejectPost(post.id); }, "Пост отклонён")}><X size={16} /> Отклонить</button>
                {post.mock_only ? <button className="btn secondary" disabled={busy === `archive-${post.id}`} onClick={() => run(`archive-${post.id}`, async () => { await api.archivePost(post.id); }, "Mock-пост отправлен в архив")}><Archive size={16} /> Архив</button> : null}
              </div>

              {decisions[post.id]?.length ? <div className="mini-log"><strong>Решения агентов</strong>{decisions[post.id].map((item) => <div key={item.id}>{item.decision}: {item.reason}</div>)}</div> : null}
              {explain[post.id] ? <details className="mini-log" open><summary>Как это создано?</summary><pre className="json-box">{JSON.stringify(explain[post.id], null, 2)}</pre></details> : null}
              {post.structured_outputs_json ? <details className="mini-log"><summary>Структурированные ответы</summary><pre className="json-box">{JSON.stringify(post.structured_outputs_json, null, 2)}</pre></details> : null}
            </article>
          );
        })}
      </section>
      <Toast message={toast} kind={toastKind} />
    </>
  );
}
