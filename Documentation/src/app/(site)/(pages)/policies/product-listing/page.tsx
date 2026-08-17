import PolicyPage from "@/components/Policies/PolicyPage";
import { marketplacePolicies } from "@/content/marketplacePolicies";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Product Listing Policy | Xerin Marketplace",
  description: marketplacePolicies.productListing.summary,
};

export default function ProductListingPolicyPage() {
  return <PolicyPage policy={marketplacePolicies.productListing} />;
}

