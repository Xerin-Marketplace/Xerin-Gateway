"use client";

import { ApiError } from "@/lib/api/client";
import {
  type AccessPermission,
  type AccessRole,
  type AccessSession,
  type AccessUser,
  createAccessRole,
  createStaffAccount,
  deleteAccessRole,
  listAccessPermissions,
  listAccessRoles,
  listAccessSessions,
  listAccessUsers,
  updateAccessRole,
  updateAccessRolePermissions,
  updateAccessUser,
  updateUserRoles,
} from "@/lib/api/endpoints/admin";
import { authStorage } from "@/lib/auth/storage";
import { can, isSuperAdmin } from "@/lib/auth/admin-access";
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  KeyRound,
  LockKeyhole,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";

export type UserManagementView =
  | "users"
  | "create-user"
  | "roles"
  | "permissions"
  | "sessions";

type CurrentAdmin = {
  roles?: string[];
  permissions?: string[];
  account_type?: string;
};

const titles: Record<UserManagementView, string> = {
  users: "Staff & User Access",
  "create-user": "Add New User",
  roles: "Roles & Access Control",
  permissions: "Permission Catalogue",
  sessions: "Active Sessions",
};

const descriptions: Record<UserManagementView, string> = {
  users:
    "Search and manage staff access using server-side pagination for a scalable administration workspace.",
  "create-user":
    "Create a staff account and assign one or more roles that determine exactly what the user can view and do.",
  roles:
    "Create reusable roles and choose exactly what users assigned to each role can view or do.",
  permissions:
    "Review the backend permission catalogue used by roles and direct authorization checks.",
  sessions:
    "Review authenticated sessions and revoke access where supported by the backend.",
};

const pretty = (value: string) =>
  value
    .replaceAll(":", " · ")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const roleIsSystem = (role: AccessRole) =>
  ["super_admin", "admin", "customer", "seller"].includes(role.name);

const getError = (error: unknown, fallback: string) =>
  error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : fallback;

