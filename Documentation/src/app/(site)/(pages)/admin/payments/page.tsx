import { redirect } from "next/navigation";

export default function PaymentsPage() {
  redirect("/admin/payments/transactions");
}
