import { redirect } from "next/navigation";

export default function CatalogBrandsPage() {
  redirect("/admin/dashboard?menu=catalog&item=brands");
}
