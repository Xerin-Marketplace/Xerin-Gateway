import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Low Stock Products | Xerin Admin",
};

export default function LowStockPage() {
  return <AdminDashboard />;
}
