"use client";

import { ApiError } from "@/lib/api/client";
import { productsApi } from "@/lib/api/endpoints/products";
import { sellersApi } from "@/lib/api/endpoints/sellers";
import {
  sellerInventoryApi,
  type SellerInventory,
} from "@/lib/api/endpoints/seller-inventory";
import { authStorage } from "@/lib/auth/storage";
import type { Product } from "@/types/api/product";
import type {
  PayoutAccount,
  Seller,
  SellerBusinessProfile,
  SellerKycDocument,
  SellerKycStatus,
  SellerDashboardPerformance,
} from "@/types/api/seller";
import {
  AlertCircle,
  ArrowRight,
  BadgeCheck,
  Box,
  Check,
  CheckCircle2,
  CircleDashed,
  Clock3,
  ExternalLink,
  FileWarning,
  ImageIcon,
  PackageCheck,
  PackageOpen,
  Plus,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Store,
  TrendingUp,
  WalletCards,
  Warehouse,
  Star,
  MessageCircleQuestion,
  TicketPercent,
  Truck,
  CircleDollarSign,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type CurrentUser = {
  account_type?: string;
  roles?: string[];
  seller_status?: string | null;
  first_name?: string | null;
};

type LoadState = "loading" | "ready" | "error";

const documentNames: Record<string, string> = {
  tin: "TIN Certificate",
  business_profile: "Business Profile",
  business_registration: "Business Registration",
};

const pretty = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const number = new Intl.NumberFormat("en-US");

const formatMoney = (value: number, currency: string) =>
  new Intl.NumberFormat("en-TZ", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number.isFinite(value) ? value : 0);

export default function SellerDashboard() {
  const router = useRouter();
  const user = authStorage.getUser<CurrentUser>();
  const token = authStorage.getAccessToken();

  const isSeller = useMemo(
    () =>
      Boolean(
        user &&
          (user.account_type === "seller" || (user.roles ?? []).includes("seller")),
      ),
    [user],
  );

  const [products, setProducts] = useState<Product[]>([]);
  const [inventory, setInventory] = useState<SellerInventory[]>([]);
  const [kyc, setKyc] = useState<SellerKycStatus | null>(null);
  const [documents, setDocuments] = useState<SellerKycDocument[]>([]);
  const [payouts, setPayouts] = useState<PayoutAccount[]>([]);
  const [seller, setSeller] = useState<Seller | null>(null);
  const [profile, setProfile] = useState<SellerBusinessProfile | null>(null);
  const [performance, setPerformance] =
    useState<SellerDashboardPerformance | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      router.replace("/signin?redirect=/seller/dashboard");
      return;
    }

    if (!isSeller) {
      router.replace("/my-account");
      return;
    }

    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSeller, router, token]);

  async function load(background: boolean) {
    if (!token) return;

    background ? setRefreshing(true) : setState("loading");
    setError("");

    try {
      // Seller status is the first decision point. Pending/under-review sellers
      // should not call commerce APIs that may be unavailable before approval.
      const sellerData = await sellersApi.getMe(token);
      setSeller(sellerData);

      const activationData = await Promise.all([
        sellersApi.getKycStatus(token),
        sellersApi.getKycDocuments(token),
        sellersApi.getProfile(),
      ]);

      const [status, docs, profileData] = activationData;
      setKyc(status);
      setDocuments(docs);
      setProfile(profileData);

      if (sellerData.status === "approved") {
        const [productData, inventoryData, payoutList, performanceData] =
          await Promise.all([
            productsApi.getMyProducts({ skip: 0, limit: 100 }),
            sellerInventoryApi.list().catch(() => []),
            sellersApi.getPayoutAccounts(token),
            sellersApi.getDashboardPerformance(),
          ]);

        setProducts(productData);
        setInventory(inventoryData);
        setPayouts(payoutList);
        setPerformance(performanceData);
      } else {
        setProducts([]);
        setInventory([]);
        setPayouts([]);
        setPerformance(null);
      }

      setState("ready");
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "Unable to load seller dashboard. Check your connection and retry.",
      );
      setState("error");
    } finally {
      setRefreshing(false);
    }
  }

  if (!token || !isSeller) return null;
  if (state === "loading") return <DashboardSkeleton />;
  if (state === "error")
    return <ErrorState message={error} retry={() => void load(false)} />;

  const accountStatus = seller?.status || user?.seller_status || "pending";

  if (accountStatus !== "approved") {
    return (
      <SellerActivationDashboard
        seller={seller}
        kyc={kyc}
        documents={documents}
        profile={profile}
        refreshing={refreshing}
        refresh={() => void load(true)}
      />
    );
  }

  const requiredDocuments = kyc?.required_documents ?? [];
  const missingDocuments = kyc?.missing_documents ?? [];
  const rejectedDocs = documents.filter((document) => document.status === "rejected");

  const kycLabel = rejectedDocs.length
    ? "Changes Requested"
    : missingDocuments.length
      ? documents.length
        ? "Incomplete"
        : "Not Started"
      : kyc?.can_submit_for_review
        ? "Ready to Submit"
        : documents.some(
              (document) =>
                document.status === "pending" || document.status === "under_review",
            )
          ? "Under Review"
          : "Approved";

  const approvedProducts = products.filter(
    (product) => product.status === "approved",
  ).length;
  const pendingProducts = products.filter((product) =>
    ["pending", "submitted", "under_review"].includes(product.status || ""),
  ).length;
  const rejectedProducts = products.filter(
    (product) => product.status === "rejected",
  ).length;
  const draftProducts = Math.max(
    0,
    products.length - approvedProducts - pendingProducts - rejectedProducts,
  );

  const availableUnits = inventory.reduce(
    (sum, row) => sum + Math.max(0, row.available_quantity || 0),
    0,
  );
  const lowStockRows = inventory.filter(
    (row) =>
      row.available_quantity > 0 &&
      row.available_quantity <= (row.low_stock_threshold ?? 0),
  );
  const outOfStockRows = inventory.filter(
    (row) => row.available_quantity <= 0,
  );
  const healthyInventoryRows = Math.max(
    0,
    inventory.length - lowStockRows.length - outOfStockRows.length,
  );

  const dashboardProductsTotal = performance?.products_total ?? products.length;
  const dashboardProductsApproved =
    performance?.products_approved ?? approvedProducts;
  const dashboardProductsPending =
    performance?.products_pending_review ?? pendingProducts;

  const ordersTotal = performance?.orders_total ?? 0;
  const ordersNew = performance?.orders_new ?? 0;
  const ordersProcessing = performance?.orders_processing ?? 0;
  const ordersReady = performance?.orders_ready_to_ship ?? 0;

  const walletCurrency = performance?.wallet_currency || "TZS";
  const walletPending = Number(performance?.wallet_pending ?? 0);
  const walletAvailable = Number(performance?.wallet_available ?? 0);
  const walletReserved = Number(performance?.wallet_reserved ?? 0);

  const activePromotions = performance?.active_promotions ?? 0;
  const averageRating = Number(performance?.rating_average ?? 0);
  const reviewCount = performance?.review_count ?? 0;
  const unansweredQuestions = performance?.unanswered_questions ?? 0;
  const pendingPayouts = performance?.pending_payouts ?? 0;

  const kycProgress = requiredDocuments.length
    ? Math.round(
        ((requiredDocuments.length - missingDocuments.length) /
          requiredDocuments.length) *
          100,
      )
    : 0;

  const setupChecks = [
    Boolean(profile?.business_description),
    requiredDocuments.length > 0 && missingDocuments.length === 0,
    payouts.length > 0,
    products.length > 0,
  ];
  const setupProgress = Math.round(
    (setupChecks.filter(Boolean).length / setupChecks.length) * 100,
  );

  const nextActions = [
    ...missingDocuments.map((type) => ({
      priority: "High",
      title: `Upload ${documentNames[type] ?? pretty(type)}`,
      description: "Required for seller verification.",
      href: "/seller/kyc",
    })),
    ...(payouts.length
      ? []
      : [
          {
            priority: "High",
            title: "Add a payout account",
            description: "Prepare your account for future settlements.",
            href: "/seller/kyc?tab=payouts",
          },
        ]),
    ...(profile?.business_description
      ? []
      : [
          {
            priority: "Medium",
            title: "Complete your business profile",
            description: "Add your description, address and business information.",
            href: "/seller/store",
          },
        ]),
    ...(products.length
      ? []
      : [
          {
            priority: "Medium",
            title: "Add your first product",
            description: "Start building your marketplace catalog.",
            href: "/seller/products?create=true",
          },
        ]),
    ...products
      .filter((product) => product.status === "rejected")
      .slice(0, 2)
      .map((product) => ({
        priority: "High",
        title: `Resolve ${product.name}`,
        description:
          product.rejection_reason || "This product requires changes.",
        href: `/seller/products?product=${product.id}`,
      })),
  ];

  const statusBars = [
    { label: "Approved", value: approvedProducts, className: "bg-emerald-500" },
    { label: "Pending review", value: pendingProducts, className: "bg-amber-500" },
    { label: "Rejected", value: rejectedProducts, className: "bg-rose-500" },
    { label: "Draft / other", value: draftProducts, className: "bg-slate-400" },
  ];

  return (
    <div
      className="w-full space-y-6"
      style={{
        fontFamily:
          'Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      }}
    >
      {accountStatus !== "approved" && (
        <div
          className={`flex gap-3 rounded-2xl border p-4 ${
            accountStatus === "suspended" || accountStatus === "rejected"
              ? "border-red-200 bg-red-50 text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200"
              : "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200"
          }`}
        >
          <AlertCircle className="mt-0.5 shrink-0" size={20} />
          <div>
            <p className="font-semibold">Seller account: {pretty(accountStatus)}</p>
            <p className="mt-1 text-sm opacity-80">
              {accountStatus === "suspended"
                ? "Selling operations are restricted. Contact support for account review."
                : "Complete the remaining verification steps so your store can operate without restrictions."}
            </p>
          </div>
        </div>
      )}

      <Hero
        name={user?.first_name || "Seller"}
        businessName={seller?.business_name || "Your store"}
        setupProgress={setupProgress}
        refreshing={refreshing}
        refresh={() => void load(true)}
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6">
        <MetricCard
          label="Total Products"
          value={number.format(dashboardProductsTotal)}
          helper={`${number.format(dashboardProductsApproved)} approved`}
          icon={ShoppingBag}
          tone="orange"
        />
        <MetricCard
          label="Pending Review"
          value={number.format(dashboardProductsPending)}
          helper="Awaiting catalog approval"
          icon={Clock3}
          tone="amber"
        />
        <MetricCard
          label="Total Orders"
          value={number.format(ordersTotal)}
          helper={`${number.format(ordersNew)} new`}
          icon={PackageCheck}
          tone="blue"
        />
        <MetricCard
          label="Available Balance"
          value={formatMoney(walletAvailable, walletCurrency)}
          helper={`${number.format(pendingPayouts)} pending payout${pendingPayouts === 1 ? "" : "s"}`}
          icon={WalletCards}
          tone="green"
        />
        <MetricCard
          label="Average Rating"
          value={`${averageRating.toFixed(2)} / 5`}
          helper={`${number.format(reviewCount)} review${reviewCount === 1 ? "" : "s"}`}
          icon={Star}
          tone="amber"
        />
        <MetricCard
          label="Unanswered Q&A"
          value={number.format(unansweredQuestions)}
          helper="Customer questions"
          icon={MessageCircleQuestion}
          tone={unansweredQuestions ? "red" : "green"}
        />
      </section>

      <section className="grid gap-5 2xl:grid-cols-[1.45fr_.85fr]">
        <Card>
          <SectionHeading
            eyebrow="Catalog performance"
            title="Product status overview"
            description="Live distribution of your seller products by approval status."
            icon={TrendingUp}
          />

          <div className="mt-7 grid gap-7 lg:grid-cols-[1fr_220px]">
            <div className="space-y-5">
              {statusBars.map((item) => (
                <StatusBar
                  key={item.label}
                  label={item.label}
                  value={item.value}
                  total={Math.max(products.length, 1)}
                  className={item.className}
                />
              ))}
            </div>

            <DonutSummary
              value={approvedProducts}
              total={products.length}
              label="Approved catalog"
            />
          </div>
        </Card>

        <InventoryHealth
          healthy={healthyInventoryRows}
          low={lowStockRows.length}
          out={outOfStockRows.length}
          total={inventory.length}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.05fr_.95fr]">
        <Verification
          documents={documents}
          required={requiredDocuments}
          missing={missingDocuments}
          accountStatus={accountStatus}
          kycLabel={kycLabel}
        />

        <StoreReadiness
          progress={setupProgress}
          profileReady={Boolean(profile?.business_description)}
          kycReady={
            requiredDocuments.length > 0 && missingDocuments.length === 0
          }
          payoutReady={payouts.length > 0}
          productReady={products.length > 0}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
        <NextActions actions={nextActions} />

        <Card>
          <SectionHeading
            eyebrow="Quick actions"
            title="Run your store"
            description="Jump directly to the tasks sellers use most often."
            icon={Sparkles}
          />

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <QuickAction
              href="/seller/products?create=true"
              icon={Plus}
              title="Add product"
              description="Create a new catalog item"
            />
            <QuickAction
              href="/seller/inventory"
              icon={Box}
              title="Inventory"
              description="Review stock availability"
            />
            <QuickAction
              href="/seller/store"
              icon={Store}
              title="Store profile"
              description="Update business storefront"
            />
            <QuickAction
              href="/seller/kyc?tab=payouts"
              icon={WalletCards}
              title="Payout setup"
              description="Manage payout account"
            />
          </div>
        </Card>
      </section>

      <RecentProducts products={products} inventory={inventory} />

      <section className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
        <Card>
          <SectionHeading
            eyebrow="Order operations"
            title="Fulfilment pipeline"
            description="Live seller-order workload from the Seller Phase 10 dashboard endpoint."
            icon={PackageCheck}
          />

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <PipelineStat
              label="New"
              value={ordersNew}
              total={Math.max(ordersTotal, 1)}
              href="/seller/orders?status=new"
            />
            <PipelineStat
              label="Processing"
              value={ordersProcessing}
              total={Math.max(ordersTotal, 1)}
              href="/seller/orders?status=processing"
            />
            <PipelineStat
              label="Ready to Ship"
              value={ordersReady}
              total={Math.max(ordersTotal, 1)}
              href="/seller/orders?status=ready_to_ship"
            />
            <PipelineStat
              label="All Orders"
              value={ordersTotal}
              total={Math.max(ordersTotal, 1)}
              href="/seller/orders"
            />
          </div>

          <div className="mt-6">
            <PerformanceBar
              label="New orders"
              value={ordersNew}
              total={Math.max(ordersTotal, 1)}
              className="bg-blue-500"
            />
            <PerformanceBar
              label="Processing"
              value={ordersProcessing}
              total={Math.max(ordersTotal, 1)}
              className="bg-amber-500"
            />
            <PerformanceBar
              label="Ready to ship"
              value={ordersReady}
              total={Math.max(ordersTotal, 1)}
              className="bg-emerald-500"
            />
          </div>

          <Link
            href="/seller/orders"
            className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#f7941d]"
          >
            Open order workspace <ArrowRight size={15} />
          </Link>
        </Card>

        <Card>
          <SectionHeading
            eyebrow="Finance"
            title="Wallet position"
            description="Current pending, available and reserved seller balances."
            icon={CircleDollarSign}
          />

          <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
            <WalletStat
              label="Pending"
              value={formatMoney(walletPending, walletCurrency)}
              icon={Clock3}
            />
            <WalletStat
              label="Available"
              value={formatMoney(walletAvailable, walletCurrency)}
              icon={WalletCards}
              highlight
            />
            <WalletStat
              label="Reserved"
              value={formatMoney(walletReserved, walletCurrency)}
              icon={ShieldCheck}
            />
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <MiniStat
              label="Payout accounts"
              value={number.format(payouts.length)}
            />
            <MiniStat
              label="Pending payouts"
              value={number.format(pendingPayouts)}
            />
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              href="/seller/earnings"
              className="inline-flex items-center gap-2 text-sm font-semibold text-[#f7941d]"
            >
              Wallet & earnings <ArrowRight size={15} />
            </Link>
            <Link
              href="/seller/payouts"
              className="inline-flex items-center gap-2 text-sm font-semibold text-[#64748b]"
            >
              Payout requests <ArrowRight size={15} />
            </Link>
          </div>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-3">
        <PerformanceLinkCard
          href="/seller/promotions"
          icon={TicketPercent}
          eyebrow="Promotions"
          value={number.format(activePromotions)}
          title="Active promotions"
          description="Seller-funded promotions currently active."
        />
        <PerformanceLinkCard
          href="/seller/reviews"
          icon={Star}
          eyebrow="Reputation"
          value={averageRating.toFixed(2)}
          title={`${number.format(reviewCount)} customer reviews`}
          description="Average product-review rating across your seller catalog."
        />
        <PerformanceLinkCard
          href="/seller/questions"
          icon={MessageCircleQuestion}
          eyebrow="Customer Q&A"
          value={number.format(unansweredQuestions)}
          title="Questions need attention"
          description="Respond quickly to product questions before customers abandon purchase decisions."
          alert={unansweredQuestions > 0}
        />
      </section>
    </div>
  );
}


