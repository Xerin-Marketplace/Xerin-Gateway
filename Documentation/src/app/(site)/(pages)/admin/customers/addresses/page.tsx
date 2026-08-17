import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Customer Addresses | Xerin Admin",
};

export default function CustomerAddressesPage() {
  return <AdminDashboard />;
}
