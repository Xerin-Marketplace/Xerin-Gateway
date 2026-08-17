import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Inventory Overview | Xerin Admin",
};

export default function InventoryPage() {
  return <AdminDashboard />;
}
