"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  Bell,
  Bot,
  Building2,
  CalendarDays,
  CircleDollarSign,
  FileText,
  Gauge,
  Goal,
  History,
  Library,
  ListChecks,
  Plug,
  Radio,
  Repeat,
  ScrollText,
  Waypoints
} from "lucide-react";
import { api } from "@/lib/api";

const nav = [
  { href: "/", label: "Панель", icon: Gauge },
  { href: "/channels", label: "Каналы", icon: Radio },
  { href: "/editions", label: "Выпуски", icon: FileText },
  { href: "/sources", label: "Источники", icon: Waypoints },
  { href: "/source-items", label: "Материалы", icon: FileText },
  { href: "/topics", label: "Темы", icon: ListChecks },
  { href: "/posts", label: "Посты", icon: FileText },
  { href: "/calendar", label: "Календарь", icon: CalendarDays },
  { href: "/integrations", label: "Интеграции", icon: Plug },
  { href: "/notifications", label: "Уведомления", icon: Bell },
  { href: "/issues", label: "Задачи", icon: ListChecks },
  { href: "/org", label: "Оргструктура", icon: Building2 },
  { href: "/goals", label: "Цели", icon: Goal },
  { href: "/routines", label: "Регламенты", icon: Repeat },
  { href: "/costs", label: "Расходы", icon: CircleDollarSign },
  { href: "/activity", label: "Активность", icon: History },
  { href: "/agents", label: "Агенты", icon: Bot },
  { href: "/prompts", label: "Промпты", icon: Library },
  { href: "/logs", label: "Логи", icon: ScrollText }
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    const load = () => api.unreadNotifications().then((value) => setUnread(value.unread)).catch(() => undefined);
    load();
    const timer = setInterval(load, 10000);
    const source = new EventSource("/api/events/stream");
    source.addEventListener("notification_count", (event) => setUnread(Number((event as MessageEvent).data || 0)));
    source.onerror = () => source.close();
    return () => {
      clearInterval(timer);
      source.close();
    };
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">E</div>
          <span>ERA Media Factory</span>
        </div>
        <nav className="nav">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link key={item.href} href={item.href} className={active ? "active" : ""}>
                <Icon size={17} />
                <span>{item.label}</span>
                {item.href === "/notifications" && unread ? <span className="nav-badge">{unread}</span> : null}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="main">
        <div className="command-bar">
          <Link className="btn secondary" href="/topics#create-topic">Создать тему</Link>
          <Link className="btn secondary" href="/topics">Запустить dry-run</Link>
          <Link className="btn secondary" href="/posts">Посты на проверке</Link>
          <Link className="btn secondary" href="/agents">Настройки агентов</Link>
          <Link className="btn secondary" href="/#readiness">Проверить систему</Link>
        </div>
        {children}
      </main>
    </div>
  );
}
