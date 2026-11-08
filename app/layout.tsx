import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeSync, TopBar } from "@/components/shell";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono-face", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Trading Engine", template: "%s · Trading Engine" },
  description: "Market intelligence powered by neural networks: an LSTM, GRU, temporal CNN and Transformer ensemble, live model training, rule-strategy baselines and plain-language AI analysis.",
  applicationName: "Trading Engine",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

// Sets the theme before first paint so there is no flash between light and dark.
const themeScript = `(function(){try{var t=JSON.parse(localStorage.getItem('te.theme')||'"system"');var d=t==='dark'||(t==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.dataset.theme=d?'dark':'light';}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen font-sans">
        <ThemeSync />
        <TopBar />
        <main className="mx-auto max-w-[1920px] px-3 pb-10 pt-3 sm:px-4">{children}</main>
        <footer className="mx-auto max-w-[1920px] border-t border-line px-4 py-3 text-[11px] text-fg-3">
          Trading Engine. Forecasts come from neural networks trained on historical prices and are for research and education, not financial advice. Market data from Yahoo Finance may be delayed. Charts by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer" className="underline">TradingView</a> Lightweight Charts.
        </footer>
      </body>
    </html>
  );
}
