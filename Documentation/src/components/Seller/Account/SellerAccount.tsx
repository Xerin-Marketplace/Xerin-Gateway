"use client";

import {
  sellerAccountApi,
  type SellerSession,
  type SellerUserProfile,
} from "@/lib/api/endpoints/seller-account";
import { sellersApi } from "@/lib/api/endpoints/sellers";
import type {
  PayoutAccount,
  Seller,
  SellerBusinessProfile,
  SellerKycStatus,
} from "@/types/api/seller";
import {
  Bell,
  Building2,
  CheckCircle2,
  ExternalLink,
  KeyRound,
  Loader2,
  ShieldCheck,
  Store,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";

export type SellerAccountView =
  | "overview"
  | "profile"
  | "security"
  | "notifications"
  | "store"
  | "support";
export default function SellerAccount({ view }: { view: SellerAccountView }) {
  const [user, setUser] = useState<SellerUserProfile | null>(null);
  const [seller, setSeller] = useState<Seller | null>(null);
  const [business, setBusiness] = useState<SellerBusinessProfile | null>(null);
  const [kyc, setKyc] = useState<SellerKycStatus | null>(null);
  const [payouts, setPayouts] = useState<PayoutAccount[]>([]);
  const [sessions, setSessions] = useState<SellerSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [profile, setProfile] = useState({
    first_name: "",
    last_name: "",
    phone: "",
  });
  const [sellerForm, setSellerForm] = useState({
    business_name: "",
    contact_email: "",
    contact_phone: "",
  });
  const [businessForm, setBusinessForm] = useState({
    business_description: "",
    business_country: "",
    business_region: "",
    business_city: "",
    business_address: "",
  });
  const [passwords, setPasswords] = useState({
    current: "",
    next: "",
    confirm: "",
  });

  useEffect(() => {
    void load();
  }, []);
  async function load() {
    setLoading(true);
    setLoadError("");
    try {
      const [u, s, b, k, p] = await Promise.all([
        sellerAccountApi.getUser(),
        sellersApi.getMe(),
        sellersApi.getProfile(),
        sellersApi.getKycStatus(),
        sellersApi.getPayoutAccounts(),
      ]);
      setUser(u);
      setSeller(s);
      setBusiness(b);
      setKyc(k);
      setPayouts(p);
      setProfile({
        first_name: u.first_name || "",
        last_name: u.last_name || "",
        phone: u.phone || "",
      });
      setSellerForm({
        business_name: s.business_name || "",
        contact_email: s.contact_email || "",
        contact_phone: s.contact_phone || "",
      });
      setBusinessForm({
        business_description: b.business_description || "",
        business_country: b.business_country || "",
        business_region: b.business_region || "",
        business_city: b.business_city || "",
        business_address: b.business_address || "",
      });
      if (view === "security")
        setSessions(await sellerAccountApi.listSessions());
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Unable to load seller account settings.";
      setLoadError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const updated = await sellerAccountApi.updateUser({
        ...profile,
        phone: profile.phone || null,
      });
      setUser(updated);
      toast.success("Profile information updated.");
    } catch {
      toast.error("Profile update failed.");
    } finally {
      setSaving(false);
    }
  }
  async function saveBusiness(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const [s, b] = await Promise.all([
        sellersApi.updateMe(sellerForm),
        sellersApi.updateProfile(businessForm),
      ]);
      setSeller(s);
      setBusiness(b);
      toast.success("Business information updated.");
    } catch {
      toast.error("Business update failed.");
    } finally {
      setSaving(false);
    }
  }
  async function changePassword(event: FormEvent) {
    event.preventDefault();
    if (passwords.next.length < 8)
      return toast.error("New password must contain at least 8 characters.");
    if (passwords.next !== passwords.confirm)
      return toast.error("New passwords do not match.");
    setSaving(true);
    try {
      await sellerAccountApi.changePassword(passwords.current, passwords.next);
      toast.success("Password changed. Please sign in again.");
      window.location.assign("/signin");
    } catch {
      toast.error("Password change failed.");
    } finally {
      setSaving(false);
    }
  }

  if (loading)
    return (
      <div className="flex min-h-72 items-center justify-center">
        <Loader2 className="animate-spin text-[#f7941d]" />
      </div>
    );
  if (loadError)
    return <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700"><p>{loadError}</p><button type="button" onClick={() => void load()} className="mt-3 rounded-xl bg-red-700 px-4 py-2 font-semibold text-white">Retry</button></div>;
  if (view === "security")
    return (
      <Security
        passwords={passwords}
        setPasswords={setPasswords}
        submit={changePassword}
        saving={saving}
        sessions={sessions}
        revoke={async (id) => {
          await sellerAccountApi.revokeSession(id);
          setSessions((v) => v.filter((s) => s.id !== id));
          toast.success("Session signed out.");
        }}
      />
    );
  if (view === "notifications")
    return <Notifications />;
  if (view === "store")
    return (
      <StoreSettings
        seller={seller}
        business={business}
        form={businessForm}
        setForm={setBusinessForm}
        save={saveBusiness}
        saving={saving}
      />
    );
  if (view === "support") return <Support />;

  const kycDisplayStatus = kyc?.missing_documents.length
    ? "Incomplete"
    : kyc?.seller_status === "under_review"
      ? "Under Review"
      : kyc?.seller_status === "approved"
        ? "Approved"
        : "Ready to Submit";

  return (
    <div className="space-y-6">
      <PageIntro
        title={view === "profile" ? "Seller Profile" : "Account Settings"}
        text="Manage your seller identity, business details and marketplace account status."
      />
      <AccountNav />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Status
          label="Account Status"
          value={
            seller?.status === "approved"
              ? "Approved Seller"
              : seller?.status || "Pending"
          }
          good={seller?.status === "approved"}
        />
        <Status
          label="KYC Status"
          value={kycDisplayStatus}
          good={kycDisplayStatus === "Approved"}
        />
        <Status
          label="Store Status"
          value="Unavailable"
          good={false}
        />
        <Status
          label="Payout Status"
          value={
            payouts.some(
              (account) =>
                account.is_active !== false &&
                account.verification_status === "verified",
            )
              ? "Verified & Ready"
              : payouts.length
                ? "Verification Pending"
                : "Not Configured"
          }
          good={payouts.some(
            (account) =>
              account.is_active !== false &&
              account.verification_status === "verified",
          )}
        />
      </div>
      <form onSubmit={saveProfile}>
        <Section
          icon={UserRound}
          title="Profile Information"
          description="Personal details used for your Seller Center account."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="First name"
              value={profile.first_name}
              set={(v) => setProfile({ ...profile, first_name: v })}
            />
            <Field
              label="Last name"
              value={profile.last_name}
              set={(v) => setProfile({ ...profile, last_name: v })}
            />
            <Field
              label="Email address"
              value={user?.email || ""}
              disabled
              hint={
                user?.is_verified
                  ? "Verified email"
                  : "Email verification pending"
              }
            />
            <Field
              label="Phone number"
              value={profile.phone}
              set={(v) => setProfile({ ...profile, phone: v })}
            />
          </div>
          <Actions saving={saving} />
        </Section>
      </form>
      <form onSubmit={saveBusiness}>
        <Section
          icon={Building2}
          title="Business Information"
          description="Legal business information used for verification and payouts."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="Business name"
              value={sellerForm.business_name}
              set={(v) => setSellerForm({ ...sellerForm, business_name: v })}
              disabled={seller?.status === "approved"}
              hint={
                seller?.status === "approved"
                  ? "Approved sensitive field—contact support to request a change"
                  : undefined
              }
            />
            <Field
              label="Business type"
              value={seller?.business_category || "Not provided"}
              disabled
            />
            <Field
              label="Business email"
              value={sellerForm.contact_email}
              set={(v) => setSellerForm({ ...sellerForm, contact_email: v })}
            />
            <Field
              label="Business phone"
              value={sellerForm.contact_phone}
              set={(v) => setSellerForm({ ...sellerForm, contact_phone: v })}
            />
            <Field
              label="Country"
              value={businessForm.business_country}
              set={(v) =>
                setBusinessForm({ ...businessForm, business_country: v })
              }
            />
            <Field
              label="Region"
              value={businessForm.business_region}
              set={(v) =>
                setBusinessForm({ ...businessForm, business_region: v })
              }
            />
            <Field
              label="City"
              value={businessForm.business_city}
              set={(v) =>
                setBusinessForm({ ...businessForm, business_city: v })
              }
            />
            <Field
              label="Business address"
              value={businessForm.business_address}
              set={(v) =>
                setBusinessForm({ ...businessForm, business_address: v })
              }
            />
          </div>
          <div className="mt-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-400/10 dark:text-amber-300">
            KYC review:{" "}
            {kyc?.missing_documents.length
              ? `Incomplete — ${kyc.missing_documents.length} document(s) missing`
              : "Submitted for review"}
            .{" "}
            <Link className="font-semibold underline" href="/seller/kyc">
              Open verification
            </Link>
          </div>
          <Actions saving={saving} />
        </Section>
      </form>
    </div>
  );
}

