import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Customer Management | Xerin Admin",
};

export default function CustomersPage() {
  return <AdminDashboard />;
}
