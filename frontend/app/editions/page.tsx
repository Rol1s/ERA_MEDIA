"use client";

import { Check, Copy, FilePlus2, RefreshCw, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, DailyEdition, EditionDetail, Post, Topic } from "@/lib/api";
import { Toast } from "@/components/operator";

const tabs = [
  ["sources", "Sources"],
  ["candidate", "Candidate topics"],
  ["selected", "Selected topics"],
  ["posts", "Generated posts"],
  ["rejected", "Rejected"],
  ["final", "Final pack"],
] as const;

const ruStatus: Record<string, string> = {
  collecting: "сбор",
  drafting: "черновики",
  review: "проверка",
  ready: "готов",
  published_manually: "опубликован вручную",
  cancelled: "отменён",
  edition_selected: "выбрана",
  edition_generated: "пост создан",
  edition_rejected: "отклонено",
  ready_for_dry_run: "готова",
  needs_review: "на проверке",
  final_pack: "final pack",
};

function finalBlockReason(post: Post) {
  const factcheck = post.structured_outputs_json?.factcheck || {};
  if (post.generation_mode !== "dry_run") return "Только dry-run посты входят в final pack.";
  if (Number(post.quality_score || 0) < 75) return "Качество ниже 75.";
  if ((factcheck.factcheck_result || factcheck.result) === "fail") return "Factcheck failed.";
  if (!post.source_urls?.length) return "Нет ссылки на источник.";
  return "";
}

