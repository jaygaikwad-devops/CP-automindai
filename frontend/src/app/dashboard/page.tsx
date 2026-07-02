"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { DashboardStats, LeadSummary } from "@/types";

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: string;
}) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <span className="text-3xl">{icon}</span>
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 8
      ? "bg-red-100 text-red-800"
      : score >= 5
        ? "bg-orange-100 text-orange-800"
        : "bg-green-100 text-green-800";
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {score}/10
    </span>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [leads, setLeads] = useState<LeadSummary[]>([]);
  const [totalLeads, setTotalLeads] = useState(0);
  const [loading, setLoading] = useState(true);

  const handleHotLead = useCallback((lead: Record<string, unknown>) => {
    const newLead = lead as unknown as LeadSummary;
    setLeads((prev) => {
      // Prepend and keep sorted by score
      const updated = [newLead, ...prev.filter((l) => l.lead_id !== newLead.lead_id)];
      updated.sort((a, b) => b.score - a.score);
      return updated.slice(0, 50);
    });
    setTotalLeads((t) => t + 1);
    // Update hot leads stat
    setStats((s) => s ? { ...s, hot_leads: s.hot_leads + 1 } : s);
  }, []);

  useWebSocket(handleHotLead);

  useEffect(() => {
    async function fetchData() {
      try {
        const [statsData, leadsData] = await Promise.all([
          api.getDashboardStats(),
          api.getHotLeads(),
        ]);
        setStats(statsData);
        setLeads(leadsData.leads);
        setTotalLeads(leadsData.total);
      } catch (err) {
        console.error("Failed to load dashboard:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      {/* Stats grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Tours Shared" value={stats?.tours_shared ?? 0} icon="🔗" />
        <StatCard label="Leads Generated" value={stats?.leads_generated ?? 0} icon="👤" />
        <StatCard label="Hot Leads" value={stats?.hot_leads ?? 0} icon="🔥" />
        <StatCard label="Conversions" value={stats?.conversions ?? 0} icon="✅" />
      </div>

      {/* Hot leads list */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Hot Leads</h2>
            <span className="text-sm text-gray-500">{totalLeads} total</span>
          </div>
        </div>

        {leads.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">No hot leads yet. Share tours to start generating leads!</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full" role="table">
              <thead>
                <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <th className="px-6 py-3">Buyer</th>
                  <th className="px-6 py-3">Project</th>
                  <th className="px-6 py-3">Score</th>
                  <th className="px-6 py-3">Signals</th>
                  <th className="px-6 py-3">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {leads.map((lead) => (
                  <tr key={lead.lead_id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <Link
                        href={`/dashboard/leads/${lead.lead_id}`}
                        className="text-sm font-medium text-primary-600 hover:text-primary-700"
                      >
                        {lead.buyer_name || "Anonymous Buyer"}
                      </Link>
                      {lead.buyer_phone && (
                        <p className="text-xs text-gray-500">{lead.buyer_phone}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">{lead.project_name}</td>
                    <td className="px-6 py-4">
                      <ScoreBadge score={lead.score} />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {lead.signals.slice(0, 3).map((s, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600"
                          >
                            {s.type.replace(/_/g, " ")} (+{s.points})
                          </span>
                        ))}
                        {lead.signals.length > 3 && (
                          <span className="text-xs text-gray-400">
                            +{lead.signals.length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs text-gray-500">
                      {new Date(lead.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
