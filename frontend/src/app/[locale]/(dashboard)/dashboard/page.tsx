"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent, Button, Skeleton } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks";
import { ROUTES, BACKEND_URL } from "@/lib/constants";
import type { HealthResponse } from "@/types";
import {
  CheckCircle,
  XCircle,
  User,
  ArrowRight,
  MessageSquare,
  Database,
  Settings,
  Activity,
  ExternalLink,
  BookOpen,
} from "lucide-react";
import { listCollections, getCollectionInfo } from "@/lib/rag-api";

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState(false);
  const [ragStats, setRagStats] = useState<{ collections: number; vectors: number } | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await apiClient.get<HealthResponse>("/health");
        setHealth(data);
        setHealthError(false);
      } catch {
        setHealthError(true);
      } finally {
        setHealthLoading(false);
      }
    };

    checkHealth();
    const loadRagStats = async () => {
      try {
        const data = await listCollections();
        let totalVectors = 0;
        for (const name of data.items) {
          try {
            const info = await getCollectionInfo(name);
            totalVectors += info.total_vectors;
          } catch { /* ignore */ }
        }
        setRagStats({ collections: data.items.length, vectors: totalVectors });
      } catch (err) {
        console.error("Failed to load RAG stats:", err);
        setRagStats({ collections: 0, vectors: 0 });
      }
    };
    loadRagStats();
  }, []);

  return (
    <div className="space-y-6 pb-8">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold">
          {getGreeting()}{user?.name ? `, ${user.name}` : user?.email ? `, ${user.email.split("@")[0]}` : ""}
        </h1>
        <p className="text-sm sm:text-base text-muted-foreground">
          Here&apos;s what&apos;s happening with your project.
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">API Status</CardTitle>
            {healthLoading ? (
              <Skeleton className="h-4 w-4 rounded-full" />
            ) : healthError ? (
              <XCircle className="h-4 w-4 text-destructive" />
            ) : (
              <CheckCircle className="h-4 w-4 text-green-500" />
            )}
          </CardHeader>
          <CardContent>
            {healthLoading ? <Skeleton className="h-8 w-16 rounded" /> : (
              <p className="text-2xl font-bold">{healthError ? "Offline" : health?.status || "OK"}</p>
            )}
            {health?.version && (
              <p className="text-xs text-muted-foreground">v{health.version}</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Account</CardTitle>
            <User className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {user?.email ? (
              <p className="text-sm font-medium truncate">{user.email}</p>
            ) : (
              <Skeleton className="h-5 w-40 rounded" />
            )}
            <p className="text-xs text-muted-foreground">
              {user?.role === "admin" ? "Admin" : "User"}
              {user?.created_at && ` · Since ${new Date(user.created_at).toLocaleDateString()}`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">AI Agent</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">langchain</p>
            <p className="text-xs text-muted-foreground">openai provider</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Knowledge Base</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {!ragStats ? <Skeleton className="h-8 w-16 rounded" /> : (
              <p className="text-2xl font-bold">{ragStats.vectors.toLocaleString()}</p>
            )}
            <p className="text-xs text-muted-foreground">
              vectors in {ragStats?.collections ?? 0} collection{ragStats?.collections !== 1 ? "s" : ""}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Quick Actions</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Link href={ROUTES.CHAT}>
            <Card className="cursor-pointer transition-colors hover:bg-accent">
              <CardContent className="flex items-center gap-3 p-4">
                <MessageSquare className="h-5 w-5 text-primary" />
                <div className="flex-1">
                  <p className="text-sm font-medium">Start a Chat</p>
                  <p className="text-xs text-muted-foreground">Talk to the AI agent</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </CardContent>
            </Card>
          </Link>
          <Link href={ROUTES.RAG}>
            <Card className="cursor-pointer transition-colors hover:bg-accent">
              <CardContent className="flex items-center gap-3 p-4">
                <Database className="h-5 w-5 text-primary" />
                <div className="flex-1">
                  <p className="text-sm font-medium">Knowledge Base</p>
                  <p className="text-xs text-muted-foreground">Manage collections & search</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </CardContent>
            </Card>
          </Link>

          <Link href={ROUTES.PROFILE}>
            <Card className="cursor-pointer transition-colors hover:bg-accent">
              <CardContent className="flex items-center gap-3 p-4">
                <Settings className="h-5 w-5 text-primary" />
                <div className="flex-1">
                  <p className="text-sm font-medium">Profile & Settings</p>
                  <p className="text-xs text-muted-foreground">Manage your account</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </CardContent>
            </Card>
          </Link>

          <a href={`${BACKEND_URL}/docs`} target="_blank" rel="noopener noreferrer">
            <Card className="cursor-pointer transition-colors hover:bg-accent">
              <CardContent className="flex items-center gap-3 p-4">
                <BookOpen className="h-5 w-5 text-primary" />
                <div className="flex-1">
                  <p className="text-sm font-medium">API Documentation</p>
                  <p className="text-xs text-muted-foreground">OpenAPI / Swagger docs</p>
                </div>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </CardContent>
            </Card>
          </a>

          <a href="/api/conversations/export" download="conversations_export.json">
            <Card className="cursor-pointer transition-colors hover:bg-accent">
              <CardContent className="flex items-center gap-3 p-4">
                <ArrowRight className="h-5 w-5 text-primary" />
                <div className="flex-1">
                  <p className="text-sm font-medium">Export Conversations</p>
                  <p className="text-xs text-muted-foreground">Download all chats as JSON</p>
                </div>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </CardContent>
            </Card>
          </a>
        </div>
      </div>
    </div>
  );
}
