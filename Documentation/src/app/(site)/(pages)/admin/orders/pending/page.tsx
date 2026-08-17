import { redirect } from "next/navigation";

export default function PendingOrdersPage() {
  redirect("/admin/dashboard?tab=orders&menu=orders&orders_tab=pending");
}
