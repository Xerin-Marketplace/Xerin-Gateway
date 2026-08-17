"use client";

import { RotateCcw } from "lucide-react";
import SellerUnavailableModule from "@/components/Seller/shared/SellerUnavailableModule";

export default function SellerReturns() {
  return (
    <SellerUnavailableModule
      title="Returns"
      description="Review and process customer return requests, issue refunds and manage return logistics."
      icon={RotateCcw}
      action="Return management is not available yet. A seller returns workflow API is required."
    />
  );
}
