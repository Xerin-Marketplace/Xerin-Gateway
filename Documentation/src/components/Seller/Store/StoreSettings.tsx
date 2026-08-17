"use client";

import { FormEvent, useEffect, useState } from "react";
import { ExternalLink, ImageIcon, Loader2, Store } from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";
import { useMyStore, useUpdateMyStore, useUploadStoreLogo, useUploadStoreBanner } from "@/hooks/useStore";
import { authStorage } from "@/lib/auth/storage";
import { useRouter } from "next/navigation";

export default function SellerStoreSettings() {
  const router = useRouter();
  const user = authStorage.getUser<{ account_type?: string; roles?: string[]; seller_status?: string | null }>();
  const token = authStorage.getAccessToken();
  const isSeller = Boolean(user && (user.account_type === "seller" || (user.roles ?? []).includes("seller")));

  const { data: store, isLoading, error } = useMyStore();
  const updateStore = useUpdateMyStore();
  const uploadLogo = useUploadStoreLogo();
  const uploadBanner = useUploadStoreBanner();

  const [form, setForm] = useState({
    name: "",
    description: "",
    contact_email: "",
    contact_phone: "",
    business_country: "",
    business_region: "",
    business_city: "",
    business_address: "",
  });

  useEffect(() => {
    if (store) {
      setForm({
        name: store.name || "",
        description: store.description || "",
        contact_email: store.contact_email || "",
        contact_phone: store.contact_phone || "",
        business_country: store.business_country || "",
        business_region: store.business_region || "",
        business_city: store.business_city || "",
        business_address: store.business_address || "",
      });
    }
  }, [store]);

  if (!token || !isSeller) {
    router.replace("/signin?redirect=/seller/store");
    return null;
  }

  if (isLoading) {
    return (
      <div className="flex min-h-72 items-center justify-center">
        <Loader2 className="animate-spin text-[#f7941d]" />
      </div>
    );
  }

  if (error || !store) {
    return (
      <div className="mx-auto max-w-xl rounded-2xl border border-red-200 bg-white p-8 text-center shadow-sm dark:border-red-500/30 dark:bg-[#1f2937]">
        <h2 className="text-xl font-semibold">Unable to load store settings</h2>
        <p className="mt-2 text-sm text-[#64748b]">{(error as Error)?.message || "Store data could not be loaded."}</p>
      </div>
    );
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    try {
      await updateStore.mutateAsync({
        name: form.name,
        description: form.description,
        contact_email: form.contact_email,
        contact_phone: form.contact_phone,
        business_country: form.business_country,
        business_region: form.business_region,
        business_city: form.business_city,
        business_address: form.business_address,
      });
      toast.success("Store settings updated.");
    } catch {
      toast.error("Failed to update store settings.");
    }
  }

  async function handleLogoUpload(file: File) {
    try {
      await uploadLogo.mutateAsync(file);
      toast.success("Store logo uploaded.");
    } catch {
      toast.error("Failed to upload logo.");
    }
  }

  async function handleBannerUpload(file: File) {
    try {
      await uploadBanner.mutateAsync(file);
      toast.success("Store banner uploaded.");
    } catch {
      toast.error("Failed to upload banner.");
    }
  }

  return (
    <div className="mx-auto max-w-[1280px] space-y-6">
      <div className="flex flex-col gap-4 rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Store Settings</h2>
          <p className="mt-1 text-sm text-[#64748b]">Control how your business appears to marketplace customers.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/shop-with-sidebar" className="inline-flex items-center gap-2 rounded-xl border border-[#e2e8f0] px-4 py-2.5 text-sm font-semibold dark:border-white/10">
            <ExternalLink size={16} /> View storefront
          </Link>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        <Section icon={Store} title="Store Information" description="Store identity and customer-facing contact information.">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Store name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
            <Field label="Store slug" value={store.slug || ""} disabled hint="Generated from store name" />
            <Field label="Support email" value={form.contact_email} onChange={(v) => setForm({ ...form, contact_email: v })} />
            <Field label="Support phone" value={form.contact_phone} onChange={(v) => setForm({ ...form, contact_phone: v })} />
          </div>
          <label className="mt-4 block text-sm font-semibold">
            Store description
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={5}
              className="mt-2 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-4 font-normal outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-white/5"
            />
          </label>
        </Section>

        <Section icon={ImageIcon} title="Store Media" description="Upload your store logo and banner image.">
          <div className="grid gap-6 md:grid-cols-2">
            <FileUploader
              label="Store logo"
              currentUrl={store.logo_url}
              onUpload={handleLogoUpload}
              uploading={uploadLogo.isPending}
              ratio="square"
            />
            <FileUploader
              label="Store banner"
              currentUrl={store.banner_url}
              onUpload={handleBannerUpload}
              uploading={uploadBanner.isPending}
              ratio="wide"
            />
          </div>
        </Section>

        <Section icon={Store} title="Business Location" description="Location information shown to customers.">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Country" value={form.business_country} onChange={(v) => setForm({ ...form, business_country: v })} />
            <Field label="Region" value={form.business_region} onChange={(v) => setForm({ ...form, business_region: v })} />
            <Field label="City" value={form.business_city} onChange={(v) => setForm({ ...form, business_city: v })} />
            <Field label="Business address" value={form.business_address} onChange={(v) => setForm({ ...form, business_address: v })} />
          </div>
        </Section>

        <Section icon={Store} title="Store Policies" description="Return, shipping and delivery policies for your customers.">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Return policy" value="Configure through Seller Support" disabled />
            <Field label="Shipping information" value={store.business_city ? `Ships from ${store.business_city}` : "Not configured"} disabled />
            <Field label="Delivery time estimate" value="Not configured" disabled />
          </div>
          <div className="mt-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-400/10 dark:text-amber-300">
            Policy and delivery configuration will be available when the seller store API supports these fields.
          </div>
        </Section>

        <Section icon={Store} title="Operating Status" description="Control store visibility and operating hours.">
          <label className="flex items-center justify-between rounded-xl border border-[#e2e8f0] p-4 dark:border-white/10">
            <span>
              <b className="text-sm">Store is open</b>
              <small className="block text-[#64748b]">Customers can view and purchase from your storefront.</small>
            </span>
            <input type="checkbox" checked={false} disabled className="h-5 w-5 accent-[#f7941d] disabled:opacity-50" />
          </label>
          <div className="mt-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-400/10 dark:text-amber-300">
            Operating status and hours will be available when the seller store API supports these settings.
          </div>
        </Section>

        <div className="flex justify-end gap-3">
          <Link href="/seller/dashboard" className="rounded-xl border border-[#e2e8f0] px-5 py-2.5 text-sm font-semibold dark:border-white/10">Cancel</Link>
          <button type="submit" disabled={updateStore.isPending} className="rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
            {updateStore.isPending ? "Saving..." : "Update store"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Section({ icon: Icon, title, description, children }: { icon: typeof Store; title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:p-6">
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

function Field({ label, value, onChange, disabled, hint }: { label: string; value: string; onChange?: (v: string) => void; disabled?: boolean; hint?: string }) {
  return (
    <label className="block text-sm font-semibold">
      {label}
      <input
        type="text"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.value)}
        className="mt-2 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 font-normal outline-none focus:border-[#f7941d] disabled:cursor-not-allowed disabled:opacity-65 dark:border-white/10 dark:bg-white/5"
      />
      {hint && <small className="mt-1 block font-normal text-[#64748b]">{hint}</small>}
    </label>
  );
}

function FileUploader({ label, currentUrl, onUpload, uploading, ratio }: { label: string; currentUrl: string | null; onUpload: (file: File) => void; uploading: boolean; ratio: "square" | "wide" }) {
  return (
    <div>
      <p className="mb-2 text-sm font-semibold">{label}</p>
      <div className={`flex items-center justify-center overflow-hidden rounded-xl border border-dashed border-[#cbd5e1] bg-[#f8fafc] dark:border-white/15 dark:bg-white/5 ${ratio === "wide" ? "h-32" : "h-32 w-32"}`}>
        {currentUrl ? (
          <img src={currentUrl} alt={label} className="h-full w-full object-cover" />
        ) : (
          <ImageIcon size={32} className="text-[#94a3b8]" />
        )}
      </div>
      <label className="mt-2 inline-block">
        <input
          type="file"
          accept="image/*"
          disabled={uploading}
          onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
          className="hidden"
        />
        <span className={`inline-flex cursor-pointer items-center gap-2 rounded-xl border border-[#e2e8f0] px-4 py-2 text-sm font-semibold dark:border-white/10 ${uploading ? "opacity-60" : ""}`}>
          {uploading ? "Uploading..." : `Upload ${label.toLowerCase()}`}
        </span>
      </label>
    </div>
  );
}
