"use client";

import { ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/useAuthStore";
import {
  hasAllPermissions,
  hasAnyAccountType,
  hasAnyPermission,
  hasAnyRole,
  hasSellerStatus,
} from "./permissions";

type RouteGuardProps = {
  children: ReactNode;
  requireAuth?: boolean;
  permission?: string;
  permissions?: string[];
  anyPermissions?: string[];
  roles?: string[];
  accountTypes?: string[];
  sellerStatuses?: string[];
  fallbackPath?: string;
};

export default function RouteGuard({
  children,
  requireAuth = true,
  permission,
  permissions = [],
  anyPermissions = [],
  roles = [],
  accountTypes = [],
  sellerStatuses = [],
  fallbackPath = "/",
}: RouteGuardProps) {
  const router = useRouter();
  const pathname = usePathname();

  const auth = useAuthStore();
  const user = auth?.user ?? null;

  const isAuthenticated = Boolean(auth?.isAuthenticated || auth?.accessToken || user);

  const requiredPermissions = permission
    ? [permission, ...permissions]
    : permissions;

  const hasRequiredAccess =
    (!requireAuth || isAuthenticated) &&
    hasAllPermissions(user, requiredPermissions) &&
    hasAnyPermission(user, anyPermissions) &&
    hasAnyRole(user, roles) &&
    hasAnyAccountType(user, accountTypes) &&
    hasSellerStatus(user, sellerStatuses);

  useEffect(() => {
    if (requireAuth && !isAuthenticated) {
      const redirectTo = pathname ? `?redirect=${encodeURIComponent(pathname)}` : "";
      router.replace(`/signin${redirectTo}`);
      return;
    }

    if (!hasRequiredAccess) {
      router.replace(fallbackPath);
    }
  }, [fallbackPath, hasRequiredAccess, isAuthenticated, pathname, requireAuth, router]);

  if (!hasRequiredAccess) return null;

  return <>{children}</>;
}
