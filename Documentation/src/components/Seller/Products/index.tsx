"use client";

import { ApiError } from "@/lib/api/client";
import { API_BASE_URL } from "@/lib/api/endpoints";
import { productsApi } from "@/lib/api/endpoints/products";
import { sellersApi } from "@/lib/api/endpoints/sellers";
import { sellerInventoryApi } from "@/lib/api/endpoints/seller-inventory";
import { authStorage } from "@/lib/auth/storage";
import type {
  Brand,
  Category,
  Product,
  ProductImage,
  ProductRequest,
} from "@/types/api/product";
import type { SellerPricingPreviewResponse } from "@/types/api/seller";
import {
  AlertCircle,
  Archive,
  BadgeCheck,
  Boxes,
  Camera,
  CheckCircle2,
  Clock3,
  Eye,
  FileText,
  CircleDollarSign,
  Percent,
  ImagePlus,
  Package,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShoppingBag,
  Tag,
  Trash2,
  UploadCloud,
  Warehouse,
  X,
} from "lucide-react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ChangeEvent,
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import toast from "react-hot-toast";

type StoredUser = {
  account_type?: string;
  roles?: string[];
  seller_status?: string | null;
  first_name?: string | null;
};

type SelectedImage = {
  file: File;
  previewUrl: string;
};

type InitialStockForm = {
  quantity: string;
  low_stock_threshold: string;
  warehouse_location: string;
  restock_date: string;
};

const INITIAL_STOCK_FORM: InitialStockForm = {
  quantity: "0",
  low_stock_threshold: "5",
  warehouse_location: "",
  restock_date: "",
};

const STATUS_OPTIONS = [
  "all",
  "draft",
  "pending_review",
  "approved",
  "rejected",
  "inactive",
];

const MAX_PRODUCT_IMAGES = 10;
const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

const INITIAL_FORM: ProductRequest = {
  category_id: "",
  brand_id: null,
  sku: "",
  name: "",
  slug: "",
  description: "",
  price: "",
  sale_price: null,
  currency: "TZS",
  weight: null,
};

const resolveImageUrl = (imageUrl: string) => {
  if (/^(https?:|data:|blob:)/.test(imageUrl)) return imageUrl;

  try {
    const base = new URL(API_BASE_URL);
    return `${base.origin}${imageUrl.startsWith("/") ? "" : "/"}${imageUrl}`;
  } catch {
    return `${API_BASE_URL}${imageUrl.startsWith("/") ? "" : "/"}${imageUrl}`;
  }
};

const slugify = (value: string) =>
  value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 240);

const statusLabel = (status?: string | null) =>
  (status || "draft").replaceAll("_", " ");

const statusClasses = (status?: string | null) => {
  switch (status) {
    case "approved":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "pending_review":
      return "border-blue-200 bg-blue-50 text-blue-700";
    case "rejected":
      return "border-red-200 bg-red-50 text-red-700";
    case "inactive":
      return "border-slate-200 bg-slate-100 text-slate-600";
    default:
      return "border-amber-200 bg-amber-50 text-amber-700";
  }
};

