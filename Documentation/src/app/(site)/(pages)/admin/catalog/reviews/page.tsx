import { redirect } from "next/navigation";

export default function CatalogReviewsPage() {
  redirect("/admin/dashboard?menu=catalog&item=product-reviews");
}
