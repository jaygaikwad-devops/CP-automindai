"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function AdminProjectsPage() {
  const [name, setName] = useState("");
  const [builderId, setBuilderId] = useState("");
  const [location, setLocation] = useState("");
  const [unitTypes, setUnitTypes] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState("");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    try {
      const data = await api.createProject({
        name,
        builder_id: builderId,
        location,
        unit_types: unitTypes.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setResult(`Project created: ${data.project_id} (status: ${data.status})`);
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

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Create Project</h1>

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

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-lg">
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Project Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Sunshine Heights"
              className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-primary-500 focus:border-primary-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Builder ID</label>
            <input
              type="text"
              value={builderId}
              onChange={(e) => setBuilderId(e.target.value)}
              placeholder="UUID of the builder"
              className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-primary-500 focus:border-primary-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Pune, Maharashtra"
              className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-primary-500 focus:border-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Unit Types</label>
            <input
              type="text"
              value={unitTypes}
              onChange={(e) => setUnitTypes(e.target.value)}
              placeholder="2BHK, 3BHK, 4BHK"
              className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-primary-500 focus:border-primary-500"
            />
            <p className="text-xs text-gray-500 mt-1">Comma separated</p>
          </div>

          <button
            type="submit"
            disabled={loading || !name || !builderId}
            className="w-full py-2.5 px-4 bg-primary-600 text-white rounded-lg font-medium text-sm hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Creating..." : "Create Project"}
          </button>
        </form>
      </div>
    </div>
  );
}
