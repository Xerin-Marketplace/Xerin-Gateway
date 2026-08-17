import { Metadata } from "next";
import AdminDashboard from "@/components/Admin/Dashboard";

export const metadata: Metadata = {
  title: "Customer Reviews | Xerin Admin",
};

export default function CustomerReviewsPage() {
  return <AdminDashboard />;
}
