import { redirect } from "next/navigation";

export default function CatalogProductsPage() {
  redirect("/admin/dashboard?menu=catalog&item=products");
}
