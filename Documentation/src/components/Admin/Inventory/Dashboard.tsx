import UnavailableFeature from "@/components/Admin/Common/UnavailableFeature";

export default function AdminInventoryDashboard() {
  return <UnavailableFeature title="Admin inventory is not available yet" description="Existing inventory APIs are seller-owned and cannot be used as a cross-seller admin inventory source. No inventory totals or records are simulated." />;
}
