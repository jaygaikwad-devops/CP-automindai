"use client";

import { useState, useRef } from "react";
import { api } from "@/lib/api";

const ASSET_TYPES = [
  { value: "image", label: "Images", accept: ".jpg,.jpeg,.png", maxSize: 20 },
  { value: "video", label: "Video", accept: ".mp4", maxSize: 100 },
  { value: "brochure", label: "Brochure (PDF)", accept: ".pdf", maxSize: 20 },
  { value: "floor_plan", label: "Floor Plan", accept: ".jpg,.jpeg,.png,.pdf", maxSize: 20 },
];

interface UploadResult {
  fileName: string;
  status: "success" | "error";
  message: string;
}

export default function AdminAssetsPage() {
  const [projectId, setProjectId] = useState("");
  const [assetType, setAssetType] = useState("image");
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);
  const [triggerError, setTriggerError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const selectedType = ASSET_TYPES.find((t) => t.value === assetType)!;

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || !projectId) return;

    setUploading(true);
    const uploadResults: UploadResult[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const sizeMB = file.size / (1024 * 1024);

      if (sizeMB > selectedType.maxSize) {
        uploadResults.push({
          fileName: file.name,
          status: "error",
          message: `File too large (${sizeMB.toFixed(1)}MB). Max: ${selectedType.maxSize}MB`,
        });
        continue;
      }

      try {
        await api.uploadAsset(projectId, file, assetType);
        uploadResults.push({
          fileName: file.name,
          status: "success",
          message: "Uploaded successfully",
        });
      } catch (err: unknown) {
        const apiErr = err as { error?: { message?: string }; detail?: string };
        uploadResults.push({
          fileName: file.name,
          status: "error",
          message: apiErr?.error?.message || apiErr?.detail || "Upload failed",
        });
      }
    }

    setResults(uploadResults);
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleTriggerProcessing = async () => {
    if (!projectId) return;
    setTriggerError("");
    setTriggerResult(null);

    try {
      const data = await api.triggerProcessing(projectId);
      setTriggerResult(`Processing started: job_id=${data.job_id}, status=${data.status}`);
    } catch (err: unknown) {
      const apiErr = err as { error?: { message?: string }; detail?: string };
      setTriggerError(apiErr?.error?.message || apiErr?.detail || "Failed to trigger processing.");
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Asset Upload & Processing</h1>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-2xl mb-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Project ID</label>
            <input
              type="text"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              placeholder="UUID of the project"
              className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-primary-500 focus:border-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Asset Type</label>
            <select
              value={assetType}
              onChange={(e) => setAssetType(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:ring-primary-500 focus:border-primary-500"
            >
              {ASSET_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label} (max {t.maxSize}MB)
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Upload Files</label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-primary-400 transition-colors">
              <input
                ref={fileInputRef}
                type="file"
                accept={selectedType.accept}
                multiple={assetType === "image"}
                onChange={handleUpload}
                disabled={!projectId || uploading}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className={`cursor-pointer ${!projectId || uploading ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                <div className="text-3xl mb-2">📁</div>
                <p className="text-sm text-gray-600">
                  {uploading ? "Uploading..." : "Click to select files or drag and drop"}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Accepted: {selectedType.accept} • Max: {selectedType.maxSize}MB
                </p>
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* Upload results */}
      {results.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-2xl mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Upload Results</h3>
          <div className="space-y-2">
            {results.map((r, i) => (
              <div
                key={i}
                className={`flex items-center justify-between p-2 rounded text-sm ${
                  r.status === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
                }`}
              >
                <span className="truncate">{r.fileName}</span>
                <span className="text-xs">{r.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trigger processing */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-2xl">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Trigger AI Processing</h2>
        <p className="text-sm text-gray-500 mb-4">
          Requires: minimum 10 images + 1 floor plan uploaded for the project.
        </p>

        {triggerError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {triggerError}
          </div>
        )}
        {triggerResult && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
            {triggerResult}
          </div>
        )}

        <button
          onClick={handleTriggerProcessing}
          disabled={!projectId}
          className="py-2.5 px-6 bg-orange-600 text-white rounded-lg font-medium text-sm hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          🚀 Trigger Processing Pipeline
        </button>
      </div>
    </div>
  );
}
