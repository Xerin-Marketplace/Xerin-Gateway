import type { Metadata } from "next";
import SellerInventoryPage from "@/components/Seller/Inventory";

export const metadata: Metadata = { title: "Seller Inventory | Xerin Market" };

export default function Page() { return <SellerInventoryPage />; }
