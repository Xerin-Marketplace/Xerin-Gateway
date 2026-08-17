import PolicyPage from "@/components/Policies/PolicyPage";
import { marketplacePolicies } from "@/content/marketplacePolicies";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Intellectual Property Protection | Xerin Marketplace",
  description: marketplacePolicies.intellectualProperty.summary,
};

export default function IntellectualPropertyPolicyPage() {
  return <PolicyPage policy={marketplacePolicies.intellectualProperty} />;
}

