"use client";

import BackendDocumentPreview from "@/components/Common/BackendDocumentPreview";
import { ApiError } from "@/lib/api/client";
import {
  adminService,
  type AdminSeller,
  type AdminSellerDocument,
} from "@/lib/api/endpoints/admin";
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Eye,
  FileText,
  Globe2,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  Search,
  ShieldCheck,
  UserCheck,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";

const errorMessage = (error: unknown) =>
  error instanceof ApiError
    ? error.message
    : "Unable to complete this seller action.";

const documentLabel = (type: string) => {
  const labels: Record<string, string> = {
    tin: "TIN Certificate",
    business_registration: "Business Licence / Registration",
    business_profile: "Business Profile",
  };

  return (
    labels[type] ||
    type.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
};


const sellerStatusStyle = (status: string) => {
  switch (status) {
    case "approved":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "rejected":
      return "bg-red-50 text-red-700 border-red-200";
    case "under_review":
      return "bg-blue-50 text-blue-700 border-blue-200";
    case "pending":
      return "bg-amber-50 text-amber-700 border-amber-200";
    default:
      return "bg-slate-50 text-slate-700 border-slate-200";
  }
};

const documentStatusStyle = (status: string) => {
  switch (status) {
    case "approved":
      return "bg-emerald-50 text-emerald-700";
    case "rejected":
      return "bg-red-50 text-red-700";
    case "under_review":
      return "bg-blue-50 text-blue-700";
    default:
      return "bg-amber-50 text-amber-700";
  }
};

export default function AdminSellers({
  mode = "all",
}: {
  mode?: "all" | "applications";
}) {
  const [sellers, setSellers] = useState<AdminSeller[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState(
    mode === "applications" ? "under_review" : "all",
  );
  const [selected, setSelected] = useState<AdminSeller | null>(null);
  const [documents, setDocuments] = useState<AdminSellerDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentPreview, setDocumentPreview] = useState<{
    title: string;
    url: string;
  } | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const load = async () => {
    setLoading(true);
    try {
      setSellers(await adminService.listAllSellers());
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const filtered = useMemo(
    () =>
      sellers.filter((seller) => {
        const matchesStatus = status === "all" || seller.status === status;
        const haystack =
          `${seller.business_name} ${seller.contact_email ?? ""} ${seller.contact_phone ?? ""}`.toLowerCase();

        return matchesStatus && haystack.includes(query.toLowerCase());
      }),
    [query, sellers, status],
  );

  useEffect(() => {
    setPage(1);
  }, [query, status, mode]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * pageSize;
  const visibleSellers = filtered.slice(pageStart, pageStart + pageSize);

  const openSeller = async (seller: AdminSeller) => {
    setSelected(seller);
    setRejectReason("");
    setShowRejectModal(false);
    setDocuments([]);
    setDocumentsLoading(true);

    try {
      let currentSeller = seller;
      if (seller.status === "under_review") {
        currentSeller = await adminService.startSellerReview(seller.id);
        setSelected(currentSeller);
        setSellers((items) => items.map((item) => item.id === currentSeller.id ? currentSeller : item));
      }
      setDocuments(await adminService.getSellerDocuments(seller.id));
    } catch (error) {
      setDocuments([]);
      toast.error(errorMessage(error));
    } finally {
      setDocumentsLoading(false);
    }
  };

  const approve = async () => {
    if (!selected) return;
    setBusy("approve");

    try {
      const updated = await adminService.approveSeller(selected.id);
      setSellers((items) =>
        items.map((item) => (item.id === updated.id ? updated : item)),
      );
      setSelected(updated);
      toast.success("Seller approved successfully.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  };

  const reject = async () => {
    if (!selected || !rejectReason.trim()) {
      toast.error("Add a rejection reason first.");
      return;
    }

    setBusy("reject");

    try {
      const updated = await adminService.rejectSeller(
        selected.id,
        rejectReason.trim(),
      );
      setSellers((items) =>
        items.map((item) => (item.id === updated.id ? updated : item)),
      );
      setSelected(updated);
      setDocuments(await adminService.getSellerDocuments(selected.id));
      setShowRejectModal(false);
      setRejectReason("");
      toast.success(
        "Seller application rejected. The seller can now see the reason and correct the rejected documents.",
      );
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  };

  const counts = {
    total: sellers.length,
    pending: sellers.filter((seller) => seller.status === "pending").length,
    review: sellers.filter((seller) => seller.status === "under_review").length,
    approved: sellers.filter((seller) => seller.status === "approved").length,
    rejected: sellers.filter((seller) => seller.status === "rejected").length,
  };

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f47524]">
              Seller operations
            </p>
            <h2 className="mt-1 text-2xl font-bold tracking-[-0.02em] text-slate-900">
              {mode === "applications" ? "Seller Applications" : "Seller Management"}
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
              {mode === "applications"
                ? "Review onboarding details, KYC documents and business information before activating marketplace access."
                : "Monitor every seller account, verification state and operational readiness from one workspace."}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-right">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Marketplace sellers
            </p>
            <p className="mt-1 text-2xl font-bold text-slate-900">{counts.total}</p>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 2xl:grid-cols-5">
        {[
          ["All sellers", counts.total, "All registered seller accounts"],
          ["Pending", counts.pending, "Waiting for review"],
          ["Under review", counts.review, "Currently being assessed"],
          ["Approved", counts.approved, "Marketplace access active"],
          ["Rejected", counts.rejected, "Correction required"],
        ].map(([label, value, hint]) => (
          <article
            key={label}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-600">{label}</p>
              <span className={`h-2.5 w-2.5 rounded-full ${
                label === "Approved"
                  ? "bg-emerald-500"
                  : label === "Rejected"
                    ? "bg-red-500"
                    : label === "Under review"
                      ? "bg-blue-500"
                      : label === "Pending"
                        ? "bg-amber-500"
                        : "bg-[#f47524]"
              }`} />
            </div>
            <p className="mt-3 text-3xl font-bold tracking-[-0.03em] text-slate-900">
              {value}
            </p>
            <p className="mt-1 text-xs text-slate-400">{hint}</p>
          </article>
        ))}
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_8px_30px_rgba(15,23,42,0.05)]">
        <div className="border-b border-slate-100 bg-white p-5 lg:p-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-50 text-[#f47524]">
                  <Building2 size={18} />
                </span>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">
                    {mode === "applications" ? "Seller applications" : "Seller directory"}
                  </h3>
                  <p className="mt-0.5 text-sm text-slate-500">
                    {filtered.length} of {sellers.length} seller{filtered.length === 1 ? "" : "s"}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex w-full flex-col gap-2 sm:flex-row xl:w-auto">
              <label className="relative min-w-0 flex-1 xl:w-[320px]">
                <Search className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search seller, email or phone..."
                  className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm text-slate-700 outline-none transition focus:border-orange-300 focus:bg-white focus:ring-4 focus:ring-orange-50"
                />
              </label>
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="h-11 rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 outline-none focus:border-orange-300"
              >
                <option value="all">All statuses</option>
                <option value="pending">Pending</option>
                <option value="under_review">Under review</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
              <button
                type="button"
                onClick={() => void load()}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:border-orange-200 hover:bg-orange-50 hover:text-[#f47524]"
              >
                <RefreshCw size={15} />
                Refresh
              </button>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="p-14 text-center text-sm text-slate-500">Loading sellers...</div>
        ) : filtered.length === 0 ? (
          <div className="p-14 text-center text-sm text-slate-500">No sellers match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] table-auto text-left">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-bold uppercase tracking-[0.08em] text-slate-500">
                  <th className="px-6 py-3.5">Seller / Business</th>
                  <th className="px-5 py-3.5">Contact</th>
                  <th className="px-5 py-3.5">Location</th>
                  <th className="px-5 py-3.5">Registered</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visibleSellers.map((seller) => (
                  <tr key={seller.id} className="group transition hover:bg-orange-50/35">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-orange-100 bg-orange-50 text-sm font-bold uppercase text-[#f47524]">
                          {seller.business_name?.trim().charAt(0) || "S"}
                        </span>
                        <div className="min-w-0">
                          <p className="max-w-[260px] truncate text-sm font-semibold text-slate-900">{seller.business_name}</p>
                          <p className="mt-0.5 text-xs text-slate-400">Seller ID: {seller.id.slice(0, 8)}…</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <p className="max-w-[230px] truncate text-sm font-medium text-slate-700">{seller.contact_email ?? "No email"}</p>
                      <p className="mt-1 text-xs text-slate-400">{seller.contact_phone ?? "No phone"}</p>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">
                      <div className="flex items-center gap-1.5"><MapPin size={14} className="shrink-0 text-slate-400" /><span>{[seller.business_city, seller.business_country].filter(Boolean).join(", ") || "—"}</span></div>
                    </td>
                    <td className="px-5 py-4">
                      <p className="text-sm font-medium text-slate-700">{new Date(seller.created_at).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })}</p>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold capitalize ${sellerStatusStyle(seller.status)}`}>
                        <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
                        {seller.status.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => void openSeller(seller)}
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:border-orange-200 hover:bg-orange-50 hover:text-[#f47524]"
                      >
                        <Eye size={14} />
                        {seller.status === "approved" ? "View seller" : seller.status === "rejected" ? "Review correction" : "Review application"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && filtered.length > 0 && (
          <div className="flex flex-col gap-3 border-t border-slate-100 bg-white px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-500">
              Showing{" "}
              <b className="text-slate-900">
                {pageStart + 1}-{Math.min(pageStart + pageSize, filtered.length)}
              </b>{" "}
              of <b className="text-slate-900">{filtered.length}</b> sellers
            </p>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={pageSize}
                onChange={(event) => {
                  setPageSize(Number(event.target.value));
                  setPage(1);
                }}
                className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-600"
              >
                {[10, 20, 50].map((size) => (
                  <option key={size} value={size}>
                    {size} / page
                  </option>
                ))}
              </select>

              <button
                type="button"
                disabled={safePage <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                className="inline-flex h-10 items-center gap-1 rounded-xl border border-slate-200 px-3 text-sm font-semibold text-slate-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft size={14} />
                Previous
              </button>

              <span className="min-w-24 text-center text-xs font-semibold text-slate-500">
                Page {safePage} of {totalPages}
              </span>

              <button
                type="button"
                disabled={safePage >= totalPages}
                onClick={() =>
                  setPage((current) => Math.min(totalPages, current + 1))
                }
                className="inline-flex h-10 items-center gap-1 rounded-xl border border-slate-200 px-3 text-sm font-semibold text-slate-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {selected && (
        <div
          className="fixed inset-0 z-[99999] flex justify-end bg-black/40"
          onMouseDown={() => {
            setSelected(null);
            setShowRejectModal(false);
            setRejectReason("");
          }}
        >
          <aside
            className="flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex-1 overflow-y-auto p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[#f47524]">
                  Seller application
                </p>
                <h3 className="mt-1 text-2xl font-semibold text-[#111827]">
                  {selected.business_name}
                </h3>
                <p className="mt-1 text-sm text-gray-500">
                  {selected.contact_email ?? "No contact email"}
                </p>
              </div>

              <button
                onClick={() => setSelected(null)}
                className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100"
              >
                <X size={17} />
              </button>
            </div>

            <div className="mt-6 rounded-2xl border border-[#e7ebf0] bg-[#f8fafc] p-5">
              <div className="mb-4 flex items-center gap-2">
                <Building2 size={18} className="text-[#f47524]" />
                <h4 className="font-semibold text-[#111827]">
                  Seller business details
                </h4>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <Detail icon={ShieldCheck} label="Seller Status" value={selected.status.replaceAll("_", " ")} />
                <Detail icon={Clock3} label="Years in Business" value={selected.years_in_business ?? "—"} />
                <Detail icon={Mail} label="Contact Email" value={selected.contact_email ?? "—"} />
                <Detail icon={Phone} label="Contact Phone" value={selected.contact_phone ?? "—"} />
                <Detail
                  icon={MapPin}
                  label="Business Location"
                  value={[
                    selected.business_address,
                    selected.business_city,
                    selected.business_region,
                    selected.business_country,
                  ]
                    .filter(Boolean)
                    .join(", ") || "—"}
                />
                <Detail
                  icon={Globe2}
                  label="Website"
                  value={selected.website_url ?? "—"}
                />
                <Detail
                  icon={UserCheck}
                  label="Seller Agreement"
                  value={selected.agreement_accepted ? "Accepted" : "Not accepted"}
                />
                <Detail
                  icon={FileText}
                  label="Documents Submitted"
                  value={documentsLoading ? "Loading..." : `${documents.length} document(s)`}
                />
              </div>

              {selected.business_description && (
                <div className="mt-4 rounded-xl border border-white bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Business description
                  </p>
                  <p className="mt-2 text-sm leading-6 text-gray-700">
                    {selected.business_description}
                  </p>
                </div>
              )}

              {selected.product_description && (
                <div className="mt-3 rounded-xl border border-white bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Products / services
                  </p>
                  <p className="mt-2 text-sm leading-6 text-gray-700">
                    {selected.product_description}
                  </p>
                </div>
              )}
            </div>

            <div
              className={`mt-6 rounded-xl border p-4 text-sm ${
                selected.status === "rejected"
                  ? "border-red-200 bg-red-50 text-red-800"
                  : selected.status === "approved"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-blue-100 bg-blue-50 text-blue-800"
              }`}
            >
              <p className="font-semibold">
                {selected.status === "rejected"
                  ? "Correction requested"
                  : selected.status === "approved"
                    ? "Seller verified"
                    : "Admin review mode"}
              </p>
              <p className="mt-1 text-xs leading-5">
                {selected.status === "rejected"
                  ? "The seller can edit the rejected document(s). Review the corrected submission when it is uploaded again."
                  : selected.status === "approved"
                    ? "This seller has completed verification. Documents remain available for audit and viewing."
                    : "Seller documents are view-only during review. Admin does not edit seller files. Reject with a clear reason when a correction is required."}
              </p>
            </div>

            <div className="mt-6">
              <div className="flex items-center gap-2">
                <ShieldCheck size={18} className="text-[#f47524]" />
                <div>
                  <h4 className="font-semibold text-[#111827]">
                    Submitted KYC documents
                  </h4>
                  <p className="text-xs text-gray-500">
                    Loaded from this seller&apos;s backend document records.
                  </p>
                </div>
              </div>

              {documentsLoading ? (
                <div className="mt-4 flex items-center gap-2 rounded-xl bg-gray-50 p-4 text-sm text-gray-500">
                  <RefreshCw size={15} className="animate-spin" />
                  Loading seller documents...
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  {documents.map((document) => (
                    <div
                      key={document.id}
                      className="rounded-xl border border-gray-200 p-4"
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-50 text-[#f47524]">
                          <FileText size={18} />
                        </span>

                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-[#111827]">
                            {documentLabel(document.document_type)}
                          </p>
                          <span
                            className={`mt-1 inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold capitalize ${documentStatusStyle(
                              document.status,
                            )}`}
                          >
                            {document.status.replaceAll("_", " ")}
                          </span>
                        </div>

                        <button
                          type="button"
                          onClick={() =>
                            setDocumentPreview({
                              title: `${selected.business_name} — ${documentLabel(
                                document.document_type,
                              )}`,
                              url: adminService.getSellerDocumentViewUrl(selected.id, document.id),
                            })
                          }
                          className="inline-flex items-center gap-1.5 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs font-semibold text-[#f47524] hover:bg-orange-100"
                        >
                          <Eye size={14} />
                          Preview
                        </button>
                      </div>

                      {document.rejection_reason && (
                        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3">
                          <p className="text-[10px] font-bold uppercase tracking-wider text-red-700">
                            Rejection reason
                          </p>
                          <p className="mt-1 text-xs leading-5 text-red-700">
                            {document.rejection_reason}
                          </p>
                        </div>
                      )}
                    </div>
                  ))}

                  {documents.length === 0 && (
                    <p className="rounded-xl bg-orange-50 p-4 text-sm text-orange-700">
                      No KYC documents uploaded by this seller.
                    </p>
                  )}
                </div>
              )}
            </div>

            </div>

            {selected.status !== "approved" && (
              <div className="shrink-0 border-t border-gray-200 bg-white px-6 py-4 shadow-[0_-8px_24px_rgba(15,23,42,0.04)]">
                <p className="mb-3 text-xs leading-5 text-gray-500">
                  After reviewing the seller details and all submitted documents,
                  approve the application or reject it and provide a correction reason.
                </p>

                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    disabled={Boolean(busy) || documentsLoading || documents.length === 0}
                    onClick={() => void approve()}
                    className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 text-sm font-semibold text-black transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <CheckCircle2 size={17} />
                    {busy === "approve" ? "Approving..." : "Approve Seller"}
                  </button>

                  <button
                    type="button"
                    disabled={Boolean(busy) || documentsLoading || documents.length === 0}
                    onClick={() => {
                      setRejectReason("");
                      setShowRejectModal(true);
                    }}
                    className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-semibold text-black transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <AlertCircle size={17} />
                    Reject Seller
                  </button>
                </div>
              </div>
            )}
          </aside>
        </div>
      )}

      {showRejectModal && selected && (
        <div
          className="fixed inset-0 z-[100000] flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm"
          onMouseDown={() => {
            if (!busy) {
              setShowRejectModal(false);
              setRejectReason("");
            }
          }}
        >
          <div
            className="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-gray-100 px-6 py-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-red-600">
                  Reject Seller Application
                </p>
                <h3 className="mt-1 text-xl font-semibold text-[#111827]">
                  {selected.business_name}
                </h3>
                <p className="mt-1 text-sm leading-6 text-gray-500">
                  Tell the seller exactly what must be corrected. This reason will
                  be visible to the seller and will allow document editing again.
                </p>
              </div>

              <button
                type="button"
                disabled={Boolean(busy)}
                onClick={() => {
                  setShowRejectModal(false);
                  setRejectReason("");
                }}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 disabled:opacity-50"
              >
                <X size={17} />
              </button>
            </div>

            <div className="px-6 py-5">
              <label
                htmlFor="seller-rejection-reason"
                className="text-sm font-semibold text-[#111827]"
              >
                Rejection reason <span className="text-red-600">*</span>
              </label>

              <p className="mt-1 text-xs leading-5 text-gray-500">
                Be specific. For example, identify the document and what is wrong
                with it.
              </p>

              <textarea
                id="seller-rejection-reason"
                value={rejectReason}
                onChange={(event) => setRejectReason(event.target.value)}
                rows={5}
                autoFocus
                maxLength={1000}
                placeholder="Example: The Business Licence has expired. Please upload a valid current Business Licence."
                className="mt-3 w-full resize-none rounded-xl border border-gray-200 p-3 text-sm outline-none transition focus:border-red-400 focus:ring-4 focus:ring-red-50"
              />

              <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
                <span>
                  Minimum 5 characters
                </span>
                <span>{rejectReason.length}/1000</span>
              </div>

              <div className="mt-5 flex gap-3">
                <button
                  type="button"
                  disabled={Boolean(busy)}
                  onClick={() => {
                    setShowRejectModal(false);
                    setRejectReason("");
                  }}
                  className="flex-1 rounded-xl border border-gray-200 px-4 py-3 text-sm font-semibold text-[#334155] transition hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  disabled={Boolean(busy) || rejectReason.trim().length < 5}
                  onClick={() => void reject()}
                  className="flex-1 rounded-xl bg-red-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy === "reject"
                    ? "Rejecting..."
                    : "Confirm Rejection"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <BackendDocumentPreview
        open={Boolean(documentPreview)}
        title={documentPreview?.title || "Seller document"}
        documentUrl={documentPreview?.url || ""}
        onClose={() => setDocumentPreview(null)}
      />
    </div>
  );
}


function Detail({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof ShieldCheck;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl bg-white p-3">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-orange-50 text-[#f47524]">
        <Icon size={15} />
      </span>
      <div className="min-w-0">
        <p className="text-[11px] text-gray-400">{label}</p>
        <p className="mt-0.5 break-words text-sm font-medium capitalize text-[#111827]">
          {value}
        </p>
      </div>
    </div>
  );
}

