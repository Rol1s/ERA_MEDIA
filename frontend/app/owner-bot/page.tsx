"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Toast } from "@/components/operator";

export default function OwnerBotPage() {
  const [status, setStatus] = useState<any>(null);
  const [chatId, setChatId] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");
  const [toastKind, setToastKind] = useState<"info" | "success" | "error">("info");

  const load = async () => {
    const next = await api.ownerBotStatus();
    setStatus(next);
    setChatId(next.allowed_chat_id || "");
    setEnabled(Boolean(next.enabled));
  };

  useEffect(() => {
    load().catch((error) => {
      setToast(error.message);
      setToastKind("error");
    });
  }, []);

  const run = async (label: string, action: () => Promise<void>, success: string) => {
    setBusy(label);
    setToast("");
    try {
      await action();
      await load();
      setToast(success);
      setToastKind("success");
    } catch (error: any) {
      setToast(error.message || "Не удалось выполнить действие");
      setToastKind("error");
    } finally {
      setBusy("");
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Telegram-пульт владельца</h1>
          <p className="page-subtitle">Бот управляет редакцией через backend: радар, повестка, черновики, approve, publish в MAX.</p>
        </div>
        <span className={`status ${enabled ? "active" : "warning"}`}>{enabled ? "включен" : "выключен"}</span>
      </div>

      <section className="panel">
        <h2>Подключение</h2>
        <p className="muted">1. В интеграциях добавь TELEGRAM_BOT_TOKEN. 2. Напиши боту /start. 3. Скопируй chat_id из ответа сюда. 4. Включи бота.</p>
        <div className="form-grid">
          <label>
            chat_id владельца
            <input className="input" value={chatId} onChange={(event) => setChatId(event.target.value)} placeholder="например 123456789" />
          </label>
          <label>
            Статус
            <select className="select" value={enabled ? "on" : "off"} onChange={(event) => setEnabled(event.target.value === "on")}>
              <option value="off">выключен</option>
              <option value="on">включен</option>
            </select>
          </label>
        </div>
        <div className="actions">
          <button className="btn" disabled={busy === "save"} onClick={() => run("save", async () => api.updateOwnerBotSettings({ enabled, allowed_chat_id: chatId }), "Настройки Telegram-бота сохранены")}>Сохранить</button>
          <button className="btn secondary" disabled={busy === "poll"} onClick={() => run("poll", async () => api.pollOwnerBotOnce(), "Проверил новые сообщения Telegram")}>Проверить сообщения</button>
          <button className="btn secondary" disabled={busy === "test"} onClick={() => run("test", async () => api.sendOwnerBotTest("ERA Media Factory: Telegram-пульт работает."), "Тестовое сообщение отправлено")}>Отправить тест</button>
        </div>
      </section>

      <section className="panel">
        <h2>Команды</h2>
        <div className="mini-log">
          <div>/status — состояние редакции</div>
          <div>/scan — собрать свежие источники</div>
          <div>/radar — показать свежие темы</div>
          <div>/agenda — собрать редакционную повестку</div>
          <div>/brief — показать последнюю повестку</div>
          <div>/draft &lt;topic_id&gt; — написать черновик</div>
          <div>/posts, /post &lt;id&gt;, /approve &lt;id&gt;, /publish &lt;id&gt;, /rewrite &lt;id&gt; текст, /reject &lt;id&gt;</div>
        </div>
      </section>

      <section className="panel">
        <h2>Текущее состояние</h2>
        <pre className="mini-log">{status?.text || "Загрузка..."}</pre>
      </section>

      {toast ? <Toast message={toast} kind={toastKind} onClose={() => setToast("")} /> : null}
    </>
  );
}
