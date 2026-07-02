"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PackInfo } from "@/types";

export default function BillingPage() {
  const [packs, setPacks] = useState<PackInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState<string | null>(null);

  useEffect(() => {
    async function fetchPacks() {
      try {
        const data = await api.getCreditPacks();
        setPacks(data);
      } catch (err) {
        console.error("Failed to load credit packs:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchPacks();
  }, []);

  const handlePurchase = async (packType: string) => {
    setPurchasing(packType);
    try {
      const order = await api.purchaseCredits(packType);

      // Open Razorpay checkout
      const options = {
        key: order.razorpay_key_id,
        amount: order.amount_paise,
        currency: "INR",
        name: "AutoMind AI",
        description: `${order.credits} Credits`,
        order_id: order.order_id,
        handler: function () {
          alert("Payment successful! Credits will be added shortly.");
        },
        theme: { color: "#2563eb" },
      };

      // @ts-expect-error Razorpay loaded via script
      const rzp = new window.Razorpay(options);
      rzp.open();
    } catch (err) {
      console.error("Purchase failed:", err);
      alert("Failed to initiate payment. Please try again.");
    } finally {
      setPurchasing(null);
    }
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
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Credit Packs</h1>
      <p className="text-gray-500 mb-8">Purchase credits to generate and share AI virtual tours.</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {packs.map((pack) => (
          <div
            key={pack.pack_type}
            className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col"
          >
            <h3 className="text-lg font-semibold text-gray-900">{pack.name}</h3>
            <div className="mt-4">
              <span className="text-3xl font-bold text-gray-900">
                ₹{(pack.amount_paise / 100).toLocaleString()}
              </span>
            </div>
            <p className="mt-2 text-sm text-gray-500">{pack.credits} credits included</p>
            <p className="text-xs text-gray-400 mt-1">
              ₹{((pack.amount_paise / 100) / pack.credits).toFixed(0)} per credit
            </p>
            <button
              onClick={() => handlePurchase(pack.pack_type)}
              disabled={purchasing === pack.pack_type}
              className="mt-auto pt-6 w-full py-2.5 px-4 bg-primary-600 text-white rounded-lg font-medium text-sm hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {purchasing === pack.pack_type ? "Processing..." : "Buy Now"}
            </button>
          </div>
        ))}
      </div>

      {/* Razorpay script */}
      <script src="https://checkout.razorpay.com/v1/checkout.js" async />
    </div>
  );
}
