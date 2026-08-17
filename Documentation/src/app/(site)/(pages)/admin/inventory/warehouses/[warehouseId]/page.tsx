import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Warehouse Details | Xerin Admin",
};

export default function WarehouseDetailsPage() {
  return <AdminDashboard />;
}
