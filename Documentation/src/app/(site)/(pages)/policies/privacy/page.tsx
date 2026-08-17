import PolicyPage from "@/components/Policies/PolicyPage";
import { marketplacePolicies } from "@/content/marketplacePolicies";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy | Xerin Marketplace",
  description: marketplacePolicies.privacy.summary,
};

export default function PrivacyPolicyPage() {
  return <PolicyPage policy={marketplacePolicies.privacy} />;
}

