import type { Metadata } from "next";
import RouteGuard from "@/guards/RouteGuard";
import SellerStoreSettings from "@/components/Seller/Store/StoreSettings";

export const metadata: Metadata = {
  title: "Store Settings | Seller Center",
  description: "Manage your Xerin Market storefront.",
};

export default function SellerStorePage() {
  return (
    <RouteGuard accountTypes={["seller"]} fallbackPath="/my-account">
      <SellerStoreSettings />
    </RouteGuard>
  );
}
