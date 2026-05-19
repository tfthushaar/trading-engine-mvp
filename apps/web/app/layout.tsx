import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/ui/Navbar";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "AI Market Intelligence OS",
  description: "AI-powered market analysis and trader decision-support platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-bg text-white min-h-screen font-sans antialiased">
        <Providers>
          <Navbar />
          <main className="pt-14 min-h-screen">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
