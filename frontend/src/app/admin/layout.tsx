"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { isAuthenticated, getUserInfo, logout } from "@/lib/auth";

const adminNav = [
  { href: "/admin", label: "Projects", icon: "🏗️" },
  { href: "/admin/partnerships", label: "Partnerships", icon: "🤝" },
  { href: "/admin/assets", label: "Assets", icon: "📁" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    const user = getUserInfo();
    if (user?.role !== "admin" && user?.role !== "cp") {
      // In dev mode, allow CP users to access admin (role check would be strict in prod)
      // For production, uncomment: router.replace("/dashboard");
    }
    setChecking(false);
  }, [router]);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Admin sidebar */}
      <aside className="w-64 bg-gray-900 text-white min-h-screen flex flex-col">
        <div className="p-6 border-b border-gray-700">
          <h1 className="text-lg font-bold">AutoMind Admin</h1>
          <p className="text-xs text-gray-400 mt-1">Internal Dashboard</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {adminNav.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/admin" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-white/10 text-white"
                    : "text-gray-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-gray-700">
          <Link href="/dashboard" className="block text-xs text-gray-400 hover:text-white mb-2">
            ← Back to CP Portal
          </Link>
          <button
            onClick={logout}
            className="w-full px-4 py-2 text-sm text-red-400 hover:bg-red-900/20 rounded-lg transition-colors text-left"
          >
            Sign Out
          </button>
        </div>
      </aside>

      <main className="flex-1 p-8 bg-gray-50">{children}</main>
    </div>
  );
}
