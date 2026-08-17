"use client";

import { ReactNode, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authStorage } from "@/lib/auth/storage";

export default function ProtectedRoute({
  children,
  redirectTo = "/signin",
}: {
  children: ReactNode;
  redirectTo?: string;
}) {
  const router = useRouter();
  const token = authStorage.getAccessToken();

  useEffect(() => {
    if (!token) {
      router.replace(redirectTo);
    }
  }, [token, router, redirectTo]);

  if (!token) return null;
  return <>{children}</>;
}
