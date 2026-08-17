"use client";

import MyAccount from "@/components/MyAccount";
import RouteGuard from "@/guards/RouteGuard";
import { isSellerUser } from "@/guards/permissions";
import { useAuthStore } from "@/store/useAuthStore";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function MyAccountClient() {
  const user = useAuthStore(state => state.user);
  const router = useRouter();
  const seller = isSellerUser(user);
  useEffect(() => { if (seller) router.replace("/seller/account"); }, [router, seller]);
  if (seller) return null;
  return (
    <RouteGuard>
      <MyAccount />
    </RouteGuard>
  );
}
