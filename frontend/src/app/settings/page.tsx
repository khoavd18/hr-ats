"use client";

import { PlaceholderPage } from "@/components/placeholder-page";
import { useAuth } from "@/components/auth-provider";
import { UsersSettings } from "@/components/users-settings";

export default function SettingsPage() {
  const { user } = useAuth();
  return user?.role === "admin" ? <UsersSettings /> : <PlaceholderPage page="settings" />;
}
