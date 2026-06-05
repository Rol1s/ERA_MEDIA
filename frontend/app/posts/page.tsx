"use client";

import { Archive, Check, Copy, Save, Send, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, Channel, Post } from "@/lib/api";
import { Toast } from "@/components/operator";

const splitUrls = (value: string) => value.split("\n").map((item) => item.trim()).filter(Boolean);

const isFeedUrl = (value: string) => {
  const clean = value.trim().toLowerCase();
  return clean.endsWith(".xml") || clean.endsWith(".rss") || clean.endsWith(".atom") || clean.includes("/rss") || clean.includes("/feed") || clean.includes("/feeds/") || clean.includes("/atom");
};

const publicSourceUrls = (urls?: string[]) => (urls || []).filter((url) => url && !isFeedUrl(url));

function formatDate(value?: string | null) {
  if (!value) return "не указано";
  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isRealPost(post: Post) {
  return !post.mock_only && !post.is_demo && post.provider !== "mock" && post.generation_mode !== "mock";
}

function hasOnlyHumanResolvableBlockers(loop: any) {
  const blockingIssues = loop?.blocking_issues || [];
  const codes = blockingIssues.map((issue: any) => String(issue.code || ""));
  const humanResolvable = [
    "missing_primary_source",
    "high_risk_needs_human",
    "unsupported_claim",
    "invented_number",
    "invented_date",
    "invented_quote",
    "unsupported_motive",
    "causality_not_supported",
    "responsibility_not_supported",
    "experts_without_source",
  ];
  return codes.length > 0 && codes.every((code: string) => humanResolvable.includes(code));
}

function approveBlockReason(post: Post) {
  if (!isRealPost(post)) return "Mock/demo нельзя одобрять и публиковать.";
  if (!post.source_urls?.length) return "Перед одобрением нужны ссылки на источники.";
  if (post.status === "published") return "Пост уже опубликован.";
  const loop = post.structured_outputs_json?.quality_loop || {};
  if (loop.version !== "v1") return "Сначала нажми «Проверить смысл».";
  if (!loop.passed) return loop.reason || "Quality loop не пройден.";
  if ((loop.blocking_issues || []).length) return "Есть blocking issues. Одобрение запрещено.";
  return "";
}

function approveBlockReasonV2(post: Post) {
  const base = approveBlockReason(post);
  const loop = post.structured_outputs_json?.quality_loop || {};
  if (base && hasOnlyHumanResolvableBlockers(loop)) return "";
  return base;
}

function maxPublishBlockReason(post: Post) {
  const base = approveBlockReasonV2(post);
  if (base) return base;
  if (!["approved", "final_pack", "ready_for_manual_copy"].includes(post.status)) return "Сначала нажми “Одобрить”.";
  return "";
}

function badge(post: Post) {
  if (!isRealPost(post)) return "MOCK";
  if (post.status === "published") return "ОПУБЛИКОВАНО";
  if (post.status === "approved") return "ОДОБРЕНО";
  if (post.generation_mode === "dry_run") return "РЕАЛЬНЫЙ ЧЕРНОВИК";
  return "РЕАЛЬНЫЙ ПОСТ";
}

function score(data: any, key: string, fallback = 0) {
  return Number(data?.quality_scores?.[key] ?? data?.chief_editor?.[key] ?? fallback ?? 0);
}

function qualityBadge(post: Post) {
  const loop = post.structured_outputs_json?.quality_loop || {};
  if (loop.version !== "v1") return "НЕТ QUALITY LOOP";
  if ((loop.blocking_issues || []).length) return "ЕСТЬ BLOCKING CLAIMS";
  if (loop.passed) return "СМЫСЛ ПРОВЕРЕН";
  return "НУЖЕН ЧЕЛОВЕК";
}

export default function PostsPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Partial<Post>>>({});
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

  const patchDraft = (id: number, data: Partial<Post>) => {
    setDrafts((current) => ({ ...current, [id]: { ...current[id], ...data } }));
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Посты</h1>
          <p className="page-subtitle">
            Здесь финальный человеческий контроль: прочитать текст, поправить, одобрить и только потом вручную отправить в MAX.
            Автопубликации и Publisher Agent здесь нет.
          </p>
        </div>
      </div>

      <section className="post-grid">
        {posts.map((post) => {
          const draft = drafts[post.id] || post;
          const channel = channelById.get(post.channel_id);
          const data = post.structured_outputs_json || {};
          const angle = data.editorial_voice?.chief_editor_angle?.editorial_angle || data.editorial_voice?.opinion_angle_editor?.selected_angle || "";
          const visual = post.visual_prompt || data.editorial_voice?.visual_idea_editor?.visual_concept || "";
          const qualityLoop = data.quality_loop || {};
          const meaningCard = data.meaning_card || {};
          const decisionTrace = data.editor_decision_trace || {};
          const dedup = post.dedup_decision_json || data.dedup_decision || data.pre_draft_gate || {};
          const evidencePre = data.evidence_pack_pre_draft || {};
          const claimCheck = data.draft_claim_check || {};
          const chiefV2 = data.chief_editor_v2 || {};
          const sourceTiers = data.source_tiers || {};
          const blockingIssues = qualityLoop.blocking_issues || [];
          const previewSources = publicSourceUrls(draft.source_urls);
          const approveReason = approveBlockReasonV2(post);
          const maxReason = maxPublishBlockReason(post);
          return (
            <article className="row-card" key={post.id}>
              <div className="actions">
                <span className={`status ${post.status}`}>{post.status}</span>
                <span className={`status ${isRealPost(post) ? "completed" : "danger"}`}>{badge(post)}</span>
                <span className={`status ${qualityLoop.passed ? "completed" : "warning"}`}>{qualityBadge(post)}</span>
                <span className="status">{post.provider} / {post.model}</span>
                <span className="status">${Number(post.estimated_cost_usd || 0).toFixed(5)}</span>
              </div>

              <div className="review-layout">
                <div>
                  <p className="muted">{channel?.name || `Канал #${post.channel_id}`}</p>
                  <label>
                    Заголовок
                    <input className="input" value={draft.title || ""} onChange={(event) => patchDraft(post.id, { title: event.target.value })} />
                  </label>
                  <label>
                    Текст
                    <textarea className="textarea tall" value={draft.body || ""} onChange={(event) => patchDraft(post.id, { body: event.target.value })} />
                  </label>
                  <label>
                    Источники
                    <textarea className="textarea" value={(draft.source_urls || []).join("\n")} onChange={(event) => patchDraft(post.id, { source_urls: splitUrls(event.target.value) })} />
                  </label>
                  <label>
                    Визуальная идея
                    <textarea className="textarea" value={draft.visual_prompt || ""} onChange={(event) => patchDraft(post.id, { visual_prompt: event.target.value })} />
                  </label>
                  {post.image_url ? (
                    <div className="visual-preview">
                      <img src={`${post.image_url}?v=${encodeURIComponent(post.updated_at || "")}`} alt={post.title} />
                      <small>{post.image_generation_status || "image_ready"}</small>
                    </div>
                  ) : (
                    <div className="mini-log">Картинка ещё не создана. Для новостей генерируется безопасная editorial card, не фейковое фото события.</div>
                  )}
                  <div className="max-preview">
                    <strong>{draft.title}</strong>
                    <p>{draft.body}</p>
                    <small>{previewSources.join(" | ")}</small>
                  </div>
                </div>

                <aside className="safety-block">
                  <h3>Контроль</h3>
                  <div className="score-grid">
                    <div className="score-row"><span>Качество</span><strong>{Number(post.quality_score || 0).toFixed(0)}/100</strong></div>
                    <div className="score-row"><span>Риск</span><strong>{Number(post.risk_score || 0).toFixed(0)}/100</strong></div>
                    <div className="score-row"><span>Ясность</span><strong>{score(data, "clarity_score")}/100</strong></div>
                    <div className="score-row"><span>Польза</span><strong>{score(data, "usefulness_score")}/100</strong></div>
                    <div className="score-row"><span>Оригинальность</span><strong>{score(data, "originality_score")}/100</strong></div>
                  </div>
                  <div><strong>Создан:</strong> {formatDate(post.created_at)}</div>
                  <div><strong>Изменён:</strong> {formatDate(post.updated_at)}</div>
                  <div><strong>Опубликован:</strong> {formatDate(post.published_at)}</div>
                  <div><strong>Режим:</strong> {post.generation_mode}</div>
                  <div><strong>MAX message:</strong> {post.max_message_id || "нет"}</div>
                  <div><strong>Медиа:</strong> {post.media_status || "missing"} · {post.media_source_type || "none"}</div>
                  <div><strong>Права/заметка:</strong> {post.media_rights_note || "нет"}</div>
                  <div><strong>Quality loop:</strong> {qualityLoop.version || "нет"} · {qualityLoop.passed ? "passed" : "не пройден"}</div>
                  <div><strong>Quality verdict:</strong> {post.quality_verdict || qualityLoop.verdict || "none"}</div>
                  <div><strong>Post type:</strong> {post.post_type || data.recommended_post_type || "NEWS"}</div>
                  <div><strong>Novelty:</strong> {Math.round(Number(post.novelty_score ?? data.novelty_score ?? 0) * 100)}/100</div>
                  <div><strong>Dedup action:</strong> {dedup.action || "none"}</div>
                  <div><strong>Dedup reason:</strong> {dedup.reason || "none"}</div>
                  {dedup.matched_topic_id || dedup.matched_post_id ? (
                    <div><strong>Matched:</strong> topic {dedup.matched_topic_id || "-"} · post {dedup.matched_post_id || "-"}</div>
                  ) : null}
                  <div><strong>Primary source:</strong> {sourceTiers.primary_source || "нет"}</div>
                  <div><strong>Credible secondary:</strong> {(sourceTiers.credible_secondary || []).length}</div>
                  <div><strong>Suggested status:</strong> {qualityLoop.suggested_status || "нет"}</div>
                  <div><strong>Chief confidence:</strong> {chiefV2.confidence ?? "нет"}</div>
                  <div><strong>Cost:</strong> ${Number(qualityLoop.cost?.estimated_cost_usd ?? post.estimated_cost_usd ?? 0).toFixed(5)} · calls {qualityLoop.cost?.llm_calls ?? "?"}/{qualityLoop.cost?.max_llm_calls ?? 6}</div>
                  {(decisionTrace.headline_rationale || decisionTrace.content_length_reason || decisionTrace.source_coverage) ? (
                    <div className="mini-log">
                      <strong>Почему редактор решил так</strong>
                      {decisionTrace.headline_rationale ? <p><b>Заголовок:</b> {decisionTrace.headline_rationale}</p> : null}
                      {decisionTrace.content_length_reason ? <p><b>Объём:</b> {decisionTrace.content_length_reason}</p> : null}
                      {decisionTrace.source_coverage ? <p><b>Смысл источника:</b> {decisionTrace.source_coverage}</p> : null}
                      {decisionTrace.meaning_coverage_score !== undefined ? <p><b>Раскрытие:</b> {Math.round(Number(decisionTrace.meaning_coverage_score || 0) * 100)}/100</p> : null}
                    </div>
                  ) : null}
                  {meaningCard.what_happened ? (
                    <div className="mini-log">
                      <strong>Карточка смысла</strong>
                      <p><b>Что случилось:</b> {meaningCard.what_happened}</p>
                      <p><b>Почему важно:</b> {meaningCard.why_it_matters}</p>
                      <p><b>Угол:</b> {meaningCard.recommended_angle || "нет"}</p>
                      <p><b>Не говорить:</b> {(meaningCard.do_not_say || []).join(" · ")}</p>
                    </div>
                  ) : null}
                  {(dedup.new_facts || data.new_facts || []).length ? (
                    <div className="mini-log">
                      <strong>New facts</strong>
                      {(dedup.new_facts || data.new_facts || []).slice(0, 8).map((item: string, index: number) => <p key={index}>{item}</p>)}
                    </div>
                  ) : null}
                  {(evidencePre.risk_flags || []).length ? (
                    <div className="mini-log warning-soft">
                      <strong>Risk flags</strong>
                      {(evidencePre.risk_flags || []).map((item: string, index: number) => <p key={index}>{item}</p>)}
                    </div>
                  ) : null}
                  {blockingIssues.length ? (
                    <div className="mini-log danger-soft">
                      <strong>Blocking issues</strong>
                      {blockingIssues.map((issue: any, index: number) => (
                        <p key={`${issue.code}-${index}`}><b>{issue.code}</b>: {issue.message} {issue.recommended_fix ? `→ ${issue.recommended_fix}` : ""}</p>
                      ))}
                    </div>
                  ) : null}
                  {(claimCheck.unsupported_claims || []).length ? (
                    <div className="mini-log danger-soft">
                      <strong>Unsupported claims</strong>
                      {(claimCheck.unsupported_claims || []).slice(0, 5).map((item: any, index: number) => (
                        <p key={index}>{item.claim} · {(item.codes || []).join(", ")}</p>
                      ))}
                    </div>
                  ) : null}
                  {angle ? <div><strong>Угол:</strong> {angle}</div> : null}
                  {visual ? <div><strong>Визуал:</strong> {visual}</div> : null}
                  <div><strong>Фактчек:</strong> {data.factcheck?.factcheck_result || data.factcheck?.result || "нет данных"}</div>
                  <div><strong>Причина риска:</strong> {post.risk_reason || "нет"}</div>
                  <div><strong>Почему качество:</strong> {post.quality_reason || "нет"}</div>
                </aside>
              </div>

              {post.max_packaged_text ? (
                <div className="max-preview">
                  <strong>MAX-упаковка</strong>
                  <p>{post.max_packaged_text}</p>
                  <small>{(post.max_buttons_json?.buttons || []).map((button: any) => button.text).join(" · ")}</small>
                </div>
              ) : null}

              <div className="actions">
                <button className="btn" disabled={busy === `save-${post.id}`} onClick={() => run(`save-${post.id}`, async () => { await api.updatePost(post.id, draft); }, "Правки сохранены")}>
                  <Save size={16} /> Сохранить
                </button>
                <button className="btn secondary" disabled={Boolean(approveReason) || busy === `approve-${post.id}`} title={approveReason} onClick={() => run(`approve-${post.id}`, async () => { await api.approvePost(post.id); }, "Пост одобрен человеком")}>
                  <Check size={16} /> Одобрить
                </button>
                <button className="btn secondary" disabled={busy === `quality-${post.id}`} onClick={() => run(`quality-${post.id}`, async () => { await api.qualityCheckPost(post.id); }, "Смысл и claims проверены")}>
                  <Check size={16} /> Проверить смысл
                </button>
                <button className="btn" disabled={Boolean(maxReason) || busy === `publish-max-${post.id}`} title={maxReason} onClick={() => {
                  if (!window.confirm("Опубликовать этот пост в MAX сейчас? Это реальная публикация в канал.")) return;
                  run(`publish-max-${post.id}`, async () => { await api.publishPostToMax(post.id, "Опубликовано вручную из панели ERA."); }, "Пост опубликован в MAX");
                }}>
                  <Send size={16} /> Опубликовать в MAX
                </button>
                <button className="btn secondary" disabled={busy === `rewrite-${post.id}`} onClick={() => run(`rewrite-${post.id}`, async () => { await api.rewritePost(post.id, ["make_more_useful"]); }, "Запрошена перепись")}>
                  <Sparkles size={16} /> Переписать
                </button>
                <button className="btn secondary" disabled={busy === `visual-${post.id}`} onClick={() => run(`visual-${post.id}`, async () => { await api.generatePostVisual(post.id); }, "Визуал создан и ждёт проверки")}>
                  <Sparkles size={16} /> Создать визуал
                </button>
                <button className="btn secondary" disabled={busy === `media-${post.id}`} onClick={() => run(`media-${post.id}`, async () => { await api.preparePostMedia(post.id); }, "Медиа подготовлено")}>
                  <Sparkles size={16} /> Подобрать медиа
                </button>
                <button className="btn secondary" disabled={busy === `package-${post.id}`} onClick={() => run(`package-${post.id}`, async () => { await api.prepareMaxPackage(post.id); }, "MAX-упаковка готова")}>
                  <Sparkles size={16} /> Упаковать MAX
                </button>
                <button className="btn secondary" onClick={async () => {
                  await navigator.clipboard?.writeText(`${draft.title}\n\n${draft.body}`);
                  setToast("Текст скопирован");
                  setToastKind("success");
                }}>
                  <Copy size={16} /> Скопировать
                </button>
                <button className="btn secondary" disabled={busy === `archive-${post.id}`} title="Скрыть из рабочей ленты без удаления данных" onClick={() => run(`archive-${post.id}`, async () => { await api.archivePost(post.id); }, "Пост скрыт из рабочей ленты")}>
                  <Archive size={16} /> Скрыть
                </button>
                <button className="btn danger" disabled={busy === `reject-${post.id}`} onClick={() => run(`reject-${post.id}`, async () => { await api.rejectPost(post.id); }, "Пост отклонён")}>
                  <X size={16} /> Отклонить
                </button>
              </div>
            </article>
          );
        })}
      </section>
      <Toast message={toast} kind={toastKind} />
    </>
  );
}
