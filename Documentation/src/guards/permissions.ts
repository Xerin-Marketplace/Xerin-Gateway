export type GuardUser = {
  account_type?: string;
  roles?: string[];
  permissions?: string[];
  is_seller?: boolean;
  seller_status?: string | null;
};

export const getUserPermissions = (user?: GuardUser | null): string[] => {
  return user?.permissions ?? [];
};

export const getUserRoles = (user?: GuardUser | null): string[] => {
  return user?.roles ?? [];
};

export const hasPermission = (
  userOrPermissions: GuardUser | string[] | null | undefined,
  required?: string | null
): boolean => {
  if (!required) return true;

  const permissions = Array.isArray(userOrPermissions)
    ? userOrPermissions
    : getUserPermissions(userOrPermissions);

  return permissions.includes(required);
};

export const hasAllPermissions = (
  user: GuardUser | null | undefined,
  required: string[] = []
): boolean => {
  return required.every((permission) => hasPermission(user, permission));
};

export const hasAnyPermission = (
  user: GuardUser | null | undefined,
  required: string[] = []
): boolean => {
  if (required.length === 0) return true;
  return required.some((permission) => hasPermission(user, permission));
};

export const hasAnyRole = (
  user: GuardUser | null | undefined,
  requiredRoles: string[] = []
): boolean => {
  if (requiredRoles.length === 0) return true;

  const roles = getUserRoles(user);
  return requiredRoles.some((role) => roles.includes(role));
};

export const hasAnyAccountType = (
  user: GuardUser | null | undefined,
  accountTypes: string[] = []
): boolean => {
  if (accountTypes.length === 0) return true;
  if (!user?.account_type) return false;

  return accountTypes.includes(user.account_type);
};

export const hasSellerStatus = (
  user: GuardUser | null | undefined,
  sellerStatuses: string[] = []
): boolean => {
  if (sellerStatuses.length === 0) return true;
  if (!user?.seller_status) return false;

  return sellerStatuses.includes(user.seller_status);
};

export const isAdminUser = (user?: GuardUser | null): boolean => {
  if (!user) return false;

  if (
    hasAnyAccountType(user, ["admin", "super_admin"]) ||
    hasAnyRole(user, ["admin", "super_admin"])
  ) {
    return true;
  }

  const basicRoles = new Set(["buyer", "customer", "seller"]);
  const roles = getUserRoles(user).map((role) => role.toLowerCase());

  // A custom non-marketplace role is a staff role. The backend still decides
  // what that staff user may actually view/do through permissions.
  return roles.some((role) => !basicRoles.has(role));
};

export const isSellerUser = (user?: GuardUser | null): boolean => {
  return Boolean(user?.is_seller) || hasAnyAccountType(user, ["seller"]) || hasAnyRole(user, ["seller"]);
};