export default function EditionsPage() {
  const [editions, setEditions] = useState<DailyEdition[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<EditionDetail | null>(null);
  const [tab, setTab] = useState<(typeof tabs)[number][0]>("candidate");
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");

  const selected = useMemo(() => editions.find((item) => item.id === selectedId) || editions[0], [editions, selectedId]);

  const load = async (id?: number | null) => {
    const rows = await api.editions();
    setEditions(rows);
    const nextId = id || selectedId || rows[0]?.id || null;
    setSelectedId(nextId);
    if (nextId) setDetail(await api.editionDetail(nextId));
  };

  useEffect(() => {
    load().catch((error) => {
      setToast(error.message);
      setToastKind("error");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (label: string, action: () => Promise<void>, success: string) => {
    setBusy(label);
    setToast("");
    try {
      await action();
      setToast(success);
      setToastKind("success");
      await load(selected?.id);
    } catch (error: any) {
      setToast(error.message || "Действие не выполнено");
      setToastKind("error");
    } finally {
      setBusy("");
    }
  };

  const copyPost = async (post: Post) => {
    await navigator.clipboard?.writeText(`${post.title}\n\n${post.body}\n\nИсточники: ${(post.source_urls || []).join(", ")}`);
    setToast("Пост скопирован для ручной публикации");
    setToastKind("success");
  };

  const topicCard = (topic: Topic, selectedTopic = false) => (
    <article className="row-card" key={topic.id}>
      <div className="actions">
        <span className={`status ${topic.status}`}>{ruStatus[topic.status] || topic.status}</span>
        <span className="status">score {Number(topic.final_score || 0).toFixed(2)}</span>
        <span className="status">risk {Number(topic.risk_score || 0).toFixed(2)}</span>
        {topic.source_item_id ? <span className="status completed">source item #{topic.source_item_id}</span> : null}
      </div>
      <h3>{topic.title}</h3>
      <p>{topic.summary || topic.why_this_matters || "Описание не заполнено."}</p>
      <div className="mini-log">
        <div>Источник: {topic.url || "не указан"}</div>
        <div>Извлечение: {topic.extraction_status || "manual"} / {topic.content_length || 0} символов</div>
        <div>Угол: {topic.suggested_angle || "не задан"}</div>
      </div>
      <div className="actions">
        {!selectedTopic ? <button className="btn secondary" onClick={() => run(`select-${topic.id}`, async () => { await api.selectEditionTopic(selected!.id, topic.id); }, "Тема выбрана")}><Check size={16} /> Выбрать</button> : null}
        <button className="btn secondary" onClick={() => run(`gen-${topic.id}`, async () => { await api.generateEditionPost(selected!.id, topic.id); }, "Dry-run пост создан")}><Sparkles size={16} /> Generate post</button>
        <button className="btn danger" onClick={() => run(`reject-topic-${topic.id}`, async () => { await api.rejectEditionTopic(selected!.id, topic.id); }, "Тема отклонена")}><X size={16} /> Reject</button>
      </div>
    </article>
  );

  const postCard = (post: Post, final = false) => {
    const reason = finalBlockReason(post);
    return (
      <article className="row-card" key={post.id}>
        <div className="actions">
          <span className={`status ${post.status}`}>{ruStatus[post.status] || post.status}</span>
          <span className="status warning">DRY RUN / ручная проверка</span>
          <span className="status">quality {Number(post.quality_score || 0).toFixed(0)}</span>
          <span className="status">risk {Number(post.risk_score || 0).toFixed(0)}</span>
          <span className="status">${Number(post.estimated_cost_usd || 0).toFixed(5)}</span>
          {final ? <span className="status completed">ready for manual MAX publishing</span> : null}
        </div>
        <h3>{post.title}</h3>
        <div className="max-preview"><p>{post.body}</p><small>{(post.source_urls || []).join(" | ")}</small></div>
        <div className="mini-log">
          <div>Risk notes: {post.risk_reason || "нет"}</div>
          <div>Quality: {post.quality_reason || "нет"}</div>
          {reason ? <div>Final pack blocked: {reason}</div> : <div>Final pack gate: OK после human approval</div>}
        </div>
        <div className="actions">
          <button className="btn secondary" onClick={() => copyPost(post)}><Copy size={16} /> Copy</button>
          {!final ? <button className="btn secondary" disabled={!!reason} title={reason || undefined} onClick={() => run(`approve-${post.id}`, async () => { await api.approveEditionPost(selected!.id, post.id, "Human editor checked sources, risk notes and quality for internal final pack."); }, "Пост добавлен в final pack")}><Check size={16} /> Approve final</button> : null}
          {!final ? <button className="btn secondary" onClick={() => run(`regen-${post.id}`, async () => { await api.regenerateEditionPost(selected!.id, post.id); }, "Пост переписан один раз")}><RefreshCw size={16} /> Переписать один раз</button> : null}
          {!final ? <button className="btn danger" onClick={() => run(`reject-post-${post.id}`, async () => { await api.rejectEditionPost(selected!.id, post.id); }, "Пост отклонён")}><X size={16} /> Reject</button> : null}
        </div>
      </article>
    );
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Выпуски</h1>
          <p className="page-subtitle">Первый внутренний editorial issue MVP: только ERA AI и ERA Деньги, dry-run посты, final pack для ручной подготовки. Публичной публикации нет.</p>
        </div>
        <button className="btn" onClick={() => run("create-editions", async () => { await api.createTodayEditions(); }, "Сегодняшние выпуски созданы")}><FilePlus2 size={16} /> Создать выпуски дня</button>
      </div>

      <section className="metric-grid">
        {editions.map((edition) => (
          <button className={`metric-card ${selected?.id === edition.id ? "active" : ""}`} key={edition.id} onClick={() => load(edition.id)}>
            <span>{edition.channel_name}</span>
            <strong>{ruStatus[edition.status] || edition.status}</strong>
            <small>{edition.selected_topics_count}/{edition.target_topics_count} тем, {edition.generated_posts_count}/{edition.target_posts_count} постов, final {edition.approved_posts_count}</small>
            <small>{edition.next_action}</small>
          </button>
        ))}
      </section>

      {selected && detail ? (
        <>
          <section className="panel">
            <div className="actions">
              <button className="btn" disabled={busy === "collect"} onClick={() => run("collect", async () => { await api.collectEdition(selected.id); }, "Материалы собраны")}>Собрать curated sources</button>
              <button className="btn secondary" onClick={() => run("select-top", async () => { await api.selectEditionTop(selected.id); }, "Топ тем выбран")}>Выбрать топ тем</button>
              <span className="status">Cost ${Number(selected.cost || 0).toFixed(5)}</span>
              <span className="status danger">MAX publishing disabled</span>
            </div>
            <textarea className="textarea" placeholder="Заметки редактора" value={detail.edition.editor_notes || ""} onChange={(event) => setDetail({ ...detail, edition: { ...detail.edition, editor_notes: event.target.value } })} onBlur={() => run("notes", async () => { await api.updateEditionNotes(selected.id, detail.edition.editor_notes || ""); }, "Заметки сохранены")} />
          </section>
          <div className="tabs">
            {tabs.map(([key, label]) => <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{label}</button>)}
          </div>
          <section className="post-grid">
            {tab === "sources" ? detail.sources.map((source) => <article className="row-card" key={source.id}><h3>{source.name}</h3><p>{source.url}</p><div className="mini-log">items {source.items_count || 0}, valid {source.valid_items_count || 0}, duplicates {source.duplicate_items_count || 0}</div></article>) : null}
            {tab === "candidate" ? detail.candidate_topics.map((topic) => topicCard(topic)) : null}
            {tab === "selected" ? detail.selected_topics.map((topic) => topicCard(topic, true)) : null}
            {tab === "posts" ? detail.generated_posts.map((post) => postCard(post)) : null}
            {tab === "rejected" ? [...detail.rejected_topics.map((topic) => topicCard(topic)), ...detail.rejected_posts.map((post) => postCard(post))] : null}
            {tab === "final" ? detail.final_pack_posts.map((post) => postCard(post, true)) : null}
          </section>
        </>
      ) : <section className="panel">Создайте выпуски дня для ERA AI и ERA Деньги.</section>}
      <Toast message={toast} kind={toastKind} />
    </>
  );
}
