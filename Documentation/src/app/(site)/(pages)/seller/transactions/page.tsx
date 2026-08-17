import type { Metadata } from "next";
import SellerTransactions from "@/components/Seller/Transactions";

export const metadata: Metadata = {
  title: "Transactions | Seller Center",
  description: "View seller payment and payout transactions.",
};

export default function SellerTransactionsPage() {
  return (
    <main>
      <SellerTransactions />
    </main>
  );
}
