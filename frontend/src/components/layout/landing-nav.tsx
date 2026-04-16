"use client";

import Link from "next/link";
import { useAuth } from "@/hooks";
import { ThemeToggle } from "@/components/theme";
import { LanguageSwitcherCompact } from "@/components/language-switcher";
import { APP_NAME, ROUTES } from "@/lib/constants";
import { LogOut, User } from "lucide-react";

interface LandingNavProps {
  signInLabel: string;
  getStartedLabel: string;
  dashboardLabel: string;
}

export function LandingNav({ signInLabel, getStartedLabel, dashboardLabel }: LandingNavProps) {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex justify-center px-4 pt-4">
      <nav className="navbar-beam relative flex h-12 w-full max-w-3xl items-center justify-between rounded-full px-4 sm:px-6">
        <Link href={ROUTES.HOME} className="text-sm font-bold tracking-tight text-foreground">
          {APP_NAME}
        </Link>

        <div className="flex items-center gap-1.5 sm:gap-2">
          <LanguageSwitcherCompact />
          <ThemeToggle />
          {isAuthenticated ? (
            <>
              <Link
                href={ROUTES.DASHBOARD}
                className="rounded-full bg-brand px-4 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-brand-hover"
              >
                {dashboardLabel}
              </Link>
              <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
                <User className="h-3 w-3" />
                {user?.email?.split("@")[0]}
              </span>
              <button
                onClick={logout}
                className="rounded-full p-1.5 text-muted-foreground transition-colors hover:text-foreground"
                title="Logout"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </>
          ) : (
            <>
              <Link
                href={ROUTES.LOGIN}
                className="rounded-full px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                {signInLabel}
              </Link>
              <Link
                href={ROUTES.REGISTER}
                className="hidden rounded-full bg-brand px-4 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-brand-hover sm:inline-flex"
              >
                {getStartedLabel}
              </Link>
            </>
          )}
        </div>
      </nav>
    </div>
  );
}
