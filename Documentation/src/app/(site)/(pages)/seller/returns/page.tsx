import type { Metadata } from "next";
import SellerReturns from "@/components/Seller/Returns";

export const metadata: Metadata = {
  title: "Returns | Seller Center",
  description: "Manage customer returns and refunds.",
};

export default function SellerReturnsPage() {
  return (
    <main>
      <SellerReturns />
    </main>
  );
}
