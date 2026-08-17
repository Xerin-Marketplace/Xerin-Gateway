import PolicyPage from "@/components/Policies/PolicyPage";
import { marketplacePolicies } from "@/content/marketplacePolicies";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Integrity Compliance | Xerin Marketplace",
  description: marketplacePolicies.integrityCompliance.summary,
};

export default function IntegrityCompliancePage() {
  return <PolicyPage policy={marketplacePolicies.integrityCompliance} />;
}

