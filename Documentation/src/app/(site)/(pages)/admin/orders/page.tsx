import { redirect } from "next/navigation";

export default function AllOrdersPage() {
  redirect("/admin/dashboard?tab=orders&menu=orders&orders_tab=all");
}
