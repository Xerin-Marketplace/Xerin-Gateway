import { redirect } from "next/navigation";

export default function CancelledOrdersPage() {
  redirect("/admin/dashboard?tab=orders&menu=orders&orders_tab=cancelled");
}
