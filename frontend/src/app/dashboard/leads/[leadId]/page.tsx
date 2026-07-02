"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { LeadDetail } from "@/types";

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.leadId as string;
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchLead() {
      try {
        const data = await api.getLeadDetail(leadId);
        setLead(data);
      } catch (err: unknown) {
        const apiErr = err as { status?: number };
        if (apiErr?.status === 404) {
          setError("Lead not found.");
        } else if (apiErr?.status === 403) {
          setError("You don't have access to this lead.");
        } else {
          setError("Failed to load lead details.");
        }
      } finally {
        setLoading(false);
      }
    }
    if (leadId) fetchLead();
  }, [leadId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600 mb-4">{error}</p>
        <button onClick={() => router.back()} className="text-primary-600 hover:underline">
          ← Back to dashboard
        </button>
      </div>
    );
  }

  if (!lead) return null;

  return (
    <div>
      <button
        onClick={() => router.back()}
        className="text-sm text-primary-600 hover:underline mb-4 inline-block"
      >
        ← Back to dashboard
      </button>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {lead.buyer_name || "Anonymous Buyer"}
            </h1>
            {lead.buyer_phone && (
              <p className="text-gray-500 mt-1">{lead.buyer_phone}</p>
            )}
            <p className="text-sm text-gray-500 mt-1">Project: {lead.project_name}</p>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold text-gray-900">{lead.score}</div>
            <div className="text-sm text-gray-500">Lead Score</div>
            <span
              className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-medium ${
                lead.classification === "hot"
                  ? "bg-red-100 text-red-800"
                  : lead.classification === "warm"
                    ? "bg-orange-100 text-orange-800"
                    : "bg-green-100 text-green-800"
              }`}
            >
              {lead.classification}
            </span>
          </div>
        </div>
      </div>

      {/* Signals */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Engagement Signals</h2>
        <div className="space-y-3">
          {lead.signals.map((signal, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
              <span className="text-sm text-gray-700">{signal.type.replace(/_/g, " ")}</span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
                +{signal.points} pts
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Session Events Timeline */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Session Timeline</h2>
        {lead.events.length === 0 ? (
          <p className="text-sm text-gray-500">No session events recorded.</p>
        ) : (
          <div className="space-y-4">
            {lead.events.map((event, i) => (
              <div key={i} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div className="w-2.5 h-2.5 rounded-full bg-primary-500" />
                  {i < lead.events.length - 1 && <div className="w-px flex-1 bg-gray-200 mt-1" />}
                </div>
                <div className="pb-4">
                  <p className="text-sm font-medium text-gray-900">
                    {event.type.replace(/_/g, " ")}
                  </p>
                  <p className="text-xs text-gray-500">
                    {new Date(event.timestamp).toLocaleString()}
                  </p>
                  {Object.keys(event.data).length > 0 && (
                    <pre className="mt-1 text-xs bg-gray-50 rounded p-2 overflow-x-auto">
                      {JSON.stringify(event.data, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
