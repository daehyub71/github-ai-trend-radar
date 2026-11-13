import type { Metadata } from "next";
import { IBM_Plex_Sans_KR, Space_Grotesk } from "next/font/google";

import "./globals.css";

// DESIGN §3 — 본문 IBM Plex Sans KR · 숫자 Space Grotesk
const sans = IBM_Plex_Sans_KR({ weight: ["400", "500", "600", "700"], variable: "--font-sans", preload: false });
const num = Space_Grotesk({ weight: ["500", "600", "700"], subsets: ["latin"], variable: "--font-num" });

export const metadata: Metadata = {
  title: "깃허브 AI 트렌드 레이더",
  description: "스타·포크·기여·사용·언급 다섯 신호로 본 주간 AI 저장소 종합 지수",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={`${sans.variable} ${num.variable}`}>
      <body>{children}</body>
    </html>
  );
}
