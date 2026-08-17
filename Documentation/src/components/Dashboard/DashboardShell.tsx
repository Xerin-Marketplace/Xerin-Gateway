"use client";

import Link from "next/link";
import { useAuthStore } from "@/store/useAuthStore";
import { dashboardModules, type DashboardModule } from "@/constants/dashboard";
import {
  hasAllPermissions,
  hasAnyAccountType,
  hasAnyPermission,
  hasAnyRole,
  isAdminUser,
  isSellerUser,
  type GuardUser,
} from "@/guards/permissions";

const groupLabels: Record<DashboardModule["group"], string> = {
  buyer: "Buyer",
  seller: "Seller",
  admin: "Admin",
  logistics: "Logistics",
  support: "Support",
};

const canAccessModule = (
  user: GuardUser | null,
  module: DashboardModule
): boolean => {
  const access = module.access;

  if (!access) return true;
  if (access.publicToAuthenticated) return true;
  if (isAdminUser(user)) return true;

  const sellerAllowed = access.sellerOnly ? isSellerUser(user) : false;
  const roleAllowed = hasAnyRole(user, access.roles ?? []);
  const accountTypeAllowed = hasAnyAccountType(user, access.accountTypes ?? []);
  const anyPermissionAllowed = hasAnyPermission(user, access.anyPermissions ?? []);
  const allPermissionsAllowed =
    access.permissions && access.permissions.length > 0
      ? hasAllPermissions(user, access.permissions)
      : false;

  return Boolean(
    sellerAllowed ||
      roleAllowed ||
      accountTypeAllowed ||
      anyPermissionAllowed ||
      allPermissionsAllowed
  );
};

export default function DashboardShell() {
  const auth = useAuthStore();
  const user = (auth?.user ?? null) as GuardUser | null;

  const visibleModules = dashboardModules.filter((module) =>
    canAccessModule(user, module)
  );

  const modulesByGroup = visibleModules.reduce(
    (groups, module) => {
      groups[module.group] = [...(groups[module.group] ?? []), module];
      return groups;
    },
    {} as Partial<Record<DashboardModule["group"], DashboardModule[]>>
  );

  return (
    <section className="overflow-hidden py-20 bg-gray-2">
      <div className="max-w-[1170px] w-full mx-auto px-4 sm:px-8 xl:px-0">
        <div className="mb-10">
          <span className="inline-flex rounded-full bg-blue/10 px-4 py-2 text-sm font-medium text-blue">
            Xerin Dashboard
          </span>

          <h1 className="mt-4 text-2xl sm:text-4xl font-bold text-dark">
            Your workspace
          </h1>

          <p className="mt-3 max-w-[720px] text-dark-4">
            Access the Xerin Market modules available to your account. More
            modules will appear here automatically when your role or permissions
            are updated.
          </p>
        </div>

        <div className="space-y-8">
          {Object.entries(modulesByGroup).map(([group, modules]) => (
            <div key={group}>
              <h2 className="mb-4 text-lg font-semibold text-dark">
                {groupLabels[group as DashboardModule["group"]]} modules
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                {modules.map((module) => {
                  const isReady = module.status === "ready" && module.href;

                  const card = (
                    <div className="h-full rounded-xl bg-white shadow-1 p-6 transition hover:shadow-2">
                      <div className="flex items-start justify-between gap-4">
                        <h3 className="text-lg font-semibold text-dark">
                          {module.title}
                        </h3>

                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${
                            isReady
                              ? "bg-green-100 text-green-700"
                              : "bg-yellow-100 text-yellow-700"
                          }`}
                        >
                          {isReady ? "Ready" : "Coming soon"}
                        </span>
                      </div>

                      <p className="mt-3 text-sm leading-6 text-dark-4">
                        {module.description}
                      </p>

                      <div className="mt-5 text-sm font-medium text-blue">
                        {isReady ? "Open module" : "Planned module"}
                      </div>
                    </div>
                  );

                  return isReady ? (
                    <Link key={module.id} href={module.href as string}>
                      {card}
                    </Link>
                  ) : (
                    <div key={module.id}>{card}</div>
                  );
                })}
              </div>
            </div>
          ))}

          {visibleModules.length === 0 && (
            <div className="rounded-xl bg-white shadow-1 p-8">
              <h2 className="text-xl font-semibold text-dark">
                No dashboard modules available yet
              </h2>
              <p className="mt-3 text-dark-4">
                Your account is active, but no dashboard permissions have been
                assigned yet.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
