"use client";

import type { ReactNode } from "react";

import { SignedIn, useUser } from "@clerk/nextjs";

import { BrandMark } from "@/components/atoms/BrandMark";
import { UserMenu } from "@/components/organisms/UserMenu";

export function DashboardShell({ children }: { children: ReactNode }) {
  const { user } = useUser();
  const displayName =
    user?.fullName ?? user?.firstName ?? user?.username ?? "Operator";

  return (
    <div className="min-h-screen bg-app text-strong">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between px-6 py-3">
          <BrandMark />
          <SignedIn>
            <div className="flex items-center gap-3">
              <div className="hidden text-right lg:block">
                <p className="text-sm font-semibold text-slate-900">
                  {displayName}
                </p>
                <p className="text-xs text-slate-500">Operator</p>
              </div>
              <UserMenu />
            </div>
          </SignedIn>
        </div>
      </header>
      <div className="grid min-h-[calc(100vh-64px)] grid-cols-[260px_1fr] bg-slate-50">
        {children}
      </div>
    </div>
  );
}
