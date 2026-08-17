import type { Metadata } from "next";
import SellerMessages from "@/components/Seller/Messages";

export const metadata: Metadata = {
  title: "Messages | Seller Center",
  description: "Seller messaging and notifications inbox.",
};

export default function SellerMessagesPage() {
  return (
    <main>
      <SellerMessages />
    </main>
  );
}
