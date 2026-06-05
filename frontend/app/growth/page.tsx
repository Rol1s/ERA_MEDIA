"use client";

import { Copy, PlusCircle, RefreshCw, Rocket, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { SafeActionButton, Toast } from "@/components/operator";
import { api, FunnelAsset, GrowthDashboard } from "@/lib/api";

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Действие не выполнено";
}

function formatDate(value?: string | null) {
  if (!value) return "нет";
  return new Date(value).toLocaleString("ru-RU");
}

function assetLabel(type: string) {
  const map: Record<string, string> = {
    pinned_intro: "закреп",
    landing_post: "пост-приманка",
    seed_comment: "вброс",
    cta: "CTA",
    lead_magnet: "лид-магнит",
  };
  return map[type] || type;
}

function AssetCard({ asset, onCopy }: { asset: FunnelAsset; onCopy: (text: string) => void }) {
  return (
    <article className="row-card">
      <div className="section-title">
        <div>
          <h3>{asset.title || assetLabel(asset.asset_type)}</h3>
          <p className="muted">{assetLabel(asset.asset_type)} · {asset.platform} · {formatDate(asset.created_at)}</p>
        </div>
        <span className="status warning">{asset.status}</span>
      </div>
      <p style={{ whiteSpace: "pre-wrap" }}>{asset.text}</p>
      {asset.cta ? <p className="muted">CTA: {asset.cta}</p> : null}
      {asset.risk_notes ? <p className="muted">Риск: {asset.risk_notes}</p> : null}
      <div className="actions">
        <button className="btn secondary" onClick={() => onCopy(asset.text)}><Copy size={16} /> Скопировать</button>
        {asset.post_id ? <a className="btn secondary" href={`/posts?post_id=${asset.post_id}`}>Открыть пост #{asset.post_id}</a> : null}
      </div>
    </article>
  );
}

export default function GrowthPage() {
  const [data, setData] = useState<GrowthDashboard | null>(null);
  const [busy, setBusy] = useState("");
  const [topic, setTopic] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();

  const campaign = data?.campaigns[0];
  const latestAssets = useMemo(() => data?.assets.slice(0, 18) || [], [data]);

  const load = async () => setData(await api.growth());

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
  }, []);

  const run = async (label: string, action: () => Promise<void>, success: string) => {
    setBusy(label);
    setToast(undefined);
    try {
      await action();
      setToast({ message: success, kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    } finally {
      setBusy("");
    }
  };

  const bootstrap = async () => {
    setData(await api.bootstrapGrowth());
  };

  const generatePack = async () => {
    if (!campaign) throw new Error("Сначала создай Growth-контур.");
    const result = await api.generateGrowthPack(campaign.id, {
      topic: topic.trim() || undefined,
      target_url: targetUrl.trim(),
      create_post: true,
      comments_count: 10,
    });
    setData(result.dashboard);
    setTopic("");
  };

  const copy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setToast({ message: "Скопировано", kind: "success" });
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Growth / Трафик</h1>
          <p className="page-subtitle">
            Отдельный контур для офферов, постов-приманок, вбросов, ручного посева и замера подписок. Публикация только вручную.
          </p>
        </div>
        <span className="status warning">manual only</span>
      </div>

      <Toast message={toast?.message} kind={toast?.kind} />

      <section className="panel">
        <div className="section-title">
          <div>
            <h2>1. Контур «Схема дня»</h2>
            <p className="muted">Создает MAX-канал в ERA, кампанию запуска, источники ручного трафика и первый закреп.</p>
          </div>
          <span className={`status ${campaign ? "active" : "warning"}`}>{campaign ? "создан" : "не создан"}</span>
        </div>
        {campaign ? (
          <div className="mini-log">
            <div>Кампания: {campaign.name}</div>
            <div>Канал: {campaign.target_channel?.name || campaign.target_channel_id}</div>
            <div>Оффер: {campaign.offer}</div>
            <div>Ограничения: без гарантий дохода, без купленных баз, без массового спама</div>
          </div>
        ) : null}
        <div className="actions">
          <SafeActionButton disabled={busy === "bootstrap"} onClick={() => run("bootstrap", bootstrap, "Growth-контур создан/обновлен.")}>
            <Rocket size={16} /> Создать / обновить «Схема дня»
          </SafeActionButton>
          <button className="btn secondary" disabled={busy === "refresh"} onClick={() => run("refresh", load, "Данные обновлены.")}>
            <RefreshCw size={16} /> Обновить
          </button>
        </div>
      </section>

      <section className="grid two">
        <article className="panel">
          <div className="section-title">
            <div>
              <h2>Метрики</h2>
              <p className="muted">Ручной учет посева и результата.</p>
            </div>
            <TrendingUp size={20} />
          </div>
          <div className="kpi-grid">
            <div className="kpi"><span>Кампании</span><strong>{data?.totals.campaigns || 0}</strong></div>
            <div className="kpi"><span>Активы</span><strong>{data?.totals.assets || 0}</strong></div>
            <div className="kpi"><span>Посевы</span><strong>{data?.totals.placements || 0}</strong></div>
            <div className="kpi"><span>Клики</span><strong>{data?.totals.clicks || 0}</strong></div>
            <div className="kpi"><span>Подписки</span><strong>{data?.totals.joins || 0}</strong></div>
            <div className="kpi"><span>Баны/жалобы</span><strong>{(data?.totals.bans || 0) + (data?.totals.complaints || 0)}</strong></div>
          </div>
        </article>

        <article className="panel">
          <div className="section-title">
            <div>
              <h2>2. Сгенерировать traffic-pack</h2>
              <p className="muted">Создает draft-пост, пост-приманку и 10 вбросов для ручного размещения.</p>
            </div>
            <PlusCircle size={20} />
          </div>
          <div className="form-grid">
            <label>
              Тема / крючок
              <input className="input" value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="Например: Как каналы обещают 300к" />
            </label>
            <label>
              Ссылка на MAX-пост / прокладку
              <input className="input" value={targetUrl} onChange={(event) => setTargetUrl(event.target.value)} placeholder="можно оставить пустым и подставить позже" />
            </label>
          </div>
          <div className="actions">
            <SafeActionButton disabled={busy === "generate"} disabledReason={!campaign ? "Сначала создай Growth-контур." : ""} onClick={() => run("generate", generatePack, "Traffic-pack создан.")}>
              <Rocket size={16} /> Собрать pack
            </SafeActionButton>
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="section-title">
          <div>
            <h2>Площадки для ручного посева</h2>
            <p className="muted">Система не рассылает сама. Оператор берет тексты и вносит результат после размещений.</p>
          </div>
          <span className="status">{data?.traffic_sources.length || 0}</span>
        </div>
        <div className="post-grid">
          {(data?.traffic_sources || []).map((source) => (
            <article className="row-card" key={source.id}>
              <div className="section-title">
                <div>
                  <h3>{source.name}</h3>
                  <p className="muted">{source.platform} · {source.category}</p>
                </div>
                <span className={`status ${source.risk_level === "low" ? "active" : "warning"}`}>{source.risk_level}</span>
              </div>
              <p>{source.notes}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-title">
          <div>
            <h2>Последние assets</h2>
            <p className="muted">Копируй и используй вручную: закрепы, посты-приманки, вбросы.</p>
          </div>
          <span className="status">{latestAssets.length}</span>
        </div>
        <div className="post-grid">
          {latestAssets.map((asset) => <AssetCard key={asset.id} asset={asset} onCopy={copy} />)}
          {!latestAssets.length ? <p className="muted">Пока пусто. Нажми «Создать / обновить Схема дня».</p> : null}
        </div>
      </section>
    </>
  );
}
