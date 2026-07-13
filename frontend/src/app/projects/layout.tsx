"use client";

import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";

export default function ProjectsLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 p-4 pt-16 lg:p-8 lg:pt-8 w-full min-w-0">{children}</main>
      </div>
    </AuthGuard>
  );
}
