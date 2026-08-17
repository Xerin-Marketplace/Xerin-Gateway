"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BadgePercent,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Copy,
  Edit3,
  Package,
  Plus,
  RefreshCw,
  Search,
  Tag,
  TicketPercent,
  Trash2,
  X,
} from "lucide-react";
import toast from "react-hot-toast";

import { ApiError } from "@/lib/api/client";
import { productsApi } from "@/lib/api/endpoints/products";
import { sellerPromotionsApi } from "@/lib/api/endpoints/promotions";
import type { Product } from "@/types/api/product";
import type {
  PromotionType,
  SellerPromotion,
  SellerPromotionRequest,
} from "@/types/api/promotion";

type Filter = "all" | "active" | "inactive";

type PromotionFormState = {
  name: string;
  code: string;
  description: string;
  promotion_type: PromotionType;
  discount_value: string;
  minimum_order_amount: string;
  maximum_discount_amount: string;
  usage_limit: string;
  usage_per_customer: string;
  stackable: boolean;
  automatic: boolean;
  is_active: boolean;
  starts_at: string;
  ends_at: string;
  product_ids: string[];
};

const initialForm: PromotionFormState = {
  name: "",
  code: "",
  description: "",
  promotion_type: "percentage",
  discount_value: "",
  minimum_order_amount: "",
  maximum_discount_amount: "",
  usage_limit: "",
  usage_per_customer: "1",
  stackable: false,
  automatic: false,
  is_active: true,
  starts_at: "",
  ends_at: "",
  product_ids: [],
};

const money = (value: number | string | null | undefined, currency = "TZS") => {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-TZ", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number.isFinite(amount) ? amount : 0);
};

const pretty = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const localDateTimeToIso = (value: string) =>
  value ? new Date(value).toISOString() : null;

const apiError = (error: unknown) => {
  if (error instanceof ApiError) return error.message;
  const candidate = error as {
    response?: { data?: { detail?: string | Array<{ msg?: string }> } };
    message?: string;
  };
  const detail = candidate.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg || "Request failed.";
  return candidate.message || "Request failed.";
};

