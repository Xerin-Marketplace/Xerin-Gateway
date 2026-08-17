import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Customer Details | Xerin Admin",
};

export default function CustomerDetailsPage() {
  return <AdminDashboard />;
}
