import { redirect } from "next/navigation";

export default function AdminFinancePage() {
  redirect("/admin/payments/transactions");
}
