import type { Metadata } from "next";
import SellerEarnings from "@/components/Seller/Earnings";

export const metadata: Metadata = {
  title: "Earnings | Seller Center",
  description: "Track seller earnings, commissions and settlements.",
};

export default function SellerEarningsPage() {
  return (
    <main>
      <SellerEarnings />
    </main>
  );
}
