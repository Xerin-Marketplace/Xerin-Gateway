import { redirect } from "next/navigation";

export default function OrderTrackingPage() {
  redirect("/admin/dashboard?tab=orders&menu=orders&orders_tab=tracking");
}
