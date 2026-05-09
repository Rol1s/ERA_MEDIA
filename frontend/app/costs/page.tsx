"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, CostSummary } from "@/lib/api";

function CostTable({ title, data }: { title: string; data: Record<string, number> }) {
  return (
    <section className="panel table-wrap">
      <h2>{title}</h2>
      <table>
        <thead><tr><th>Название</th><th>USD</th></tr></thead>
        <tbody>
          {Object.entries(data).map(([name, value]) => (
            <tr key={name}><td>{name}</td><td>${value.toFixed(6)}</td></tr>
          ))}
        </tbody>
      </table>
      {!Object.keys(data).length ? <p className="muted">Расходов по этой группе сегодня нет.</p> : null}
    </section>
  );
}

export default function CostsPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null);

  useEffect(() => {
    api.costs().then(setSummary);
  }, []);

  const remaining = summary?.budget_remaining || 0;

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Расходы</h1>
          <p className="page-subtitle">Реальная стоимость LLM-вызовов по агентам, каналам и типам задач. Mock-режим не должен маскироваться под реальные расходы.</p>
        </div>
        <Link className="btn secondary" href="/logs">Открыть agent runs</Link>
      </div>
      <section className="stats">
        <div className="stat"><div className="stat-label">Сегодня</div><div className="stat-value">${(summary?.total_estimated_cost_today || 0).toFixed(4)}</div><p className="muted">{summary?.total_estimated_cost_today_rub || 0} RUB</p></div>
        <div className="stat"><div className="stat-label">Бюджет</div><div className="stat-value">${(summary?.budget_daily_total || 0).toFixed(2)}</div><p className="muted">{summary?.budget_daily_total_rub || 0} RUB</p></div>
        <div className="stat"><div className="stat-label">Остаток</div><div className="stat-value">${remaining.toFixed(2)}</div><p className="muted">{summary?.budget_remaining_rub || 0} RUB</p></div>
        <div className="stat"><div className="stat-label">Предупреждения</div><div className="stat-value">{summary?.budget_warnings.length || 0}</div><p className="muted">курс {summary?.rub_rate || 100} RUB/USD</p></div>
      </section>
      {remaining <= 0 ? <section className="panel error-panel">Бюджет исчерпан. Реальные LLM-вызовы должны быть заблокированы до увеличения лимита или следующего дня.</section> : null}
      {summary?.budget_warnings.length ? (
        <section className="panel error-panel">
          {summary.budget_warnings.map((warning: any, index) => (
            <div key={index}>{warning.title || warning.name}: бюджет близко к лимиту</div>
          ))}
        </section>
      ) : null}
      {summary ? (
        <>
          <CostTable title="Расход по агентам" data={summary.by_agent} />
          <CostTable title="Расход по каналам" data={summary.by_channel} />
          <CostTable title="Расход по типам задач" data={summary.by_task_type} />
        </>
      ) : <section className="panel muted">Загружаю расходы...</section>}
    </>
  );
}
