"use client";

import { Plus, Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { SafeActionButton, Toast, ru } from "@/components/operator";
import { api, OrgAgent, PromptTemplate } from "@/lib/api";

const errorText = (error: unknown) => error instanceof Error ? error.message : "Действие не выполнено";

export default function PromptsPage() {
  const [items, setItems] = useState<PromptTemplate[]>([]);
  const [agents, setAgents] = useState<OrgAgent[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Partial<PromptTemplate>>>({});
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();
  const [form, setForm] = useState({ name: "", agent_type: "editorial", content: "" });

  const load = async () => {
    const [prompts, orgAgents] = await Promise.all([api.promptTemplates(), api.orgAgents()]);
    setItems(prompts);
    setAgents(orgAgents);
    setDrafts(Object.fromEntries(prompts.map((item) => [item.id, item])));
  };

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
  }, []);

  const patch = (id: number, data: Partial<PromptTemplate>) => setDrafts((current) => ({ ...current, [id]: { ...current[id], ...data } }));
  const usedBy = (agentType: string) => agents.filter((agent) => agent.role === agentType).map((agent) => agent.title).join(", ") || "нет привязанных агентов";

  const createPrompt = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.name.trim() || !form.content.trim()) {
      setToast({ message: "Укажите название и текст prompt.", kind: "error" });
      return;
    }
    try {
      await api.createPromptTemplate({ ...form, variables_json: {}, status: "draft" } as Partial<PromptTemplate>);
      setForm({ name: "", agent_type: "editorial", content: "" });
      await load();
      setToast({ message: "Prompt создан как draft.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const savePrompt = async (item: PromptTemplate) => {
    try {
      await api.updatePromptTemplate(item.id, drafts[item.id] || item);
      await load();
      setToast({ message: "Prompt сохранён. Если текст изменился, backend создаёт новую версию.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Промпты</h1>
          <p className="page-subtitle">Версионированные системные промпты. Активная версия влияет на agent_config и dry-run pipeline.</p>
        </div>
      </div>
      <Toast message={toast?.message} kind={toast?.kind} />
      <section className="panel">
        <h2>Создать prompt</h2>
        <form className="form-grid" onSubmit={createPrompt}>
          <input className="input" placeholder="Название" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="select" value={form.agent_type} onChange={(e) => setForm({ ...form, agent_type: e.target.value })}>
            <option value="scout">Research / Scout</option>
            <option value="factcheck">Factcheck</option>
            <option value="editorial">Editor / Chief Editor</option>
            <option value="risk">Risk</option>
            <option value="analytics">Analytics</option>
          </select>
          <textarea className="textarea" placeholder="Текст prompt" value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} />
          <button className="btn" type="submit"><Plus size={16} /> Создать prompt</button>
        </form>
      </section>
      <section className="post-grid">
        {items.map((item) => {
          const draft = drafts[item.id] || item;
          return (
            <article className="row-card" key={item.id}>
              <div className="actions"><span className={`status ${item.status}`}>{ru(item.status)}</span><span className="status">v{item.version}</span><span className="status">{item.agent_type}</span></div>
              <h3>{item.name}</h3>
              <p className="muted">Используют: {usedBy(item.agent_type)}</p>
              <label>Статус
                <select className="select" value={draft.status || "draft"} onChange={(e) => patch(item.id, { status: e.target.value as PromptTemplate["status"] })}>
                  <option value="draft">draft</option><option value="active">active</option><option value="archived">archived</option>
                </select>
              </label>
              <label>Prompt content<textarea className="textarea tall" value={draft.content || ""} onChange={(e) => patch(item.id, { content: e.target.value })} /></label>
              <div className="actions">
                <button className="btn" data-testid={`prompt-save-${item.id}`} onClick={() => savePrompt(item)}><Save size={16} /> Сохранить</button>
                <SafeActionButton className="btn secondary" disabledReason="Rollback отдельной кнопкой пока не реализован. Для отката активируйте нужную старую версию через статус active.">Rollback</SafeActionButton>
              </div>
            </article>
          );
        })}
      </section>
    </>
  );
}
