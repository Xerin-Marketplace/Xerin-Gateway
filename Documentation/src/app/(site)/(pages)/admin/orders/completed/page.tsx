import { redirect } from "next/navigation";

export default function CompletedOrdersPage() {
  redirect("/admin/dashboard?tab=orders&menu=orders&orders_tab=completed");
}
