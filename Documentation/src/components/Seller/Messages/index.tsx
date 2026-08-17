"use client";

import { MessageSquare } from "lucide-react";
import SellerUnavailableModule from "@/components/Seller/shared/SellerUnavailableModule";

export default function SellerMessages() {
  return (
    <SellerUnavailableModule
      title="Messages"
      description="Communicate with customers and receive marketplace notifications in one inbox."
      icon={MessageSquare}
      action="Seller messaging is not available yet. A seller messaging and notifications API is required."
    />
  );
}
