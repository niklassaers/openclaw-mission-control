"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Bot, LayoutGrid } from "lucide-react";

import { cn } from "@/lib/utils";

export function DashboardSidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-64 flex-col border-r border-slate-200 bg-white">
      <div className="flex-1 px-3 py-4">
        <p className="px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Navigation
        </p>
        <nav className="mt-3 space-y-1 text-sm">
          <Link
            href="/dashboard"
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-slate-700 transition",
              pathname === "/dashboard"
                ? "bg-blue-100 text-blue-800 font-medium"
                : "hover:bg-slate-100"
            )}
          >
            <BarChart3 className="h-4 w-4" />
            Dashboard
          </Link>
          <Link
            href="/boards"
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-slate-700 transition",
              pathname.startsWith("/boards")
                ? "bg-blue-100 text-blue-800 font-medium"
                : "hover:bg-slate-100"
            )}
          >
            <LayoutGrid className="h-4 w-4" />
            Boards
          </Link>
          <Link
            href="/agents"
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-slate-700 transition",
              pathname.startsWith("/agents")
                ? "bg-blue-100 text-blue-800 font-medium"
                : "hover:bg-slate-100"
            )}
          >
            <Bot className="h-4 w-4" />
            Agents
          </Link>
        </nav>
      </div>
      <div className="border-t border-slate-200 p-4">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="h-2 w-2 rounded-full bg-blue-500" />
          All systems operational
        </div>
      </div>
    </aside>
  );
}
