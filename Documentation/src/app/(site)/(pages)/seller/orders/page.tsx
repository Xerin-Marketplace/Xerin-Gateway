import type { Metadata } from "next";
import SellerOrders from "@/components/Seller/Orders";

export const metadata: Metadata = {
  title: "Seller Orders | Xerin Market",
  description: "Manage customer orders in Seller Center.",
};

export default function SellerOrdersPage() {
  return (
    <main>
      <SellerOrders />
    </main>
  );
}
