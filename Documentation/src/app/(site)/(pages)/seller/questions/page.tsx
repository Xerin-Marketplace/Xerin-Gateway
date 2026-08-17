import type { Metadata } from "next";
import SellerQuestions from "@/components/Seller/Questions";

export const metadata: Metadata = {
  title: "Product Q&A | Seller Center",
  description: "Answer customer questions about your products.",
};

export default function SellerQuestionsPage() {
  return <main><SellerQuestions /></main>;
}
