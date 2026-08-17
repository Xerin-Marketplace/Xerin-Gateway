import { redirect } from "next/navigation";

export default function CatalogPage() {
  redirect("/admin/dashboard?menu=catalog");
}
