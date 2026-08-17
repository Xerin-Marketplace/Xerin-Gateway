import type { Metadata } from "next";
import SellerReviews from "@/components/Seller/Reviews";

export const metadata: Metadata = {
  title: "Reviews | Seller Center",
  description: "Manage customer reviews and seller responses.",
};

export default function SellerReviewsPage() {
  return (
    <main>
      <SellerReviews />
    </main>
  );
}
