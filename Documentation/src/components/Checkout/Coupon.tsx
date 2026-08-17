"use client";

import React, { useState } from "react";
import { useApplyCoupon } from "@/hooks/useCartActions";

const Coupon = () => {
  const [code, setCode] = useState("");
  const applyCoupon = useApplyCoupon();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    applyCoupon.mutate(code.trim());
  };

  return (
    <div className="bg-white dark:bg-darkTheme-card shadow-1 rounded-[10px] mt-7.5">
      <div className="border-b border-gray-3 dark:border-darkTheme-border-color py-5 px-4 sm:px-8.5">
        <h3 className="font-medium text-xl text-dark dark:text-white">Have any Coupon Code?</h3>
      </div>

      <div className="py-8 px-4 sm:px-8.5">
        <div className="flex gap-4">
          <input
            type="text"
            name="coupon"
            id="coupon"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Enter coupon code"
            className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
          />

          <button
            type="submit"
            disabled={applyCoupon.isPending || !code.trim()}
            className="inline-flex font-medium text-white bg-blue py-3 px-6 rounded-md ease-out duration-200 hover:bg-blue-dark disabled:opacity-50"
          >
            {applyCoupon.isPending ? "Applying..." : "Apply"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Coupon;
