import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "ERA Media Factory",
  description: "AI media orchestration dashboard for MAX channels"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
