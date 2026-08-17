import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Product Inventory | Xerin Admin",
};

export default function ProductInventoryPage() {
  return <AdminDashboard />;
}
