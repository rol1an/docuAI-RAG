"use client";

import { Card, Badge } from "@/components/ui";
import { ThemeToggle } from "@/components/theme";
import { Server, Code, Shield, Palette } from "lucide-react";
import { Breadcrumb } from "@/components/layout/breadcrumb";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl pb-8">
      <Breadcrumb />
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Application configuration and preferences
        </p>
      </div>

      <div className="grid gap-4">
        {/* Appearance */}
        <Card className="p-4 sm:p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Palette className="h-5 w-5" />
            Appearance
          </h3>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="font-medium text-sm">Theme</p>
              <p className="text-xs text-muted-foreground">Choose light, dark, or system theme</p>
            </div>
            <ThemeToggle variant="dropdown" />
          </div>
        </Card>

        {/* Application Info */}
        <Card className="p-4 sm:p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Server className="h-5 w-5" />
            Application
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Project</span>
              <span className="font-medium">docuai</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">AI Framework</span>
              <Badge variant="secondary">langchain</Badge>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">LLM Provider</span>
              <Badge variant="secondary">openai</Badge>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Vector Store</span>
              <Badge variant="secondary">pgvector</Badge>
            </div>
          </div>
        </Card>

        {/* Stack Info */}
        <Card className="p-4 sm:p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Code className="h-5 w-5" />
            Stack
          </h3>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">FastAPI</Badge>
            <Badge variant="outline">Next.js 15</Badge>
            <Badge variant="outline">PostgreSQL</Badge>
          </div>
        </Card>

        {/* Security */}
        <Card className="p-4 sm:p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Shield className="h-5 w-5" />
            Security
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Authentication</span>
              <Badge variant="outline">JWT</Badge>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">API Key</span>
              <Badge variant="outline">Enabled</Badge>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
