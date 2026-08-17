"use client";

import { Star, MessageSquare, Info } from "lucide-react";

export default function ReviewsPlaceholder() {
  return (
    <div className="space-y-5">
      <div className="rounded-xl bg-[#f8fafc] p-4 text-sm text-[#64748b]">
        <span className="mb-1 flex items-center gap-2 font-semibold">
          <Info size={16} />
          Reviews are not available yet
        </span>
        The product review API is still being prepared. Once live, you will be
        able to rate and review products from delivered orders here.
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-[#e2e8f0] p-5">
          <div className="mb-3 flex items-center gap-2 text-[#f7941d]">
            <Star size={20} />
            <h3 className="font-bold">Product Reviews</h3>
          </div>
          <p className="text-sm text-[#64748b]">
            Rate purchased products from 1 to 5 stars and share feedback with
            other buyers.
          </p>
        </div>

        <div className="rounded-xl border border-[#e2e8f0] p-5">
          <div className="mb-3 flex items-center gap-2 text-[#f7941d]">
            <MessageSquare size={20} />
            <h3 className="font-bold">Seller Ratings</h3>
          </div>
          <p className="text-sm text-[#64748b]">
            Rate seller communication, packaging, and delivery speed after your
            order is complete.
          </p>
        </div>
      </div>
    </div>
  );
}