function PipelineStat({
  label,
  value,
  total,
  href,
}: {
  label: string;
  value: number;
  total: number;
  href: string;
}) {
  const percent = Math.min(100, Math.max(0, (value / total) * 100));
  return (
    <Link
      href={href}
      className="rounded-xl border border-[#e7ebf0] bg-slate-50 p-4 transition hover:border-orange-200 hover:bg-orange-50/40 dark:border-white/10 dark:bg-white/[0.03]"
    >
      <p className="text-2xl font-bold tracking-[-0.03em]">{number.format(value)}</p>
      <p className="mt-1 text-xs font-semibold text-[#64748b]">{label}</p>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-white/10">
        <div className="h-full rounded-full bg-[#f7941d]" style={{ width: `${percent}%` }} />
      </div>
    </Link>
  );
}

function PerformanceBar({
  label,
  value,
  total,
  className,
}: {
  label: string;
  value: number;
  total: number;
  className: string;
}) {
  const percent = Math.min(100, Math.max(0, (value / total) * 100));
  return (
    <div className="mb-4 last:mb-0">
      <div className="flex items-center justify-between gap-4 text-xs">
        <span className="font-semibold text-[#64748b]">{label}</span>
        <span className="font-bold">{number.format(value)}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10">
        <div className={`h-full rounded-full ${className}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function WalletStat({
  label,
  value,
  icon: Icon,
  highlight = false,
}: {
  label: string;
  value: string;
  icon: typeof WalletCards;
  highlight?: boolean;
}) {
  return (
    <div className={`rounded-xl border p-4 ${highlight ? "border-orange-200 bg-orange-50" : "border-[#e7ebf0] bg-slate-50 dark:border-white/10 dark:bg-white/[0.03]"}`}>
      <Icon size={17} className={highlight ? "text-[#f7941d]" : "text-[#94a3b8]"} />
      <p className="mt-3 text-xs font-semibold text-[#64748b]">{label}</p>
      <p className="mt-1 text-lg font-bold tracking-[-0.025em]">{value}</p>
    </div>
  );
}

function PerformanceLinkCard({
  href,
  icon: Icon,
  eyebrow,
  value,
  title,
  description,
  alert = false,
}: {
  href: string;
  icon: typeof Star;
  eyebrow: string;
  value: string;
  title: string;
  description: string;
  alert?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`rounded-2xl border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:bg-[#1f2937] ${
        alert ? "border-amber-200" : "border-[#e7ebf0] dark:border-white/10"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${alert ? "bg-amber-50 text-amber-600" : "bg-orange-50 text-[#f7941d]"}`}>
          <Icon size={18} />
        </span>
        <ArrowRight size={16} className="text-[#94a3b8]" />
      </div>
      <p className="mt-4 text-[10px] font-bold uppercase tracking-[.12em] text-[#94a3b8]">
        {eyebrow}
      </p>
      <p className="mt-1 text-3xl font-bold tracking-[-0.04em]">{value}</p>
      <p className="mt-1 text-sm font-semibold">{title}</p>
      <p className="mt-2 text-xs leading-5 text-[#64748b]">{description}</p>
    </Link>
  );
}

function SellerActivationDashboard({
  seller,
  kyc,
  documents,
  profile,
  refreshing,
  refresh,
}: {
  seller: Seller | null;
  kyc: SellerKycStatus | null;
  documents: SellerKycDocument[];
  profile: SellerBusinessProfile | null;
  refreshing: boolean;
  refresh: () => void;
}) {
  const required = kyc?.required_documents ?? [];
  const missing = kyc?.missing_documents ?? [];
  const uploadedCount = Math.max(0, required.length - missing.length);
  const rejectedDocuments = documents.filter(
    (document) => document.status === "rejected",
  );

  const documentProgress = required.length
    ? Math.round((uploadedCount / required.length) * 100)
    : 0;

  const profileComplete = Boolean(
    profile?.business_description &&
      profile?.business_country &&
      profile?.business_city &&
      profile?.business_address,
  );

  const kycReady = required.length > 0 && missing.length === 0;
  const activationChecks = [
    profileComplete,
    required.length > 0,
    kycReady,
    rejectedDocuments.length === 0 && documents.length > 0,
  ];
  const activationProgress = Math.round(
    (activationChecks.filter(Boolean).length / activationChecks.length) * 100,
  );

  const status = seller?.status || kyc?.seller_status || "pending";
  const isUnderReview = status === "under_review";
  const hasRejectedDocs = rejectedDocuments.length > 0;

  return (
    <div
      className="w-full space-y-6"
      style={{
        fontFamily:
          'Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      }}
    >
      <section className="relative overflow-hidden rounded-[24px] border border-[#e7ebf0] bg-white/85 p-6 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-[#1f2937]/85 sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full bg-[#f7941d]/10 blur-3xl" />

        <div className="relative grid gap-8 xl:grid-cols-[1fr_320px] xl:items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
              <ShieldCheck size={14} />
              Seller account · {pretty(status)}
            </div>

            <h2 className="mt-4 text-2xl font-bold tracking-[-0.03em] text-[#111827] dark:text-white sm:text-3xl">
              Activate your seller account
            </h2>

            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#64748b] sm:text-base">
              Before selling on Xerin Market, complete your business verification.
              Product, inventory, order, store and finance features will unlock
              after your seller account is approved.
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/seller/kyc"
                className="inline-flex items-center gap-2 rounded-xl bg-[#f7941d] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#e78315]"
              >
                <ShieldCheck size={17} />
                Continue KYC
              </Link>

              <Link
                href="/seller/documents"
                className="inline-flex items-center gap-2 rounded-xl border border-[#dfe4ea] bg-white px-4 py-2.5 text-sm font-semibold text-[#334155] transition hover:border-[#f7941d] dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                <FileWarning size={17} />
                Business Documents
              </Link>

              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                className="inline-flex items-center gap-2 rounded-xl border border-[#dfe4ea] px-4 py-2.5 text-sm font-semibold text-[#64748b] transition hover:bg-slate-50 disabled:opacity-50 dark:border-white/10 dark:hover:bg-white/5"
              >
                <RefreshCw
                  size={16}
                  className={refreshing ? "animate-spin" : ""}
                />
                {refreshing ? "Refreshing" : "Refresh status"}
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-[#e7ebf0] bg-slate-50/80 p-5 dark:border-white/10 dark:bg-white/[0.04]">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#94a3b8]">
              Activation progress
            </p>
            <div className="mt-2 flex items-end gap-2">
              <p className="text-4xl font-bold tracking-[-0.04em]">
                {activationProgress}%
              </p>
              <p className="pb-1 text-xs text-[#94a3b8]">complete</p>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-white/10">
              <div
                className="h-full rounded-full bg-[#f7941d]"
                style={{ width: `${activationProgress}%` }}
              />
            </div>
            <p className="mt-3 text-xs leading-5 text-[#64748b]">
              {isUnderReview
                ? "Your application is being reviewed. Keep your documents up to date while you wait."
                : hasRejectedDocs
                  ? "One or more documents need correction before approval."
                  : "Complete the remaining steps and submit valid documents for review."}
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <ActivationMetric
          label="Seller Status"
          value={pretty(status)}
          helper="Marketplace approval"
          icon={ShieldCheck}
          good={status === "under_review"}
        />
        <ActivationMetric
          label="KYC Documents"
          value={`${uploadedCount}/${required.length}`}
          helper={`${documentProgress}% complete`}
          icon={FileWarning}
          good={kycReady}
        />
        <ActivationMetric
          label="Business Profile"
          value={profileComplete ? "Complete" : "Incomplete"}
          helper="Legal business information"
          icon={Store}
          good={profileComplete}
        />
        <ActivationMetric
          label="Document Issues"
          value={String(rejectedDocuments.length)}
          helper={
            rejectedDocuments.length
              ? "Requires your attention"
              : "No rejected documents"
          }
          icon={AlertCircle}
          good={rejectedDocuments.length === 0}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_.9fr]">
        <Card>
          <SectionHeading
            eyebrow="Activation"
            title="Complete these steps"
            description="Only activation and account-management tools are available until approval."
            icon={CheckCircle2}
          />

          <div className="mt-6 space-y-3">
            <ActivationStep
              number={1}
              title="Review account settings"
              description="Confirm your personal and business contact details."
              href="/seller/account"
              complete={Boolean(seller?.business_name)}
            />
            <ActivationStep
              number={2}
              title="Complete KYC verification"
              description="Review verification requirements and your current status."
              href="/seller/kyc"
              complete={kycReady && !hasRejectedDocs}
            />
            <ActivationStep
              number={3}
              title="Upload business documents"
              description="Provide all required legal and business documents."
              href="/seller/documents"
              complete={kycReady}
            />
            <ActivationStep
              number={4}
              title="Wait for approval"
              description="Once your documents are accepted, seller commerce features will unlock automatically."
              href="/seller/kyc"
              complete={status === "approved"}
              waiting={isUnderReview}
            />
          </div>
        </Card>

        <Card>
          <SectionHeading
            eyebrow="What you can access now"
            title="Activation workspace"
            description="These tools remain available while your seller account is pending."
            icon={ShieldCheck}
          />

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <QuickAction
              href="/seller/dashboard"
              icon={TrendingUp}
              title="Dashboard"
              description="Track activation progress"
            />
            <QuickAction
              href="/seller/kyc"
              icon={ShieldCheck}
              title="KYC Verification"
              description="Review verification status"
            />
            <QuickAction
              href="/seller/documents"
              icon={FileWarning}
              title="Business Documents"
              description="Upload required files"
            />
            <QuickAction
              href="/seller/account"
              icon={Store}
              title="Account Settings"
              description="Update account information"
            />
            <QuickAction
              href="/seller/account/security"
              icon={BadgeCheck}
              title="Security"
              description="Password and active sessions"
            />
            <QuickAction
              href="/seller/support"
              icon={AlertCircle}
              title="Help & Support"
              description="Get assistance"
            />
          </div>
        </Card>
      </section>

      {hasRejectedDocs && (
        <section className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
          <div className="flex items-start gap-3">
            <FileWarning className="mt-0.5 shrink-0" size={20} />
            <div>
              <p className="font-semibold">Document changes are required</p>
              <p className="mt-1 text-sm opacity-80">
                Review the rejection notes in Business Documents and upload corrected files.
              </p>
              <Link
                href="/seller/documents"
                className="mt-3 inline-flex text-sm font-semibold underline"
              >
                Review documents
              </Link>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function ActivationMetric({
  label,
  value,
  helper,
  icon: Icon,
  good,
}: {
  label: string;
  value: string;
  helper: string;
  icon: typeof Box;
  good: boolean;
}) {
  return (
    <div className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937]">
      <div
        className={`flex h-10 w-10 items-center justify-center rounded-xl ${
          good
            ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10"
            : "bg-amber-50 text-amber-600 dark:bg-amber-500/10"
        }`}
      >
        <Icon size={19} />
      </div>
      <p className="mt-4 text-xs font-medium text-[#64748b]">{label}</p>
      <p className="mt-1 text-xl font-bold tracking-[-0.025em]">{value}</p>
      <p className="mt-1 text-xs text-[#94a3b8]">{helper}</p>
    </div>
  );
}

function ActivationStep({
  number,
  title,
  description,
  href,
  complete,
  waiting = false,
}: {
  number: number;
  title: string;
  description: string;
  href: string;
  complete: boolean;
  waiting?: boolean;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-4 rounded-xl border border-[#edf0f4] p-4 transition hover:border-[#f7941d]/50 dark:border-white/10"
    >
      <span
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${
          complete
            ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10"
            : waiting
              ? "bg-blue-50 text-blue-600 dark:bg-blue-500/10"
              : "bg-orange-50 text-[#f7941d] dark:bg-orange-500/10"
        }`}
      >
        {complete ? <Check size={18} /> : waiting ? <Clock3 size={18} /> : number}
      </span>

      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">{title}</span>
        <span className="mt-0.5 block text-xs leading-5 text-[#64748b]">
          {description}
        </span>
      </span>

      <ArrowRight size={16} className="shrink-0 text-[#94a3b8]" />
    </Link>
  );
}

function Hero({
  name,
  businessName,
  setupProgress,
  refreshing,
  refresh,
}: {
  name: string;
  businessName: string;
  setupProgress: number;
  refreshing: boolean;
  refresh: () => void;
}) {
  return (
    <section className="relative overflow-hidden rounded-[24px] border border-[#e7ebf0] bg-white/80 px-6 py-7 text-[#111827] shadow-[0_1px_2px_rgba(15,23,42,0.03)] backdrop-blur-xl sm:px-8 lg:px-9 dark:border-white/10 dark:bg-[#1f2937]/80 dark:text-white">
      <div className="pointer-events-none absolute -right-24 -top-28 h-72 w-72 rounded-full bg-[#f7941d]/10 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 right-32 h-36 w-36 rounded-full bg-slate-100/60 blur-2xl dark:bg-white/5" />

      <div className="relative flex flex-col gap-7 xl:flex-row xl:items-center xl:justify-between">
        <div className="max-w-2xl">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-[#e7ebf0] bg-white/70 px-3 py-1.5 text-xs font-medium text-[#64748b] dark:border-white/10 dark:bg-white/5 dark:text-white/70">
            <Sparkles size={14} className="text-[#f7941d]" />
            Seller Center
          </div>

          <h2 className="text-2xl font-bold tracking-[-0.025em] sm:text-3xl">
            Welcome back, {name}
          </h2>
          <p className="mt-2 text-sm leading-6 text-[#64748b] sm:text-base dark:text-white/65">
            {businessName} · Keep your catalog healthy, complete store setup and
            respond quickly to items that need attention.
          </p>

          <div className="mt-6 flex flex-wrap gap-2">
            <Link
              href="/seller/products?create=true"
              className="inline-flex items-center gap-2 rounded-xl bg-[#f7941d] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#e78315]"
            >
              <Plus size={17} />
              Add Product
            </Link>
            <Link
              href="/shop-with-sidebar"
              className="inline-flex items-center gap-2 rounded-xl border border-[#dfe4ea] bg-white/70 px-4 py-2.5 text-sm font-semibold text-[#334155] transition hover:bg-white dark:border-white/15 dark:bg-white/5 dark:text-white dark:hover:bg-white/10"
            >
              <ExternalLink size={16} />
              View Store
            </Link>
            <button
              onClick={refresh}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-xl border border-[#dfe4ea] bg-white/50 px-4 py-2.5 text-sm font-semibold text-[#475569] transition hover:bg-white disabled:opacity-60 dark:border-white/15 dark:bg-transparent dark:text-white/80 dark:hover:bg-white/10"
            >
              <RefreshCw
                size={16}
                className={refreshing ? "animate-spin" : ""}
              />
              {refreshing ? "Refreshing" : "Refresh"}
            </button>
          </div>
        </div>

        <div className="w-full rounded-2xl border border-[#e7ebf0] bg-white/75 p-5 shadow-sm xl:max-w-[320px] dark:border-white/10 dark:bg-white/[0.06]">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#94a3b8] dark:text-white/45">
                Store readiness
              </p>
              <p className="mt-1 text-2xl font-bold">{setupProgress}%</p>
            </div>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#f7941d]/15 text-[#f7941d]">
              <Store size={21} />
            </div>
          </div>

          <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-[#f7941d] transition-all"
              style={{ width: `${setupProgress}%` }}
            />
          </div>

          <p className="mt-3 text-xs leading-5 text-[#64748b] dark:text-white/55">
            Complete profile, verification, payout setup and your first catalog
            item.
          </p>
        </div>
      </div>
    </section>
  );
}

function MetricCard({
  label,
  value,
  helper,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  helper: string;
  icon: typeof Box;
  tone: "orange" | "green" | "amber" | "blue" | "red";
}) {
  const tones = {
    orange: "bg-orange-50 text-[#f7941d] dark:bg-orange-500/10",
    green: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10",
    amber: "bg-amber-50 text-amber-600 dark:bg-amber-500/10",
    blue: "bg-blue-50 text-blue-600 dark:bg-blue-500/10",
    red: "bg-rose-50 text-rose-600 dark:bg-rose-500/10",
  };

  return (
    <div className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.03)] transition hover:-translate-y-0.5 hover:shadow-md dark:border-white/10 dark:bg-[#1f2937]">
      <div className="flex items-start justify-between gap-4">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${tones[tone]}`}>
          <Icon size={19} />
        </div>
      </div>

      <p className="mt-5 text-[13px] font-medium text-[#64748b]">{label}</p>
      <p className="mt-1 text-[28px] font-bold tracking-[-0.035em] text-[#111827] dark:text-white">
        {value}
      </p>
      <p className="mt-1 text-xs text-[#94a3b8]">{helper}</p>
    </div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  description,
  icon: Icon,
}: {
  eyebrow: string;
  title: string;
  description: string;
  icon: typeof Box;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#f7941d]">
          {eyebrow}
        </p>
        <h3 className="mt-1 text-lg font-bold tracking-[-0.02em] text-[#111827] dark:text-white">
          {title}
        </h3>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-[#64748b]">
          {description}
        </p>
      </div>
      <div className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-[#64748b] dark:bg-white/5 sm:flex">
        <Icon size={19} />
      </div>
    </div>
  );
}

function StatusBar({
  label,
  value,
  total,
  className,
}: {
  label: string;
  value: number;
  total: number;
  className: string;
}) {
  const percent = Math.round((value / total) * 100);

  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium text-[#334155] dark:text-slate-200">
          {label}
        </span>
        <span className="font-semibold text-[#0f172a] dark:text-white">
          {value} <span className="font-normal text-[#94a3b8]">({percent}%)</span>
        </span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10">
        <div
          className={`h-full rounded-full transition-all ${className}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function DonutSummary({
  value,
  total,
  label,
}: {
  value: number;
  total: number;
  label: string;
}) {
  const percent = total ? Math.round((value / total) * 100) : 0;

  return (
    <div className="flex flex-col items-center justify-center rounded-2xl bg-slate-50 p-5 text-center dark:bg-white/[0.04]">
      <div
        className="grid h-32 w-32 place-items-center rounded-full"
        style={{
          background: `conic-gradient(#f7941d ${percent * 3.6}deg, #e9edf2 0deg)`,
        }}
      >
        <div className="grid h-24 w-24 place-items-center rounded-full bg-white dark:bg-[#1f2937]">
          <div>
            <p className="text-2xl font-bold tracking-[-0.03em]">{percent}%</p>
            <p className="text-[10px] uppercase tracking-wider text-[#94a3b8]">
              approved
            </p>
          </div>
        </div>
      </div>
      <p className="mt-4 text-sm font-semibold">{label}</p>
      <p className="mt-1 text-xs text-[#94a3b8]">
        {value} of {total} products
      </p>
    </div>
  );
}

function InventoryHealth({
  healthy,
  low,
  out,
  total,
}: {
  healthy: number;
  low: number;
  out: number;
  total: number;
}) {
  const rows = [
    { label: "Healthy stock", value: healthy, color: "bg-emerald-500" },
    { label: "Low stock", value: low, color: "bg-amber-500" },
    { label: "Out of stock", value: out, color: "bg-rose-500" },
  ];

  return (
    <Card>
      <SectionHeading
        eyebrow="Inventory"
        title="Stock health"
        description="Inventory status from your connected seller stock records."
        icon={Warehouse}
      />

      {total ? (
        <div className="mt-6 space-y-4">
          {rows.map((row) => {
            const percent = Math.round((row.value / total) * 100);
            return (
              <div
                key={row.label}
                className="rounded-xl border border-[#edf0f4] p-4 dark:border-white/10"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className={`h-2.5 w-2.5 rounded-full ${row.color}`} />
                    <span className="text-sm font-medium">{row.label}</span>
                  </div>
                  <span className="text-sm font-bold">{row.value}</span>
                </div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10">
                  <div
                    className={`h-full rounded-full ${row.color}`}
                    style={{ width: `${percent}%` }}
                  />
                </div>
              </div>
            );
          })}

          <Link
            href="/seller/inventory"
            className="inline-flex items-center gap-2 text-sm font-semibold text-[#f7941d]"
          >
            Manage inventory <ArrowRight size={15} />
          </Link>
        </div>
      ) : (
        <EmptyFutureState
          icon={Warehouse}
          title="No inventory records yet"
          text="Add products and stock records to see live inventory health."
        />
      )}
    </Card>
  );
}

function Verification({
  documents,
  required,
  missing,
  accountStatus,
  kycLabel,
}: {
  documents: SellerKycDocument[];
  required: string[];
  missing: string[];
  accountStatus: string;
  kycLabel: string;
}) {
  const progress = required.length
    ? Math.round(((required.length - missing.length) / required.length) * 100)
    : null;

  return (
    <Card>
      <SectionHeading
        eyebrow="Compliance"
        title="KYC verification"
        description="Complete your business verification to unlock full seller operations."
        icon={ShieldCheck}
      />

      <div className="mt-5 flex items-center justify-between rounded-xl bg-slate-50 p-4 dark:bg-white/[0.04]">
        <div>
          <p className="text-xs text-[#64748b]">Verification status</p>
          <p className="mt-1 font-semibold">{kycLabel}</p>
        </div>
        <Status label={pretty(accountStatus)} />
      </div>

      {progress !== null && (
        <>
          <div className="mt-5 flex justify-between text-sm">
            <span className="text-[#64748b]">
              {required.length - missing.length} of {required.length} documents
            </span>
            <b>{progress}%</b>
          </div>
          <div className="mt-2 h-2 rounded-full bg-slate-100 dark:bg-white/10">
            <div
              className="h-2 rounded-full bg-[#f7941d]"
              style={{ width: `${progress}%` }}
            />
          </div>
        </>
      )}

      <div className="mt-5 grid gap-2">
        {required.map((type) => {
          const document = documents.find((item) => item.document_type === type);

          return (
            <div
              key={type}
              className="flex items-center gap-3 rounded-xl border border-[#edf0f4] p-3 dark:border-white/10"
            >
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                  document
                    ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10"
                    : "bg-slate-100 text-[#94a3b8] dark:bg-white/5"
                }`}
              >
                {document ? <Check size={17} /> : <CircleDashed size={17} />}
              </span>

              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">
                  {documentNames[type] ?? pretty(type)}
                </p>
                <p className="text-xs text-[#64748b]">
                  {document ? pretty(document.status || "uploaded") : "Missing"}
                </p>
              </div>

              {(document?.document_url || document?.file_url) && (
                <a
                  href={document.document_url || document.file_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-semibold text-[#f7941d]"
                >
                  View
                </a>
              )}
            </div>
          );
        })}
      </div>

      <Link
        href="/seller/kyc"
        className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#f7941d]"
      >
        {missing.length ? "Complete verification" : "Review documents"}
        <ArrowRight size={15} />
      </Link>
    </Card>
  );
}

function StoreReadiness({
  progress,
  profileReady,
  kycReady,
  payoutReady,
  productReady,
}: {
  progress: number;
  profileReady: boolean;
  kycReady: boolean;
  payoutReady: boolean;
  productReady: boolean;
}) {
  const items = [
    {
      label: "Business profile",
      description: "Store description and location",
      complete: profileReady,
      href: "/seller/store",
    },
    {
      label: "KYC documents",
      description: "Required business verification",
      complete: kycReady,
      href: "/seller/kyc",
    },
    {
      label: "Payout account",
      description: "Settlement destination",
      complete: payoutReady,
      href: "/seller/kyc?tab=payouts",
    },
    {
      label: "Catalog started",
      description: "At least one seller product",
      complete: productReady,
      href: "/seller/products?create=true",
    },
  ];

  return (
    <Card>
      <SectionHeading
        eyebrow="Onboarding"
        title="Store readiness"
        description="A practical setup checklist calculated from data already available in your seller account."
        icon={Store}
      />

      <div className="mt-5 flex items-center gap-5 rounded-2xl bg-[#25292d] p-5 text-white">
        <div>
          <p className="text-3xl font-bold tracking-[-0.04em]">{progress}%</p>
          <p className="mt-1 text-xs text-white/55">setup complete</p>
        </div>
        <div className="h-10 w-px bg-white/10" />
        <div className="flex-1">
          <div className="h-2 rounded-full bg-white/10">
            <div
              className="h-2 rounded-full bg-[#f7941d]"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-white/55">
            Finish the remaining items to prepare your store for selling.
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {items.map((item) => (
          <Link
            key={item.label}
            href={item.href}
            className="flex items-center gap-3 rounded-xl border border-[#edf0f4] p-3 transition hover:border-[#f7941d]/50 dark:border-white/10"
          >
            <span
              className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                item.complete
                  ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10"
                  : "bg-slate-100 text-[#94a3b8] dark:bg-white/5"
              }`}
            >
              {item.complete ? <Check size={16} /> : <CircleDashed size={16} />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">{item.label}</p>
              <p className="text-xs text-[#64748b]">{item.description}</p>
            </div>
            <ArrowRight size={15} className="text-[#94a3b8]" />
          </Link>
        ))}
      </div>
    </Card>
  );
}

function NextActions({
  actions,
}: {
  actions: Array<{
    priority: string;
    title: string;
    description: string;
    href: string;
  }>;
}) {
  return (
    <Card>
      <SectionHeading
        eyebrow="Priorities"
        title="Next actions"
        description="The most important items that currently need your attention."
        icon={AlertCircle}
      />

      <div className="mt-5 space-y-2">
        {actions.length ? (
          actions.slice(0, 5).map((action) => (
            <Link
              key={`${action.title}-${action.href}`}
              href={action.href}
              className="flex items-center gap-3 rounded-xl border border-[#edf0f4] p-3.5 transition hover:border-[#f7941d]/60 hover:bg-orange-50/30 dark:border-white/10 dark:hover:bg-white/[0.03]"
            >
              <span
                className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase ${
                  action.priority === "High"
                    ? "bg-red-50 text-red-700"
                    : "bg-amber-50 text-amber-700"
                }`}
              >
                {action.priority}
              </span>
              <span className="min-w-0 flex-1">
                <b className="block truncate text-sm">{action.title}</b>
                <small className="block truncate text-[#64748b]">
                  {action.description}
                </small>
              </span>
              <ArrowRight size={16} />
            </Link>
          ))
        ) : (
          <div className="rounded-xl bg-emerald-50 p-6 text-center text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
            <CheckCircle2 className="mx-auto" />
            <p className="mt-2 font-semibold">You are all caught up.</p>
            <p className="mt-1 text-xs opacity-75">
              There are no urgent setup actions right now.
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}

function QuickAction({
  href,
  icon: Icon,
  title,
  description,
}: {
  href: string;
  icon: typeof Box;
  title: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-xl border border-[#edf0f4] p-4 transition hover:border-[#f7941d]/50 hover:bg-orange-50/30 dark:border-white/10 dark:hover:bg-white/[0.03]"
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-50 text-[#64748b] transition group-hover:bg-[#f7941d] group-hover:text-white dark:bg-white/5">
        <Icon size={17} />
      </div>
      <p className="mt-3 text-sm font-semibold">{title}</p>
      <p className="mt-1 text-xs leading-5 text-[#64748b]">{description}</p>
    </Link>
  );
}

function RecentProducts({
  products,
  inventory,
}: {
  products: Product[];
  inventory: SellerInventory[];
}) {
  const stockByProduct = useMemo(() => {
    const result = new Map<string, number>();
    for (const row of inventory) {
      result.set(
        row.product_id,
        (result.get(row.product_id) || 0) + (row.available_quantity || 0),
      );
    }
    return result;
  }, [inventory]);

  return (
    <Card flush>
      <div className="flex items-center justify-between border-b border-[#edf0f4] p-5 sm:p-6 dark:border-white/10">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#f7941d]">
            Catalog
          </p>
          <h3 className="mt-1 text-lg font-bold tracking-[-0.02em]">
            Recent products
          </h3>
          <p className="mt-1 text-sm text-[#64748b]">
            Latest seller products, stock and moderation status.
          </p>
        </div>
        <Link
          href="/seller/products"
          className="text-sm font-semibold text-[#f7941d]"
        >
          View all
        </Link>
      </div>

      {products.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] text-left text-sm">
            <thead className="bg-slate-50/80 text-[11px] uppercase tracking-wider text-[#64748b] dark:bg-white/[0.03]">
              <tr>
                {["Product", "SKU", "Price", "Stock", "Approval", "Created", "Action"].map(
                  (heading) => (
                    <th key={heading} className="px-5 py-3.5 font-semibold">
                      {heading}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#edf0f4] dark:divide-white/10">
              {products.slice(0, 6).map((product) => {
                const stock = stockByProduct.get(String(product.id));

                return (
                  <tr
                    key={product.id}
                    className="transition hover:bg-slate-50/60 dark:hover:bg-white/[0.02]"
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-[#94a3b8] dark:bg-white/10">
                          <ImageIcon size={18} />
                        </span>
                        <b className="max-w-[260px] truncate">{product.name}</b>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-[#64748b]">{product.sku}</td>
                    <td className="px-5 py-4 font-medium">
                      {product.currency} {product.price}
                    </td>
                    <td className="px-5 py-4">
                      {stock === undefined ? (
                        <span className="text-[#94a3b8]">—</span>
                      ) : (
                        <span
                          className={
                            stock <= 0
                              ? "font-semibold text-rose-600"
                              : stock <= 5
                                ? "font-semibold text-amber-600"
                                : "font-semibold text-emerald-600"
                          }
                        >
                          {stock}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <Status label={pretty(product.status || "draft")} />
                    </td>
                    <td className="px-5 py-4 text-[#64748b]">
                      {new Date(product.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-4">
                      <Link
                        href={`/seller/products?product=${product.id}`}
                        className="font-semibold text-[#f7941d]"
                      >
                        View / Edit
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="p-12 text-center">
          <ShoppingBag className="mx-auto text-[#94a3b8]" size={34} />
          <h4 className="mt-3 font-semibold">No products yet</h4>
          <p className="mt-1 text-sm text-[#64748b]">
            Add your first product to start building your storefront.
          </p>
          <Link
            href="/seller/products?create=true"
            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-[#f7941d] px-4 py-2.5 text-sm font-semibold text-white"
          >
            <Plus size={16} />
            Add Product
          </Link>
        </div>
      )}
    </Card>
  );
}

function EmptyFutureState({
  icon: Icon,
  title,
  text,
}: {
  icon: typeof Box;
  title: string;
  text: string;
}) {
  return (
    <div className="mt-5 rounded-2xl border border-dashed border-[#d8dee6] bg-slate-50/60 p-7 text-center dark:border-white/10 dark:bg-white/[0.02]">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-white text-[#94a3b8] shadow-sm dark:bg-white/5">
        <Icon size={20} />
      </div>
      <p className="mt-3 text-sm font-semibold">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-5 text-[#64748b]">
        {text}
      </p>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 p-4 dark:bg-white/[0.04]">
      <p className="text-xs text-[#64748b]">{label}</p>
      <p className="mt-1 text-lg font-bold">{value}</p>
    </div>
  );
}

function Card({
  children,
  flush = false,
}: {
  children: React.ReactNode;
  flush?: boolean;
}) {
  return (
    <section
      className={`overflow-hidden rounded-2xl border border-[#e7ebf0] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.03)] dark:border-white/10 dark:bg-[#1f2937] ${
        flush ? "" : "p-5 sm:p-6"
      }`}
    >
      {children}
    </section>
  );
}

function Status({ label }: { label: string }) {
  const value = label.toLowerCase();
  const tone =
    value.includes("approved") || value.includes("complete")
      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"
      : value.includes("reject") || value.includes("changes")
        ? "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
        : "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300";

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}
    >
      {label}
    </span>
  );
}

function DashboardSkeleton() {
  return (
    <div className="w-full animate-pulse space-y-5">
      <div className="h-52 rounded-[24px] bg-slate-200 dark:bg-white/10" />
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <div
            key={index}
            className="h-36 rounded-2xl bg-slate-200 dark:bg-white/10"
          />
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="h-96 rounded-2xl bg-slate-200 dark:bg-white/10" />
        <div className="h-96 rounded-2xl bg-slate-200 dark:bg-white/10" />
      </div>
    </div>
  );
}

function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  return (
    <div className="mx-auto max-w-xl rounded-2xl border border-red-200 bg-white p-8 text-center shadow-sm dark:border-red-500/30 dark:bg-[#1f2937]">
      <AlertCircle className="mx-auto text-red-600" size={34} />
      <h2 className="mt-3 text-xl font-semibold">Unable to load seller dashboard</h2>
      <p className="mt-2 text-sm text-[#64748b]">{message}</p>
      <button
        onClick={retry}
        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[#25292d] px-4 py-2.5 text-sm font-semibold text-white"
      >
        <RefreshCw size={16} />
        Try again
      </button>
    </div>
  );
}
