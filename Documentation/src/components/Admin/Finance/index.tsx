"use client";

import UnavailableFeature from "@/components/Admin/Common/UnavailableFeature";

export default function AdminFinance() {
  return (
    <UnavailableFeature
      title="Finance summary is not available yet"
      description="Finance summary, ledger, settlement and reconciliation data will appear here when the backend finance-summary endpoints are available. Payment workspaces are rendered independently from the Payments menu."
    />
  );
}