const SellerProducts = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const user = authStorage.getUser<StoredUser>();
  const token = authStorage.getAccessToken();
  const objectUrlsRef = useRef<Set<string>>(new Set());

  const isSeller = useMemo(() => {
    if (!user) return false;
    return (
      user.account_type === "seller" ||
      (user.roles ?? []).includes("seller")
    );
  }, [user]);

  const sellerApproved = user?.seller_status === "approved";

  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const [editorOpen, setEditorOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [form, setForm] = useState<ProductRequest>(INITIAL_FORM);
  const [stockForm, setStockForm] =
    useState<InitialStockForm>(INITIAL_STOCK_FORM);
  const [existingImages, setExistingImages] = useState<ProductImage[]>([]);
  const [selectedImages, setSelectedImages] = useState<SelectedImage[]>([]);
  const [imagesLoading, setImagesLoading] = useState(false);
  const [imageError, setImageError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitIntent, setSubmitIntent] = useState<"draft" | "review">("draft");
  const [pricingPreview, setPricingPreview] =
    useState<SellerPricingPreviewResponse | null>(null);
  const [pricingPreviewLoading, setPricingPreviewLoading] = useState(false);
  const [pricingPreviewError, setPricingPreviewError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [submittingProductId, setSubmittingProductId] = useState<string | null>(
    null,
  );

  const loadData = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError("");

    try {
      const [items, categoryList, brandList] = await Promise.all([
        productsApi.getMyProducts(),
        productsApi.getCategories(),
        productsApi.getBrands(),
      ]);

      setProducts(items);
      setCategories(categoryList);
      setBrands(brandList);
    } catch (cause) {
      const message =
        cause instanceof ApiError
          ? cause.message
          : "Unable to load your seller products.";

      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) {
      router.replace("/signin?redirect=/seller/products");
      return;
    }

    if (!isSeller) {
      router.replace("/my-account");
      return;
    }

    void loadData();
  }, [isSeller, loadData, router, token]);

  useEffect(() => {
    const requestedStatus = searchParams.get("status");

    if (requestedStatus && STATUS_OPTIONS.includes(requestedStatus)) {
      setStatusFilter(requestedStatus);
    }

    if (searchParams.get("create") === "true" && sellerApproved) {
      openCreate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, sellerApproved]);

  useEffect(() => {
    return () => {
      objectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      objectUrlsRef.current.clear();
    };
  }, []);


  // Phase 1 pricing preview is always calculated by the backend.
  // The browser never decides marketplace commission by itself.
  useEffect(() => {
    const basePrice = Number(form.price);
    const salePrice =
      form.sale_price === null || form.sale_price === ""
        ? null
        : Number(form.sale_price);

    if (
      !editorOpen ||
      !form.category_id ||
      !Number.isFinite(basePrice) ||
      basePrice <= 0 ||
      (salePrice !== null && (!Number.isFinite(salePrice) || salePrice <= 0))
    ) {
      setPricingPreview(null);
      setPricingPreviewError("");
      return;
    }

    const timer = window.setTimeout(async () => {
      setPricingPreviewLoading(true);
      setPricingPreviewError("");

      try {
        const preview = await sellersApi.previewPricing({
          seller_base_price: basePrice,
          seller_sale_price: salePrice,
          category_id: form.category_id,
          product_id: editingProduct?.id ?? null,
          currency: form.currency || "TZS",
        });

        setPricingPreview(preview);
      } catch (cause) {
        setPricingPreview(null);
        setPricingPreviewError(
          cause instanceof ApiError
            ? cause.message
            : "Unable to calculate marketplace pricing.",
        );
      } finally {
        setPricingPreviewLoading(false);
      }
    }, 350);

    return () => window.clearTimeout(timer);
  }, [
    editorOpen,
    editingProduct?.id,
    form.category_id,
    form.currency,
    form.price,
    form.sale_price,
  ]);

  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      const category = categories.find((item) => item.id === product.category_id);
      const brand = brands.find((item) => item.id === product.brand_id);
      const haystack = [
        product.name,
        product.sku,
        product.status,
        category?.name,
        brand?.name,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      const matchesSearch =
        !search.trim() || haystack.includes(search.trim().toLowerCase());
      const matchesStatus =
        statusFilter === "all" || product.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [brands, categories, products, search, statusFilter]);

  const counts = useMemo(
    () => ({
      total: products.length,
      draft: products.filter((item) => item.status === "draft").length,
      review: products.filter((item) => item.status === "pending_review").length,
      approved: products.filter((item) => item.status === "approved").length,
      rejected: products.filter((item) => item.status === "rejected").length,
    }),
    [products],
  );

  function clearSelectedImages() {
    selectedImages.forEach(({ previewUrl }) => {
      URL.revokeObjectURL(previewUrl);
      objectUrlsRef.current.delete(previewUrl);
    });
    setSelectedImages([]);
  }

  function closeEditor() {
    if (isSubmitting) return;

    clearSelectedImages();
    setEditorOpen(false);
    setEditingProduct(null);
    setForm(INITIAL_FORM);
    setStockForm(INITIAL_STOCK_FORM);
    setPricingPreview(null);
    setPricingPreviewError("");
    setExistingImages([]);
    setImageError("");
    setSubmitIntent("draft");
  }

  function openCreate() {
    if (!sellerApproved) {
      toast.error("Your seller account must be approved before listing products.");
      return;
    }

    clearSelectedImages();
    setEditingProduct(null);
    setExistingImages([]);
    setForm(INITIAL_FORM);
    setStockForm(INITIAL_STOCK_FORM);
    setImageError("");
    setSubmitIntent("draft");
    setEditorOpen(true);
  }

  async function openEdit(product: Product) {
    if (product.status === "pending_review") {
      toast.error("This product is under review and cannot be edited.");
      return;
    }

    clearSelectedImages();
    setEditingProduct(product);
    setForm({
      category_id: product.category_id ?? "",
      brand_id: product.brand_id ?? null,
      sku: product.sku ?? "",
      name: product.name,
      slug: product.slug ?? "",
      description: product.description ?? "",
      price: product.seller_base_price ?? product.price,
      sale_price: product.seller_sale_price ?? product.sale_price ?? null,
      currency: product.currency ?? "TZS",
      weight: product.weight ?? null,
    });
    setImageError("");
    setPricingPreview(null);
    setPricingPreviewError("");
    setExistingImages([]);
    setSubmitIntent("draft");
    setEditorOpen(true);
    setImagesLoading(true);

    try {
      setExistingImages(await productsApi.getMyImages(product.id));
    } catch (cause) {
      toast.error(
        cause instanceof ApiError
          ? cause.message
          : "Unable to load the product images.",
      );
    } finally {
      setImagesLoading(false);
    }
  }

  function validateImage(file: File) {
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      return "Only JPEG, PNG and WEBP images are allowed.";
    }

    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      return "Each product image must be 5 MB or smaller.";
    }

    return null;
  }

  function selectImages(event: ChangeEvent<HTMLInputElement>) {
    setImageError("");

    const incoming = Array.from(event.target.files ?? []);
    event.target.value = "";

    if (!incoming.length) return;

    const availableSlots =
      MAX_PRODUCT_IMAGES - existingImages.length - selectedImages.length;

    if (availableSlots <= 0) {
      setImageError(`Maximum ${MAX_PRODUCT_IMAGES} product images are allowed.`);
      return;
    }

    const accepted: SelectedImage[] = [];

    for (const file of incoming.slice(0, availableSlots)) {
      const validationError = validateImage(file);

      if (validationError) {
        setImageError(`${file.name}: ${validationError}`);
        continue;
      }

      const previewUrl = URL.createObjectURL(file);
      objectUrlsRef.current.add(previewUrl);
      accepted.push({ file, previewUrl });
    }

    setSelectedImages((current) => [...current, ...accepted]);

    if (incoming.length > availableSlots) {
      setImageError(
        `Only ${availableSlots} more image${
          availableSlots === 1 ? "" : "s"
        } can be added.`,
      );
    }
  }

  function removeSelectedImage(index: number) {
    setSelectedImages((current) => {
      const target = current[index];

      if (target) {
        URL.revokeObjectURL(target.previewUrl);
        objectUrlsRef.current.delete(target.previewUrl);
      }

      return current.filter((_, itemIndex) => itemIndex !== index);
    });
  }

  async function removeExistingImage(image: ProductImage) {
    if (!editingProduct || editingProduct.status === "pending_review") return;

    try {
      await productsApi.deleteImage(editingProduct.id, image.id);
      setExistingImages((current) =>
        current.filter((item) => item.id !== image.id),
      );
      toast.success("Product image removed.");
    } catch (cause) {
      toast.error(
        cause instanceof ApiError ? cause.message : "Unable to remove image.",
      );
    }
  }

  function updateName(value: string) {
    setForm((current) => ({
      ...current,
      name: value,
      slug:
        editingProduct && current.slug
          ? current.slug
          : slugify(value),
    }));
  }

  function validateForm() {
    if (!form.category_id) return "Select a product category.";
    if (!form.name.trim()) return "Enter the product name.";
    if (!form.sku.trim()) return "Enter the product SKU.";
    if (!form.slug.trim()) return "Enter the product slug.";
    if (!form.description?.trim()) return "Add a useful product description.";

    const price = Number(form.price);
    if (!Number.isFinite(price) || price < 0) {
      return "Enter a valid seller base price.";
    }

    if (form.sale_price !== null && form.sale_price !== "") {
      const salePrice = Number(form.sale_price);

      if (!Number.isFinite(salePrice) || salePrice < 0) {
        return "Enter a valid sale price.";
      }

      if (salePrice > price) {
        return "Your promotional base price cannot be greater than your regular base price.";
      }
    }

    if (!editingProduct) {
      const openingStock = Number(stockForm.quantity);
      const threshold = Number(stockForm.low_stock_threshold);

      if (!Number.isInteger(openingStock) || openingStock < 0) {
        return "Enter a valid opening stock quantity (0 or more).";
      }

      if (!Number.isInteger(threshold) || threshold < 0) {
        return "Enter a valid low-stock threshold (0 or more).";
      }
    }

    const totalImages = existingImages.length + selectedImages.length;

    if (totalImages < 1) {
      return "Upload at least one product image.";
    }

    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!sellerApproved) {
      toast.error("Your seller account is not approved.");
      return;
    }

    const validationError = validateForm();

    if (validationError) {
      toast.error(validationError);
      return;
    }

    const payload: ProductRequest = {
      ...form,
      category_id: form.category_id,
      brand_id: form.brand_id || null,
      sku: form.sku.trim(),
      name: form.name.trim(),
      slug: slugify(form.slug),
      description: form.description?.trim() || null,
      price: Number(form.price),
      sale_price:
        form.sale_price === null || form.sale_price === ""
          ? null
          : Number(form.sale_price),
      currency: form.currency || "TZS",
      weight:
        form.weight === null || form.weight === ""
          ? null
          : Number(form.weight),
    };

    setIsSubmitting(true);

    try {
      const product = editingProduct
        ? await productsApi.update(editingProduct.id, payload)
        : await productsApi.create(payload);

      if (!editingProduct) {
        await sellerInventoryApi.configure({
          product_id: String(product.id),
          variant_id: null,
          quantity: Number(stockForm.quantity),
          low_stock_threshold: Number(stockForm.low_stock_threshold),
          warehouse_location:
            stockForm.warehouse_location.trim() || null,
          restock_date: stockForm.restock_date
            ? new Date(stockForm.restock_date).toISOString()
            : null,
        });
      }

      if (selectedImages.length) {
        await productsApi.uploadImageFiles(
          product.id,
          selectedImages.map((item) => item.file),
          payload.name,
        );
      }

      if (submitIntent === "review") {
        await productsApi.submitForReview(product.id);
        toast.success(
          "Product submitted successfully and is now waiting for Admin review.",
        );
      } else {
        toast.success(
          editingProduct
            ? "Product draft updated successfully."
            : "Product saved as a draft.",
        );
      }

      closeEditor();
      await loadData();
    } catch (cause) {
      toast.error(
        cause instanceof ApiError ? cause.message : "Unable to save the product.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitExistingProduct(product: Product) {
    if (!["draft", "rejected"].includes(product.status)) return;

    setSubmittingProductId(String(product.id));

    try {
      await productsApi.submitForReview(product.id);
      toast.success("Product submitted for Admin review.");
      await loadData();
    } catch (cause) {
      toast.error(
        cause instanceof ApiError
          ? cause.message
          : "Unable to submit the product for review.",
      );
    } finally {
      setSubmittingProductId(null);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;

    setIsDeleting(true);

    try {
      await productsApi.delete(deleteTarget.id);
      toast.success("Product archived successfully.");
      setDeleteTarget(null);
      await loadData();
    } catch (cause) {
      toast.error(
        cause instanceof ApiError ? cause.message : "Unable to archive product.",
      );
    } finally {
      setIsDeleting(false);
    }
  }

  function formatPrice(value: number | string | null | undefined) {
    if (value === null || value === undefined) return "—";

    const numeric = Number(value);

    if (!Number.isFinite(numeric)) return "—";

    return `TZS ${numeric.toLocaleString()}`;
  }

  if (!token || !isSeller) return null;

  return (
    <>
      <div className="mx-auto max-w-[1500px] space-y-5">
        {!sellerApproved && (
          <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
            <AlertCircle size={20} className="mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold">Product listing is currently locked</p>
              <p className="mt-1 text-sm leading-6">
                Your seller account must be approved before you can create or
                manage marketplace products.
              </p>
            </div>
          </div>
        )}

        <section className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f7941d]">
                Seller catalogue
              </p>
              <h1 className="mt-1 text-2xl font-bold tracking-[-0.025em] text-[#111827]">
                Products
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#64748b]">
                Create product listings, upload real product images, save drafts
                and submit completed products for marketplace review.
              </p>
            </div>

            <button
              type="button"
              disabled={!sellerApproved}
              onClick={openCreate}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#f7941d] px-5 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(247,148,29,0.18)] transition hover:bg-[#e98716] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus size={17} />
              Add Product
            </button>
          </div>
        </section>

        <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          <StatCard label="All products" value={counts.total} icon={ShoppingBag} />
          <StatCard label="Draft" value={counts.draft} icon={FileText} />
          <StatCard label="Under review" value={counts.review} icon={Clock3} />
          <StatCard label="Approved" value={counts.approved} icon={BadgeCheck} />
          <StatCard label="Rejected" value={counts.rejected} icon={AlertCircle} />
        </section>

        <section className="rounded-2xl border border-[#e7ebf0] bg-white shadow-sm">
          <div className="flex flex-col gap-3 border-b border-[#edf0f4] p-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative min-w-0 flex-1 lg:max-w-xl">
              <Search
                size={17}
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94a3b8]"
              />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by product name, SKU, category or brand..."
                className="h-11 w-full rounded-xl border border-[#e1e6ec] bg-[#f8fafc] pl-10 pr-4 text-sm outline-none transition focus:border-[#f7941d] focus:bg-white"
              />
            </div>

            <div className="flex gap-2">
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="h-11 rounded-xl border border-[#e1e6ec] bg-white px-4 text-sm outline-none"
              >
                {STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {status === "all" ? "All statuses" : statusLabel(status)}
                  </option>
                ))}
              </select>

              <button
                type="button"
                onClick={() => void loadData()}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-[#e1e6ec] bg-white px-4 text-sm font-semibold text-[#475569] hover:bg-slate-50"
              >
                <RefreshCw size={15} />
                Refresh
              </button>
            </div>
          </div>

          {loading ? (
            <div className="p-16 text-center">
              <RefreshCw
                className="mx-auto animate-spin text-[#f7941d]"
                size={25}
              />
              <p className="mt-3 text-sm text-[#64748b]">Loading products...</p>
            </div>
          ) : error ? (
            <div className="p-12 text-center text-red-600">{error}</div>
          ) : filteredProducts.length === 0 ? (
            <div className="p-14 text-center">
              <Package className="mx-auto text-[#cbd5e1]" size={40} />
              <h3 className="mt-3 font-semibold text-[#111827]">
                No products found
              </h3>
              <p className="mt-1 text-sm text-[#64748b]">
                {products.length
                  ? "Try changing your search or status filter."
                  : "Create your first product listing to start building your seller catalogue."}
              </p>
              {!products.length && sellerApproved && (
                <button
                  type="button"
                  onClick={openCreate}
                  className="mt-5 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white"
                >
                  Add your first product
                </button>
              )}
            </div>
          ) : (
            <div className="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {filteredProducts.map((product) => {
                const category = categories.find(
                  (item) => item.id === product.category_id,
                );
                const brand = brands.find(
                  (item) => item.id === product.brand_id,
                );
                const editable = product.status !== "pending_review";

                return (
                  <article
                    key={String(product.id)}
                    className="overflow-hidden rounded-2xl border border-[#e7ebf0] bg-white transition hover:-translate-y-0.5 hover:shadow-lg"
                  >
                    <div className="relative flex h-40 items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100">
                      {product.images?.[0]?.image_url ? (
                        <Image
                          src={resolveImageUrl(product.images[0].image_url)}
                          alt={product.name}
                          fill
                          unoptimized
                          className="object-cover"
                        />
                      ) : (
                        <Package size={38} className="text-[#cbd5e1]" />
                      )}

                      <span
                        className={`absolute left-3 top-3 rounded-full border px-2.5 py-1 text-[10px] font-bold capitalize ${statusClasses(
                          product.status,
                        )}`}
                      >
                        {statusLabel(product.status)}
                      </span>
                    </div>

                    <div className="p-4">
                      <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#f7941d]">
                        {category?.name || "Uncategorised"}
                      </p>

                      <h3 className="mt-1 line-clamp-1 font-semibold text-[#111827]">
                        {product.name}
                      </h3>

                      <p className="mt-1 text-xs text-[#94a3b8]">
                        SKU: {product.sku}
                        {brand?.name ? ` · ${brand.name}` : ""}
                      </p>

                      <div className="mt-4 grid grid-cols-2 gap-3">
                        <div className="rounded-xl bg-slate-50 p-3">
                          <p className="text-[10px] font-bold uppercase tracking-wide text-[#94a3b8]">
                            Your base price
                          </p>
                          <p className="mt-1 font-bold text-[#111827]">
                            {formatPrice(
                              product.seller_sale_price ||
                                product.seller_base_price ||
                                product.sale_price ||
                                product.price,
                            )}
                          </p>
                        </div>

                        <div className="rounded-xl bg-orange-50 p-3">
                          <p className="text-[10px] font-bold uppercase tracking-wide text-[#c66c0b]">
                            Customer price
                          </p>
                          <p className="mt-1 font-bold text-[#111827]">
                            {formatPrice(product.sale_price || product.price)}
                          </p>
                        </div>
                      </div>

                      {product.commission_rate_snapshot !== undefined && (
                        <p className="mt-2 text-xs text-[#64748b]">
                          Marketplace commission:{" "}
                          <b className="text-[#111827]">
                            {Number(product.commission_rate_snapshot).toLocaleString()}%
                          </b>
                          {" · "}
                          {formatPrice(product.commission_amount_snapshot)}
                        </p>
                      )}

                      {product.rejection_reason && (
                        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3">
                          <p className="text-[10px] font-bold uppercase tracking-wider text-red-700">
                            Admin feedback
                          </p>
                          <p className="mt-1 text-xs leading-5 text-red-700">
                            {product.rejection_reason}
                          </p>
                        </div>
                      )}

                      <div className="mt-4 flex flex-wrap gap-2 border-t border-[#edf0f4] pt-4">
                        {editable && (
                          <button
                            type="button"
                            onClick={() => void openEdit(product)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-[#e1e6ec] px-3 py-2 text-xs font-semibold text-[#475569] hover:border-[#f7941d] hover:text-[#f7941d]"
                          >
                            <Pencil size={13} />
                            Edit
                          </button>
                        )}

                        {["draft", "rejected"].includes(product.status) && (
                          <button
                            type="button"
                            disabled={
                              submittingProductId === String(product.id)
                            }
                            onClick={() => void submitExistingProduct(product)}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-[#111827] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
                          >
                            <Send size={13} />
                            {submittingProductId === String(product.id)
                              ? "Submitting..."
                              : "Submit review"}
                          </button>
                        )}

                        {product.status !== "pending_review" && (
                          <button
                            type="button"
                            onClick={() => setDeleteTarget(product)}
                            className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-semibold text-red-600 hover:bg-red-50"
                          >
                            <Archive size={13} />
                            Archive
                          </button>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {editorOpen && (
        <div
          className="fixed inset-0 z-[100] flex justify-end bg-black/45 backdrop-blur-[2px]"
          onMouseDown={closeEditor}
        >
          <aside
            className="flex h-full w-full max-w-4xl flex-col bg-[#f8fafc] shadow-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex shrink-0 items-start justify-between border-b border-[#e7ebf0] bg-white px-5 py-4 sm:px-7">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f7941d]">
                  Seller catalogue
                </p>
                <h2 className="mt-1 text-xl font-bold text-[#111827]">
                  {editingProduct ? "Edit Product" : "Create New Product"}
                </h2>
                <p className="mt-1 text-xs text-[#64748b]">
                  Product ownership is automatically linked to your approved
                  seller account.
                </p>
              </div>

              <button
                type="button"
                onClick={closeEditor}
                disabled={isSubmitting}
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#e7ebf0] bg-white text-[#64748b] hover:bg-slate-50"
              >
                <X size={18} />
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="flex min-h-0 flex-1 flex-col"
            >
              <div className="flex-1 space-y-5 overflow-y-auto p-5 sm:p-7">
                {editingProduct?.rejection_reason && (
                  <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
                    <p className="text-xs font-bold uppercase tracking-wider">
                      Admin correction request
                    </p>
                    <p className="mt-1 text-sm leading-6">
                      {editingProduct.rejection_reason}
                    </p>
                  </div>
                )}

                <FormSection
                  icon={Tag}
                  title="Product identity"
                  description="Choose the marketplace category and provide the basic product information."
                >
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Product category" required>
                      <select
                        value={String(form.category_id || "")}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            category_id: event.target.value,
                          }))
                        }
                        disabled={isSubmitting}
                        className="input"
                      >
                        <option value="">Select category</option>
                        {categories.map((category) => (
                          <option
                            key={String(category.id)}
                            value={String(category.id)}
                          >
                            {category.name}
                          </option>
                        ))}
                      </select>
                    </Field>

                    <Field label="Brand">
                      <select
                        value={String(form.brand_id || "")}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            brand_id: event.target.value || null,
                          }))
                        }
                        disabled={isSubmitting}
                        className="input"
                      >
                        <option value="">No brand / unbranded</option>
                        {brands.map((brand) => (
                          <option key={String(brand.id)} value={String(brand.id)}>
                            {brand.name}
                          </option>
                        ))}
                      </select>
                    </Field>

                    <Field label="Product name" required>
                      <input
                        value={form.name}
                        onChange={(event) => updateName(event.target.value)}
                        placeholder="e.g. Samsung Galaxy S24 256GB"
                        disabled={isSubmitting}
                        className="input"
                      />
                    </Field>

                    <Field
                      label="SKU / ownership reference"
                      required
                      hint="Your unique stock-keeping reference for this product."
                    >
                      <input
                        value={form.sku}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            sku: event.target.value.toUpperCase(),
                          }))
                        }
                        placeholder="e.g. PHYSIO-001"
                        disabled={isSubmitting}
                        className="input"
                      />
                    </Field>

                    <div className="md:col-span-2">
                      <Field
                        label="Product slug"
                        required
                        hint="Used in product URLs. Generated from the product name and editable."
                      >
                        <input
                          value={form.slug}
                          onChange={(event) =>
                            setForm((current) => ({
                              ...current,
                              slug: slugify(event.target.value),
                            }))
                          }
                          placeholder="samsung-galaxy-s24-256gb"
                          disabled={isSubmitting}
                          className="input"
                        />
                      </Field>
                    </div>
                  </div>
                </FormSection>

                <FormSection
                  icon={FileText}
                  title="Description"
                  description="Explain exactly what the buyer is purchasing, its condition and important features."
                >
                  <Field label="Product description" required>
                    <textarea
                      value={form.description ?? ""}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          description: event.target.value,
                        }))
                      }
                      rows={6}
                      maxLength={5000}
                      placeholder="Describe the product, specifications, material, condition, package contents and other important buyer information..."
                      disabled={isSubmitting}
                      className="input min-h-36 resize-y"
                    />
                    <p className="mt-1 text-right text-[11px] text-[#94a3b8]">
                      {(form.description?.length ?? 0).toLocaleString()} / 5,000
                    </p>
                  </Field>
                </FormSection>

                <FormSection
                  icon={Camera}
                  title="Product images"
                  description={`Upload up to ${MAX_PRODUCT_IMAGES} real product images. JPEG, PNG or WEBP only, maximum 5 MB each.`}
                >
                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-[#d7dee7] bg-[#f8fafc] px-5 py-8 text-center transition hover:border-[#f7941d] hover:bg-orange-50/30">
                    <UploadCloud size={30} className="text-[#f7941d]" />
                    <span className="mt-3 text-sm font-semibold text-[#111827]">
                      Choose product images
                    </span>
                    <span className="mt-1 text-xs text-[#64748b]">
                      Select multiple files · JPEG, PNG, WEBP · max 5 MB each
                    </span>
                    <input
                      type="file"
                      multiple
                      accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                      disabled={
                        isSubmitting ||
                        existingImages.length + selectedImages.length >=
                          MAX_PRODUCT_IMAGES
                      }
                      onChange={selectImages}
                      className="hidden"
                    />
                  </label>

                  {imagesLoading && (
                    <p className="mt-3 inline-flex items-center gap-2 text-sm text-[#64748b]">
                      <RefreshCw size={14} className="animate-spin" />
                      Loading stored product images...
                    </p>
                  )}

                  {(existingImages.length > 0 || selectedImages.length > 0) && (
                    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                      {existingImages.map((image, index) => (
                        <div
                          key={String(image.id)}
                          className="group relative overflow-hidden rounded-xl border border-[#e1e6ec] bg-white"
                        >
                          <div className="relative h-28">
                            <Image
                              src={resolveImageUrl(
                                image.thumbnail_url || image.image_url,
                              )}
                              alt={
                                image.alt_text ||
                                `${form.name || "Product"} image ${index + 1}`
                              }
                              fill
                              unoptimized
                              className="object-cover"
                            />
                          </div>

                          {image.is_primary && (
                            <span className="absolute left-2 top-2 rounded-full bg-[#111827] px-2 py-1 text-[9px] font-bold uppercase text-white">
                              Primary
                            </span>
                          )}

                          <button
                            type="button"
                            disabled={isSubmitting}
                            onClick={() => void removeExistingImage(image)}
                            className="flex w-full items-center justify-center gap-1.5 border-t border-[#edf0f4] px-2 py-2 text-[11px] font-semibold text-red-600 hover:bg-red-50"
                          >
                            <Trash2 size={12} />
                            Remove
                          </button>
                        </div>
                      ))}

                      {selectedImages.map((image, index) => (
                        <div
                          key={image.previewUrl}
                          className="relative overflow-hidden rounded-xl border border-orange-200 bg-white"
                        >
                          <div className="relative h-28">
                            <Image
                              src={image.previewUrl}
                              alt={`New product image ${index + 1}`}
                              fill
                              unoptimized
                              className="object-cover"
                            />
                          </div>

                          <span className="absolute left-2 top-2 rounded-full bg-[#f7941d] px-2 py-1 text-[9px] font-bold uppercase text-white">
                            New
                          </span>

                          <button
                            type="button"
                            disabled={isSubmitting}
                            onClick={() => removeSelectedImage(index)}
                            className="flex w-full items-center justify-center gap-1.5 border-t border-[#edf0f4] px-2 py-2 text-[11px] font-semibold text-red-600 hover:bg-red-50"
                          >
                            <Trash2 size={12} />
                            Remove
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="mt-3 flex items-center justify-between gap-3 text-xs">
                    <span className="text-[#64748b]">
                      {existingImages.length + selectedImages.length} /{" "}
                      {MAX_PRODUCT_IMAGES} images selected
                    </span>
                    <span className="text-[#94a3b8]">
                      The first uploaded image becomes the primary image.
                    </span>
                  </div>

                  {imageError && (
                    <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700">
                      {imageError}
                    </p>
                  )}
                </FormSection>

                <FormSection
                  icon={Boxes}
                  title="Pricing & physical details"
                  description="Enter the amount you want to receive. Xerin calculates the marketplace commission and customer-facing price from Admin commission rules."
                >
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <Field label="Currency" required>
                      <select
                        value={form.currency || "TZS"}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            currency: event.target.value,
                          }))
                        }
                        disabled={isSubmitting}
                        className="input"
                      >
                        <option value="TZS">TZS — Tanzanian Shilling</option>
                        <option value="USD">USD — US Dollar</option>
                      </select>
                    </Field>

                    <Field
                      label="Your base price"
                      required
                      hint="The amount you want for this product before Xerin marketplace commission."
                    >
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={form.price}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            price: event.target.value,
                          }))
                        }
                        placeholder="0.00"
                        disabled={isSubmitting}
                        className="input"
                      />
                    </Field>

                    <Field
                      label="Your promotional base price"
                      hint="Optional seller price before commission. Must be lower than your regular base price."
                    >
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={form.sale_price ?? ""}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            sale_price: event.target.value || null,
                          }))
                        }
                        placeholder="0.00"
                        disabled={isSubmitting}
                        className="input"
                      />
                    </Field>

                    <Field label="Weight (kg)">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={form.weight ?? ""}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            weight: event.target.value || null,
                          }))
                        }
                        placeholder="e.g. 0.75"
                        disabled={isSubmitting}
                        className="input"
                      />
                    </Field>
                  </div>
                


                  {!editingProduct && (
                    <div className="mt-5 rounded-2xl border border-[#dfe5ec] bg-[#f8fafc] p-4 sm:p-5">
                      <div className="flex items-start gap-3">
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-[#f7941d] shadow-sm">
                          <Warehouse size={19} />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-bold text-[#111827]">
                            Opening inventory
                          </p>
                          <p className="mt-1 text-xs leading-5 text-[#64748b]">
                            Enter the seller's real physical stock for this product.
                            Xerin calculates available quantity as physical quantity
                            minus units reserved by active orders.
                          </p>

                          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            <Field label="Opening stock" required>
                              <input
                                type="number"
                                min="0"
                                step="1"
                                value={stockForm.quantity}
                                onChange={(event) =>
                                  setStockForm((current) => ({
                                    ...current,
                                    quantity: event.target.value,
                                  }))
                                }
                                disabled={isSubmitting}
                                className="input"
                              />
                            </Field>

                            <Field label="Low-stock threshold">
                              <input
                                type="number"
                                min="0"
                                step="1"
                                value={stockForm.low_stock_threshold}
                                onChange={(event) =>
                                  setStockForm((current) => ({
                                    ...current,
                                    low_stock_threshold: event.target.value,
                                  }))
                                }
                                disabled={isSubmitting}
                                className="input"
                              />
                            </Field>

                            <Field label="Warehouse / stock location">
                              <input
                                value={stockForm.warehouse_location}
                                onChange={(event) =>
                                  setStockForm((current) => ({
                                    ...current,
                                    warehouse_location: event.target.value,
                                  }))
                                }
                                placeholder="e.g. Main Store - Rack A"
                                disabled={isSubmitting}
                                className="input"
                              />
                            </Field>

                            <Field label="Expected restock date">
                              <input
                                type="date"
                                value={stockForm.restock_date}
                                onChange={(event) =>
                                  setStockForm((current) => ({
                                    ...current,
                                    restock_date: event.target.value,
                                  }))
                                }
                                disabled={isSubmitting}
                                className="input"
                              />
                            </Field>
                          </div>

                          <div className="mt-4 grid gap-3 sm:grid-cols-3">
                            <InventoryPreviewStat
                              label="Physical quantity"
                              value={Math.max(0, Number(stockForm.quantity) || 0)}
                            />
                            <InventoryPreviewStat label="Reserved" value={0} />
                            <InventoryPreviewStat
                              label="Available to customers"
                              value={Math.max(0, Number(stockForm.quantity) || 0)}
                              highlight
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="mt-5 rounded-2xl border border-orange-200 bg-orange-50/60 p-4 sm:p-5">
                    <div className="flex items-start gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-[#f7941d] shadow-sm">
                        <CircleDollarSign size={19} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <p className="text-sm font-bold text-[#111827]">
                              Marketplace pricing preview
                            </p>
                            <p className="mt-0.5 text-xs leading-5 text-[#64748b]">
                              Calculated from the active Admin commission rule. The final amount is recalculated again by the backend when the product is saved.
                            </p>
                          </div>
                          {pricingPreview?.commission_scope && (
                            <span className="mt-2 inline-flex w-fit rounded-full border border-orange-200 bg-white px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-[#c66c0b] sm:mt-0">
                              {pricingPreview.commission_scope.replaceAll("_", " ")} rule
                            </span>
                          )}
                        </div>

                        {pricingPreviewLoading ? (
                          <div className="mt-4 flex items-center gap-2 text-sm text-[#64748b]">
                            <RefreshCw size={15} className="animate-spin" />
                            Calculating customer price...
                          </div>
                        ) : pricingPreview ? (
                          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                            <PricingStat
                              label="Your base price"
                              value={formatPrice(pricingPreview.seller_base_price)}
                            />
                            <PricingStat
                              label="Commission"
                              value={`${Number(pricingPreview.commission_rate).toLocaleString()}%`}
                              detail={formatPrice(pricingPreview.commission_amount)}
                            />
                            <PricingStat
                              label="Customer regular price"
                              value={formatPrice(pricingPreview.customer_price)}
                              highlight
                            />
                            <PricingStat
                              label="Customer sale price"
                              value={
                                pricingPreview.customer_sale_price
                                  ? formatPrice(pricingPreview.customer_sale_price)
                                  : "Not set"
                              }
                            />
                          </div>
                        ) : (
                          <p className="mt-4 text-sm text-[#64748b]">
                            Select a category and enter your base price to see the marketplace calculation.
                          </p>
                        )}

                        {pricingPreviewError && (
                          <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700">
                            {pricingPreviewError}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
</FormSection>

                <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4">
                  <div className="flex items-start gap-3">
                    <CheckCircle2
                      size={19}
                      className="mt-0.5 shrink-0 text-blue-600"
                    />
                    <div>
                      <p className="text-sm font-semibold text-blue-900">
                        Product ownership & review
                      </p>
                      <p className="mt-1 text-xs leading-5 text-blue-700">
                        This product is automatically owned by your seller
                        account. You can save it as a draft, or submit it for
                        Admin review. Products become visible to customers only
                        after approval.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="shrink-0 border-t border-[#e7ebf0] bg-white px-5 py-4 sm:px-7">
                <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <button
                    type="button"
                    onClick={closeEditor}
                    disabled={isSubmitting}
                    className="h-11 rounded-xl border border-[#e1e6ec] px-5 text-sm font-semibold text-[#475569] hover:bg-slate-50"
                  >
                    Cancel
                  </button>

                  <div className="flex flex-col gap-2 sm:flex-row">
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      onClick={() => setSubmitIntent("draft")}
                      className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-[#111827] bg-white px-5 text-sm font-semibold text-[#111827] disabled:opacity-50"
                    >
                      <FileText size={15} />
                      {isSubmitting && submitIntent === "draft"
                        ? "Saving..."
                        : "Save Draft"}
                    </button>

                    <button
                      type="submit"
                      disabled={isSubmitting}
                      onClick={() => setSubmitIntent("review")}
                      className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#f7941d] px-5 text-sm font-semibold text-white shadow-[0_6px_18px_rgba(247,148,29,0.18)] disabled:opacity-50"
                    >
                      <Send size={15} />
                      {isSubmitting && submitIntent === "review"
                        ? "Submitting..."
                        : "Save & Submit for Review"}
                    </button>
                  </div>
                </div>
              </div>
            </form>
          </aside>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/55 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-red-50 text-red-600">
              <Archive size={20} />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-[#111827]">
              Archive this product?
            </h3>
            <p className="mt-2 text-sm leading-6 text-[#64748b]">
              <strong>{deleteTarget.name}</strong> will be removed from active
              seller products. A product currently under review cannot be
              archived.
            </p>

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setDeleteTarget(null)}
                className="flex-1 rounded-xl border border-[#e1e6ec] px-4 py-3 text-sm font-semibold text-[#475569]"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => void handleDelete()}
                className="flex-1 rounded-xl bg-red-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
              >
                {isDeleting ? "Archiving..." : "Archive Product"}
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx global>{`
        .input {
          width: 100%;
          min-height: 44px;
          border-radius: 0.75rem;
          border: 1px solid #e1e6ec;
          background: #ffffff;
          padding: 0.7rem 0.9rem;
          font-size: 0.875rem;
          color: #111827;
          outline: none;
          transition:
            border-color 160ms ease,
            box-shadow 160ms ease;
        }

        .input:focus {
          border-color: #f7941d;
          box-shadow: 0 0 0 3px rgba(247, 148, 29, 0.09);
        }

        .input:disabled {
          cursor: not-allowed;
          background: #f8fafc;
          opacity: 0.7;
        }
      `}</style>
    </>
  );
};

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: typeof ShoppingBag;
}) {
  return (
    <div className="rounded-2xl border border-[#e7ebf0] bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-50 text-[#f7941d]">
          <Icon size={17} />
        </span>
        <span className="text-2xl font-bold tracking-[-0.03em] text-[#111827]">
          {value}
        </span>
      </div>
      <p className="mt-3 text-xs font-medium text-[#64748b]">{label}</p>
    </div>
  );
}

function FormSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Tag;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm sm:p-6">
      <div className="mb-5 flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-50 text-[#f7941d]">
          <Icon size={18} />
        </span>
        <div>
          <h3 className="font-semibold text-[#111827]">{title}</h3>
          <p className="mt-1 text-xs leading-5 text-[#64748b]">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}


function InventoryPreviewStat({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        highlight
          ? "border-emerald-200 bg-emerald-50"
          : "border-[#e2e8f0] bg-white"
      }`}
    >
      <p className="text-[10px] font-bold uppercase tracking-wide text-[#94a3b8]">
        {label}
      </p>
      <p
        className={`mt-1 text-lg font-bold ${
          highlight ? "text-emerald-700" : "text-[#111827]"
        }`}
      >
        {value.toLocaleString()}
      </p>
    </div>
  );
}

function PricingStat({
  label,
  value,
  detail,
  highlight = false,
}: {
  label: string;
  value: string;
  detail?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        highlight
          ? "border-orange-200 bg-white shadow-sm"
          : "border-white/80 bg-white/70"
      }`}
    >
      <p className="text-[10px] font-bold uppercase tracking-wide text-[#94a3b8]">
        {label}
      </p>
      <p
        className={`mt-1 text-base font-bold ${
          highlight ? "text-[#f7941d]" : "text-[#111827]"
        }`}
      >
        {value}
      </p>
      {detail && <p className="mt-0.5 text-xs text-[#64748b]">{detail}</p>}
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
        <span className="mt-0.5 block text-[11px] leading-4 text-[#94a3b8]">
          {hint}
        </span>
      )}
      <div className="mt-2">{children}</div>
    </label>
  );
}

export default SellerProducts;