export default function AdminUserManagement({
  view,
}: {
  view: UserManagementView;
}) {
  const currentAdmin = authStorage.getUser<CurrentAdmin>();
  const canAssign = isSuperAdmin(currentAdmin) || can(currentAdmin, "can_assign_permissions");
  const canCreateUsers =
    isSuperAdmin(currentAdmin) || can(currentAdmin, "can_create_users");
  const canUpdateUsers =
    isSuperAdmin(currentAdmin) || can(currentAdmin, "can_update_users");

  const [users, setUsers] = useState<AccessUser[]>([]);
  const [roles, setRoles] = useState<AccessRole[]>([]);
  const [permissions, setPermissions] = useState<AccessPermission[]>([]);
  const [sessions, setSessions] = useState<AccessSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalUsers, setTotalUsers] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedUser, setSelectedUser] = useState<AccessUser | null>(null);
  const [selectedRole, setSelectedRole] = useState<AccessRole | null>(null);
  const [showCreateRole, setShowCreateRole] = useState(false);
  const [showCreateStaff, setShowCreateStaff] = useState(false);
  const [busy, setBusy] = useState(false);

  const ensureRoles = async () => {
    if (roles.length) return roles;
    const result = await listAccessRoles();
    setRoles(result);
    return result;
  };

  const ensurePermissions = async () => {
    if (permissions.length) return permissions;
    const result = await listAccessPermissions();
    setPermissions(result);
    return result;
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
      setPage(1);
    }, 350);

    return () => window.clearTimeout(timer);
  }, [query]);

  const load = async () => {
    setLoading(true);
    setError("");

    try {
      if (view === "users") {
        const [userPage, roleRows] = await Promise.all([
          listAccessUsers({
            page,
            page_size: pageSize,
            search: debouncedQuery || undefined,
            status_filter: statusFilter || undefined,
          }),
          listAccessRoles(),
        ]);
        setUsers(userPage.results);
        setTotalUsers(userPage.total);
        setRoles(roleRows);
      }

      if (view === "create-user") {
        setRoles(await listAccessRoles());
      }

      if (view === "roles") {
        const [roleRows, permissionRows] = await Promise.all([
          listAccessRoles(),
          listAccessPermissions(),
        ]);
        setRoles(roleRows);
        setPermissions(permissionRows);
      }

      if (view === "permissions") {
        setPermissions(await listAccessPermissions());
      }

      if (view === "sessions") {
        setSessions(await listAccessSessions());
      }
    } catch (cause) {
      setError(getError(cause, "Unable to load access-control data."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setSelectedUser(null);
    setSelectedRole(null);
    setShowCreateRole(false);
    setShowCreateStaff(false);
    setQuery("");
    setDebouncedQuery("");
    setPage(1);
    setStatusFilter("");
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  useEffect(() => {
    if (view !== "users") return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, debouncedQuery, statusFilter]);

  const rows = useMemo(() => {
    const normalized = query.trim().toLowerCase();

    if (view === "users") {
      // Search and pagination for users are performed by the backend.
      return users;
    }

    if (view === "create-user") {
      return [];
    }

    if (view === "roles") {
      return roles.filter((role) =>
        [role.name, role.description, ...role.permissions]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(normalized),
      );
    }

    if (view === "permissions") {
      return permissions.filter((permission) =>
        [
          permission.code,
          permission.name,
          permission.description,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(normalized),
      );
    }

    return sessions.filter((session) =>
      `${session.user_name} ${session.email}`
        .toLowerCase()
        .includes(normalized),
    );
  }, [permissions, query, roles, sessions, users, view]);

  const metrics =
    view === "users"
      ? [
          ["Total users", totalUsers],
          ["Staff accounts", users.filter((user) => user.roles.some((role) => !["seller", "customer", "buyer"].includes(role))).length],
          ["Active", users.filter((user) => user.status === "active").length],
          ["With roles", users.filter((user) => user.roles.length > 0).length],
        ]
      : view === "create-user"
        ? [
            ["Available roles", roles.length],
            ["Custom roles", roles.filter((role) => !roleIsSystem(role)).length],
            ["Account status", "Active"],
            ["Verification", "Verified"],
          ]
      : view === "roles"
        ? [
            ["Roles", roles.length],
            ["Custom roles", roles.filter((role) => !roleIsSystem(role)).length],
            ["Assigned users", roles.reduce((sum, role) => sum + role.users_count, 0)],
            ["Permission links", roles.reduce((sum, role) => sum + role.permissions.length, 0)],
          ]
        : view === "permissions"
          ? [
              ["Permissions", permissions.length],
              ["User access", permissions.filter((permission) => permission.code.includes("user")).length],
              ["Seller access", permissions.filter((permission) => permission.code.includes("seller")).length],
              ["Commerce", permissions.filter((permission) => /(product|order|payment|inventory|refund)/.test(permission.code)).length],
            ]
          : [
              ["Active sessions", sessions.length],
              ["Users online", new Set(sessions.map((session) => session.user_id)).size],
              ["Current account", sessions.filter((session) => session.is_current_user).length],
              ["Expiring today", sessions.filter((session) => new Date(session.expires_at).getTime() - Date.now() < 86_400_000).length],
            ];

  const saveUser = async (
    user: AccessUser,
    nextRoleIds: string[],
    status: string,
  ) => {
    setBusy(true);

    try {
      if (canAssign) {
        await updateUserRoles(user.id, nextRoleIds);
      }

      if (status !== user.status && canUpdateUsers) {
        await updateAccessUser(user.id, { status });
      }

      toast.success("User access updated successfully.");
      setSelectedUser(null);
      await load();
    } catch (cause) {
      toast.error(getError(cause, "Could not update user access."));
    } finally {
      setBusy(false);
    }
  };

  const saveRole = async (
    role: AccessRole,
    details: { name: string; description: string },
    codes: string[],
  ) => {
    setBusy(true);

    try {
      if (!roleIsSystem(role)) {
        await updateAccessRole(role.id, {
          name: details.name,
          description: details.description || null,
        });
      }

      await updateAccessRolePermissions(role.id, codes);
      toast.success("Role permissions updated.");
      setSelectedRole(null);
      await load();
    } catch (cause) {
      toast.error(getError(cause, "Could not update this role."));
    } finally {
      setBusy(false);
    }
  };

  const removeRole = async (role: AccessRole) => {
    if (roleIsSystem(role)) return;

    if (
      !window.confirm(
        `Delete the role "${pretty(role.name)}"? It must not be assigned to any users.`,
      )
    ) {
      return;
    }

    setBusy(true);

    try {
      await deleteAccessRole(role.id);
      toast.success("Role deleted.");
      setSelectedRole(null);
      await load();
    } catch (cause) {
      toast.error(getError(cause, "Could not delete this role."));
    } finally {
      setBusy(false);
    }
  };

  const createRole = async (payload: {
    name: string;
    description: string;
    permissionCodes: string[];
  }) => {
    setBusy(true);

    try {
      await createAccessRole({
        name: payload.name,
        description: payload.description || null,
        permission_codes: payload.permissionCodes,
      });
      toast.success("New role created successfully.");
      setShowCreateRole(false);
      await load();
    } catch (cause) {
      toast.error(getError(cause, "Could not create role."));
    } finally {
      setBusy(false);
    }
  };

  const createStaff = async (payload: {
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
    password: string;
    role_ids: string[];
  }) => {
    setBusy(true);

    try {
      await createStaffAccount({
        ...payload,
        phone: payload.phone || null,
        status: "active",
        is_verified: true,
      });
      toast.success("Staff account created with the selected role access.");
      setShowCreateStaff(false);
      await load();
    } catch (cause) {
      toast.error(getError(cause, "Could not create staff account."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-[#e7ebf0] bg-transparent p-5 sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.2em] text-[#94a3b8]">
              Access governance
            </p>
            <h2 className="mt-2 text-3xl font-semibold text-[#111827]">{titles[view]}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#64748b]">
              {descriptions[view]}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {view === "roles" && canAssign && (
              <button
                type="button"
                onClick={() => setShowCreateRole(true)}
                className="inline-flex h-11 items-center gap-2 rounded-xl border border-[#e1e6ec] bg-white px-4 text-sm font-semibold text-[#111827]"
              >
                <Plus size={16} />
                Create Role
              </button>
            )}

            {view === "users" && canCreateUsers && canAssign && (
              <button
                type="button"
                onClick={async () => {
                  await ensureRoles();
                  setShowCreateStaff(true);
                }}
                className="inline-flex h-11 items-center gap-2 rounded-xl border border-[#e1e6ec] bg-white px-4 text-sm font-semibold text-[#111827]"
              >
                <UserPlus size={16} />
                Add New User
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(([label, value]) => (
          <article
            key={String(label)}
            className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm"
          >
            <p className="text-sm text-gray-500">{label}</p>
            <p className="mt-2 text-2xl font-semibold text-[#111827]">
              {value}
            </p>
          </article>
        ))}
      </section>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {view === "create-user" ? (
        <CreateStaffWorkspace
          roles={roles}
          busy={busy}
          canCreate={canCreateUsers && canAssign}
          onCreate={createStaff}
        />
      ) : (
      <section className="overflow-hidden rounded-2xl border border-[#e7ebf0] bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-[#edf0f4] p-5 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <Search
              size={16}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94a3b8]"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={`Search ${titles[view].toLowerCase()}`}
              className="h-11 w-full rounded-xl border border-[#e1e6ec] bg-[#f8fafc] pl-10 pr-4 text-sm outline-none focus:border-[#f47524]"
            />
          </div>

          {view === "users" && (
            <>
              <select
                value={statusFilter}
                onChange={(event) => {
                  setStatusFilter(event.target.value);
                  setPage(1);
                }}
                className="h-11 rounded-xl border border-[#e1e6ec] bg-white px-3 text-sm outline-none"
              >
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="suspended">Suspended</option>
                <option value="pending_verification">Pending verification</option>
              </select>

              <select
                value={pageSize}
                onChange={(event) => {
                  setPageSize(Number(event.target.value));
                  setPage(1);
                }}
                className="h-11 rounded-xl border border-[#e1e6ec] bg-white px-3 text-sm outline-none"
              >
                <option value={10}>10 / page</option>
                <option value={25}>25 / page</option>
                <option value={50}>50 / page</option>
              </select>
            </>
          )}

          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-[#e1e6ec] px-4 text-sm font-semibold text-[#475569]"
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="p-12 text-center text-gray-500">
            <RefreshCw className="mx-auto animate-spin" size={20} />
            <p className="mt-3 text-sm">Loading access data...</p>
          </div>
        ) : rows.length === 0 ? (
          <p className="p-12 text-center text-gray-500">
            No matching records.
          </p>
        ) : view === "users" ? (
          <UsersTable
            rows={rows as AccessUser[]}
            canManage={canAssign || canUpdateUsers}
            onSelect={setSelectedUser}
          />
        ) : view === "roles" ? (
          <RolesTable
            rows={rows as AccessRole[]}
            canManage={canAssign}
            onSelect={setSelectedRole}
          />
        ) : view === "permissions" ? (
          <PermissionsGrid rows={rows as AccessPermission[]} />
        ) : (
          <SessionsTable rows={rows as AccessSession[]} />
        )}

        {view === "users" && totalUsers > 0 && (
          <Pagination
            page={page}
            pageSize={pageSize}
            total={totalUsers}
            onPageChange={setPage}
          />
        )}
      </section>
      )}

      {selectedUser && (
        <UserDrawer
          user={selectedUser}
          roles={roles}
          loadRoles={ensureRoles}
          canAssign={canAssign}
          canUpdate={canUpdateUsers}
          busy={busy}
          onClose={() => setSelectedUser(null)}
          onSave={saveUser}
        />
      )}

      {selectedRole && (
        <RoleDrawer
          role={selectedRole}
          permissions={permissions}
          loadPermissions={ensurePermissions}
          busy={busy}
          onClose={() => setSelectedRole(null)}
          onSave={saveRole}
          onDelete={removeRole}
        />
      )}

      {showCreateRole && (
        <CreateRoleModal
          permissions={permissions}
          loadPermissions={ensurePermissions}
          busy={busy}
          onClose={() => setShowCreateRole(false)}
          onCreate={createRole}
        />
      )}

      {showCreateStaff && (
        <CreateStaffModal
          roles={roles}
          busy={busy}
          onClose={() => setShowCreateStaff(false)}
          onCreate={createStaff}
        />
      )}
    </div>
  );
}

function UsersTable({
  rows,
  canManage,
  onSelect,
}: {
  rows: AccessUser[];
  canManage: boolean;
  onSelect: (user: AccessUser) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="bg-[#f8fafc] text-xs uppercase text-gray-500">
          <tr>
            {["User", "Roles", "Effective permissions", "Status", ""].map(
              (heading) => (
                <th key={heading} className="px-5 py-3">
                  {heading}
                </th>
              ),
            )}
          </tr>
        </thead>

        <tbody className="divide-y divide-[#edf0f4]">
          {rows.map((user) => (
            <tr key={user.id} className="hover:bg-orange-50/30">
              <td className="px-5 py-4">
                <p className="font-semibold text-[#111827]">
                  {`${user.first_name || ""} ${user.last_name || ""}`.trim() ||
                    user.email}
                </p>
                <p className="mt-0.5 text-xs text-gray-500">{user.email}</p>
              </td>

              <td className="px-5 py-4">
                <div className="flex max-w-sm flex-wrap gap-1.5">
                  {user.roles.length ? (
                    user.roles.map((role) => (
                      <span
                        key={role}
                        className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700"
                      >
                        {pretty(role)}
                      </span>
                    ))
                  ) : (
                    <span className="text-gray-400">No role</span>
                  )}
                </div>
              </td>

              <td className="px-5 py-4">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                  <KeyRound size={12} />
                  {user.permissions.length}
                </span>
              </td>

              <td className="px-5 py-4">
                <Badge value={user.status} />
              </td>

              <td className="px-5 py-4 text-right">
                {canManage ? (
                  <button
                    type="button"
                    onClick={() => onSelect(user)}
                    className="font-semibold text-[#f47524]"
                  >
                    Manage access
                  </button>
                ) : (
                  <span className="text-xs text-gray-400">View only</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RolesTable({
  rows,
  canManage,
  onSelect,
}: {
  rows: AccessRole[];
  canManage: boolean;
  onSelect: (role: AccessRole) => void;
}) {
  return (
    <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
      {rows.map((role) => {
        const protectedRole = role.name === "super_admin";

        return (
          <article
            key={role.id}
            className="rounded-2xl border border-[#e7ebf0] p-5 transition hover:shadow-md"
          >
            <div className="flex items-start justify-between gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-50 text-[#f47524]">
                <ShieldCheck size={18} />
              </span>

              <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
                {role.users_count} users
              </span>
            </div>

            <h3 className="mt-4 font-semibold text-[#111827]">
              {pretty(role.name)}
            </h3>

            <p className="mt-1 min-h-10 text-xs leading-5 text-gray-500">
              {role.description || "Reusable application access role."}
            </p>

            <div className="mt-5 flex items-end justify-between">
              <div>
                <p className="text-2xl font-semibold text-[#111827]">
                  {role.permissions.length}
                </p>
                <p className="text-xs text-gray-500">permissions</p>
              </div>

              {protectedRole && (
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold uppercase text-slate-600">
                  <LockKeyhole size={11} />
                  Protected
                </span>
              )}
            </div>

            <button
              type="button"
              disabled={!canManage || protectedRole}
              onClick={() => onSelect(role)}
              className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-[#f47524] disabled:cursor-not-allowed disabled:text-gray-400"
            >
              {protectedRole ? "Protected role" : "Manage role"}
              {!protectedRole && <ChevronRight size={14} />}
            </button>
          </article>
        );
      })}
    </div>
  );
}

function PermissionsGrid({ rows }: { rows: AccessPermission[] }) {
  const groups = rows.reduce<Record<string, AccessPermission[]>>(
    (all, permission) => {
      let key = "General";

      if (permission.code.includes(":")) {
        key = permission.code.split(":")[0];
      } else if (permission.code.startsWith("can_")) {
        const parts = permission.code.replace(/^can_/, "").split("_");
        key = parts.length > 1 ? parts[parts.length - 1] : parts[0];
      } else {
        key = permission.code.split("_")[0];
      }

      (all[key] ??= []).push(permission);
      return all;
    },
    {},
  );

  return (
    <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
      {Object.entries(groups).map(([group, items]) => (
        <article
          key={group}
          className="rounded-2xl border border-[#e7ebf0] p-4"
        >
          <h3 className="font-semibold text-[#111827]">{pretty(group)}</h3>

          <div className="mt-3 space-y-2">
            {items.map((permission) => (
              <div
                key={permission.id}
                className="rounded-xl bg-[#f8fafc] p-3"
              >
                <p className="text-sm font-medium text-[#111827]">
                  {pretty(permission.name || permission.code)}
                </p>
                <code className="mt-1 block text-[10px] text-[#f47524]">
                  {permission.code}
                </code>
                <p className="mt-1 text-xs leading-5 text-gray-500">
                  {permission.description || "No description provided."}
                </p>
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function SessionsTable({ rows }: { rows: AccessSession[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="bg-[#f8fafc] text-xs uppercase text-gray-500">
          <tr>
            {["User", "Started", "Expires", "Session"].map((heading) => (
              <th key={heading} className="px-5 py-3">
                {heading}
              </th>
            ))}
          </tr>
        </thead>

        <tbody className="divide-y divide-[#edf0f4]">
          {rows.map((session) => (
            <tr key={session.id}>
              <td className="px-5 py-4">
                <p className="font-semibold">{session.user_name}</p>
                <p className="text-xs text-gray-500">{session.email}</p>
              </td>
              <td className="px-5 py-4">
                {new Date(session.created_at).toLocaleString()}
              </td>
              <td className="px-5 py-4">
                {new Date(session.expires_at).toLocaleString()}
              </td>
              <td className="px-5 py-4">
                <Badge value={session.is_current_user ? "current" : "active"} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UserDrawer({
  user,
  roles,
  loadRoles,
  canAssign,
  canUpdate,
  busy,
  onClose,
  onSave,
}: {
  user: AccessUser;
  roles: AccessRole[];
  loadRoles: () => Promise<AccessRole[]>;
  canAssign: boolean;
  canUpdate: boolean;
  busy: boolean;
  onClose: () => void;
  onSave: (user: AccessUser, roleIds: string[], status: string) => void;
}) {
  const [selectedRoleIds, setSelectedRoleIds] = useState(user.role_ids);
  const [status, setStatus] = useState(user.status);

  useEffect(() => {
    if (!roles.length) void loadRoles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Drawer title="Manage User Access" onClose={onClose}>
      <p className="font-semibold text-[#111827]">{user.email}</p>

      <div className="mt-4 rounded-xl bg-[#f8fafc] p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Effective permissions
        </p>
        <p className="mt-1 text-2xl font-semibold">{user.permissions.length}</p>
        <p className="mt-1 text-xs text-gray-500">
          Calculated from assigned roles and any direct backend permissions.
        </p>
      </div>

      {canUpdate && (
        <label className="mt-5 block text-sm font-medium">
          Account status
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="mt-1.5 w-full rounded-xl border border-[#e1e6ec] px-3 py-2.5"
          >
            {["active", "inactive", "suspended", "pending_verification"].map(
              (value) => (
                <option key={value} value={value}>
                  {pretty(value)}
                </option>
              ),
            )}
          </select>
        </label>
      )}

      <div className="mt-5">
        <p className="text-sm font-medium">Roles</p>
        <p className="mt-1 text-xs text-gray-500">
          The user receives the combined permissions of all selected roles.
        </p>

        <div className="mt-3 space-y-2">
          {roles.map((role) => (
            <label
              key={role.id}
              className="flex items-start gap-3 rounded-xl border border-[#e7ebf0] p-3"
            >
              <input
                type="checkbox"
                className="mt-1"
                disabled={!canAssign}
                checked={selectedRoleIds.includes(role.id)}
                onChange={(event) =>
                  setSelectedRoleIds((current) =>
                    event.target.checked
                      ? [...current, role.id]
                      : current.filter((id) => id !== role.id),
                  )
                }
              />

              <span>
                <b className="text-sm">{pretty(role.name)}</b>
                <small className="mt-0.5 block text-gray-500">
                  {role.permissions.length} permissions
                </small>
              </span>
            </label>
          ))}
        </div>
      </div>

      <button
        type="button"
        disabled={busy || (!canAssign && !canUpdate)}
        onClick={() => onSave(user, selectedRoleIds, status)}
        className="mt-6 w-full rounded-xl bg-[#111827] py-3 font-semibold text-white disabled:opacity-50"
      >
        {busy ? "Saving..." : "Save Access Changes"}
      </button>
    </Drawer>
  );
}

function RoleDrawer({
  role,
  permissions,
  loadPermissions,
  busy,
  onClose,
  onSave,
  onDelete,
}: {
  role: AccessRole;
  permissions: AccessPermission[];
  loadPermissions: () => Promise<AccessPermission[]>;
  busy: boolean;
  onClose: () => void;
  onSave: (
    role: AccessRole,
    details: { name: string; description: string },
    codes: string[],
  ) => void;
  onDelete: (role: AccessRole) => void;
}) {
  const protectedRole = role.name === "super_admin";
  const editableMetadata = !roleIsSystem(role);
  const [name, setName] = useState(role.name);
  const [description, setDescription] = useState(role.description ?? "");
  const [selected, setSelected] = useState(role.permissions);

  useEffect(() => {
    if (!permissions.length) void loadPermissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Drawer title={`Manage ${pretty(role.name)}`} onClose={onClose}>
      {protectedRole && (
        <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          The super-admin role is protected and cannot be edited.
        </div>
      )}

      {editableMetadata && (
        <div className="grid gap-4">
          <Field label="Role name">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="input resize-none"
            />
          </Field>
        </div>
      )}

      <p className="mt-5 text-sm text-gray-500">
        Choose the capabilities inherited by every user assigned to this role.
      </p>

      <PermissionSelector
        permissions={permissions}
        selected={selected}
        disabled={protectedRole}
        onChange={setSelected}
      />

      {!protectedRole && (
        <button
          type="button"
          disabled={busy || !name.trim()}
          onClick={() =>
            onSave(
              role,
              {
                name: name.trim(),
                description: description.trim(),
              },
              selected,
            )
          }
          className="mt-5 w-full rounded-xl bg-[#111827] py-3 font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Saving..." : "Save Role & Permissions"}
        </button>
      )}

      {!roleIsSystem(role) && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onDelete(role)}
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-red-200 py-3 text-sm font-semibold text-red-600 hover:bg-red-50"
        >
          <Trash2 size={15} />
          Delete Role
        </button>
      )}
    </Drawer>
  );
}

function CreateRoleModal({
  permissions,
  loadPermissions,
  busy,
  onClose,
  onCreate,
}: {
  permissions: AccessPermission[];
  loadPermissions: () => Promise<AccessPermission[]>;
  busy: boolean;
  onClose: () => void;
  onCreate: (payload: {
    name: string;
    description: string;
    permissionCodes: string[];
  }) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    if (!permissions.length) void loadPermissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const roleInputClass =
    "mt-3 h-12 w-full rounded-xl border-2 border-[#cfd8e3] bg-white px-4 text-sm font-medium text-[#111827] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[#a8b1bf] hover:border-[#b8c4d2] focus:border-[#f47524] focus:ring-4 focus:ring-orange-100/70";

  return (
    <Modal title="Create New Role" onClose={onClose}>
      <div className="rounded-2xl border-2 border-[#d8e0e9] bg-[#f8fafc] p-5 shadow-[0_3px_12px_rgba(15,23,42,0.04)]">
        <div className="flex items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d8e0e9] bg-white text-sm font-bold text-[#111827]">
            1
          </span>
          <div>
            <h3 className="text-sm font-bold text-[#111827]">Role details</h3>
            <p className="mt-1 text-xs leading-5 text-gray-500">
              Give this role a clear name and explain what responsibility it represents.
            </p>
          </div>
        </div>

        <div className="mt-5 overflow-hidden rounded-2xl border-2 border-[#d8e0e9] bg-white">
          <div className="border-b border-[#e2e8f0] p-4">
            <label className="block">
              <span className="text-sm font-semibold text-[#1f2937]">
                Role name <span className="text-red-500">*</span>
              </span>
              <span className="mt-1 block text-[11px] text-[#94a3b8]">
                Use a clear job or responsibility name that administrators will recognize.
              </span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Finance Manager"
                className={roleInputClass}
              />
            </label>
          </div>

          <div className="p-4">
            <label className="block">
              <span className="text-sm font-semibold text-[#1f2937]">
                Role description
              </span>
              <span className="mt-1 block text-[11px] text-[#94a3b8]">
                Briefly explain the duties and purpose of users assigned to this role.
              </span>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={4}
                placeholder="e.g. Manages payments, refunds, commissions and finance reports."
                className="mt-3 w-full resize-none rounded-xl border-2 border-[#cfd8e3] bg-white px-4 py-3 text-sm font-medium text-[#111827] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[#a8b1bf] hover:border-[#b8c4d2] focus:border-[#f47524] focus:ring-4 focus:ring-orange-100/70"
              />
            </label>
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-2xl border-2 border-[#d8e0e9] bg-[#f8fafc] p-5 shadow-[0_3px_12px_rgba(15,23,42,0.04)]">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d8e0e9] bg-white text-sm font-bold text-[#111827]">
              2
            </span>
            <div>
              <h3 className="text-sm font-bold text-[#111827]">
                Assign permissions
              </h3>
              <p className="mt-1 text-xs leading-5 text-gray-500">
                Select exactly what users with this role are allowed to view or do.
              </p>
            </div>
          </div>

          <span className="shrink-0 rounded-full border border-[#fed7aa] bg-[#fff7ed] px-3 py-1 text-xs font-semibold text-[#f47524]">
            {selected.length} selected
          </span>
        </div>

        <div className="mt-4 rounded-2xl border border-[#e2e8f0] bg-white p-3">
          <PermissionSelector
            permissions={permissions}
            selected={selected}
            onChange={setSelected}
          />
        </div>
      </div>

      <div className="mt-5 rounded-2xl border-2 border-[#d8e0e9] bg-white p-4">
        <div className="mb-4 flex items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d8e0e9] bg-[#f8fafc] text-sm font-bold text-[#111827]">
            3
          </span>
          <div>
            <p className="text-sm font-bold text-[#111827]">Create role</p>
            <p className="mt-1 text-xs text-gray-500">
              Review the role name and selected permissions before creating it.
            </p>
          </div>
        </div>

        {!selected.length && (
          <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800">
            No permissions are selected yet. You can create the role, but users assigned
            to it will not have functional access until permissions are added.
          </div>
        )}

        <button
          type="button"
          disabled={busy || name.trim().length < 2}
          onClick={() =>
            onCreate({
              name: name.trim(),
              description: description.trim(),
              permissionCodes: selected,
            })
          }
          className="w-full rounded-xl bg-[#f47524] py-3 font-semibold text-white shadow-sm transition hover:bg-[#dc651d] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Creating..." : "Create Role"}
        </button>
      </div>
    </Modal>
  );
}

function CreateStaffWorkspace({
  roles,
  busy,
  canCreate,
  onCreate,
}: {
  roles: AccessRole[];
  busy: boolean;
  canCreate: boolean;
  onCreate: (payload: {
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
    password: string;
    role_ids: string[];
  }) => void;
}) {
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    password: "",
  });
  const [roleIds, setRoleIds] = useState<string[]>([]);

  const valid =
    canCreate &&
    form.first_name.trim() &&
    form.last_name.trim() &&
    form.email.trim() &&
    form.password.length >= 8 &&
    roleIds.length > 0;

  if (!canCreate) {
    return (
      <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-800">
        <div className="flex items-start gap-3">
          <AlertTriangle size={20} className="mt-0.5" />
          <div>
            <h3 className="font-semibold">Additional permission required</h3>
            <p className="mt-1 text-sm leading-6">
              Creating a staff account requires both can_create_users and can_assign_permissions.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[#dfe5ec] bg-white p-5 shadow-sm sm:p-6">
      <div className="flex items-start gap-3 border-b border-[#edf0f4] pb-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#e2e8f0] bg-[#f8fafc] text-[#334155]">
          <UserPlus size={19} />
        </span>
        <div>
          <h3 className="text-lg font-semibold text-[#111827]">Create a new staff user</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-[#64748b]">
            Complete the account details below, then select at least one role. Required fields are marked with an asterisk.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,.85fr)]">
        <div className="rounded-2xl border-2 border-[#d8e0e9] bg-[#f8fafc] p-5 shadow-[0_3px_12px_rgba(15,23,42,0.04)] sm:p-6">
          <div className="mb-5 flex items-start gap-3 border-b border-[#e7ebf0] pb-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#e2e8f0] bg-white text-sm font-bold text-[#334155]">1</span>
            <div>
              <h4 className="font-semibold text-[#111827]">User details</h4>
              <p className="mt-1 text-xs leading-5 text-[#64748b]">Enter the staff member's personal and login information.</p>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border-2 border-[#d8e0e9] bg-white">
            <div className="grid sm:grid-cols-2">
              <div className="border-b border-[#e2e8f0] p-4 sm:border-r">
                <label className="block">
                  <span className="text-sm font-semibold text-[#1f2937]">
                    First name <span className="text-red-500">*</span>
                  </span>
                  <span className="mt-1 block text-[11px] text-[#94a3b8]">
                    Staff member&apos;s given name
                  </span>
                  <input
                    className="mt-3 h-12 w-full rounded-xl border-2 border-[#cfd8e3] bg-white px-4 text-sm font-medium text-[#111827] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[#a8b1bf] hover:border-[#b8c4d2] focus:border-[#f47524] focus:ring-4 focus:ring-orange-100/70"
                    placeholder="e.g. Juma"
                    value={form.first_name}
                    onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                  />
                </label>
              </div>

              <div className="border-b border-[#e2e8f0] p-4">
                <label className="block">
                  <span className="text-sm font-semibold text-[#1f2937]">
                    Last name <span className="text-red-500">*</span>
                  </span>
                  <span className="mt-1 block text-[11px] text-[#94a3b8]">
                    Staff member&apos;s family name
                  </span>
                  <input
                    className="mt-3 h-12 w-full rounded-xl border-2 border-[#cfd8e3] bg-white px-4 text-sm font-medium text-[#111827] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[#a8b1bf] hover:border-[#b8c4d2] focus:border-[#f47524] focus:ring-4 focus:ring-orange-100/70"
                    placeholder="e.g. Mushi"
                    value={form.last_name}
                    onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                  />
                </label>
              </div>

              <div className="border-b border-[#e2e8f0] p-4 sm:border-r">
                <label className="block">
                  <span className="text-sm font-semibold text-[#1f2937]">
                    Email address <span className="text-red-500">*</span>
                  </span>
                  <span className="mt-1 block text-[11px] text-[#94a3b8]">
                    This email will be used to sign in
                  </span>
                  <input
                    type="email"
                    className="mt-3 h-12 w-full rounded-xl border-2 border-[#cfd8e3] bg-white px-4 text-sm font-medium text-[#111827] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[#a8b1bf] hover:border-[#b8c4d2] focus:border-[#f47524] focus:ring-4 focus:ring-orange-100/70"
                    placeholder="juma@xerinmarketplace.com"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                  />
                </label>
              </div>

              <div className="border-b border-[#e2e8f0] p-4">
                <label className="block">
                  <span className="text-sm font-semibold text-[#1f2937]">
                    Phone number
                  </span>
                  <span className="mt-1 block text-[11px] text-[#94a3b8]">
                    Use international format where possible
                  </span>
                  <input
                    className="mt-3 h-12 w-full rounded-xl border-2 border-[#cfd8e3] bg-white px-4 text-sm font-medium text-[#111827] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[#a8b1bf] hover:border-[#b8c4d2] focus:border-[#f47524] focus:ring-4 focus:ring-orange-100/70"
                    placeholder="+255..."
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  />
                </label>
              </div>

              <div className="p-4 sm:col-span-2">
                <label className="block">
                  <span className="text-sm font-semibold text-[#1f2937]">
                    Temporary password <span className="text-red-500">*</span>
                  </span>
                  <span className="mt-1 block text-[11px] text-[#94a3b8]">
                    Minimum 8 characters. The user can change it after signing in.
                  </span>
                  <input
                    type="password"
                    className="mt-3 h-12 w-full rounded-xl border-2 border-[#cfd8e3] bg-white px-4 text-sm font-medium text-[#111827] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[#a8b1bf] hover:border-[#b8c4d2] focus:border-[#f47524] focus:ring-4 focus:ring-orange-100/70"
                    placeholder="Create a temporary password"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                  />
                </label>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border-2 border-[#d8e0e9] bg-[#f8fafc] p-5 shadow-[0_3px_12px_rgba(15,23,42,0.04)] sm:p-6">
          <div className="mb-5 flex items-start gap-3 border-b border-[#e7ebf0] pb-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#e2e8f0] bg-white text-sm font-bold text-[#334155]">2</span>
            <div>
              <h4 className="font-semibold text-[#111827]">Assign role & access</h4>
              <p className="mt-1 text-xs leading-5 text-[#64748b]">Select what responsibility this user will have in Xerin Market.</p>
            </div>
          </div>

          <div className="rounded-xl border border-[#e2e8f0] bg-white p-3">
            <p className="text-xs font-semibold uppercase tracking-[.12em] text-[#64748b]">Available roles <span className="text-red-500">*</span></p>
            <p className="mt-1 text-xs text-[#94a3b8]">Click a role card to assign it. You can select more than one.</p>
          </div>

          <div className="mt-3 grid gap-3">
            {roles.filter((role) => !["customer", "seller"].includes(role.name)).map((role) => {
              const selected = roleIds.includes(role.id);
              return (
                <label key={role.id} className={`flex cursor-pointer items-start gap-3 rounded-xl border-2 bg-white p-4 transition ${selected ? "border-[#f47524] shadow-sm" : "border-[#e7ebf0] hover:border-[#cbd5e1]"}`}>
                  <input type="checkbox" className="mt-1 h-4 w-4 accent-[#f47524]" checked={selected} onChange={(e) => setRoleIds((current) => e.target.checked ? [...current, role.id] : current.filter((id) => id !== role.id))} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-[#111827]">{pretty(role.name)}</span>
                    <span className="mt-1 block text-xs text-[#64748b]">{role.description || `${role.permissions.length} permissions assigned to this role.`}</span>
                    <span className="mt-2 inline-flex rounded-full bg-[#f1f5f9] px-2.5 py-1 text-[10px] font-semibold text-[#475569]">{role.permissions.length} permissions</span>
                  </span>
                </label>
              );
            })}
          </div>

          {roleIds.length === 0 && (
            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800">
              Select at least one role before creating the account.
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-[#e2e8f0] bg-[#f8fafc] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-[#334155]">Ready to create this account?</p>
          <p className="mt-1 text-xs text-[#64748b]">Review the details and assigned role before saving.</p>
        </div>
        <button type="button" disabled={busy || !valid} onClick={() => onCreate({ ...form, first_name: form.first_name.trim(), last_name: form.last_name.trim(), email: form.email.trim().toLowerCase(), phone: form.phone.trim(), role_ids: roleIds })} className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-[#111827] px-6 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">
          <UserPlus size={16} /> {busy ? "Creating..." : "Create User Account"}
        </button>
      </div>
    </section>
  );
}

function Pagination({ page, pageSize, total, onPageChange }: { page: number; pageSize: number; total: number; onPageChange: (page: number) => void; }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-col gap-3 border-t border-[#edf0f4] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-xs text-[#64748b]">Showing {start}-{end} of {total.toLocaleString()} users</p>
      <div className="flex items-center gap-2">
        <button type="button" disabled={page <= 1} onClick={()=>onPageChange(page-1)} className="inline-flex h-9 items-center gap-1 rounded-lg border border-[#e1e6ec] px-3 text-xs font-semibold disabled:opacity-40"><ChevronLeft size={14}/> Previous</button>
        <span className="min-w-24 text-center text-xs font-semibold text-[#334155]">Page {page} of {totalPages}</span>
        <button type="button" disabled={page >= totalPages} onClick={()=>onPageChange(page+1)} className="inline-flex h-9 items-center gap-1 rounded-lg border border-[#e1e6ec] px-3 text-xs font-semibold disabled:opacity-40">Next <ChevronRight size={14}/></button>
      </div>
    </div>
  );
}

function CreateStaffModal({
  roles,
  busy,
  onClose,
  onCreate,
}: {
  roles: AccessRole[];
  busy: boolean;
  onClose: () => void;
  onCreate: (payload: {
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
    password: string;
    role_ids: string[];
  }) => void;
}) {
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    password: "",
  });
  const [roleIds, setRoleIds] = useState<string[]>([]);

  const valid =
    form.first_name.trim() &&
    form.last_name.trim() &&
    form.email.trim() &&
    form.password.length >= 8 &&
    roleIds.length > 0;

  const inputClass =
    "mt-3 h-12 w-full rounded-xl border-2 border-[#cfd8e3] bg-white px-4 text-sm font-medium text-[#111827] shadow-[0_1px_2px_rgba(15,23,42,0.03)] outline-none transition placeholder:text-[#a8b1bf] hover:border-[#b8c4d2] focus:border-[#f47524] focus:ring-4 focus:ring-orange-100/70";

  const availableRoles = roles.filter(
    (role) => !["customer", "seller"].includes(role.name),
  );

  return (
    <Modal title="Create Staff Account" onClose={onClose}>
      <div className="rounded-2xl border-2 border-[#d8e0e9] bg-[#f8fafc] p-5 shadow-[0_3px_12px_rgba(15,23,42,0.04)]">
        <div className="flex items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d8e0e9] bg-white text-sm font-bold text-[#111827]">
            1
          </span>
          <div>
            <h3 className="text-sm font-bold text-[#111827]">Staff details</h3>
            <p className="mt-1 text-xs leading-5 text-gray-500">
              Enter the staff member&apos;s personal and login information.
            </p>
          </div>
        </div>

        <div className="mt-5 overflow-hidden rounded-2xl border-2 border-[#d8e0e9] bg-white">
          <div className="grid sm:grid-cols-2">
            <div className="border-b border-[#e2e8f0] p-4 sm:border-r">
              <label className="block">
                <span className="text-sm font-semibold text-[#1f2937]">
                  First name <span className="text-red-500">*</span>
                </span>
                <span className="mt-1 block text-[11px] text-[#94a3b8]">
                  Staff member&apos;s given name
                </span>
                <input
                  value={form.first_name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      first_name: event.target.value,
                    }))
                  }
                  placeholder="e.g. Juma"
                  className={inputClass}
                />
              </label>
            </div>

            <div className="border-b border-[#e2e8f0] p-4">
              <label className="block">
                <span className="text-sm font-semibold text-[#1f2937]">
                  Last name <span className="text-red-500">*</span>
                </span>
                <span className="mt-1 block text-[11px] text-[#94a3b8]">
                  Staff member&apos;s family name
                </span>
                <input
                  value={form.last_name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      last_name: event.target.value,
                    }))
                  }
                  placeholder="e.g. Mushi"
                  className={inputClass}
                />
              </label>
            </div>

            <div className="border-b border-[#e2e8f0] p-4 sm:border-r">
              <label className="block">
                <span className="text-sm font-semibold text-[#1f2937]">
                  Email address <span className="text-red-500">*</span>
                </span>
                <span className="mt-1 block text-[11px] text-[#94a3b8]">
                  This email will be used for staff sign in
                </span>
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      email: event.target.value,
                    }))
                  }
                  placeholder="juma@xerinmarketplace.com"
                  className={inputClass}
                />
              </label>
            </div>
            <div className="border-b border-[#e2e8f0] p-4">
              <label className="block">
                <span className="text-sm font-semibold text-[#1f2937]">
                  Phone number
                </span>
                <span className="mt-1 block text-[11px] text-[#94a3b8]">
                  Use international format where possible
                </span>
                <input
                  value={form.phone}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      phone: event.target.value,
                    }))
                  }
                  placeholder="+255..."
                  className={inputClass}
                />
              </label>
            </div>

            <div className="p-4 sm:col-span-2">
              <label className="block">
                <span className="text-sm font-semibold text-[#1f2937]">
                  Temporary password <span className="text-red-500">*</span>
                </span>
                <span className="mt-1 block text-[11px] text-[#94a3b8]">
                  Minimum 8 characters. The staff member should change it after first login.
                </span>
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      password: event.target.value,
                    }))
                  }
                  placeholder="Create a temporary password"
                  className={inputClass}
                />
              </label>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-2xl border-2 border-[#d8e0e9] bg-[#f8fafc] p-5 shadow-[0_3px_12px_rgba(15,23,42,0.04)]">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d8e0e9] bg-white text-sm font-bold text-[#111827]">
              2
            </span>
            <div>
              <h3 className="text-sm font-bold text-[#111827]">
                Assign role & access
              </h3>
              <p className="mt-1 text-xs leading-5 text-gray-500">
                Select one or more staff roles. Multiple roles combine their permissions.
              </p>
            </div>
          </div>

          <span className="shrink-0 rounded-full border border-[#fed7aa] bg-[#fff7ed] px-3 py-1 text-xs font-semibold text-[#f47524]">
            {roleIds.length} selected
          </span>
        </div>

        <div className="mt-4 overflow-hidden rounded-2xl border-2 border-[#d8e0e9] bg-white">
          <div className="grid gap-0 sm:grid-cols-2">
            {availableRoles.map((role, index) => {
              const selected = roleIds.includes(role.id);

              return (
                <label
                  key={role.id}
                  className={`flex cursor-pointer items-start gap-3 border-[#e2e8f0] p-4 transition ${
                    index % 2 === 0 ? "sm:border-r" : ""
                  } ${
                    index < availableRoles.length - 2
                      ? "border-b"
                      : availableRoles.length % 2 === 0
                        ? ""
                        : index === availableRoles.length - 1
                          ? ""
                          : "border-b"
                  } ${
                    selected
                      ? "bg-orange-50/60"
                      : "bg-white hover:bg-[#f8fafc]"
                  }`}
                >
                  <span
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 ${
                      selected
                        ? "border-[#f47524] bg-[#f47524] text-white"
                        : "border-[#cbd5e1] bg-white"
                    }`}
                  >
                    {selected && <Check size={13} strokeWidth={3} />}
                  </span>

                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={selected}
                    onChange={(event) =>
                      setRoleIds((current) =>
                        event.target.checked
                          ? [...current, role.id]
                          : current.filter((id) => id !== role.id),
                      )
                    }
                  />

                  <span className="min-w-0 flex-1">
                    <b className="text-sm text-[#111827]">{pretty(role.name)}</b>
                    <small className="mt-1 block text-gray-500">
                      {role.permissions.length} permissions
                    </small>
                    {role.description && (
                      <small className="mt-1 line-clamp-2 block leading-5 text-[#94a3b8]">
                        {role.description}
                      </small>
                    )}
                  </span>
                </label>
              );
            })}
          </div>
        </div>

        {!roleIds.length && (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800">
            Select at least one role before creating this staff account.
          </div>
        )}
      </div>

      <div className="mt-5 rounded-2xl border-2 border-[#d8e0e9] bg-white p-4">
        <div className="mb-4 flex items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d8e0e9] bg-[#f8fafc] text-sm font-bold text-[#111827]">
            3
          </span>
          <div>
            <p className="text-sm font-bold text-[#111827]">Create staff account</p>
            <p className="mt-1 text-xs leading-5 text-gray-500">
              Review the user details and selected access roles before creating the account.
              Backend RBAC will enforce the assigned permissions.
            </p>
          </div>
        </div>

        <div className="mb-4 grid gap-3 rounded-xl bg-[#f8fafc] p-4 sm:grid-cols-2">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-[#94a3b8]">
              Staff member
            </p>
            <p className="mt-1 text-sm font-semibold text-[#111827]">
              {[form.first_name.trim(), form.last_name.trim()]
                .filter(Boolean)
                .join(" ") || "Not entered yet"}
            </p>
          </div>

          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-[#94a3b8]">
              Roles selected
            </p>
            <p className="mt-1 text-sm font-semibold text-[#111827]">
              {roleIds.length}
            </p>
          </div>
        </div>

        <button
          type="button"
          disabled={busy || !valid}
          onClick={() =>
            onCreate({
              ...form,
              first_name: form.first_name.trim(),
              last_name: form.last_name.trim(),
              email: form.email.trim().toLowerCase(),
              phone: form.phone.trim(),
              role_ids: roleIds,
            })
          }
          className="w-full rounded-xl bg-[#f47524] py-3 font-semibold text-white shadow-sm transition hover:bg-[#dc651d] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Creating..." : "Create Staff Account"}
        </button>
      </div>
    </Modal>
  );
}

function PermissionSelector({
  permissions,
  selected,
  disabled = false,
  onChange,
}: {
  permissions: AccessPermission[];
  selected: string[];
  disabled?: boolean;
  onChange: (codes: string[]) => void;
}) {
  const grouped = permissions.reduce<Record<string, AccessPermission[]>>(
    (all, permission) => {
      const code = permission.code;

      let group = "General";
      if (/seller/i.test(code)) group = "Sellers";
      else if (/product|brand|categor|review/i.test(code)) group = "Catalogue";
      else if (/order|shipping|delivery/i.test(code)) group = "Orders & Delivery";
      else if (/payment|refund|wallet|commission/i.test(code)) group = "Finance";
      else if (/user|profile|permission/i.test(code)) group = "Users & Access";
      else if (/dashboard|analytic|report/i.test(code)) group = "Dashboard & Analytics";
      else if (/notification|communication/i.test(code)) group = "Communications";
      else if (/audit|security|system/i.test(code)) group = "Security & System";

      (all[group] ??= []).push(permission);
      return all;
    },
    {},
  );

  return (
    <div className="mt-5 max-h-[55vh] space-y-4 overflow-y-auto pr-1">
      {Object.entries(grouped).map(([group, items]) => {
        const codes = items.map((item) => item.code);
        const selectedCount = codes.filter((code) =>
          selected.includes(code),
        ).length;
        const allSelected = selectedCount === codes.length && codes.length > 0;

        return (
          <section
            key={group}
            className="overflow-hidden rounded-xl border border-[#e7ebf0]"
          >
            <div className="flex items-center justify-between bg-[#f8fafc] px-4 py-3">
              <div>
                <p className="text-sm font-semibold">{group}</p>
                <p className="text-[11px] text-gray-500">
                  {selectedCount} of {codes.length} selected
                </p>
              </div>

              <button
                type="button"
                disabled={disabled}
                onClick={() =>
                  onChange(
                    allSelected
                      ? selected.filter((code) => !codes.includes(code))
                      : Array.from(new Set([...selected, ...codes])),
                  )
                }
                className="text-xs font-semibold text-[#f47524] disabled:text-gray-400"
              >
                {allSelected ? "Clear group" : "Select all"}
              </button>
            </div>

            <div className="divide-y divide-[#edf0f4]">
              {items.map((permission) => (
                <label
                  key={permission.id}
                  className="flex items-start gap-3 p-3.5"
                >
                  <input
                    type="checkbox"
                    className="mt-1"
                    disabled={disabled}
                    checked={selected.includes(permission.code)}
                    onChange={(event) =>
                      onChange(
                        event.target.checked
                          ? [...selected, permission.code]
                          : selected.filter(
                              (code) => code !== permission.code,
                            ),
                      )
                    }
                  />

                  <span className="min-w-0">
                    <b className="text-sm text-[#111827]">
                      {permission.name || pretty(permission.code)}
                    </b>
                    <code className="ml-2 text-[10px] text-[#f47524]">
                      {permission.code}
                    </code>
                    <small className="mt-1 block leading-5 text-gray-500">
                      {permission.description || "No description provided."}
                    </small>
                  </span>
                </label>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function Drawer({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-[90] flex justify-end bg-black/45"
      onMouseDown={onClose}
    >
      <aside
        onMouseDown={(event) => event.stopPropagation()}
        className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-semibold text-[#111827]">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-gray-500"
          >
            <X size={17} />
          </button>
        </div>
        <div className="mt-6">{children}</div>
      </aside>
    </div>
  );
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <div
        onMouseDown={(event) => event.stopPropagation()}
        className="max-h-[94vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-semibold text-[#111827]">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-gray-500"
          >
            <X size={17} />
          </button>
        </div>

        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-[#334155]">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </span>
      {hint && (
        <span className="mt-0.5 block text-[11px] text-gray-500">{hint}</span>
      )}
      <div className="mt-2">{children}</div>
    </label>
  );
}

function Badge({ value }: { value: string }) {
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
        ["active", "current"].includes(value)
          ? "bg-green-50 text-green-700"
          : value === "suspended"
            ? "bg-red-50 text-red-700"
            : "bg-gray-100 text-gray-600"
      }`}
    >
      {pretty(value)}
    </span>
  );
}