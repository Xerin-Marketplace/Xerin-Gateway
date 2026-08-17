import type { Metadata } from "next";
import SellerPromotions from "@/components/Seller/Promotions";

export const metadata: Metadata = {
  title: "Promotions | Seller Center",
  description: "Manage seller promotions and campaigns.",
};

export default function SellerPromotionsPage() {
  return (
    <main>
      <SellerPromotions />
    </main>
  );
}
