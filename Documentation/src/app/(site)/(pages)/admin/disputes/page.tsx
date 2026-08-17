import AdminDisputes from "@/components/Admin/Disputes";
import AdminSidebar from "@/components/Admin/Layout/Sidebar";

export default function AdminDisputesPage() {
  return (
    <AdminSidebar title="Order Disputes" breadcrumb="Admin / Orders / Disputes">
      <AdminDisputes />
    </AdminSidebar>
  );
}
