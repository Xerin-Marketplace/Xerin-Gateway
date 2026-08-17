import type { Metadata } from "next";
import SellerPayouts from "@/components/Seller/Payouts";

export const metadata: Metadata = {
  title: "Payout Requests | Seller Center",
  description: "Request seller payouts and review settlement history.",
};

export default function SellerPayoutsPage() {
  return (
    <main>
      <SellerPayouts />
    </main>
  );
}
