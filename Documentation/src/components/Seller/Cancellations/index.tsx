"use client";

import { X } from "lucide-react";
import SellerUnavailableModule from "@/components/Seller/shared/SellerUnavailableModule";

export default function SellerCancellations() {
  return (
    <SellerUnavailableModule
      title="Cancellations"
      description="Review cancellation requests, approve seller-side cancellations and protect inventory."
      icon={X}
      action="Cancellation management is not available yet. A seller cancellations API is required."
    />
  );
}
