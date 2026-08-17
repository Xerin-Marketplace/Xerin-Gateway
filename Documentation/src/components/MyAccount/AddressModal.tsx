"use client";

import React, { FormEvent, useEffect, useState } from "react";
import type { Address, AddressRequest } from "@/types/api/user";

type Props = {
  isOpen: boolean;
  closeModal: () => void;
  initialAddress?: Address | null;
  isSubmitting?: boolean;
  onSubmit: (payload: AddressRequest) => Promise<void> | void;
};

const emptyForm: AddressRequest = {
  label: "Home",
  recipient_name: "",
  recipient_phone: "",
  country: "Tanzania",
  region: "",
  district: "",
  ward: "",
  city: "",
  street: "",
  landmark: "",
  postal_code: "",
  latitude: null,
  longitude: null,
  is_default: false,
};

const input =
  "mt-1.5 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm outline-none transition focus:border-[#f7941d] focus:ring-4 focus:ring-orange-50 disabled:opacity-60 dark:border-white/10 dark:bg-white/5";

export default function AddressModal({
  isOpen,
  closeModal,
  initialAddress,
  isSubmitting = false,
  onSubmit,
}: Props) {
  const [form, setForm] = useState<AddressRequest>(emptyForm);

  useEffect(() => {
    if (!isOpen) return;
    setForm({
      label: initialAddress?.label || "Home",
      recipient_name: initialAddress?.recipient_name || "",
      recipient_phone: initialAddress?.recipient_phone || "",
      country: initialAddress?.country || "Tanzania",
      region: initialAddress?.region || "",
      district: initialAddress?.district || "",
      ward: initialAddress?.ward || "",
      city: initialAddress?.city || "",
      street: initialAddress?.street || "",
      landmark: initialAddress?.landmark || "",
      postal_code: initialAddress?.postal_code || "",
      latitude: initialAddress?.latitude == null ? null : Number(initialAddress.latitude),
      longitude: initialAddress?.longitude == null ? null : Number(initialAddress.longitude),
      is_default: Boolean(initialAddress?.is_default),
    });
  }, [initialAddress, isOpen]);

  if (!isOpen) return null;

  const set = (key: keyof AddressRequest, value: string | boolean | number | null) =>
    setForm((current) => ({ ...current, [key]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit({
      label: form.label?.trim() || null,
      recipient_name: form.recipient_name?.trim() || null,
      recipient_phone: form.recipient_phone?.trim() || null,
      country: form.country.trim(),
      region: form.region.trim(),
      district: form.district?.trim() || null,
      ward: form.ward?.trim() || null,
      city: form.city.trim(),
      street: form.street.trim(),
      landmark: form.landmark?.trim() || null,
      postal_code: form.postal_code?.trim() || null,
      latitude: form.latitude == null ? null : Number(form.latitude),
      longitude: form.longitude == null ? null : Number(form.longitude),
      is_default: Boolean(form.is_default),
    });
  };

  return (
    <div className="fixed inset-0 z-[120] overflow-y-auto bg-black/55 p-4 sm:p-8">
      <div className="mx-auto my-8 w-full max-w-3xl rounded-2xl bg-white p-5 shadow-2xl dark:bg-darkTheme-card sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-xl font-bold">{initialAddress ? "Edit Delivery Address" : "Add Delivery Address"}</h3>
            <p className="mt-1 text-sm text-[#64748b]">
              These details are used for checkout, shipping quotes and logistics handover.
            </p>
          </div>
          <button type="button" disabled={isSubmitting} onClick={closeModal} className="rounded-xl border border-[#e2e8f0] px-3 py-2 text-sm font-semibold">Close</button>
        </div>

        <form onSubmit={submit} className="mt-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Address label">
              <input value={form.label || ""} onChange={(e)=>set("label",e.target.value)} className={input} placeholder="Home, Office..." />
            </Field>
            <Field label="Recipient name">
              <input value={form.recipient_name || ""} onChange={(e)=>set("recipient_name",e.target.value)} className={input} placeholder="Person receiving delivery" />
            </Field>
            <Field label="Recipient phone">
              <input value={form.recipient_phone || ""} onChange={(e)=>set("recipient_phone",e.target.value)} className={input} placeholder="+255..." />
            </Field>
            <Field label="Country" required>
              <input required value={form.country} onChange={(e)=>set("country",e.target.value)} className={input} />
            </Field>
            <Field label="Region" required>
              <input required value={form.region} onChange={(e)=>set("region",e.target.value)} className={input} placeholder="Dar es Salaam" />
            </Field>
            <Field label="District">
              <input value={form.district || ""} onChange={(e)=>set("district",e.target.value)} className={input} placeholder="Kinondoni" />
            </Field>
            <Field label="Ward">
              <input value={form.ward || ""} onChange={(e)=>set("ward",e.target.value)} className={input} placeholder="Mikocheni" />
            </Field>
            <Field label="City" required>
              <input required value={form.city} onChange={(e)=>set("city",e.target.value)} className={input} placeholder="Dar es Salaam" />
            </Field>
            <Field label="Street / address line" required wide>
              <input required value={form.street} onChange={(e)=>set("street",e.target.value)} className={input} placeholder="Street, building and house number" />
            </Field>
            <Field label="Landmark" wide>
              <input value={form.landmark || ""} onChange={(e)=>set("landmark",e.target.value)} className={input} placeholder="Near..." />
            </Field>
            <Field label="Postal code">
              <input value={form.postal_code || ""} onChange={(e)=>set("postal_code",e.target.value)} className={input} placeholder="Optional" />
            </Field>
          </div>

          <label className="mt-5 flex cursor-pointer items-center gap-3 rounded-xl border border-[#e2e8f0] p-4 text-sm dark:border-white/10">
            <input type="checkbox" checked={Boolean(form.is_default)} onChange={(e)=>set("is_default",e.target.checked)} />
            <span><b>Use as default delivery address</b><span className="mt-0.5 block text-xs font-normal text-[#64748b]">Checkout will prefer this address.</span></span>
          </label>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
            <button type="button" disabled={isSubmitting} onClick={closeModal} className="rounded-xl border border-[#e2e8f0] px-5 py-3 text-sm font-semibold">Cancel</button>
            <button type="submit" disabled={isSubmitting} className="rounded-xl bg-[#f7941d] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">
              {isSubmitting ? "Saving..." : initialAddress ? "Save Changes" : "Add Address"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({label,required=false,wide=false,children}:{label:string;required?:boolean;wide?:boolean;children:React.ReactNode}) {
  return <label className={`text-sm font-semibold ${wide ? "sm:col-span-2" : ""}`}>{label}{required && <span className="text-red-500"> *</span>}{children}</label>;
}
