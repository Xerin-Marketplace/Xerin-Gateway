"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  Globe2,
  ImageIcon,
  Loader2,
  MapPin,
  Pencil,
  Plus,
  Store as StoreIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  useCreateStore,
  useMyStores,
  useUpdateStore,
  useUploadStoreBannerById,
  useUploadStoreLogoById,
} from "@/hooks/useStore";
import { authStorage } from "@/lib/auth/storage";
import type { CreateStorePayload, Store } from "@/types/api/store";
import {
  STORE_COUNTRIES,
  getGlobalCities,
  getGlobalStates,
  getTanzaniaDistricts,
  getTanzaniaRegions,
  getTanzaniaWards,
} from "@/lib/locations/storeLocations";

type ViewMode = "list" | "create" | "edit";

type StoreFormState = {
  store_name: string;
  description: string;
  contact_email: string;
  contact_phone: string;
  whatsapp_phone: string;
  website_url: string;
  country: string;
  region: string;
  district: string;
  ward: string;
  street: string;
};

const EMPTY_FORM: StoreFormState = {
  store_name: "",
  description: "",
  contact_email: "",
  contact_phone: "",
  whatsapp_phone: "",
  website_url: "",
  country: "Tanzania",
  region: "",
  district: "",
  ward: "",
  street: "",
};

const TANZANIA_NAMES = new Set([
  "tanzania",
  "united republic of tanzania",
  "tanzania, united republic of",
]);

function predictedScope(country: string): "local" | "global" {
  return TANZANIA_NAMES.has(country.trim().toLowerCase()) ? "local" : "global";
}

function formFromStore(store: Store): StoreFormState {
  return {
    store_name: store.store_name || "",
    description: store.description || "",
    contact_email: store.contact_email || "",
    contact_phone: store.contact_phone || "",
    whatsapp_phone: store.whatsapp_phone || "",
    website_url: store.website_url || "",
    country: store.country || "",
    region: store.region || "",
    district: store.district || "",
    ward: store.ward || "",
    street: store.street || "",
  };
}

