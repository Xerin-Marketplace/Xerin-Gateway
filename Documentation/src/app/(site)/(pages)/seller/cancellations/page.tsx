import type { Metadata } from "next";
import SellerCancellations from "@/components/Seller/Cancellations";

export const metadata: Metadata = {
  title: "Cancellations | Seller Center",
  description: "Manage order cancellations.",
};

export default function SellerCancellationsPage() {
  return (
    <main>
      <SellerCancellations />
    </main>
  );
}
