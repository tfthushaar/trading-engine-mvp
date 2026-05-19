import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/ui/Navbar";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Market Intelligence OS",
  description: "AI-powered market analysis and trader decision-support platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-gray-950 text-gray-100 min-h-screen`}>
        <Providers>
          <Navbar />
          <main className="pt-16 min-h-screen">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
