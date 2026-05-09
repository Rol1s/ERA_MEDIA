"use client";

import Link from "next/link";
import { CalendarClock, Save, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { SafeActionButton, Toast, ru } from "@/components/operator";
import { api, Channel, Post } from "@/lib/api";

const errorText = (error: unknown) => error instanceof Error ? error.message : "Действие не выполнено";

export default function CalendarPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [dates, setDates] = useState<Record<number, string>>({});
  const [toast, setToast] = useState<{ message: string; kind: "info" | "success" | "error" }>();

  const load = async () => {
    const [nextPosts, nextChannels] = await Promise.all([api.posts(), api.channels()]);
    const scheduled = nextPosts.filter((post) => post.scheduled_at);
    setPosts(scheduled);
    setChannels(nextChannels);
    setDates(Object.fromEntries(scheduled.map((post) => [post.id, post.scheduled_at?.slice(0, 16) || ""])));
  };

  useEffect(() => {
    load().catch((error) => setToast({ message: errorText(error), kind: "error" }));
  }, []);

  const grouped = useMemo(() => {
    return posts.reduce<Record<string, Post[]>>((acc, post) => {
      const key = post.scheduled_at ? new Date(post.scheduled_at).toLocaleDateString("ru-RU") : "Без даты";
      acc[key] = [...(acc[key] || []), post];
      return acc;
    }, {});
  }, [posts]);

  const reschedule = async (post: Post) => {
    try {
      await api.schedulePost(post.id, new Date(dates[post.id]).toISOString());
      await load();
      setToast({ message: "Время поста обновлено.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  const unschedule = async (post: Post) => {
    try {
      await api.unschedulePost(post.id);
      await load();
      setToast({ message: "Пост снят с расписания.", kind: "success" });
    } catch (error) {
      setToast({ message: errorText(error), kind: "error" });
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Календарь</h1>
          <p className="page-subtitle">План расписания. Mock и dry-run посты не должны попадать сюда как будущие публикации.</p>
        </div>
      </div>
      <Toast message={toast?.message} kind={toast?.kind} />
      {Object.entries(grouped).map(([date, items]) => (
        <section className="panel table-wrap" key={date}>
          <h2><CalendarClock size={18} /> {date}</h2>
          <table>
            <thead><tr><th>Время</th><th>Канал</th><th>Пост</th><th>Статус</th><th>Действия</th></tr></thead>
            <tbody>
              {items.map((post) => {
                const disabledReason = post.mock_only || !post.publishable ? post.non_publishable_reason || post.not_publishable_reason || "Пост нельзя публиковать." : "";
                return (
                  <tr key={post.id}>
                    <td><input className="input" type="datetime-local" value={dates[post.id] || ""} onChange={(e) => setDates({ ...dates, [post.id]: e.target.value })} /></td>
                    <td>{channels.find((channel) => channel.id === post.channel_id)?.name || post.channel_id}</td>
                    <td><strong>{post.title}</strong><div className="muted">{post.generation_mode.toUpperCase()}</div></td>
                    <td><span className={`status ${post.status}`}>{ru(post.status)}</span></td>
                    <td>
                      <div className="actions">
                        <SafeActionButton className="btn" disabledReason={disabledReason || (!dates[post.id] ? "Выберите дату и время." : "")} onClick={() => reschedule(post)}>
                          <Save size={16} /> Перенести
                        </SafeActionButton>
                        <button className="btn danger" onClick={() => unschedule(post)}><X size={16} /> Снять</button>
                        <Link className="btn secondary" href="/posts">Открыть пост</Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ))}
      {!posts.length ? (
        <section className="panel empty-hint">
          <h2>Запланированных публикаций нет</h2>
          <p>Это нормальное состояние для Step 2.7: public MAX publishing выключен, а dry-run посты остаются в очереди проверки.</p>
          <Link className="btn secondary" href="/posts">Открыть очередь проверки</Link>
        </section>
      ) : null}
    </>
  );
}
