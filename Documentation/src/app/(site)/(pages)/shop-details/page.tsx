import React from "react";
import { redirect } from "next/navigation";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Product Details | Xerin Market",
  description: "View product details, seller information, pricing, and delivery options on Xerin Market.",
  // other metadata
};

const ShopDetailsPage = () => {
  redirect("/shop-with-sidebar");
};

export default ShopDetailsPage;
