import Link from "next/link";
import { ThemeToggle } from "@/components/theme";
import { APP_NAME, APP_DESCRIPTION, ROUTES } from "@/lib/constants";
import { Bot, MessageSquare, Database, Shield, Zap, Lock } from "lucide-react";

const features = [
  { icon: MessageSquare, label: "AI Chat" },
  { icon: Database, label: "Knowledge Base" },
  { icon: Shield, label: "Secure Auth" },
  { icon: Zap, label: "Real-time" },
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background min-h-screen lg:grid lg:grid-cols-2">
      {/* Left — hero panel (desktop only) */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-zinc-100 p-10 dark:bg-zinc-950 lg:flex">
        <div className="pointer-events-none absolute inset-0">
          <div className="grid-bg absolute inset-0 opacity-30 dark:opacity-60" />
          <div className="absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand/[0.08] blur-[150px] dark:bg-brand/[0.15]" />
          <div className="absolute right-0 top-0 h-[300px] w-[400px] rounded-full bg-brand/[0.05] blur-[120px] dark:bg-brand/[0.08]" />
        </div>

        <div className="relative z-10">
          <Link href={ROUTES.HOME} className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand">
              <Lock className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold text-zinc-900 dark:text-white">{APP_NAME}</span>
          </Link>
        </div>

        <div className="relative z-10">
          <div className="mb-6 inline-flex items-center rounded-full border border-zinc-200 bg-zinc-200/50 px-3 py-1 text-sm text-zinc-500 dark:border-white/10 dark:bg-white/5 dark:text-zinc-400">
            <Bot className="mr-2 h-3.5 w-3.5 text-brand" />
            {APP_DESCRIPTION}
          </div>
          <h1 className="mb-4 text-4xl font-bold leading-tight tracking-tight text-zinc-900 dark:text-white xl:text-5xl">
            Build intelligent{" "}
            <span className="bg-gradient-to-r from-brand to-brand-hover bg-clip-text text-transparent">
              applications
            </span>{" "}
            faster.
          </h1>
          <p className="max-w-md text-lg leading-relaxed text-zinc-500 dark:text-zinc-400">
            Production-ready platform with AI agents, vector search, and enterprise-grade authentication.
          </p>

          {features.length > 0 && (
            <div className="mt-8 flex flex-wrap gap-3">
              {features.map((f) => (
                <div
                  key={f.label}
                  className="flex items-center gap-2 rounded-full border border-zinc-200 bg-zinc-200/50 px-4 py-2 text-sm text-zinc-600 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300"
                >
                  <f.icon className="h-4 w-4 text-brand" />
                  {f.label}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="relative z-10">
          <blockquote className="border-l-2 border-brand/40 pl-4">
            <p className="text-sm italic leading-relaxed text-zinc-400 dark:text-zinc-500">
              &ldquo;Ship AI-powered apps in days, not months. Everything you need from auth to RAG, pre-configured and ready to deploy.&rdquo;
            </p>
          </blockquote>
        </div>
      </div>

      {/* Right — form (contrasting background) */}
      <div className="flex flex-col bg-zinc-50 dark:bg-zinc-900/50">
        <div className="flex h-14 items-center justify-between px-4 sm:px-8">
          <Link href={ROUTES.HOME} className="text-lg font-bold tracking-tight lg:hidden">
            {APP_NAME}
          </Link>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center px-4 py-8 sm:px-8">
          <div className="w-full max-w-md">{children}</div>
        </div>
      </div>
    </div>
  );
}
