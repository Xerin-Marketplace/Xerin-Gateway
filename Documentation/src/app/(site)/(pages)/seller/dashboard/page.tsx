import type { Metadata } from "next";
import SellerDashboard from "@/components/Seller/Dashboard";

export const metadata: Metadata = {
  title: "Seller Dashboard | Xerin Market",
  description: "Monitor seller products, orders, wallet, promotions, reviews, payouts and product Q&A.",
};

const SellerDashboardPage = () => {
  return (
    <main>
      <SellerDashboard />
    </main>
  );
};

export default SellerDashboardPage;