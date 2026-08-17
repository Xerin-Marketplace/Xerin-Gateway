"use client";

import { useAuth } from "./useAuth";

export const usePermissions = () => {
  const { user } = useAuth();
  const roles = user?.roles ?? [];

  return {
    hasRole: (role: string) => roles.includes(role),
    isAdmin: roles.includes("admin") || roles.includes("super_admin"),
  };
};
