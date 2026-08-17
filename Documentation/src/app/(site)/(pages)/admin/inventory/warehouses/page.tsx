import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Warehouses | Xerin Admin",
};

export default function WarehousesPage() {
  return <AdminDashboard />;
}
