"use client";

import { ReactNode, useMemo } from "react";
import ProtectedRoute from "./ProtectedRoute";
import { authStorage } from "@/lib/auth/storage";

type RouteUser = {
  account_type?: string;
  roles?: string[];
};

export default function RoleRoute({
  children,
  roles,
  fallbackPath = "/",
}: {
  children: ReactNode;
  roles: string[];
  fallbackPath?: string;
}) {
  const user = authStorage.getUser<RouteUser>();

  const allowed = useMemo(() => {
    if (!user) return false;
    const userRoles = (user.roles ?? []).map((item) => item.toLowerCase());
    const accountType = (user.account_type ?? "").toLowerCase();
    return roles.some((role) => role.toLowerCase() === accountType || userRoles.includes(role.toLowerCase()));
  }, [roles, user]);

  return (
    <ProtectedRoute redirectTo={fallbackPath}>
      {allowed ? children : null}
    </ProtectedRoute>
  );
}
