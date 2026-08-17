"use client";

import { sellersApi } from "@/lib/api/endpoints/sellers";
import BackendDocumentPreview from "@/components/Common/BackendDocumentPreview";
import { ApiError } from "@/lib/api/client";
import { authStorage } from "@/lib/auth/storage";
import type { SellerDocumentType, SellerKycDocument, PayoutAccount, SellerKycStatus } from "@/types/api/seller";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  BadgeCheck,
  Banknote,
  CircleAlert,
  Clock3,
  CreditCard,
  Eye,
  FileText,
  ImageIcon,
  LockKeyhole,
  Pencil,
  ShieldCheck,
  Smartphone,
  Trash2,
  WalletCards,
  X,
} from "lucide-react";
import Link from "next/link";
const documentLabel = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const payoutStatusMeta = (status?: string | null) => {
  const value = (status || "pending").toLowerCase();

  if (value === "verified") {
    return {
      label: "Verified",
      className: "border-emerald-200 bg-emerald-50 text-emerald-700",
      icon: BadgeCheck,
    };
  }

  if (value === "rejected") {
    return {
      label: "Rejected",
      className: "border-red-200 bg-red-50 text-red-700",
      icon: CircleAlert,
    };
  }

  return {
    label: "Pending verification",
    className: "border-amber-200 bg-amber-50 text-amber-700",
    icon: Clock3,
  };
};

const maskAccountNumber = (value: string) => {
  const clean = value.trim();
  if (clean.length <= 4) return clean;
  return `${"•".repeat(Math.min(clean.length - 4, 8))}${clean.slice(-4)}`;
};


type StoredUser = {
  account_type?: string;
  roles?: string[];
  seller_status?: string | null;
  first_name?: string | null;
};

