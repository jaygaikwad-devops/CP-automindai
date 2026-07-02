"use client";

import { useState } from "react";

interface ContactFormProps {
  onSubmit: (name: string, phone: string) => void;
  onClose: () => void;
}

export default function ContactForm({ onSubmit, onClose }: ContactFormProps) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");

  const validatePhone = (value: string) => {
    return /^[6-9]\d{9}$/.test(value);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!name.trim()) {
      setError("Please enter your name.");
      return;
    }

    if (!validatePhone(phone)) {
      setError("Please enter a valid 10-digit Indian mobile number.");
      return;
    }

    onSubmit(name.trim(), phone);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-sm w-full p-6 animate-in slide-in-from-bottom-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Book a Site Visit</h2>
        <p className="text-sm text-gray-500 mb-6">
          Share your details and a representative will contact you shortly.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="buyer-name" className="block text-sm font-medium text-gray-700 mb-1">
              Your Name
            </label>
            <input
              id="buyer-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter your name"
              className="w-full px-3 py-2.5 rounded-lg border border-gray-300 focus:ring-primary-500 focus:border-primary-500 text-sm"
              required
            />
          </div>

          <div>
            <label htmlFor="buyer-phone" className="block text-sm font-medium text-gray-700 mb-1">
              Phone Number
            </label>
            <div className="flex">
              <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                +91
              </span>
              <input
                id="buyer-phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))}
                placeholder="9876543210"
                className="flex-1 min-w-0 block w-full px-3 py-2.5 rounded-r-lg border border-gray-300 focus:ring-primary-500 focus:border-primary-500 text-sm"
                required
                maxLength={10}
                pattern="[6-9][0-9]{9}"
              />
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 px-4 border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 py-2.5 px-4 bg-primary-600 text-white rounded-lg font-medium text-sm hover:bg-primary-700"
            >
              Book Visit
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
