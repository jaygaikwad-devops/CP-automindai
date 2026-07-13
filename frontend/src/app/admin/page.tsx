"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { getUserInfo } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function AdminProjectsPage() {
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [unitTypes, setUnitTypes] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [createdProjectId, setCreatedProjectId] = useState("");

  // Quick actions
  const [quickProjectId, setQuickProjectId] = useState("");
  const [quickLoading, setQuickLoading] = useState(false);
  const [quickResult, setQuickResult] = useState<string | null>(null);

  const user = getUserInfo();
  const cpId = user?.sub || "";

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    try {
      // Step 1: Create project (uses existing builder)
      const data = await api.createProject({
        name,
        builder_id: "1d52eca5-afe2-4f31-bc70-76f0fcf2c20b", // Lodha Group (existing)
        location,
        unit_types: unitTypes.split(",").map((t) => t.trim()).filter(Boolean),
      });

      const projectId = data.project_id;
      setCreatedProjectId(projectId);

      // Step 2: Auto-assign to current CP
      try {
        await api.assignPartnership(cpId, projectId);
      } catch {
        // Partnership might already exist
      }

      // Step 3: Set tour_ready directly
      const token = localStorage.getItem("auth_token");
      await fetch(`${API_BASE}/api/v1/admin/projects/${projectId}/set-tour-ready`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});

      setResult(`✅ Project "${name}" created and assigned to you!\n\nProject ID: ${projectId}\n\nGo to Projects page to generate a share link.`);
      setName("");
      setLocation("");
      setUnitTypes("");
    } catch (err: unknown) {
      const apiErr = err as { error?: { message?: string }; detail?: string };
      setError(apiErr?.error?.message || apiErr?.detail || "Failed to create project.");
    } finally {
      setLoading(false);
    }
  };

  const handleSetTourReady = async () => {
    if (!quickProjectId) return;
    setQuickLoading(true);
    setQuickResult(null);

    try {
      const token = localStorage.getItem("auth_token");
      const res = await fetch(`${API_BASE}/api/v1/admin/projects/${quickProjectId}/set-tour-ready`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setQuickResult("✅ Project is now tour_ready! Go to Projects to generate share links.");
      } else {
        const data = await res.json().catch(() => ({}));
        setQuickResult(`❌ ${data.detail || "Failed to update status"}`);
      }
    } catch {
      setQuickResult("❌ Failed to update project status.");
    } finally {
      setQuickLoading(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Admin Dashboard</h1>
      <p className="text-gray-500 text-sm mb-8">Create projects, assign CPs, and manage tours</p>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}
      {result && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 whitespace-pre-line">{result}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Create Project */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Create New Project</h2>
          <p className="text-xs text-gray-500 mb-4">Project will be auto-assigned to your account</p>

          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Project Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Skyline Residences"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-blue-500 focus:border-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Location *</label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g., Baner, Pune"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-blue-500 focus:border-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Unit Types</label>
              <input
                type="text"
                value={unitTypes}
                onChange={(e) => setUnitTypes(e.target.value)}
                placeholder="1BHK, 2BHK, 3BHK"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-400 mt-1">Comma separated</p>
            </div>

            <button
              type="submit"
              disabled={loading || !name || !location}
              className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg font-medium text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Creating..." : "Create Project & Assign to Me"}
            </button>
          </form>

          {createdProjectId && (
            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-700 font-mono break-all">ID: {createdProjectId}</p>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Set Project Tour Ready</h2>
            <p className="text-xs text-gray-500 mb-4">Skip AI processing — mark project as ready for tour sharing</p>

            <div className="space-y-3">
              <input
                type="text"
                value={quickProjectId}
                onChange={(e) => setQuickProjectId(e.target.value)}
                placeholder="Paste project ID here"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-blue-500 focus:border-blue-500"
              />
              <button
                onClick={handleSetTourReady}
                disabled={quickLoading || !quickProjectId}
                className="w-full py-2.5 px-4 bg-green-600 text-white rounded-lg font-medium text-sm hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                {quickLoading ? "Updating..." : "✓ Set as Tour Ready"}
              </button>
              {quickResult && (
                <p className="text-sm text-gray-600">{quickResult}</p>
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Your Info</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">CP ID:</span>
                <span className="font-mono text-xs text-gray-700 break-all">{cpId}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Builder ID:</span>
                <span className="font-mono text-xs text-gray-700">1d52eca5-afe2-4f31-bc70-76f0fcf2c20b</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Phone:</span>
                <span className="text-gray-700">{user?.phone}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
