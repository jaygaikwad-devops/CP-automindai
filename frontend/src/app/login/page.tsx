"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";

type Step = "phone" | "otp";

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [countdown, setCountdown] = useState(0);

  const handleRequestOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.requestOTP(phone);
      setStep("otp");
      // Start 60 second countdown for resend
      setCountdown(60);
      const interval = setInterval(() => {
        setCountdown((c) => {
          if (c <= 1) {
            clearInterval(interval);
            return 0;
          }
          return c - 1;
        });
      }, 1000);
    } catch (err: unknown) {
      const apiErr = err as { error?: { message?: string; retry_after?: number } };
      if (apiErr?.error?.retry_after) {
        setError(`Too many requests. Retry in ${Math.ceil(apiErr.error.retry_after / 60)} minutes.`);
      } else {
        setError(apiErr?.error?.message || "Failed to send OTP. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const result = await api.verifyOTP(phone, otp);
      setToken(result.token);

      if (result.is_new_user) {
        router.push("/register");
      } else {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      const apiErr = err as { status?: number; error?: { message?: string; attempts_remaining?: number; unlock_at?: string } };
      if (apiErr?.status === 423) {
        setError("Account locked. Please try again in 15 minutes.");
      } else if (apiErr?.error?.attempts_remaining !== undefined) {
        setError(`Invalid OTP. ${apiErr.error.attempts_remaining} attempts remaining.`);
      } else {
        setError(apiErr?.error?.message || "Invalid OTP. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-blue-100 p-4">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-gray-900">AutoMind</h1>
            <p className="text-sm text-gray-500 mt-2">CP Portal Login</p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
              {error}
            </div>
          )}

          {step === "phone" ? (
            <form onSubmit={handleRequestOTP} className="space-y-4">
              <div>
                <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-1">
                  Phone Number
                </label>
                <div className="flex">
                  <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                    +91
                  </span>
                  <input
                    id="phone"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))}
                    placeholder="9876543210"
                    className="flex-1 min-w-0 block w-full px-3 py-2.5 rounded-r-lg border border-gray-300 focus:ring-primary-500 focus:border-primary-500 text-sm"
                    required
                    maxLength={10}
                    pattern="[6-9][0-9]{9}"
                    autoComplete="tel"
                  />
                </div>
                <p className="mt-1 text-xs text-gray-500">10-digit mobile number starting with 6-9</p>
              </div>

              <button
                type="submit"
                disabled={loading || phone.length !== 10}
                className="w-full py-2.5 px-4 bg-primary-600 text-white rounded-lg font-medium text-sm hover:bg-primary-700 focus:ring-4 focus:ring-primary-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? "Sending..." : "Send OTP"}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyOTP} className="space-y-4">
              <div>
                <label htmlFor="otp" className="block text-sm font-medium text-gray-700 mb-1">
                  Enter OTP
                </label>
                <input
                  id="otp"
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="123456"
                  className="w-full px-3 py-2.5 rounded-lg border border-gray-300 focus:ring-primary-500 focus:border-primary-500 text-sm text-center tracking-widest text-lg"
                  required
                  maxLength={6}
                  autoComplete="one-time-code"
                  autoFocus
                />
                <p className="mt-1 text-xs text-gray-500">
                  Sent to +91 {phone}
                </p>
              </div>

              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="w-full py-2.5 px-4 bg-primary-600 text-white rounded-lg font-medium text-sm hover:bg-primary-700 focus:ring-4 focus:ring-primary-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? "Verifying..." : "Verify OTP"}
              </button>

              <div className="flex items-center justify-between text-sm">
                <button
                  type="button"
                  onClick={() => { setStep("phone"); setOtp(""); setError(""); }}
                  className="text-primary-600 hover:text-primary-700"
                >
                  Change number
                </button>
                <button
                  type="button"
                  onClick={handleRequestOTP}
                  disabled={countdown > 0}
                  className="text-primary-600 hover:text-primary-700 disabled:text-gray-400"
                >
                  {countdown > 0 ? `Resend in ${countdown}s` : "Resend OTP"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
