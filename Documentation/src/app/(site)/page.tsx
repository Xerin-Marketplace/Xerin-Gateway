import Home from "@/components/Home";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Xerin Market | Africa's Premier E-Commerce Marketplace",
  description:
    "Browse products listed by sellers on Xerin Market.",
};

export default function HomePage() {
  return (
    <>
      <Home />
    </>
  );
}
