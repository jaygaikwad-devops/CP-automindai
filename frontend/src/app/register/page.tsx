"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import AuthGuard from "@/components/AuthGuard";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [reraId, setReraId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.register(name, reraId);
      router.push("/dashboard");
    } catch (err: unknown) {
      const apiErr = err as { error?: { message?: string; expected?: string } };
      if (apiErr?.error?.expected) {
        setError(`Invalid RERA ID format. Expected: ${apiErr.error.expected}`);
      } else {
        setError(apiErr?.error?.message || "Registration failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthGuard>
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-blue-100 p-4">
        <div className="w-full max-w-sm">
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <div className="text-center mb-8">
              <h1 className="text-2xl font-bold text-gray-900">Complete Profile</h1>
              <p className="text-sm text-gray-500 mt-2">Enter your details to get started</p>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
                {error}
              </div>
            )}

            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                  Full Name
                </label>
                <input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Raj Kumar"
                  className="w-full px-3 py-2.5 rounded-lg border border-gray-300 focus:ring-primary-500 focus:border-primary-500 text-sm"
                  required
                  minLength={1}
                  maxLength={255}
                />
              </div>

              <div>
                <label htmlFor="rera_id" className="block text-sm font-medium text-gray-700 mb-1">
                  RERA ID
                </label>
                <input
                  id="rera_id"
                  type="text"
                  value={reraId}
                  onChange={(e) => setReraId(e.target.value)}
                  placeholder="RERA/MH/2024/12345"
                  className="w-full px-3 py-2.5 rounded-lg border border-gray-300 focus:ring-primary-500 focus:border-primary-500 text-sm"
                  required
                />
                <p className="mt-1 text-xs text-gray-500">
                  Format: RERA/STATE/YEAR/NUMBER
                </p>
              </div>

              <button
                type="submit"
                disabled={loading || !name || !reraId}
                className="w-full py-2.5 px-4 bg-primary-600 text-white rounded-lg font-medium text-sm hover:bg-primary-700 focus:ring-4 focus:ring-primary-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? "Registering..." : "Complete Registration"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
