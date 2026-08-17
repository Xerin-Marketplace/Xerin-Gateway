import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Customer Support | Xerin Admin",
};

export default function CustomerSupportPage() {
  return <AdminDashboard />;
}