function PageIntro({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <h2 className="text-2xl font-bold">{title}</h2>
      <p className="mt-1 text-sm text-[#64748b]">{text}</p>
    </div>
  );
}
function AccountNav() {
  return (
    <div className="flex flex-wrap gap-2">
      {[
        ["Overview", "/seller/account"],
        ["Profile", "/seller/account/profile"],
        ["Security", "/seller/account/security"],
        ["Notifications", "/seller/account/notifications"],
        ["Store", "/seller/store"],
      ].map(([l, h]) => (
        <Link
          key={h}
          href={h}
          className="rounded-xl border border-[#e2e8f0] bg-white px-4 py-2 text-sm font-semibold hover:border-[#f7941d] dark:border-white/10 dark:bg-[#2d3134]"
        >
          {l}
        </Link>
      ))}
    </div>
  );
}
function Section({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof UserRound;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#2d3134] sm:p-6">
      <div className="mb-5 flex gap-3">
        <span className="rounded-xl bg-orange-50 p-2.5 text-[#f7941d] dark:bg-orange-400/10">
          <Icon size={21} />
        </span>
        <div>
          <h3 className="font-bold">{title}</h3>
          <p className="text-sm text-[#64748b]">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}
function Field({
  label,
  value,
  set,
  disabled,
  hint,
  type = "text",
}: {
  label: string;
  value: string;
  set?: (v: string) => void;
  disabled?: boolean;
  hint?: string;
  type?: string;
}) {
  return (
    <label className="block text-sm font-semibold">
      {label}
      <input
        type={type}
        value={value}
        disabled={disabled}
        onChange={(e) => set?.(e.target.value)}
        className="mt-2 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 font-normal outline-none focus:border-[#f7941d] disabled:cursor-not-allowed disabled:opacity-65 dark:border-white/10 dark:bg-white/5"
      />
      {hint && (
        <small className="mt-1 block font-normal text-[#64748b]">{hint}</small>
      )}
    </label>
  );
}
function Actions({ saving }: { saving: boolean }) {
  return (
    <div className="mt-6 flex justify-end gap-3">
      <button
        type="reset"
        className="rounded-xl border border-[#e2e8f0] px-5 py-2.5 text-sm font-semibold dark:border-white/10"
      >
        Cancel
      </button>
      <button
        disabled={saving}
        className="rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
      >
        {saving ? "Saving..." : "Save changes"}
      </button>
    </div>
  );
}
function Status({
  label,
  value,
  good,
}: {
  label: string;
  value: string;
  good: boolean;
}) {
  return (
    <div className="rounded-2xl border border-[#e2e8f0] bg-white p-5 dark:border-white/10 dark:bg-[#2d3134]">
      <p className="text-xs font-semibold uppercase tracking-wide text-[#64748b]">
        {label}
      </p>
      <p
        className={`mt-2 flex items-center gap-2 font-bold ${good ? "text-green-600" : "text-amber-600"}`}
      >
        <CheckCircle2 size={17} />
        {value}
      </p>
    </div>
  );
}
function Security({
  passwords,
  setPasswords,
  submit,
  saving,
  sessions,
  revoke,
}: {
  passwords: { current: string; next: string; confirm: string };
  setPasswords: (v: { current: string; next: string; confirm: string }) => void;
  submit: (e: FormEvent) => void;
  saving: boolean;
  sessions: SellerSession[];
  revoke: (id: string) => void;
}) {
  return (
    <div className="space-y-6">
      <PageIntro
        title="Security"
        text="Protect your Seller Center account and manage active sessions."
      />
      <AccountNav />
      <form onSubmit={submit}>
        <Section
          icon={KeyRound}
          title="Change Password"
          description="Changing your password signs out existing refresh sessions."
        >
          <div className="grid gap-4 md:grid-cols-3">
            <Field
              type="password"
              label="Current password"
              value={passwords.current}
              set={(v) => setPasswords({ ...passwords, current: v })}
            />
            <Field
              type="password"
              label="New password"
              value={passwords.next}
              set={(v) => setPasswords({ ...passwords, next: v })}
            />
            <Field
              type="password"
              label="Confirm password"
              value={passwords.confirm}
              set={(v) => setPasswords({ ...passwords, confirm: v })}
            />
          </div>
          <Actions saving={saving} />
        </Section>
      </form>
      <Section
        icon={ShieldCheck}
        title="Active Sessions"
        description="Sign out sessions you no longer recognize."
      >
        <div className="space-y-3">
          {sessions.length ? (
            sessions.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded-xl border border-[#e2e8f0] p-4 dark:border-white/10"
              >
                <div>
                  <b>Seller Center session</b>
                  <p className="text-xs text-[#64748b]">
                    Created {new Date(s.created_at).toLocaleString()} · Expires{" "}
                    {new Date(s.expires_at).toLocaleString()}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => revoke(s.id)}
                  className="text-sm font-semibold text-red-600"
                >
                  Sign out
                </button>
              </div>
            ))
          ) : (
            <p className="text-sm text-[#64748b]">No other active sessions.</p>
          )}
        </div>
        <div className="mt-5 rounded-xl bg-[#f8fafc] p-4 text-sm dark:bg-white/5">
          <b>Two-factor authentication</b>
          <p className="text-[#64748b]">
            Preparation complete; activation will be available when the
            authentication API supports 2FA.
          </p>
        </div>
      </Section>
    </div>
  );
}
function Notifications() {
  return (
    <div className="space-y-6">
      <PageIntro
        title="Notifications"
        text="Choose which seller events should notify you."
      />
      <AccountNav />
      <Section
        icon={Bell}
        title="Seller Notifications"
        description="Notification preferences require a persisted backend contract."
      >
        <div className="rounded-xl border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-5 text-sm text-[#64748b] dark:border-white/15 dark:bg-white/5">Seller notifications, unread counts and preferences are not available in the current backend. No local preferences or fake unread values are displayed.</div>
      </Section>
    </div>
  );
}
function StoreSettings({
  seller,
  business,
  form,
  setForm,
  save,
  saving,
}: {
  seller: Seller | null;
  business: SellerBusinessProfile | null;
  form: {
    business_description: string;
    business_country: string;
    business_region: string;
    business_city: string;
    business_address: string;
  };
  setForm: (v: typeof form) => void;
  save: (e: FormEvent) => void;
  saving: boolean;
}) {
  return (
    <div className="space-y-6">
      <PageIntro
        title="Store Settings"
        text="Control how your business appears to marketplace customers."
      />
      <AccountNav />
      <form onSubmit={save}>
        <Section
          icon={Store}
          title="Store Information"
          description="Store identity and customer-facing contact information."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="Store name"
              value={seller?.business_name || ""}
              disabled
            />
            <Field
              label="Store slug"
              value={(seller?.business_name || "store")
                .toLowerCase()
                .replace(/\s+/g, "-")}
              disabled
            />
            <Field
              label="Support email"
              value={seller?.contact_email || ""}
              disabled
            />
            <Field
              label="Support phone"
              value={seller?.contact_phone || ""}
              disabled
            />
          </div>
          <label className="mt-4 block text-sm font-semibold">
            Store description
            <textarea
              value={form.business_description}
              onChange={(e) =>
                setForm({ ...form, business_description: e.target.value })
              }
              rows={5}
              className="mt-2 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-4 font-normal outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-white/5"
            />
          </label>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <Field
              label="Return policy"
              value="Configure through Seller Support"
              disabled
            />
            <Field
              label="Shipping information"
              value={
                business?.business_country
                  ? `Ships from ${business.business_city || business.business_country}`
                  : "Not configured"
              }
              disabled
            />
          </div>
          <div className="mt-6 flex justify-end gap-3">
            <Link
              href="/shop-with-sidebar"
              className="flex items-center gap-2 rounded-xl border border-[#e2e8f0] px-5 py-2.5 text-sm font-semibold dark:border-white/10"
            >
              <ExternalLink size={16} />
              View storefront
            </Link>
            <button
              disabled={saving}
              className="rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white"
            >
              Update store
            </button>
          </div>
        </Section>
      </form>
    </div>
  );
}
function Support() {
  return (
    <div className="space-y-6">
      <PageIntro
        title="Seller Help & Support"
        text="Get assistance without leaving Seller Center."
      />
      <Section
        icon={Bell}
        title="Contact Seller Support"
        description="Our marketplace operations team can help with verification, products and payouts."
      >
        <div className="grid gap-4 md:grid-cols-3">
          {[
            ["Verification support", "KYC documents and review feedback"],
            ["Catalog support", "Product submission and approval"],
            ["Payout support", "Settlement and payout account issues"],
          ].map(([a, b]) => (
            <div
              key={a}
              className="rounded-xl border border-[#e2e8f0] p-4 dark:border-white/10"
            >
              <b>{a}</b>
              <p className="mt-1 text-sm text-[#64748b]">{b}</p>
              <a
                href="mailto:support@xerin.com"
                className="mt-3 inline-block text-sm font-semibold text-[#f7941d]"
              >
                Email support
              </a>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