const SellerKyc = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeTab = searchParams.get("tab") === "payouts" ? "payouts" : "verification";
  const user = authStorage.getUser<StoredUser>();
  const token = authStorage.getAccessToken();

  const isSeller = useMemo(() => {
    if (!user) return false;
    const roles = user.roles ?? [];
    return user.account_type === "seller" || roles.includes("seller");
  }, [user]);

  const [status, setStatus] = useState<SellerKycStatus | null>(null);
  const [documents, setDocuments] = useState<SellerKycDocument[]>([]);
  const [payoutAccounts, setPayoutAccounts] = useState<PayoutAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [uploadType, setUploadType] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [localPreviewUrl, setLocalPreviewUrl] = useState("");
  const [preview, setPreview] = useState<{
    title: string;
    url: string;
    mimeType?: string | null;
  } | null>(null);
  const [submittedPreview, setSubmittedPreview] = useState<{
    title: string;
    url: string;
  } | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const [accountType, setAccountType] = useState<"bank" | "mobile_money">("bank");
  const [provider, setProvider] = useState("");
  const [accountName, setAccountName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [currency, setCurrency] = useState("TZS");
  const [isDefault, setIsDefault] = useState(false);
  const [isAddingAccount, setIsAddingAccount] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PayoutAccount | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (!token) {
      router.replace("/signin?redirect=/seller/kyc");
      return;
    }

    if (!isSeller) {
      router.replace("/my-account");
      return;
    }

    void loadData();
  }, [isSeller, router, token]);

  useEffect(() => {
    if (!uploadFile) {
      setLocalPreviewUrl("");
      return;
    }

    const url = URL.createObjectURL(uploadFile);
    setLocalPreviewUrl(url);

    return () => URL.revokeObjectURL(url);
  }, [uploadFile]);

  async function loadData() {
    const accessToken = token;
    if (!accessToken) return;

    setLoading(true);
    setError("");
    try {
      const [statusData, docsData, accountsData] = await Promise.all([
        sellersApi.getKycStatus(accessToken),
        sellersApi.getKycDocuments(accessToken),
        sellersApi.getPayoutAccounts(accessToken),
      ]);

      setStatus(statusData);
      setUploadType((current) => current || statusData.required_documents[0] || "");
      setDocuments(docsData);
      setPayoutAccounts(accountsData);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to load KYC data.";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !uploadFile) {
      toast.error("Please select a file to upload.");
      return;
    }

    setIsUploading(true);
    try {
      await sellersApi.uploadKycDocument(
        { document_type: uploadType as SellerDocumentType, file: uploadFile },
        token
      );
      toast.success(`${documentLabel(uploadType)} uploaded successfully.`);
      setUploadFile(null);
      setLocalPreviewUrl("");
      await loadData();
    } catch (error) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to upload document.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  async function handleAddAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;

    if (!provider.trim() || !accountName.trim() || !accountNumber.trim()) {
      toast.error("Please fill in all required fields.");
      return;
    }

    setIsAddingAccount(true);
    try {
      await sellersApi.createPayoutAccount(
        {
          account_type: accountType,
          provider: provider.trim(),
          account_name: accountName.trim(),
          account_number: accountNumber.trim(),
          currency: currency.trim(),
          is_default: isDefault,
        },
        token
      );
      toast.success(
        "Payout account added. It must be verified before it can receive seller payouts.",
      );
      setProvider("");
      setAccountName("");
      setAccountNumber("");
      setCurrency("TZS");
      setIsDefault(false);
      await loadData();
    } catch (error) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to add payout account.");
      }
    } finally {
      setIsAddingAccount(false);
    }
  }

  async function handleDeleteAccount() {
    if (!token || !deleteTarget) return;

    setIsDeleting(true);
    try {
      await sellersApi.deletePayoutAccount(deleteTarget.id, token);
      toast.success("Payout account deleted.");
      setDeleteTarget(null);
      await loadData();
    } catch (error) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to delete payout account.");
      }
    } finally {
      setIsDeleting(false);
    }
  }

  function getDocumentStatus(type: string): "missing" | "pending" | "under_review" | "approved" | "rejected" | "uploaded" {
    const doc = documents.find((d) => d.document_type === type);
    if (!doc) return "missing";
    return (doc.status as "pending" | "under_review" | "approved" | "rejected") || "uploaded";
  }

  if (!token || !isSeller) return null;
  if (loading) return <div className="p-12 text-center text-dark-4 dark:text-darkTheme-body-color">Loading verification data...</div>;
  if (error) return <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-700"><p>{error}</p><button type="button" onClick={() => void loadData()} className="mt-3 rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white">Retry</button></div>;

  const allSubmitted =
    (status?.required_documents?.length ?? 0) > 0 &&
    (status?.required_documents ?? []).every((type) =>
      documents.some((document) => document.document_type === type)
    );
  const verifiedPayoutAccounts = payoutAccounts.filter(
    (account) =>
      account.is_active !== false &&
      (account.verification_status || "pending") === "verified",
  );
  const pendingPayoutAccounts = payoutAccounts.filter(
    (account) =>
      account.is_active !== false &&
      (account.verification_status || "pending") === "pending",
  );
  const rejectedPayoutAccounts = payoutAccounts.filter(
    (account) => (account.verification_status || "pending") === "rejected",
  );
  const defaultPayoutAccount = payoutAccounts.find(
    (account) => account.is_default && account.is_active !== false,
  );

  const reviewLocked =
    status?.seller_status === "approved" ||
    documents.some((document) => document.status === "under_review");
  const canEditDocument = (document: SellerKycDocument | undefined) =>
    Boolean(document && !reviewLocked && status?.seller_status !== "approved" && ["pending", "rejected"].includes(document.status || "pending"));

  return (
    <>
      <section>
        <div className="mx-auto max-w-[1280px]">

          <div className="mb-6 flex w-fit flex-wrap gap-1 rounded-xl border border-gray-3 bg-white p-1 dark:border-darkTheme-border-color dark:bg-darkTheme-card">
            <button
              type="button"
              onClick={() => router.push("/seller/kyc")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${activeTab === "verification" ? "bg-[#f7941d] text-white" : "text-dark-4 hover:bg-gray-1 dark:text-darkTheme-body-color dark:hover:bg-darkTheme-secondary-bg"}`}
            >
              KYC Verification
            </button>
            <button
              type="button"
              onClick={() => router.push("/seller/documents")}
              className="rounded-lg px-4 py-2 text-sm font-semibold text-dark-4 transition hover:bg-gray-1 dark:text-darkTheme-body-color dark:hover:bg-darkTheme-secondary-bg"
            >
              Business Documents
            </button>
            {status?.seller_status === "approved" && (
            <button
              type="button"
              onClick={() => router.push("/seller/kyc?tab=payouts")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${activeTab === "payouts" ? "bg-[#f7941d] text-white" : "text-dark-4 hover:bg-gray-1 dark:text-darkTheme-body-color dark:hover:bg-darkTheme-secondary-bg"}`}
            >
              Payout Account
            </button>
            )}
          </div>

          {status?.can_submit_for_review && (
            <div className="mb-6 rounded-lg bg-success/10 border border-success/20 text-success px-4 py-3">
              All required documents are uploaded. Your account is under review.
            </div>
          )}

          <div className="grid grid-cols-1 gap-8">
            <div className={`${activeTab === "verification" ? "block" : "hidden"} rounded-xl bg-white dark:bg-darkTheme-card shadow-1 p-6 sm:p-8`}>
              <h2 className="text-xl font-semibold text-dark dark:text-white mb-6">Required Documents</h2>

              <div className="space-y-4 mb-8">
                {(status?.required_documents ?? []).map((type) => {
                  const docStatus = getDocumentStatus(type);
                  const document = documents.find((item) => item.document_type === type);
                  return (
                    <div
                      key={type}
                      className={`flex items-center justify-between rounded-lg border p-4 ${
                        docStatus === "missing"
                          ? "border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg"
                          : docStatus === "pending"
                          ? "border-warning/30 bg-warning/5"
                          : "border-success/30 bg-success/5"
                      }`}
                    >
                      <div>
                        <p className="font-medium text-dark dark:text-white">{documentLabel(type)}</p>
                        <p className="text-sm text-dark-4 dark:text-darkTheme-body-color capitalize">
                          {docStatus === "missing" ? "Not uploaded" : docStatus}
                        </p>
                        {document?.rejection_reason && (
                          <p className="mt-2 max-w-xl rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-700">
                            <strong>Admin reason:</strong> {document.rejection_reason}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {document && (
                          <button
                            type="button"
                            onClick={() => setSubmittedPreview({ title: documentLabel(type), url: sellersApi.getKycDocumentViewUrl(document.id) })}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-[#f7941d]/30 bg-orange-50 px-3 py-1.5 text-xs font-semibold text-[#f7941d] dark:bg-orange-500/10"
                          >
                            <Eye size={14} /> View
                          </button>
                        )}
                        {canEditDocument(document) && (
                          <Link href={`/seller/documents?edit=${encodeURIComponent(type)}`} className="inline-flex items-center gap-1.5 rounded-lg bg-[#111827] px-3 py-1.5 text-xs font-semibold text-white">
                            <Pencil size={13} /> Edit
                          </Link>
                        )}
                        {document && reviewLocked && (
                          <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-medium text-[#64748b]">
                            <LockKeyhole size={13} /> View only
                          </span>
                        )}

                        <span
                          className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${
                            docStatus === "missing"
                              ? "bg-gray-2 text-dark-2"
                              : docStatus === "pending"
                              ? "bg-warning/10 text-warning"
                              : "bg-success/10 text-success"
                          }`}
                        >
                          {docStatus}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className={`relative ${allSubmitted ? "opacity-40 pointer-events-none select-none" : ""}`}>
              <h3 className="text-lg font-semibold text-dark dark:text-white mb-4">Upload Document</h3>
              <div className="mb-5 rounded-xl border border-orange/20 bg-orange/5 p-4">
                <p className="text-sm font-semibold text-dark dark:text-white">
                  Need to submit TIN, Business Licence and Business Profile together?
                </p>
                <p className="mt-1 text-xs leading-5 text-dark-4 dark:text-darkTheme-body-color">
                  Use the Business Documents workspace to select, preview and submit all required verification files in one action.
                </p>
                <Link
                  href="/seller/documents"
                  className="mt-3 inline-flex rounded-lg bg-orange px-4 py-2 text-sm font-semibold text-white hover:bg-orange-dark"
                >
                  Upload all business documents
                </Link>
              </div>

              <form onSubmit={handleUpload} className="space-y-5">
                <div>
                  <label className="block mb-2.5 dark:text-darkTheme-body-color">Document type</label>
                  <select
                    value={uploadType}
                    onChange={(event) => setUploadType(event.target.value)}
                    disabled={isUploading}
                    className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color w-full py-3 px-5 outline-none focus:ring-2 focus:ring-blue/20"
                  >
                    {(status?.required_documents ?? []).map((type) => (
                      <option key={type} value={type}>
                        {documentLabel(type)}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block mb-2.5 dark:text-darkTheme-body-color">File (PDF, JPG, PNG)</label>
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                    disabled={isUploading}
                    className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color w-full py-3 px-5 outline-none focus:ring-2 focus:ring-blue/20 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-blue file:text-white file:text-sm"
                  />
                </div>

                {uploadFile && localPreviewUrl && (
                  <div className="rounded-xl border border-gray-3 bg-white p-4 dark:border-darkTheme-border-color dark:bg-darkTheme-secondary-bg">
                    <div className="flex items-start gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-orange-50 text-[#f7941d] dark:bg-orange-500/10">
                        {uploadFile.type.startsWith("image/") ? (
                          <ImageIcon size={18} />
                        ) : (
                          <FileText size={18} />
                        )}
                      </span>

                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-dark dark:text-white">
                          {uploadFile.name}
                        </p>
                        <p className="mt-0.5 text-xs text-dark-4 dark:text-darkTheme-body-color">
                          {(uploadFile.size / 1024 / 1024).toFixed(2)} MB ·{" "}
                          {uploadFile.type || "Unknown file type"}
                        </p>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        setPreview({
                          title: `${documentLabel(uploadType)} — before upload`,
                          url: localPreviewUrl,
                          mimeType: uploadFile.type,
                        })
                      }
                      className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[#f7941d]/30 bg-orange-50 px-3 py-2 text-xs font-semibold text-[#f7941d] transition hover:bg-orange-100 dark:bg-orange-500/10"
                    >
                      <Eye size={14} />
                      Preview before upload
                    </button>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isUploading || !uploadFile}
                  className="w-full rounded-lg bg-blue text-white py-3.5 px-6 font-medium hover:bg-blue-dark disabled:opacity-60 disabled:cursor-not-allowed transition"
                >
                  {isUploading ? "Uploading..." : "Upload Document"}
                </button>
              </form>
              </div>
              {allSubmitted && (
                <div className="mt-4 rounded-xl border border-[#e7ebf0] bg-slate-50 p-4 text-sm text-[#64748b]">
                  Initial upload is complete. Use <strong>View</strong> and <strong>Edit</strong> above. Edit is hidden while Admin is reviewing and returns after rejection.
                </div>
              )}
            </div>

            <div
              className={`${activeTab === "payouts" ? "block" : "hidden"} space-y-5`}
            >
              <div className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card sm:p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="max-w-2xl">
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-50 text-[#f7941d] dark:bg-orange-400/10">
                        <WalletCards size={20} />
                      </span>
                      <div>
                        <h2 className="text-xl font-bold text-dark dark:text-white">
                          Seller Payout Accounts
                        </h2>
                        <p className="mt-1 text-sm leading-6 text-dark-4 dark:text-darkTheme-body-color">
                          Add the bank or mobile-money account where Xerin can settle
                          released marketplace earnings. New payout accounts require
                          verification before they can be used for payout requests.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 sm:min-w-[340px]">
                    <PayoutSummary
                      label="Verified"
                      value={verifiedPayoutAccounts.length}
                      tone="green"
                    />
                    <PayoutSummary
                      label="Pending"
                      value={pendingPayoutAccounts.length}
                      tone="amber"
                    />
                    <PayoutSummary
                      label="Rejected"
                      value={rejectedPayoutAccounts.length}
                      tone="red"
                    />
                  </div>
                </div>

                <div className="mt-5 rounded-xl border border-blue-100 bg-blue-50/70 p-4 text-sm leading-6 text-blue-800 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200">
                  <div className="flex items-start gap-3">
                    <ShieldCheck size={18} className="mt-0.5 shrink-0" />
                    <p>
                      A payout request will only be accepted when the selected
                      payout account is <strong>active and verified</strong>.
                      Verification is performed by an authorized Xerin staff user.
                    </p>
                  </div>
                </div>
              </div>

              <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
                <div className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card sm:p-6">
                  <div className="mb-5 flex items-center justify-between gap-3">
                    <div>
                      <h3 className="font-bold text-dark dark:text-white">
                        Registered accounts
                      </h3>
                      <p className="mt-1 text-xs text-dark-4 dark:text-darkTheme-body-color">
                        {payoutAccounts.length
                          ? `${payoutAccounts.length} payout account${payoutAccounts.length === 1 ? "" : "s"}`
                          : "No payout account configured"}
                      </p>
                    </div>

                    {defaultPayoutAccount && (
                      <span className="rounded-full border border-orange-200 bg-orange-50 px-3 py-1 text-xs font-semibold text-[#c66c0b]">
                        Default: {defaultPayoutAccount.provider}
                      </span>
                    )}
                  </div>

                  {payoutAccounts.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-[#d9dee7] bg-slate-50 px-5 py-10 text-center dark:border-white/10 dark:bg-white/[0.03]">
                      <WalletCards
                        size={30}
                        className="mx-auto text-[#94a3b8]"
                      />
                      <p className="mt-3 font-semibold text-dark dark:text-white">
                        No payout account yet
                      </p>
                      <p className="mx-auto mt-1 max-w-md text-sm leading-6 text-dark-4 dark:text-darkTheme-body-color">
                        Add a bank or mobile-money account using the form. The
                        account will start in Pending Verification status.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {payoutAccounts.map((account) => {
                        const statusMeta = payoutStatusMeta(
                          account.verification_status,
                        );
                        const StatusIcon = statusMeta.icon;
                        const isInactive = account.is_active === false;

                        return (
                          <article
                            key={account.id}
                            className={`rounded-2xl border p-4 transition ${
                              isInactive
                                ? "border-slate-200 bg-slate-50 opacity-70 dark:border-white/10 dark:bg-white/[0.03]"
                                : "border-[#e7ebf0] bg-white hover:border-orange-200 dark:border-white/10 dark:bg-white/[0.025]"
                            }`}
                          >
                            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                              <div className="flex min-w-0 gap-3">
                                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-[#64748b] dark:bg-white/10">
                                  {account.account_type === "mobile_money" ? (
                                    <Smartphone size={20} />
                                  ) : (
                                    <Banknote size={20} />
                                  )}
                                </span>

                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="font-bold text-dark dark:text-white">
                                      {account.provider}
                                    </p>

                                    {account.is_default && (
                                      <span className="rounded-full bg-orange-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-[#c66c0b]">
                                        Default
                                      </span>
                                    )}

                                    {isInactive && (
                                      <span className="rounded-full bg-slate-200 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-600">
                                        Inactive
                                      </span>
                                    )}
                                  </div>

                                  <p className="mt-1 text-sm font-medium text-[#334155] dark:text-white/80">
                                    {account.account_name}
                                  </p>
                                  <p className="mt-0.5 font-mono text-sm text-[#64748b] dark:text-white/55">
                                    {maskAccountNumber(account.account_number)}
                                  </p>

                                  <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 font-semibold text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-white/60">
                                      {account.account_type === "mobile_money"
                                        ? "Mobile Money"
                                        : "Bank Account"}
                                    </span>
                                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 font-semibold text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-white/60">
                                      {account.currency}
                                    </span>
                                  </div>
                                </div>
                              </div>

                              <div className="flex flex-col items-start gap-2 sm:items-end">
                                <span
                                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${statusMeta.className}`}
                                >
                                  <StatusIcon size={13} />
                                  {statusMeta.label}
                                </span>

                                {account.verified_at && (
                                  <span className="text-[11px] text-[#94a3b8]">
                                    Verified{" "}
                                    {new Date(
                                      account.verified_at,
                                    ).toLocaleDateString()}
                                  </span>
                                )}

                                {account.provider_reference && (
                                  <span className="max-w-[220px] truncate text-[11px] text-[#94a3b8]">
                                    Ref: {account.provider_reference}
                                  </span>
                                )}

                                <button
                                  type="button"
                                  onClick={() => setDeleteTarget(account)}
                                  className="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600 transition hover:bg-red-50"
                                >
                                  <Trash2 size={13} />
                                  {account.is_active === false
                                    ? "Remove"
                                    : "Delete / Deactivate"}
                                </button>
                              </div>
                            </div>

                            {(account.verification_status || "pending") ===
                              "rejected" && (
                              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-700">
                                This payout account was rejected. Add a corrected
                                payout account before requesting a payout.
                              </div>
                            )}

                            {(account.verification_status || "pending") ===
                              "pending" && (
                              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-700">
                                This account is waiting for verification. It cannot
                                receive a payout yet.
                              </div>
                            )}
                          </article>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card sm:p-6">
                  <div className="mb-5 flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-50 text-[#f7941d] dark:bg-orange-400/10">
                      <CreditCard size={18} />
                    </span>
                    <div>
                      <h3 className="font-bold text-dark dark:text-white">
                        Add payout account
                      </h3>
                      <p className="mt-0.5 text-xs text-dark-4 dark:text-darkTheme-body-color">
                        Settlement destination for released seller earnings.
                      </p>
                    </div>
                  </div>

                  <form onSubmit={handleAddAccount} className="space-y-4">
                    <div>
                      <label className="mb-1.5 block text-xs font-semibold text-[#475569] dark:text-white/70">
                        Account type
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          disabled={isAddingAccount}
                          onClick={() => {
                            setAccountType("bank");
                            setProvider("");
                          }}
                          className={`rounded-xl border px-3 py-3 text-sm font-semibold transition ${
                            accountType === "bank"
                              ? "border-orange-300 bg-orange-50 text-[#c66c0b]"
                              : "border-[#e2e8f0] bg-white text-[#64748b] dark:border-white/10 dark:bg-white/5"
                          }`}
                        >
                          <Banknote size={17} className="mx-auto mb-1.5" />
                          Bank
                        </button>
                        <button
                          type="button"
                          disabled={isAddingAccount}
                          onClick={() => {
                            setAccountType("mobile_money");
                            setProvider("");
                          }}
                          className={`rounded-xl border px-3 py-3 text-sm font-semibold transition ${
                            accountType === "mobile_money"
                              ? "border-orange-300 bg-orange-50 text-[#c66c0b]"
                              : "border-[#e2e8f0] bg-white text-[#64748b] dark:border-white/10 dark:bg-white/5"
                          }`}
                        >
                          <Smartphone size={17} className="mx-auto mb-1.5" />
                          Mobile Money
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="mb-1.5 block text-xs font-semibold text-[#475569] dark:text-white/70">
                        {accountType === "bank"
                          ? "Bank name"
                          : "Mobile-money provider"}{" "}
                        <span className="text-red">*</span>
                      </label>

                      {accountType === "mobile_money" ? (
                        <select
                          value={provider}
                          onChange={(event) => setProvider(event.target.value)}
                          disabled={isAddingAccount}
                          className="h-11 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-3 text-sm outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-white/5"
                        >
                          <option value="">Select provider</option>
                          <option value="M-Pesa">M-Pesa</option>
                          <option value="Airtel Money">Airtel Money</option>
                          <option value="Mixx by Yas">Mixx by Yas</option>
                          <option value="HaloPesa">HaloPesa</option>
                        </select>
                      ) : (
                        <input
                          type="text"
                          value={provider}
                          onChange={(event) => setProvider(event.target.value)}
                          placeholder="e.g. CRDB Bank"
                          disabled={isAddingAccount}
                          className="h-11 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-3 text-sm outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-white/5"
                        />
                      )}
                    </div>

                    <div>
                      <label className="mb-1.5 block text-xs font-semibold text-[#475569] dark:text-white/70">
                        Account holder name <span className="text-red">*</span>
                      </label>
                      <input
                        type="text"
                        value={accountName}
                        onChange={(event) =>
                          setAccountName(event.target.value)
                        }
                        placeholder="Name registered on the payout account"
                        disabled={isAddingAccount}
                        className="h-11 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-3 text-sm outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-white/5"
                      />
                    </div>

                    <div>
                      <label className="mb-1.5 block text-xs font-semibold text-[#475569] dark:text-white/70">
                        {accountType === "bank"
                          ? "Bank account number"
                          : "Mobile-money number"}{" "}
                        <span className="text-red">*</span>
                      </label>
                      <input
                        type="text"
                        value={accountNumber}
                        onChange={(event) =>
                          setAccountNumber(event.target.value)
                        }
                        placeholder={
                          accountType === "bank"
                            ? "Enter bank account number"
                            : "+255..."
                        }
                        disabled={isAddingAccount}
                        className="h-11 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-3 text-sm outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-white/5"
                      />
                    </div>

                    <div>
                      <label className="mb-1.5 block text-xs font-semibold text-[#475569] dark:text-white/70">
                        Currency
                      </label>
                      <select
                        value={currency}
                        onChange={(event) => setCurrency(event.target.value)}
                        disabled={isAddingAccount}
                        className="h-11 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-3 text-sm outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-white/5"
                      >
                        <option value="TZS">TZS — Tanzanian Shilling</option>
                        <option value="USD">USD — US Dollar</option>
                      </select>
                    </div>

                    <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-[#e2e8f0] p-3 dark:border-white/10">
                      <input
                        type="checkbox"
                        checked={isDefault}
                        onChange={(event) =>
                          setIsDefault(event.target.checked)
                        }
                        disabled={isAddingAccount}
                        className="mt-0.5 h-4 w-4 accent-[#f7941d]"
                      />
                      <span>
                        <span className="block text-sm font-semibold text-dark dark:text-white">
                          Make this my default payout account
                        </span>
                        <span className="mt-0.5 block text-xs leading-5 text-dark-4 dark:text-darkTheme-body-color">
                          The backend will remove default status from your other
                          payout accounts when this account is created as default.
                        </span>
                      </span>
                    </label>

                    <button
                      type="submit"
                      disabled={
                        isAddingAccount ||
                        !provider.trim() ||
                        !accountName.trim() ||
                        !accountNumber.trim()
                      }
                      className="w-full rounded-xl bg-[#f7941d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#e88312] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isAddingAccount
                        ? "Adding payout account..."
                        : "Add Payout Account"}
                    </button>

                    <p className="text-xs leading-5 text-[#64748b] dark:text-white/55">
                      For your security, payout-account verification and status
                      changes are controlled by authorized Xerin staff. Seller-side
                      editing is not enabled in the current backend; add a corrected
                      account if details are wrong.
                    </p>
                  </form>
                </div>
              </section>
            </div>
            </div>
          </div>
      </section>

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="max-w-md w-full rounded-xl bg-white dark:bg-darkTheme-card shadow-1 p-6">
            <h3 className="text-lg font-semibold text-dark dark:text-white mb-2">
              Remove payout account?
            </h3>
            <p className="text-dark-4 dark:text-darkTheme-body-color mb-6">
              Account: {deleteTarget.account_name} — {deleteTarget.provider}. If
              this account already has payout history, the backend will safely
              deactivate it instead of deleting the historical relationship.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={isDeleting}
                className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color text-dark dark:text-white py-2.5 px-5 hover:bg-gray-1 dark:hover:bg-darkTheme-secondary-bg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteAccount}
                disabled={isDeleting}
                className="rounded-lg bg-red text-white py-2.5 px-5 hover:bg-red-dark disabled:opacity-60"
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
      <BackendDocumentPreview
        open={Boolean(submittedPreview)}
        title={submittedPreview?.title || "Submitted document"}
        documentUrl={submittedPreview?.url || ""}
        onClose={() => setSubmittedPreview(null)}
      />

      <DocumentPreviewModal
        open={Boolean(preview)}
        title={preview?.title || "Document"}
        url={preview?.url || ""}
        mimeType={preview?.mimeType}
        onClose={() => setPreview(null)}
      />
    </>
  );
};

function PayoutSummary({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "green" | "amber" | "red";
}) {
  const toneClass =
    tone === "green"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : tone === "red"
        ? "border-red-200 bg-red-50 text-red-700"
        : "border-amber-200 bg-amber-50 text-amber-700";

  return (
    <div className={`rounded-xl border p-3 text-center ${toneClass}`}>
      <p className="text-xl font-bold">{value}</p>
      <p className="mt-0.5 text-[10px] font-bold uppercase tracking-wide">
        {label}
      </p>
    </div>
  );
}


export default SellerKyc;


function DocumentPreviewModal({
  open,
  title,
  url,
  mimeType,
  onClose,
}: {
  open: boolean;
  title: string;
  url: string;
  mimeType?: string | null;
  onClose: () => void;
}) {
  if (!open || !url) return null;

  const isImage =
    mimeType?.startsWith("image/") ||
    /\.(png|jpe?g|webp|gif|bmp|svg)(\?.*)?$/i.test(url);
  const isPdf =
    mimeType === "application/pdf" || /\.pdf(\?.*)?$/i.test(url);

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm">
      <div className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-[#1f2937]">
        <div className="flex items-center justify-between border-b border-[#e7ebf0] px-5 py-4 dark:border-white/10">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f7941d]">
              Document Preview
            </p>
            <h3 className="truncate text-base font-semibold text-[#111827] dark:text-white">
              {title}
            </h3>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#e7ebf0] text-[#64748b] transition hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/5"
            aria-label="Close document preview"
          >
            <X size={18} />
          </button>
        </div>

        <div className="min-h-[420px] flex-1 overflow-auto bg-slate-100 p-4 dark:bg-black/20">
          {isImage ? (
            <div className="flex min-h-[420px] items-center justify-center">
              <img
                src={url}
                alt={title}
                className="max-h-[72vh] max-w-full rounded-lg object-contain shadow-sm"
              />
            </div>
          ) : isPdf ? (
            <iframe
              src={url}
              title={title}
              className="h-[72vh] w-full rounded-lg bg-white"
            />
          ) : (
            <div className="flex min-h-[420px] flex-col items-center justify-center rounded-xl border border-dashed border-[#cbd5e1] bg-white p-8 text-center dark:border-white/10 dark:bg-white/5">
              <FileText size={36} className="text-[#94a3b8]" />
              <p className="mt-3 font-semibold">Preview is not available for this file type.</p>
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="mt-4 rounded-lg bg-[#f7941d] px-4 py-2 text-sm font-semibold text-white"
              >
                Open document
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}