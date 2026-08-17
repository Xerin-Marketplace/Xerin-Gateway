export type AppRouteMeta = {
  path: string;
  auth?: boolean;
  roles?: string[];
};

export const routeConfig: Record<string, AppRouteMeta> = {
  home: { path: "/" },
  signin: { path: "/signin" },
  signup: { path: "/signup" },
  forgotPassword: { path: "/forgot-password" },
  resetPassword: { path: "/reset-password" },
  verifyOtp: { path: "/verify-otp" },
  sellerRegister: { path: "/seller/register" },
  sellerDashboard: { path: "/seller/dashboard", auth: true, roles: ["seller"] },
  adminDashboard: { path: "/admin/dashboard", auth: true, roles: ["admin", "super_admin"] },
};
