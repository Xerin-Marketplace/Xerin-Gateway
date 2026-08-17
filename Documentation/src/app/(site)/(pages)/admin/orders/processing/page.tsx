import { redirect } from "next/navigation";

export default function ProcessingOrdersPage() {
  redirect("/admin/dashboard?tab=orders&menu=orders&orders_tab=processing");
}
