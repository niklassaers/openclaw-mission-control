"use client";

import Image from "next/image";
import { SignOutButton, useUser } from "@clerk/nextjs";
import { LogOut } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export function UserMenu({ className }: { className?: string }) {
  const { user } = useUser();
  if (!user) return null;

  const avatarUrl = user.imageUrl ?? null;
  const avatarLabelSource = user.firstName ?? user.username ?? user.id ?? "U";
  const avatarLabel = avatarLabelSource.slice(0, 1).toUpperCase();
  const displayName =
    user.fullName ?? user.firstName ?? user.username ?? "Account";
  const displayEmail = user.primaryEmailAddress?.emailAddress ?? "";

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex h-11 items-center rounded-lg border border-transparent px-1 text-slate-900 transition hover:border-slate-200 hover:bg-slate-50",
            className,
          )}
          aria-label="Open user menu"
        >
          <span className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-lg bg-slate-100 text-sm font-semibold text-slate-900 shadow-sm">
            {avatarUrl ? (
              <Image
                src={avatarUrl}
                alt="User avatar"
                width={44}
                height={44}
                className="h-11 w-11 object-cover"
              />
            ) : (
              avatarLabel
            )}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={10}
        className="w-64 rounded-2xl border border-slate-200 bg-white p-0 shadow-lg"
      >
        <div className="border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-lg bg-slate-100 text-sm font-semibold text-slate-900">
              {avatarUrl ? (
                <Image
                  src={avatarUrl}
                  alt="User avatar"
                  width={40}
                  height={40}
                  className="h-10 w-10 object-cover"
                />
              ) : (
                avatarLabel
              )}
            </span>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-slate-900">
                {displayName}
              </div>
              {displayEmail ? (
                <div className="truncate text-xs text-slate-500">{displayEmail}</div>
              ) : null}
            </div>
          </div>
        </div>
        <div className="p-2">
          <SignOutButton>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold text-slate-900 transition hover:bg-slate-100"
            >
              <LogOut className="h-4 w-4 text-slate-500" />
              Sign out
            </button>
          </SignOutButton>
        </div>
      </PopoverContent>
    </Popover>
  );
}