export default function SellerPromotions() {
  const [rows, setRows] = useState<SellerPromotion[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [productsLoading, setProductsLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [meta, setMeta] = useState({ total: 0, total_pages: 0 });

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<SellerPromotion | null>(null);
  const [form, setForm] = useState<PromotionFormState>(initialForm);
  const [saving, setSaving] = useState(false);
  const [productSearch, setProductSearch] = useState("");

  const activeFilter =
    filter === "active" ? true : filter === "inactive" ? false : undefined;

  const loadPromotions = async () => {
    setLoading(true);
    setError("");

    try {
      const result = await sellerPromotionsApi.list({
        page,
        page_size: pageSize,
        search: search.trim() || undefined,
        active: activeFilter,
      });

      setRows(result.results);
      setMeta({ total: result.total, total_pages: result.total_pages });
    } catch (cause) {
      const message = apiError(cause);
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPromotions(), 250);
    return () => window.clearTimeout(timer);
  }, [page, pageSize, search, filter]);

  const loadProducts = async () => {
    if (products.length || productsLoading) return;

    setProductsLoading(true);
    try {
      const result = await productsApi.getMyProducts();
      setProducts(result);
    } catch (cause) {
      toast.error(apiError(cause));
    } finally {
      setProductsLoading(false);
    }
  };

  const openCreate = async () => {
    setEditing(null);
    setForm(initialForm);
    setProductSearch("");
    setEditorOpen(true);
    await loadProducts();
  };

  const openEdit = (promotion: SellerPromotion) => {
    setEditing(promotion);
    setForm({
      ...initialForm,
      name: promotion.name,
      code: promotion.code || "",
      description: promotion.description || "",
      promotion_type: promotion.promotion_type as PromotionType,
      discount_value: String(promotion.discount_value ?? ""),
      minimum_order_amount:
        promotion.minimum_order_amount == null
          ? ""
          : String(promotion.minimum_order_amount),
      maximum_discount_amount:
        promotion.maximum_discount_amount == null
          ? ""
          : String(promotion.maximum_discount_amount),
      usage_limit:
        promotion.usage_limit == null ? "" : String(promotion.usage_limit),
      usage_per_customer:
        promotion.usage_per_customer == null
          ? ""
          : String(promotion.usage_per_customer),
      stackable: promotion.stackable,
      automatic: promotion.automatic,
      is_active: promotion.is_active,
      starts_at: promotion.starts_at
        ? promotion.starts_at.slice(0, 16)
        : "",
      ends_at: promotion.ends_at ? promotion.ends_at.slice(0, 16) : "",
      product_ids: [],
    });
    setEditorOpen(true);
  };

  const closeEditor = () => {
    if (saving) return;
    setEditorOpen(false);
    setEditing(null);
    setForm(initialForm);
  };

  const validateForm = () => {
    if (form.name.trim().length < 2) return "Enter a promotion name.";

    if (!form.automatic && form.code.trim().length < 2) {
      return "Enter a promo code, or enable Automatic Promotion.";
    }

    const discount = Number(form.discount_value);
    if (
      form.promotion_type !== "free_shipping" &&
      form.promotion_type !== "buy_x_get_y" &&
      (!Number.isFinite(discount) || discount <= 0)
    ) {
      return "Enter a valid discount value.";
    }

    if (form.promotion_type === "percentage" && discount > 100) {
      return "Percentage discount cannot exceed 100%.";
    }

    if (form.starts_at && form.ends_at) {
      if (new Date(form.ends_at) <= new Date(form.starts_at)) {
        return "End date must be later than start date.";
      }
    }

    if (!editing && form.product_ids.length === 0) {
      return "Select at least one of your products for this promotion.";
    }

    return null;
  };

  const submit = async () => {
    const validation = validateForm();
    if (validation) {
      toast.error(validation);
      return;
    }

    setSaving(true);
    try {
      if (editing) {
        await sellerPromotionsApi.update(editing.id, {
          name: form.name.trim(),
          description: form.description.trim() || null,
          discount_value: Number(form.discount_value || 0),
          minimum_order_amount: form.minimum_order_amount
            ? Number(form.minimum_order_amount)
            : null,
          maximum_discount_amount: form.maximum_discount_amount
            ? Number(form.maximum_discount_amount)
            : null,
          usage_limit: form.usage_limit ? Number(form.usage_limit) : null,
          usage_per_customer: form.usage_per_customer
            ? Number(form.usage_per_customer)
            : null,
          stackable: form.stackable,
          automatic: form.automatic,
          is_active: form.is_active,
          starts_at: localDateTimeToIso(form.starts_at),
          ends_at: localDateTimeToIso(form.ends_at),
        });

        toast.success("Promotion updated.");
      } else {
        const payload: SellerPromotionRequest = {
          name: form.name.trim(),
          code: form.automatic ? form.code.trim().toUpperCase() || null : form.code.trim().toUpperCase(),
          description: form.description.trim() || null,
          promotion_type: form.promotion_type,
          discount_value: Number(form.discount_value || 0),
          minimum_order_amount: form.minimum_order_amount
            ? Number(form.minimum_order_amount)
            : null,
          maximum_discount_amount: form.maximum_discount_amount
            ? Number(form.maximum_discount_amount)
            : null,
          usage_limit: form.usage_limit ? Number(form.usage_limit) : null,
          usage_per_customer: form.usage_per_customer
            ? Number(form.usage_per_customer)
            : null,
          stackable: form.stackable,
          automatic: form.automatic,
          is_active: form.is_active,
          starts_at: localDateTimeToIso(form.starts_at),
          ends_at: localDateTimeToIso(form.ends_at),
          rules: form.product_ids.map((productId) => ({
            rule_type: "product",
            product_id: productId,
          })),
        };

        await sellerPromotionsApi.create(payload);
        toast.success("Promotion created.");
      }

      closeEditor();
      await loadPromotions();
    } catch (cause) {
      toast.error(apiError(cause));
    } finally {
      setSaving(false);
    }
  };

  const togglePromotion = async (promotion: SellerPromotion) => {
    setBusy(promotion.id);
    try {
      await sellerPromotionsApi.update(promotion.id, {
        is_active: !promotion.is_active,
      });
      toast.success(
        promotion.is_active ? "Promotion paused." : "Promotion activated.",
      );
      await loadPromotions();
    } catch (cause) {
      toast.error(apiError(cause));
    } finally {
      setBusy(null);
    }
  };

  const removePromotion = async (promotion: SellerPromotion) => {
    const message = promotion.usage_count
      ? "This promotion already has usage history. The backend will safely deactivate it instead of deleting history. Continue?"
      : "Delete this promotion?";

    if (!window.confirm(message)) return;

    setBusy(promotion.id);
    try {
      await sellerPromotionsApi.delete(promotion.id);
      toast.success(
        promotion.usage_count
          ? "Promotion deactivated and history preserved."
          : "Promotion deleted.",
      );
      await loadPromotions();
    } catch (cause) {
      toast.error(apiError(cause));
    } finally {
      setBusy(null);
    }
  };

  const visibleProducts = useMemo(() => {
    const term = productSearch.trim().toLowerCase();
    if (!term) return products;
    return products.filter((product) =>
      `${product.name} ${product.sku}`.toLowerCase().includes(term),
    );
  }, [productSearch, products]);

  const activeCount = rows.filter((row) => row.is_active).length;
  const usedCount = rows.reduce((sum, row) => sum + row.usage_count, 0);

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-orange-50 text-[#f7941d] dark:bg-orange-400/10">
                <TicketPercent size={21} />
              </span>
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f7941d]">
                  Seller Phase 3
                </p>
                <h1 className="mt-0.5 text-2xl font-bold tracking-[-0.02em] text-[#111827] dark:text-white">
                  Promotions & Promo Codes
                </h1>
              </div>
            </div>

            <p className="mt-4 max-w-3xl text-sm leading-6 text-[#64748b] dark:text-white/60">
              Create seller-funded promotions for your products. Xerin marketplace
              commission remains separate from the seller-funded discount, so
              promotions do not silently reduce Xerin&apos;s commission.
            </p>
          </div>

          <button
            type="button"
            onClick={() => void openCreate()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#f7941d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#e88312]"
          >
            <Plus size={17} />
            Create Promotion
          </button>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <SummaryCard
            label="Promotions on this page"
            value={rows.length}
            icon={Tag}
          />
          <SummaryCard
            label="Active on this page"
            value={activeCount}
            icon={CheckCircle2}
          />
          <SummaryCard
            label="Total uses on this page"
            value={usedCount}
            icon={BadgePercent}
          />
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-[#e7ebf0] bg-white shadow-sm dark:border-white/10 dark:bg-[#1f2937]">
        <div className="flex flex-col gap-3 border-b border-[#eef1f5] p-5 sm:flex-row sm:items-center sm:justify-between dark:border-white/10">
          <div>
            <h2 className="font-bold text-[#111827] dark:text-white">
              My Promotions
            </h2>
            <p className="mt-1 text-xs text-[#94a3b8]">
              Search and pagination are handled by the backend.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <label className="relative">
              <Search
                size={15}
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94a3b8]"
              />
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
                placeholder="Search name or promo code..."
                className="h-11 min-w-[270px] rounded-xl border border-[#e2e8f0] bg-white pl-10 pr-3 text-sm outline-none focus:border-orange-300 focus:ring-4 focus:ring-orange-50 dark:border-white/10 dark:bg-white/5 dark:text-white"
              />
            </label>

            <select
              value={filter}
              onChange={(event) => {
                setFilter(event.target.value as Filter);
                setPage(1);
              }}
              className="h-11 rounded-xl border border-[#e2e8f0] bg-white px-3 text-sm outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
            >
              <option value="all">All promotions</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="m-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="p-12 text-center text-sm text-[#64748b]">
            <RefreshCw size={20} className="mx-auto animate-spin" />
            <p className="mt-3">Loading promotions...</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1080px] text-left text-sm">
                <thead className="bg-[#f8fafc] text-[10px] font-bold uppercase tracking-[0.08em] text-[#94a3b8] dark:bg-white/5">
                  <tr>
                    {[
                      "Promotion",
                      "Code",
                      "Discount",
                      "Schedule",
                      "Usage",
                      "Funding",
                      "Status",
                      "Actions",
                    ].map((header) => (
                      <th key={header} className="px-5 py-3.5">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody className="divide-y divide-[#eef1f5] dark:divide-white/10">
                  {rows.map((promotion) => (
                    <tr key={promotion.id}>
                      <td className="px-5 py-4">
                        <p className="font-semibold text-[#111827] dark:text-white">
                          {promotion.name}
                        </p>
                        <p className="mt-1 max-w-[280px] truncate text-xs text-[#94a3b8]">
                          {promotion.description || pretty(promotion.promotion_type)}
                        </p>
                      </td>

                      <td className="px-5 py-4">
                        {promotion.code ? (
                          <button
                            type="button"
                            onClick={async () => {
                              await navigator.clipboard.writeText(
                                promotion.code || "",
                              );
                              toast.success("Promo code copied.");
                            }}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-orange-200 bg-orange-50 px-2.5 py-1.5 font-mono text-xs font-bold text-[#c66c0b]"
                          >
                            {promotion.code}
                            <Copy size={12} />
                          </button>
                        ) : (
                          <span className="text-xs text-[#94a3b8]">Automatic</span>
                        )}
                      </td>

                      <td className="px-5 py-4">
                        <p className="font-semibold text-[#111827] dark:text-white">
                          {promotion.promotion_type === "percentage"
                            ? `${Number(promotion.discount_value).toLocaleString()}%`
                            : promotion.promotion_type === "fixed_amount"
                              ? money(promotion.discount_value)
                              : pretty(promotion.promotion_type)}
                        </p>
                        {promotion.maximum_discount_amount != null && (
                          <p className="mt-1 text-xs text-[#94a3b8]">
                            Max {money(promotion.maximum_discount_amount)}
                          </p>
                        )}
                      </td>

                      <td className="px-5 py-4 text-xs text-[#64748b] dark:text-white/60">
                        <p>
                          {promotion.starts_at
                            ? new Date(promotion.starts_at).toLocaleDateString()
                            : "Starts immediately"}
                        </p>
                        <p className="mt-1">
                          {promotion.ends_at
                            ? `Ends ${new Date(promotion.ends_at).toLocaleDateString()}`
                            : "No end date"}
                        </p>
                      </td>

                      <td className="px-5 py-4">
                        <p className="font-semibold text-[#111827] dark:text-white">
                          {promotion.usage_count}
                          {promotion.usage_limit != null
                            ? ` / ${promotion.usage_limit}`
                            : ""}
                        </p>
                        <p className="mt-1 text-xs text-[#94a3b8]">
                          {promotion.usage_per_customer
                            ? `${promotion.usage_per_customer} per customer`
                            : "No customer limit"}
                        </p>
                      </td>

                      <td className="px-5 py-4">
                        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-blue-700">
                          {promotion.funding_source || "seller"}
                        </span>
                      </td>

                      <td className="px-5 py-4">
                        <StatusBadge
                          active={promotion.is_active}
                          startsAt={promotion.starts_at}
                          endsAt={promotion.ends_at}
                        />
                      </td>

                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => openEdit(promotion)}
                            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#e2e8f0] text-[#64748b] hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/5"
                            aria-label="Edit promotion"
                          >
                            <Edit3 size={14} />
                          </button>

                          <button
                            type="button"
                            disabled={busy === promotion.id}
                            onClick={() => void togglePromotion(promotion)}
                            className="rounded-lg border border-[#e2e8f0] px-3 py-2 text-xs font-semibold text-[#475569] disabled:opacity-50 dark:border-white/10 dark:text-white/70"
                          >
                            {promotion.is_active ? "Pause" : "Activate"}
                          </button>

                          <button
                            type="button"
                            disabled={busy === promotion.id}
                            onClick={() => void removePromotion(promotion)}
                            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
                            aria-label="Delete promotion"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}

                  {!rows.length && (
                    <tr>
                      <td colSpan={8} className="px-5 py-14 text-center">
                        <TicketPercent
                          size={30}
                          className="mx-auto text-[#cbd5e1]"
                        />
                        <p className="mt-3 font-semibold text-[#475569] dark:text-white/80">
                          No promotions found
                        </p>
                        <p className="mt-1 text-sm text-[#94a3b8]">
                          Create your first product promotion or change the filters.
                        </p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <Pagination
              page={page}
              pageSize={pageSize}
              total={meta.total}
              totalPages={meta.total_pages}
              onPage={setPage}
              onPageSize={(size) => {
                setPageSize(size);
                setPage(1);
              }}
            />
          </>
        )}
      </section>

      {editorOpen && (
        <PromotionEditor
          editing={editing}
          form={form}
          setForm={setForm}
          products={visibleProducts}
          productSearch={productSearch}
          setProductSearch={setProductSearch}
          productsLoading={productsLoading}
          saving={saving}
          onClose={closeEditor}
          onSave={() => void submit()}
        />
      )}
    </div>
  );
}

function PromotionEditor({
  editing,
  form,
  setForm,
  products,
  productSearch,
  setProductSearch,
  productsLoading,
  saving,
  onClose,
  onSave,
}: {
  editing: SellerPromotion | null;
  form: PromotionFormState;
  setForm: React.Dispatch<React.SetStateAction<PromotionFormState>>;
  products: Product[];
  productSearch: string;
  setProductSearch: (value: string) => void;
  productsLoading: boolean;
  saving: boolean;
  onClose: () => void;
  onSave: () => void;
}) {
  const toggleProduct = (productId: string) => {
    setForm((current) => ({
      ...current,
      product_ids: current.product_ids.includes(productId)
        ? current.product_ids.filter((id) => id !== productId)
        : [...current.product_ids, productId],
    }));
  };

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm">
      <div className="flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-[#1f2937]">
        <div className="flex items-center justify-between border-b border-[#e7ebf0] px-5 py-4 dark:border-white/10">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f7941d]">
              {editing ? "Update Promotion" : "New Promotion"}
            </p>
            <h2 className="mt-0.5 text-xl font-bold text-[#111827] dark:text-white">
              {editing ? editing.name : "Create seller-funded promotion"}
            </h2>
          </div>
          <button
            type="button"
            disabled={saving}
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#e2e8f0] text-[#64748b] dark:border-white/10"
          >
            <X size={17} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 sm:p-6">
          {editing && (
            <div className="mb-5 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-800">
              Product targeting is fixed when the promotion is created in the current
              backend. You can edit promotion terms here. To change targeted products,
              create a new promotion.
            </div>
          )}

          <div className="grid gap-5 lg:grid-cols-2">
            <section className="space-y-4 rounded-2xl border border-[#e7ebf0] p-4 sm:p-5 dark:border-white/10">
              <div>
                <p className="font-bold text-[#111827] dark:text-white">
                  Promotion details
                </p>
                <p className="mt-1 text-xs text-[#94a3b8]">
                  Define the code, discount and usage limits.
                </p>
              </div>

              <Field label="Promotion name" required>
                <input
                  value={form.name}
                  onChange={(event) =>
                    setForm((x) => ({ ...x, name: event.target.value }))
                  }
                  className={inputClass}
                  placeholder="Weekend Soap Discount"
                />
              </Field>

              <Field
                label="Promo code"
                required={!form.automatic}
                hint={
                  form.automatic
                    ? "Optional for automatic promotions."
                    : "Customers will enter this code during checkout."
                }
              >
                <input
                  value={form.code}
                  disabled={Boolean(editing)}
                  onChange={(event) =>
                    setForm((x) => ({
                      ...x,
                      code: event.target.value.toUpperCase().replace(/\s+/g, ""),
                    }))
                  }
                  className={inputClass}
                  placeholder="SOAP10"
                />
              </Field>

              <Field label="Description">
                <textarea
                  value={form.description}
                  onChange={(event) =>
                    setForm((x) => ({ ...x, description: event.target.value }))
                  }
                  className={textareaClass}
                  placeholder="Customer-facing explanation of this promotion."
                />
              </Field>

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Discount type" required>
                  <select
                    value={form.promotion_type}
                    disabled={Boolean(editing)}
                    onChange={(event) =>
                      setForm((x) => ({
                        ...x,
                        promotion_type: event.target.value as PromotionType,
                      }))
                    }
                    className={inputClass}
                  >
                    <option value="percentage">Percentage</option>
                    <option value="fixed_amount">Fixed amount</option>
                    <option value="free_shipping">Free shipping</option>
                    <option value="buy_x_get_y">Buy X Get Y</option>
                  </select>
                </Field>

                <Field
                  label={
                    form.promotion_type === "percentage"
                      ? "Discount %"
                      : "Discount value"
                  }
                  required={
                    !["free_shipping", "buy_x_get_y"].includes(
                      form.promotion_type,
                    )
                  }
                >
                  <input
                    type="number"
                    min={0}
                    max={
                      form.promotion_type === "percentage" ? 100 : undefined
                    }
                    step="0.01"
                    value={form.discount_value}
                    onChange={(event) =>
                      setForm((x) => ({
                        ...x,
                        discount_value: event.target.value,
                      }))
                    }
                    className={inputClass}
                  />
                </Field>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Minimum order amount">
                  <input
                    type="number"
                    min={0}
                    value={form.minimum_order_amount}
                    onChange={(event) =>
                      setForm((x) => ({
                        ...x,
                        minimum_order_amount: event.target.value,
                      }))
                    }
                    className={inputClass}
                    placeholder="Optional"
                  />
                </Field>

                <Field label="Maximum discount amount">
                  <input
                    type="number"
                    min={0}
                    value={form.maximum_discount_amount}
                    onChange={(event) =>
                      setForm((x) => ({
                        ...x,
                        maximum_discount_amount: event.target.value,
                      }))
                    }
                    className={inputClass}
                    placeholder="Optional"
                  />
                </Field>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Total usage limit">
                  <input
                    type="number"
                    min={0}
                    value={form.usage_limit}
                    onChange={(event) =>
                      setForm((x) => ({ ...x, usage_limit: event.target.value }))
                    }
                    className={inputClass}
                    placeholder="Unlimited"
                  />
                </Field>

                <Field label="Usage per customer">
                  <input
                    type="number"
                    min={1}
                    value={form.usage_per_customer}
                    onChange={(event) =>
                      setForm((x) => ({
                        ...x,
                        usage_per_customer: event.target.value,
                      }))
                    }
                    className={inputClass}
                    placeholder="1"
                  />
                </Field>
              </div>
            </section>

            <section className="space-y-4 rounded-2xl border border-[#e7ebf0] p-4 sm:p-5 dark:border-white/10">
              <div>
                <p className="font-bold text-[#111827] dark:text-white">
                  Schedule & behaviour
                </p>
                <p className="mt-1 text-xs text-[#94a3b8]">
                  Control when and how customers can use the promotion.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Start date / time">
                  <input
                    type="datetime-local"
                    value={form.starts_at}
                    onChange={(event) =>
                      setForm((x) => ({ ...x, starts_at: event.target.value }))
                    }
                    className={inputClass}
                  />
                </Field>

                <Field label="End date / time">
                  <input
                    type="datetime-local"
                    value={form.ends_at}
                    onChange={(event) =>
                      setForm((x) => ({ ...x, ends_at: event.target.value }))
                    }
                    className={inputClass}
                  />
                </Field>
              </div>

              <Toggle
                label="Promotion active"
                hint="Inactive promotions cannot be applied at checkout."
                checked={form.is_active}
                onChange={(value) =>
                  setForm((x) => ({ ...x, is_active: value }))
                }
              />

              <Toggle
                label="Automatic promotion"
                hint="The backend may apply this without requiring a code when checkout integration is completed."
                checked={form.automatic}
                onChange={(value) =>
                  setForm((x) => ({ ...x, automatic: value }))
                }
              />

              <Toggle
                label="Stackable"
                hint="Marks the promotion as eligible to combine with other promotions. Final checkout combination rules remain backend-controlled."
                checked={form.stackable}
                onChange={(value) =>
                  setForm((x) => ({ ...x, stackable: value }))
                }
              />

              <div className="rounded-xl border border-orange-200 bg-orange-50 p-4 text-xs leading-5 text-[#9a5a11]">
                <strong>Seller-funded discount:</strong> this promotion reduces the
                seller-controlled amount. Xerin commission remains governed by the
                marketplace commission engine.
              </div>
            </section>
          </div>

          {!editing && (
            <section className="mt-5 rounded-2xl border border-[#e7ebf0] p-4 sm:p-5 dark:border-white/10">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-bold text-[#111827] dark:text-white">
                    Select products
                  </p>
                  <p className="mt-1 text-xs text-[#94a3b8]">
                    Only your own products can be targeted. The backend verifies
                    ownership again when saving.
                  </p>
                </div>
                <span className="rounded-full bg-orange-50 px-3 py-1 text-xs font-semibold text-[#c66c0b]">
                  {form.product_ids.length} selected
                </span>
              </div>

              <label className="relative mt-4 block">
                <Search
                  size={15}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94a3b8]"
                />
                <input
                  value={productSearch}
                  onChange={(event) => setProductSearch(event.target.value)}
                  placeholder="Search your products..."
                  className={`${inputClass} pl-10`}
                />
              </label>

              {productsLoading ? (
                <div className="py-8 text-center text-sm text-[#64748b]">
                  <RefreshCw size={18} className="mx-auto animate-spin" />
                  <p className="mt-2">Loading your products...</p>
                </div>
              ) : (
                <div className="mt-4 grid max-h-[340px] gap-2 overflow-y-auto sm:grid-cols-2">
                  {products.map((product) => {
                    const selected = form.product_ids.includes(product.id);
                    return (
                      <button
                        type="button"
                        key={product.id}
                        onClick={() => toggleProduct(product.id)}
                        className={`flex items-start gap-3 rounded-xl border p-3 text-left transition ${
                          selected
                            ? "border-orange-300 bg-orange-50"
                            : "border-[#e2e8f0] hover:border-orange-200 dark:border-white/10 dark:bg-white/[0.03]"
                        }`}
                      >
                        <span
                          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
                            selected
                              ? "border-[#f7941d] bg-[#f7941d] text-white"
                              : "border-[#cbd5e1]"
                          }`}
                        >
                          {selected && <CheckCircle2 size={13} />}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-semibold text-[#111827] dark:text-white">
                            {product.name}
                          </span>
                          <span className="mt-0.5 block truncate text-xs text-[#94a3b8]">
                            {product.sku} · Customer price {money(product.sale_price || product.price)}
                          </span>
                        </span>
                      </button>
                    );
                  })}

                  {!products.length && (
                    <div className="col-span-full rounded-xl border border-dashed border-[#d9dee7] p-8 text-center">
                      <Package size={26} className="mx-auto text-[#cbd5e1]" />
                      <p className="mt-2 text-sm text-[#64748b]">
                        No seller products are available for promotion.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </section>
          )}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-[#e7ebf0] px-5 py-4 sm:flex-row sm:justify-end dark:border-white/10">
          <button
            type="button"
            disabled={saving}
            onClick={onClose}
            className="rounded-xl border border-[#e2e8f0] px-5 py-2.5 text-sm font-semibold text-[#475569] disabled:opacity-50 dark:border-white/10 dark:text-white/70"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={onSave}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {saving && <RefreshCw size={14} className="animate-spin" />}
            {saving
              ? "Saving..."
              : editing
                ? "Save Changes"
                : "Create Promotion"}
          </button>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({
  active,
  startsAt,
  endsAt,
}: {
  active: boolean;
  startsAt?: string | null;
  endsAt?: string | null;
}) {
  const now = Date.now();
  const starts = startsAt ? new Date(startsAt).getTime() : null;
  const ends = endsAt ? new Date(endsAt).getTime() : null;

  let label = active ? "Active" : "Inactive";
  let className = active
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : "border-slate-200 bg-slate-50 text-slate-600";

  if (active && starts && starts > now) {
    label = "Scheduled";
    className = "border-blue-200 bg-blue-50 text-blue-700";
  } else if (ends && ends < now) {
    label = "Expired";
    className = "border-amber-200 bg-amber-50 text-amber-700";
  }

  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${className}`}
    >
      {label}
    </span>
  );
}

function SummaryCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: typeof Tag;
}) {
  return (
    <div className="rounded-xl border border-[#e7ebf0] bg-[#f8fafc] p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-2xl font-bold text-[#111827] dark:text-white">
            {value}
          </p>
          <p className="mt-1 text-xs font-medium text-[#64748b] dark:text-white/55">
            {label}
          </p>
        </div>
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-[#f7941d] shadow-sm dark:bg-white/10">
          <Icon size={17} />
        </span>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  required = false,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold text-[#475569] dark:text-white/70">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      {children}
      {hint && (
        <span className="mt-1.5 block text-[11px] leading-4 text-[#94a3b8]">
          {hint}
        </span>
      )}
    </label>
  );
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 rounded-xl border border-[#e2e8f0] p-3 dark:border-white/10">
      <span>
        <span className="block text-sm font-semibold text-[#334155] dark:text-white/80">
          {label}
        </span>
        <span className="mt-0.5 block text-xs leading-5 text-[#94a3b8]">
          {hint}
        </span>
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-4 w-4 accent-[#f7941d]"
      />
    </label>
  );
}

function Pagination({
  page,
  pageSize,
  total,
  totalPages,
  onPage,
  onPageSize,
}: {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}) {
  const from = total ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-col gap-3 border-t border-[#eef1f5] px-5 py-4 sm:flex-row sm:items-center sm:justify-between dark:border-white/10">
      <p className="text-sm text-[#64748b] dark:text-white/55">
        Showing <b>{from}-{to}</b> of <b>{total}</b>
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={pageSize}
          onChange={(event) => onPageSize(Number(event.target.value))}
          className="h-10 rounded-xl border border-[#e2e8f0] bg-white px-3 text-sm dark:border-white/10 dark:bg-white/5 dark:text-white"
        >
          {[10, 20, 50, 100].map((size) => (
            <option key={size} value={size}>
              {size} / page
            </option>
          ))}
        </select>

        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="inline-flex h-10 items-center gap-1 rounded-xl border border-[#e2e8f0] px-3 text-sm font-semibold disabled:opacity-40 dark:border-white/10"
        >
          <ChevronLeft size={14} />
          Previous
        </button>

        <span className="min-w-[80px] text-center text-xs text-[#94a3b8]">
          Page {page} of {Math.max(totalPages, 1)}
        </span>

        <button
          type="button"
          disabled={!totalPages || page >= totalPages}
          onClick={() => onPage(page + 1)}
          className="inline-flex h-10 items-center gap-1 rounded-xl border border-[#e2e8f0] px-3 text-sm font-semibold disabled:opacity-40 dark:border-white/10"
        >
          Next
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

const inputClass =
  "h-11 w-full rounded-xl border border-[#e2e8f0] bg-white px-3 text-sm text-[#111827] outline-none transition focus:border-orange-300 focus:ring-4 focus:ring-orange-50 dark:border-white/10 dark:bg-white/5 dark:text-white";
const textareaClass =
  "min-h-24 w-full rounded-xl border border-[#e2e8f0] bg-white px-3 py-2.5 text-sm text-[#111827] outline-none transition focus:border-orange-300 focus:ring-4 focus:ring-orange-50 dark:border-white/10 dark:bg-white/5 dark:text-white";
