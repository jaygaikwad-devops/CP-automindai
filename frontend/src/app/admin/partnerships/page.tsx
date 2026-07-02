"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function AdminPartnershipsPage() {
  const [cpId, setCpId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [removeId, setRemoveId] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState("");

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    try {
      const data = await api.assignPartnership(cpId, projectId);
      setResult(`Partnership created: ${data.partnership_id}`);
      setCpId("");
      setProjectId("");
    } catch (err: unknown) {
      const apiErr = err as { status?: number; error?: { message?: string }; detail?: string };
      if (apiErr?.status === 409) {
        setError("CP is already assigned to this project.");
      } else if (apiErr?.status === 404) {
        setError("Project or CP not found.");
      } else {
        setError(apiErr?.error?.message || apiErr?.detail || "Failed to assign partnership.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    try {
      await api.removePartnership(removeId);
      setResult(`Partnership ${removeId} removed successfully.`);
      setRemoveId("");
    } catch (err: unknown) {
      const apiErr = err as { error?: { message?: string }; detail?: string };
      setError(apiErr?.error?.message || apiErr?.detail || "Failed to remove partnership.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Partnership Management</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}
      {result && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
          {result}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Assign */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Assign CP to Project</h2>
          <form onSubmit={handleAssign} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">CP ID</label>
              <input
                type="text"
                value={cpId}
                onChange={(e) => setCpId(e.target.value)}
                placeholder="UUID of the CP"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-primary-500 focus:border-primary-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Project ID</label>
              <input
                type="text"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                placeholder="UUID of the project"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-primary-500 focus:border-primary-500"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading || !cpId || !projectId}
              className="w-full py-2.5 px-4 bg-primary-600 text-white rounded-lg font-medium text-sm hover:bg-primary-700 disabled:opacity-50"
            >
              {loading ? "Assigning..." : "Assign Partnership"}
            </button>
          </form>
        </div>

        {/* Remove */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Remove Partnership</h2>
          <form onSubmit={handleRemove} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Partnership ID</label>
              <input
                type="text"
                value={removeId}
                onChange={(e) => setRemoveId(e.target.value)}
                placeholder="UUID of the partnership"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-primary-500 focus:border-primary-500"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading || !removeId}
              className="w-full py-2.5 px-4 bg-red-600 text-white rounded-lg font-medium text-sm hover:bg-red-700 disabled:opacity-50"
            >
              {loading ? "Removing..." : "Remove Partnership"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
