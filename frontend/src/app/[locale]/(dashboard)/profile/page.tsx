
"use client";

import { useState, useRef } from "react";
import { toast } from "sonner";
import { useAuth } from "@/hooks";
import { useAuthStore } from "@/stores";
import { apiClient, ApiError } from "@/lib/api-client";
import type { User } from "@/types";
import {
  Button, Card, CardHeader, CardTitle, CardContent, Input, Label, Badge,
} from "@/components/ui";
import { ThemeToggle } from "@/components/theme";
import { User as UserIcon, Mail, Shield, Settings, Palette, LogOut, Camera } from "lucide-react";
import Image from "next/image";
import { Breadcrumb } from "@/components/layout/breadcrumb";

export default function ProfilePage() {
  const { user, isAuthenticated, logout } = useAuth();
  const { setUser } = useAuthStore();
  const [isEditing, setIsEditing] = useState(false);
  const [editEmail, setEditEmail] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const avatarInputRef = useRef<HTMLInputElement>(null);

  const handleEdit = () => {
    if (!isEditing && user) setEditEmail(user.email);
    setIsEditing(!isEditing);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const updated = await apiClient.patch<User>("/users/me", { email: editEmail });
      setUser(updated);
      toast.success("Profile updated");
      setIsEditing(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update profile");
    } finally { setIsSaving(false); }
  };

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    if (file.size > 2 * 1024 * 1024) { toast.error("Avatar too large. Maximum 2MB."); return; }
    setAvatarUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/users/me/avatar", { method: "POST", body: formData });
      if (!res.ok) { const err = await res.json().catch(() => ({ detail: "Upload failed" })); throw new Error(err.detail || "Upload failed"); }
      const updated = await res.json();
      setUser(updated);
      toast.success("Avatar updated");
    } catch (err) { toast.error(err instanceof Error ? err.message : "Failed to upload avatar"); }
    finally { setAvatarUploading(false); }
  };

  if (!isAuthenticated || !user) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Card className="p-6 sm:p-8 text-center mx-4">
          <p className="text-muted-foreground">Please log in to view your profile.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-8">
      <Breadcrumb />
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <button type="button" onClick={() => avatarInputRef.current?.click()} disabled={avatarUploading}
            className="group relative flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full bg-primary/10">
            {user.avatar_url ? (
              <Image src={`/api/users/avatar/${user.id}`} alt="" width={56} height={56} className="h-full w-full object-cover" unoptimized />
            ) : (
              <UserIcon className="text-primary h-7 w-7" />
            )}
            <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity group-hover:opacity-100">
              <Camera className="h-5 w-5 text-white" />
            </div>
          </button>
          <input ref={avatarInputRef} type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={handleAvatarUpload} className="hidden" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{user.email}</h1>
            <div className="mt-1 flex items-center gap-2">
              {user.role === "admin" && <Badge variant="secondary"><Shield className="mr-1 h-3 w-3" />Admin</Badge>}
              {user.is_active && <Badge variant="outline" className="text-green-600">Active</Badge>}
              {user.created_at && (
                <span className="text-muted-foreground text-xs">Since {new Date(user.created_at).toLocaleDateString()}</span>
              )}
            </div>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={handleEdit} className="h-10 self-start">
          <Settings className="mr-2 h-4 w-4" />
          {isEditing ? "Cancel" : "Edit Profile"}
        </Button>
      </div>

      {/* Main grid */}
      <div className="grid gap-4 lg:grid-cols-5 sm:gap-6">
        {/* Left column */}
        <div className="space-y-4 lg:col-span-3 sm:space-y-6">
          {/* Account Info */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                <Mail className="h-4 w-4" /> Account Information
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="email" className="text-sm">Email Address</Label>
                  <Input id="email" type="email" value={isEditing ? editEmail : user.email}
                    onChange={(e) => setEditEmail(e.target.value)} disabled={!isEditing}
                    className={!isEditing ? "bg-muted" : ""} />
                </div>
                {isEditing && (
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={handleEdit} size="sm">Cancel</Button>
                    <Button onClick={handleSave} disabled={isSaving} size="sm">
                      {isSaving ? "Saving..." : "Save Changes"}
                    </Button>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-4 lg:col-span-2 sm:space-y-6">

          {/* Preferences */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                <Palette className="h-4 w-4" /> Preferences
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Theme</p>
                  <p className="text-muted-foreground text-xs">Color scheme</p>
                </div>
                <ThemeToggle variant="dropdown" />
              </div>
            </CardContent>
          </Card>

          {/* Danger Zone */}
          <Card className="border-destructive/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-destructive flex items-center gap-2 text-sm font-semibold">
                <LogOut className="h-4 w-4" /> Danger Zone
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Sign out</p>
                  <p className="text-muted-foreground text-xs">Sign out from this device</p>
                </div>
                <Button variant="destructive" size="sm" onClick={logout}>Sign Out</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