export default function SellerStoreSettings() {
  const router = useRouter();
  const user = authStorage.getUser<{ account_type?: string; roles?: string[] }>();
  const token = authStorage.getAccessToken();
  const isSeller = Boolean(user && (user.account_type === "seller" || (user.roles ?? []).includes("seller")));

  const { data: stores = [], isLoading, error, refetch } = useMyStores();
  const createStore = useCreateStore();
  const updateStore = useUpdateStore();
  const uploadLogo = useUploadStoreLogoById();
  const uploadBanner = useUploadStoreBannerById();

  const [mode, setMode] = useState<ViewMode>("list");
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);
  const [form, setForm] = useState<StoreFormState>(EMPTY_FORM);
  const [regionOptions, setRegionOptions] = useState<string[]>([]);
  const [districtOptions, setDistrictOptions] = useState<string[]>([]);
  const [wardOptions, setWardOptions] = useState<string[]>([]);
  const [locationLoading, setLocationLoading] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  const selectedStore = useMemo(
    () => stores.find((store) => String(store.id) === selectedStoreId) ?? null,
    [stores, selectedStoreId],
  );

  useEffect(() => {
    if (mode === "edit" && selectedStore) setForm(formFromStore(selectedStore));
  }, [mode, selectedStore]);

  useEffect(() => {
    let cancelled = false;
    async function loadRegions() {
      if (mode === "list" || !form.country) return;
      setLocationLoading(true);
      setLocationError(null);
      try {
        const values = predictedScope(form.country) === "local"
          ? await getTanzaniaRegions()
          : await getGlobalStates(form.country);
        if (!cancelled) setRegionOptions(values);
      } catch {
        if (!cancelled) {
          setRegionOptions([]);
          setLocationError("Location suggestions are temporarily unavailable. You can still type the location manually.");
        }
      } finally {
        if (!cancelled) setLocationLoading(false);
      }
    }
    loadRegions();
    return () => { cancelled = true; };
  }, [mode, form.country]);

  useEffect(() => {
    let cancelled = false;
    async function loadDistricts() {
      if (mode === "list" || !form.country || !form.region) {
        setDistrictOptions([]);
        return;
      }
      setLocationLoading(true);
      setLocationError(null);
      try {
        const values = predictedScope(form.country) === "local"
          ? await getTanzaniaDistricts(form.region)
          : await getGlobalCities(form.country, form.region);
        if (!cancelled) setDistrictOptions(values);
      } catch {
        if (!cancelled) {
          setDistrictOptions([]);
          setLocationError("Location suggestions are temporarily unavailable. You can still type the location manually.");
        }
      } finally {
        if (!cancelled) setLocationLoading(false);
      }
    }
    loadDistricts();
    return () => { cancelled = true; };
  }, [mode, form.country, form.region]);

  useEffect(() => {
    let cancelled = false;
    async function loadWards() {
      if (mode === "list" || predictedScope(form.country) !== "local" || !form.district) {
        setWardOptions([]);
        return;
      }
      setLocationLoading(true);
      setLocationError(null);
      try {
        const values = await getTanzaniaWards(form.district);
        if (!cancelled) setWardOptions(values);
      } catch {
        if (!cancelled) {
          setWardOptions([]);
          setLocationError("Ward suggestions are temporarily unavailable. You can still type the ward manually.");
        }
      } finally {
        if (!cancelled) setLocationLoading(false);
      }
    }
    loadWards();
    return () => { cancelled = true; };
  }, [mode, form.country, form.district]);

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

  if (error && mode === "list") {
    return (
      <div className="mx-auto max-w-[1280px] space-y-6">
        <div className="flex flex-col gap-4 rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold">My Stores</h2>
            <p className="mt-1 text-sm text-[#64748b]">Create and manage all physical selling locations connected to your seller account.</p>
          </div>
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white"
          >
            <Plus size={17} /> Add Store
          </button>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-white px-6 py-12 text-center shadow-sm dark:border-amber-500/30 dark:bg-[#1f2937]">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-orange-50 text-[#f7941d] dark:bg-orange-400/10">
            <StoreIcon size={27} />
          </span>
          <h3 className="mt-4 text-lg font-bold">Your store list could not be loaded</h3>
          <p className="mx-auto mt-2 max-w-lg text-sm text-[#64748b]">
            {(error as Error)?.message || "Store data could not be loaded."} You can still create your first store, or retry loading the list.
          </p>
          <div className="mt-5 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <button
              type="button"
              onClick={openCreate}
              className="inline-flex items-center gap-2 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white"
            >
              <Plus size={17} /> Create Store
            </button>
            <button
              type="button"
              onClick={() => refetch()}
              className="rounded-xl border border-[#e2e8f0] px-5 py-2.5 text-sm font-semibold dark:border-white/10"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  function openCreate() {
    setSelectedStoreId(null);
    setForm(EMPTY_FORM);
    setMode("create");
  }

  function openEdit(store: Store) {
    setSelectedStoreId(String(store.id));
    setForm(formFromStore(store));
    setMode("edit");
  }

  function backToStores() {
    setMode("list");
    setSelectedStoreId(null);
    setForm(EMPTY_FORM);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!form.store_name.trim()) {
      toast.error("Store name is required.");
      return;
    }
    if (!form.country.trim()) {
      toast.error("Country is required.");
      return;
    }

    try {
      if (mode === "create") {
        const payload: CreateStorePayload = {
          store_name: form.store_name.trim(),
          country: form.country.trim(),
          description: form.description.trim() || null,
          contact_email: form.contact_email.trim() || null,
          contact_phone: form.contact_phone.trim() || null,
          whatsapp_phone: form.whatsapp_phone.trim() || null,
          website_url: form.website_url.trim() || null,
          region: form.region.trim() || null,
          district: form.district.trim() || null,
          ward: form.ward.trim() || null,
          street: form.street.trim() || null,
        };
        const created = await createStore.mutateAsync(payload);
        toast.success("Store created successfully.");
        setSelectedStoreId(String(created.id));
        setMode("edit");
        return;
      }

      if (!selectedStoreId) return;
      await updateStore.mutateAsync({
        storeId: selectedStoreId,
        payload: {
          store_name: form.store_name.trim(),
          description: form.description.trim() || null,
          contact_email: form.contact_email.trim() || null,
          contact_phone: form.contact_phone.trim() || null,
          whatsapp_phone: form.whatsapp_phone.trim() || null,
          website_url: form.website_url.trim() || null,
          country: form.country.trim(),
          region: form.region.trim() || null,
          district: form.district.trim() || null,
          ward: form.ward.trim() || null,
          street: form.street.trim() || null,
        },
      });
      toast.success("Store updated successfully.");
    } catch (err) {
      toast.error(apiErrorMessage(err, mode === "create" ? "Failed to create store." : "Failed to update store."));
    }
  }

  async function handleLogoUpload(file: File) {
    if (!selectedStoreId) return;
    try {
      await uploadLogo.mutateAsync({ storeId: selectedStoreId, file });
      toast.success("Store logo uploaded.");
    } catch (err) {
      toast.error(apiErrorMessage(err, "Failed to upload logo."));
    }
  }

  async function handleBannerUpload(file: File) {
    if (!selectedStoreId) return;
    try {
      await uploadBanner.mutateAsync({ storeId: selectedStoreId, file });
      toast.success("Store banner uploaded.");
    } catch (err) {
      toast.error(apiErrorMessage(err, "Failed to upload banner."));
    }
  }

  if (mode === "list") {
    return <StoreList stores={stores} onCreate={openCreate} onEdit={openEdit} />;
  }

  const scope = mode === "edit" && selectedStore ? selectedStore.store_scope : predictedScope(form.country);
  const saving = createStore.isPending || updateStore.isPending;

  return (
    <div className="mx-auto max-w-[1280px] space-y-6">
      <div className="flex flex-col gap-4 rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={backToStores}
            className="mt-0.5 rounded-xl border border-[#e2e8f0] p-2.5 transition hover:bg-[#f8fafc] dark:border-white/10 dark:hover:bg-white/5"
            aria-label="Back to stores"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <h2 className="text-2xl font-semibold">{mode === "create" ? "Add New Store" : "Manage Store"}</h2>
            <p className="mt-1 text-sm text-[#64748b]">
              {mode === "create" ? "Create another selling location for your business." : "Update this store's identity, contact details and physical location."}
            </p>
          </div>
        </div>
        {selectedStore && (
          <Link
            href="/shop-with-sidebar"
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#e2e8f0] px-4 py-2.5 text-sm font-semibold dark:border-white/10"
          >
            <ExternalLink size={16} /> View storefront
          </Link>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Section icon={StoreIcon} title="Store Information" description="The public identity and support contacts for this store.">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Store name" required value={form.store_name} onChange={(value) => setForm({ ...form, store_name: value })} />
            <Field label="Store slug" value={selectedStore?.slug || "Generated after store creation"} disabled />
            <Field label="Support email" type="email" value={form.contact_email} onChange={(value) => setForm({ ...form, contact_email: value })} />
            <Field label="Support phone" value={form.contact_phone} onChange={(value) => setForm({ ...form, contact_phone: value })} />
            <Field label="WhatsApp phone" value={form.whatsapp_phone} onChange={(value) => setForm({ ...form, whatsapp_phone: value })} />
            <Field label="Website" type="url" value={form.website_url} onChange={(value) => setForm({ ...form, website_url: value })} placeholder="https://example.com" />
          </div>
          <label className="mt-4 block text-sm font-semibold">
            Store description
            <textarea
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              rows={5}
              className="mt-2 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-4 font-normal outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-white/5"
              placeholder="Tell customers about this store..."
            />
          </label>
        </Section>

        <Section icon={MapPin} title="Store Location" description="The physical origin of products sold from this store.">
          <div className="mb-5 flex flex-col gap-3 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-4 dark:border-white/10 dark:bg-white/5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold">Store classification</p>
              <p className="mt-1 text-xs text-[#64748b]">Tanzania is LOCAL. Any country outside Tanzania is GLOBAL. The backend verifies this automatically.</p>
            </div>
            <ScopeBadge scope={scope} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <SelectField
              label="Country"
              required
              value={form.country}
              options={STORE_COUNTRIES.map((country) => ({ value: country.value, label: country.label }))}
              onChange={(value) => {
                setForm({ ...form, country: value, region: "", district: "", ward: "" });
                setRegionOptions([]);
                setDistrictOptions([]);
                setWardOptions([]);
              }}
            />
            <LocationCombobox
              id="store-region"
              label={scope === "local" ? "Region" : "State / Province / Emirate"}
              value={form.region}
              options={regionOptions}
              loading={locationLoading}
              placeholder={scope === "local" ? "Select or type a region" : "Select or type a state / province"}
              onChange={(value) => {
                setForm({ ...form, region: value, district: "", ward: "" });
                setDistrictOptions([]);
                setWardOptions([]);
              }}
            />
            <LocationCombobox
              id="store-district"
              label={scope === "local" ? "District / Municipality" : "City"}
              value={form.district}
              options={districtOptions}
              loading={locationLoading}
              disabled={!form.region}
              placeholder={scope === "local" ? "Select or type a district" : "Select or type a city"}
              onChange={(value) => {
                setForm({ ...form, district: value, ward: "" });
                setWardOptions([]);
              }}
            />
            <LocationCombobox
              id="store-ward"
              label={scope === "local" ? "Ward" : "Area / Neighborhood"}
              value={form.ward}
              options={scope === "local" ? wardOptions : []}
              loading={scope === "local" && locationLoading}
              disabled={scope === "local" && !form.district}
              placeholder={scope === "local" ? "Select or type a ward" : "Type area / neighborhood"}
              onChange={(value) => setForm({ ...form, ward: value })}
            />
            <div className="md:col-span-2">
              <Field label="Street / physical address" value={form.street} onChange={(value) => setForm({ ...form, street: value })} placeholder="Building, road, block, shop number..." />
            </div>
          </div>
          {locationError && (
            <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
              {locationError}
            </p>
          )}
          <p className="mt-3 text-xs text-[#64748b]">
            Start typing to search the dropdown. If a location is not listed, you can type it manually and continue.
          </p>
        </Section>

        {mode === "edit" && selectedStore && (
          <Section icon={ImageIcon} title="Store Media" description="Upload a logo and banner specifically for this store.">
            <div className="grid gap-6 md:grid-cols-2">
              <FileUploader label="Store logo" currentUrl={selectedStore.logo_url} onUpload={handleLogoUpload} uploading={uploadLogo.isPending} ratio="square" />
              <FileUploader label="Store banner" currentUrl={selectedStore.banner_url} onUpload={handleBannerUpload} uploading={uploadBanner.isPending} ratio="wide" />
            </div>
          </Section>
        )}

        {selectedStore && (
          <Section icon={CheckCircle2} title="Store Status" description="Status values are controlled by the backend and seller approval flow.">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatusItem label="Status" value={formatStatus(selectedStore.status)} />
              <StatusItem label="Scope" value={selectedStore.store_scope.toUpperCase()} />
              <StatusItem label="Verified" value={selectedStore.is_verified ? "Yes" : "No"} />
              <StatusItem label="Accepting orders" value={selectedStore.accept_orders ? "Yes" : "No"} />
            </div>
          </Section>
        )}

        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button type="button" onClick={backToStores} className="rounded-xl border border-[#e2e8f0] px-5 py-2.5 text-sm font-semibold dark:border-white/10">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
            {saving ? "Saving..." : mode === "create" ? "Create store" : "Save changes"}
          </button>
        </div>
      </form>
    </div>
  );
}

function StoreList({ stores, onCreate, onEdit }: { stores: Store[]; onCreate: () => void; onEdit: (store: Store) => void }) {
  const localCount = stores.filter((store) => store.store_scope === "local").length;
  const globalCount = stores.filter((store) => store.store_scope === "global").length;

  return (
    <div className="mx-auto max-w-[1280px] space-y-6">
      <div className="flex flex-col gap-4 rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">My Stores</h2>
          <p className="mt-1 text-sm text-[#64748b]">Manage all physical selling locations connected to your seller account.</p>
        </div>
        <button type="button" onClick={onCreate} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white">
          <Plus size={17} /> Add Store
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Total stores" value={stores.length} icon={StoreIcon} />
        <SummaryCard label="Local stores" value={localCount} icon={MapPin} />
        <SummaryCard label="Global stores" value={globalCount} icon={Globe2} />
      </div>

      {stores.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[#cbd5e1] bg-white px-6 py-16 text-center dark:border-white/15 dark:bg-[#1f2937]">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-orange-50 text-[#f7941d] dark:bg-orange-400/10">
            <StoreIcon size={27} />
          </span>
          <h3 className="mt-4 text-lg font-bold">No stores yet</h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-[#64748b]">Create your first store and define where it is physically located. Tanzania stores are local; stores outside Tanzania are global.</p>
          <button type="button" onClick={onCreate} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white">
            <Plus size={17} /> Create first store
          </button>
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {stores.map((store) => (
            <StoreCard key={String(store.id)} store={store} onEdit={() => onEdit(store)} />
          ))}
        </div>
      )}
    </div>
  );
}

function StoreCard({ store, onEdit }: { store: Store; onEdit: () => void }) {
  const location = [store.district, store.region, store.country].filter(Boolean).join(", ") || "Location not configured";

  return (
    <article className="overflow-hidden rounded-2xl border border-[#e2e8f0] bg-white shadow-sm dark:border-white/10 dark:bg-[#1f2937]">
      <div className="relative h-28 bg-[#f8fafc] dark:bg-white/5">
        {store.banner_url ? <img src={store.banner_url} alt="" className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-[#cbd5e1]"><ImageIcon size={32} /></div>}
        <div className="absolute right-3 top-3"><ScopeBadge scope={store.store_scope} /></div>
      </div>
      <div className="p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[#e2e8f0] bg-white dark:border-white/10 dark:bg-[#111827]">
            {store.logo_url ? <img src={store.logo_url} alt={`${store.store_name} logo`} className="h-full w-full object-cover" /> : <StoreIcon size={22} className="text-[#f7941d]" />}
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="truncate font-bold">{store.store_name}</h3>
            <p className="mt-1 flex items-start gap-1.5 text-xs text-[#64748b]"><MapPin size={13} className="mt-0.5 shrink-0" /> <span>{location}</span></p>
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between border-t border-[#e2e8f0] pt-4 dark:border-white/10">
          <span className="text-xs font-semibold text-[#64748b]">{formatStatus(store.status)}</span>
          <button type="button" onClick={onEdit} className="inline-flex items-center gap-2 rounded-xl border border-[#e2e8f0] px-3.5 py-2 text-sm font-semibold transition hover:border-[#f7941d] hover:text-[#f7941d] dark:border-white/10">
            <Pencil size={15} /> Manage
          </button>
        </div>
      </div>
    </article>
  );
}

function ScopeBadge({ scope }: { scope: "local" | "global" }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${scope === "local" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-300" : "bg-sky-100 text-sky-700 dark:bg-sky-400/15 dark:text-sky-300"}`}>
      {scope === "local" ? <MapPin size={13} /> : <Globe2 size={13} />}
      {scope.toUpperCase()}
    </span>
  );
}

function SummaryCard({ label, value, icon: Icon }: { label: string; value: number; icon: typeof StoreIcon }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937]">
      <span className="rounded-xl bg-orange-50 p-3 text-[#f7941d] dark:bg-orange-400/10"><Icon size={21} /></span>
      <div><p className="text-2xl font-bold">{value}</p><p className="text-sm text-[#64748b]">{label}</p></div>
    </div>
  );
}

function Section({ icon: Icon, title, description, children }: { icon: typeof StoreIcon; title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:p-6">
      <div className="mb-5 flex gap-3">
        <span className="rounded-xl bg-orange-50 p-2.5 text-[#f7941d] dark:bg-orange-400/10"><Icon size={21} /></span>
        <div><h3 className="font-bold">{title}</h3><p className="text-sm text-[#64748b]">{description}</p></div>
      </div>
      {children}
    </div>
  );
}

function SelectField({ label, value, options, onChange, required }: { label: string; value: string; options: Array<{ value: string; label: string }>; onChange: (value: string) => void; required?: boolean }) {
  return (
    <label className="block text-sm font-semibold">
      {label}{required && <span className="text-red-500"> *</span>}
      <select
        value={value}
        required={required}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 font-normal outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-[#111827]"
      >
        <option value="">Select {label.toLowerCase()}</option>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}

function LocationCombobox({ id, label, value, options, onChange, placeholder, disabled, loading }: { id: string; label: string; value: string; options: string[]; onChange: (value: string) => void; placeholder?: string; disabled?: boolean; loading?: boolean }) {
  const values = value && !options.includes(value) ? [value, ...options] : options;
  return (
    <label className="block text-sm font-semibold">
      {label}
      <div className="relative mt-2">
        <input
          list={`${id}-options`}
          value={value}
          disabled={disabled}
          placeholder={loading ? "Loading locations..." : placeholder}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 pr-10 font-normal outline-none focus:border-[#f7941d] disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5"
        />
        {loading && <Loader2 size={16} className="absolute right-3 top-3.5 animate-spin text-[#f7941d]" />}
      </div>
      <datalist id={`${id}-options`}>
        {values.map((option) => <option key={option} value={option} />)}
      </datalist>
    </label>
  );
}

function Field({ label, value, onChange, disabled, required, type = "text", placeholder }: { label: string; value: string; onChange?: (value: string) => void; disabled?: boolean; required?: boolean; type?: string; placeholder?: string }) {
  return (
    <label className="block text-sm font-semibold">
      {label}{required && <span className="text-red-500"> *</span>}
      <input
        type={type}
        value={value}
        disabled={disabled}
        required={required}
        placeholder={placeholder}
        onChange={(event) => onChange?.(event.target.value)}
        className="mt-2 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 font-normal outline-none focus:border-[#f7941d] disabled:cursor-not-allowed disabled:opacity-65 dark:border-white/10 dark:bg-white/5"
      />
    </label>
  );
}

function FileUploader({ label, currentUrl, onUpload, uploading, ratio }: { label: string; currentUrl: string | null; onUpload: (file: File) => void; uploading: boolean; ratio: "square" | "wide" }) {
  return (
    <div>
      <p className="mb-2 text-sm font-semibold">{label}</p>
      <div className={`flex items-center justify-center overflow-hidden rounded-xl border border-dashed border-[#cbd5e1] bg-[#f8fafc] dark:border-white/15 dark:bg-white/5 ${ratio === "wide" ? "h-32 w-full" : "h-32 w-32"}`}>
        {currentUrl ? <img src={currentUrl} alt={label} className="h-full w-full object-cover" /> : <ImageIcon size={32} className="text-[#94a3b8]" />}
      </div>
      <label className="mt-2 inline-block">
        <input type="file" accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={(event) => event.target.files?.[0] && onUpload(event.target.files[0])} className="hidden" />
        <span className={`inline-flex cursor-pointer items-center gap-2 rounded-xl border border-[#e2e8f0] px-4 py-2 text-sm font-semibold dark:border-white/10 ${uploading ? "opacity-60" : ""}`}>
          {uploading ? "Uploading..." : `Upload ${label.toLowerCase()}`}
        </span>
      </label>
    </div>
  );
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-[#f8fafc] p-4 dark:bg-white/5"><p className="text-xs text-[#64748b]">{label}</p><p className="mt-1 text-sm font-bold">{value}</p></div>;
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function apiErrorMessage(error: unknown, fallback: string) {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return fallback;
}
