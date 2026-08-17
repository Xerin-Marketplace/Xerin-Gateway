import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Stock Adjustments | Xerin Admin",
};

export default function AdjustmentsPage() {
  return <AdminDashboard />;
}
