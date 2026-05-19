"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import {
  BarChart2, Cpu, BookOpen, Search, FlaskConical,
  Briefcase, BookMarked, TrendingUp, Key, LogOut, LogIn,
  Menu, X, Bell,
} from "lucide-react";
import { auth } from "@/lib/auth";

const NAV = [
  { href: "/dashboard",  label: "Dashboard",  icon: BarChart2 },
  { href: "/explore",    label: "Explore",    icon: Search },
  { href: "/watchlist",  label: "Watchlist",  icon: Bell },
  { href: "/ai-analyst", label: "AI Analyst", icon: Cpu },
  { href: "/trade-lab",  label: "Trade Lab",  icon: FlaskConical },
  { href: "/portfolio",  label: "Portfolio",  icon: Briefcase },
  { href: "/learn",      label: "Learn",      icon: BookOpen },
  { href: "/journal",    label: "Journal",    icon: BookMarked },
];

export function Navbar() {
  const pathname = usePathname();
  const [isAuth, setIsAuth] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setIsAuth(auth.isAuthenticated());
    setMobileOpen(false);
  }, [pathname]);

  if (pathname === "/login" || pathname === "/register") return null;

  const isActive = (href: string) =>
    pathname === href || (href !== "/" && pathname?.startsWith(href + "/"));

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-[#0a0a0a]/90 backdrop-blur-xl border-b border-[#1e1e1e]">
      <div className="max-w-[1400px] mx-auto px-4 h-14 flex items-center justify-between gap-3">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-2 font-bold text-base shrink-0">
          <div className="w-7 h-7 bg-white rounded-lg flex items-center justify-center">
            <TrendingUp className="text-black" size={14} strokeWidth={2.5} />
          </div>
          <span className="hidden sm:inline tracking-tight">Market OS</span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden lg:flex items-center gap-0.5 flex-1 overflow-x-auto">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                isActive(href) ? "bg-white text-black" : "text-[#888] hover:text-white hover:bg-[#1a1a1a]"
              }`}
            >
              <Icon size={13} />
              {label}
            </Link>
          ))}
        </div>

        {/* Right actions */}
        <div className="hidden lg:flex items-center gap-1 shrink-0">
          <Link
            href="/settings/api-keys"
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              isActive("/settings") ? "bg-white text-black" : "text-[#888] hover:text-white hover:bg-[#1a1a1a]"
            }`}
          >
            <Key size={13} />
            API Keys
          </Link>
          {isAuth ? (
            <button
              onClick={() => auth.logout()}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-[#888] hover:text-white hover:bg-[#1a1a1a] transition-all"
            >
              <LogOut size={13} />
            </button>
          ) : (
            <Link
              href="/login"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-[#888] hover:text-white hover:bg-[#1a1a1a] transition-all"
            >
              <LogIn size={13} />
              Sign In
            </Link>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="lg:hidden p-2 text-[#888] hover:text-white"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile nav */}
      {mobileOpen && (
        <div className="lg:hidden border-t border-[#1e1e1e] bg-[#0a0a0a] px-4 py-3 space-y-1">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive(href) ? "bg-white text-black" : "text-[#888] hover:text-white hover:bg-[#1a1a1a]"
              }`}
            >
              <Icon size={15} />
              {label}
            </Link>
          ))}
          <div className="border-t border-[#1e1e1e] my-2" />
          <Link href="/settings/api-keys" className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm text-[#888] hover:text-white hover:bg-[#1a1a1a]">
            <Key size={15} /> API Keys
          </Link>
          {isAuth ? (
            <button onClick={() => auth.logout()} className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm text-[#888] hover:text-white hover:bg-[#1a1a1a]">
              <LogOut size={15} /> Logout
            </button>
          ) : (
            <Link href="/login" className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm text-[#888] hover:text-white hover:bg-[#1a1a1a]">
              <LogIn size={15} /> Sign In
            </Link>
          )}
        </div>
      )}
    </nav>
  );
}
