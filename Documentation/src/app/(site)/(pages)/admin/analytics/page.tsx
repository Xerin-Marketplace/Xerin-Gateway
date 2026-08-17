import AdminAnalytics from "@/components/Admin/Analytics";
import AdminSidebar from "@/components/Admin/Layout/Sidebar";

export default function AdminAnalyticsPage() {
  return (
    <AdminSidebar title="Analytics Dashboard" breadcrumb="Admin / Reports & Analytics">
      <AdminAnalytics />
    </AdminSidebar>
  );
}
