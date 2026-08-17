import PolicyPage from "@/components/Policies/PolicyPage";
import { marketplacePolicies } from "@/content/marketplacePolicies";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Use | Xerin Marketplace",
  description: marketplacePolicies.termsOfUse.summary,
};

export default function TermsOfUsePage() {
  return <PolicyPage policy={marketplacePolicies.termsOfUse} />;
}

