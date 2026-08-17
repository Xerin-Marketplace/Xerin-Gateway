import PolicyPage from "@/components/Policies/PolicyPage";
import { marketplacePolicies } from "@/content/marketplacePolicies";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "User Information Legal Enquiry Guide | Xerin Marketplace",
  description: marketplacePolicies.legalEnquiry.summary,
};

export default function LegalEnquiryGuidePage() {
  return <PolicyPage policy={marketplacePolicies.legalEnquiry} />;
}

