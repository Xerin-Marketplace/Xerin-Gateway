"use client";

import RouteGuard from "@/guards/RouteGuard";
import SellerAccount, { type SellerAccountView } from "./SellerAccount";

export default function SellerAccountGuard({ view }: { view: SellerAccountView }) {
  return <RouteGuard accountTypes={["seller"]} fallbackPath="/my-account"><SellerAccount view={view} /></RouteGuard>;
}
