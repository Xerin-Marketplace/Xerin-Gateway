import { redirect } from "next/navigation";

export default function CatalogCategoriesPage() {
  redirect("/admin/dashboard?menu=catalog&item=categories");
}
