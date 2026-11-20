"use client";

import { useAuth } from "@/components/auth-provider";
import { UsersSettings } from "@/components/users-settings";
import { HiringUnitsSettings } from "@/components/hiring-units-settings";
import { EmailTemplatesSettings } from "@/components/email-templates-settings";
import { PrivacySettings } from "@/components/privacy-settings";
import { MailboxSettings } from "@/components/mailbox-settings";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { t } from "@/i18n/vi";

export default function SettingsPage() {
  const { user } = useAuth();
  if (!user || user.role === "recruiter") return null;
  return (
    <Tabs defaultValue={user.role === "admin" ? "users" : "units"} className="space-y-6">
      <TabsList aria-label={t("nav.settings")} className="h-auto flex-wrap">
        {user.role === "admin" && <TabsTrigger value="users">{t("users.title")}</TabsTrigger>}
        {user.role === "admin" && <TabsTrigger value="privacy">{t("privacy.title")}</TabsTrigger>}
        <TabsTrigger value="units">{t("units.title")}</TabsTrigger>
        <TabsTrigger value="email-templates">{t("emailTemplates.title")}</TabsTrigger>
        <TabsTrigger value="mailbox">{t("mailbox.title")}</TabsTrigger>
      </TabsList>
      {user.role === "admin" && (
        <TabsContent value="users">
          <UsersSettings />
        </TabsContent>
      )}
      {user.role === "admin" && (
        <TabsContent value="privacy">
          <PrivacySettings />
        </TabsContent>
      )}
      <TabsContent value="units">
        <HiringUnitsSettings />
      </TabsContent>
      <TabsContent value="email-templates">
        <EmailTemplatesSettings />
      </TabsContent>
      <TabsContent value="mailbox">
        <MailboxSettings />
      </TabsContent>
    </Tabs>
  );
}
