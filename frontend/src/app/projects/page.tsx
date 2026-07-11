"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ProjectSummary, ShareLinkResponse } from "@/types";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    tour_ready: "bg-green-100 text-green-800",
    processing_in_progress: "bg-yellow-100 text-yellow-800",
    processing_failed: "bg-red-100 text-red-800",
    not_started: "bg-gray-100 text-gray-600",
  };
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] || styles.not_started}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [shareModal, setShareModal] = useState<ShareLinkResponse | null>(null);
  const [sharing, setSharing] = useState<string | null>(null);

  useEffect(() => {
    async function fetchProjects() {
      try {
        const data = await api.getProjects();
        setProjects(data.projects);
      } catch (err) {
        console.error("Failed to load projects:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchProjects();
  }, []);

  const handleShare = async (projectId: string) => {
    setSharing(projectId);
    try {
      const link = await api.createShareLink(projectId);
      setShareModal(link);
    } catch (err) {
      console.error("Failed to create share link:", err);
    } finally {
      setSharing(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Projects</h1>

      {projects.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
          <p className="text-gray-500">No projects assigned yet. Contact your admin for project access.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <div key={project.project_id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold text-gray-900">{project.name}</h3>
                <StatusBadge status={project.tour_status} />
              </div>
              {project.location && (
                <p className="text-sm text-gray-500 mb-2">📍 {project.location}</p>
              )}
              {project.unit_types.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-4">
                  {project.unit_types.map((t) => (
                    <span key={t} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {t}
                    </span>
                  ))}
                </div>
              )}
              <button
                onClick={() => handleShare(project.project_id)}
                disabled={project.tour_status !== "tour_ready" || sharing === project.project_id}
                className="w-full mt-2 py-2 px-4 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {sharing === project.project_id ? "Generating..." : "📲 Share on WhatsApp"}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Share Link Modal */}
      {shareModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Share Link Created</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Tour URL</label>
                <div className="flex items-center gap-2">
                  <input
                    readOnly
                    value={shareModal.url}
                    className="flex-1 text-sm px-3 py-2 rounded-lg border border-gray-200 bg-gray-50"
                  />
                  <button
                    onClick={() => copyToClipboard(shareModal.url)}
                    className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg"
                  >
                    Copy
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">WhatsApp Message</label>
                <textarea
                  readOnly
                  value={shareModal.whatsapp_message}
                  rows={4}
                  className="w-full text-sm px-3 py-2 rounded-lg border border-gray-200 bg-gray-50 resize-none"
                />
                <button
                  onClick={() => copyToClipboard(shareModal.whatsapp_message)}
                  className="mt-2 px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700"
                >
                  Copy WhatsApp Message
                </button>
              </div>

              <a
                href={`https://wa.me/?text=${encodeURIComponent(shareModal.whatsapp_message)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full text-center py-2.5 bg-green-600 text-white rounded-lg font-medium text-sm hover:bg-green-700"
              >
                Open WhatsApp
              </a>

              <a
                href={`/tour/?id=${shareModal.link_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full text-center py-2.5 bg-primary-600 text-white rounded-lg font-medium text-sm hover:bg-primary-700 mt-2"
              >
                🏠 Preview Tour
              </a>
            </div>

            <button
              onClick={() => setShareModal(null)}
              className="mt-4 w-full py-2 text-sm text-gray-600 hover:text-gray-800"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
