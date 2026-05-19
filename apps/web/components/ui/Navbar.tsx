"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart2, Brain, BookOpen, Search, FlaskConical, Briefcase, BookMarked, TrendingUp } from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard",   label: "Dashboard",   icon: BarChart2 },
  { href: "/explore",     label: "Explore",     icon: Search },
  { href: "/ai-analyst",  label: "AI Analyst",  icon: Brain },
  { href: "/trade-lab",   label: "Trade Lab",   icon: FlaskConical },
  { href: "/portfolio",   label: "Portfolio",   icon: Briefcase },
  { href: "/learn",       label: "Learn",       icon: BookOpen },
  { href: "/journal",     label: "Journal",     icon: BookMarked },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-gray-950/95 backdrop-blur border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-2 font-bold text-lg">
          <TrendingUp className="text-blue-400" size={22} />
          <span className="hidden sm:inline">AI Market OS</span>
        </Link>

        {/* Navigation */}
        <div className="flex items-center gap-1 overflow-x-auto">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname?.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                  active
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
              >
                <Icon size={15} />
                <span className="hidden md:inline">{label}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
