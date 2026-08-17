"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Box,
  CheckCircle2,
  ImagePlus,
  MapPin,
  Ruler,
  Scale,
  PackageOpen,
  PencilLine,
  Trash2,
  MessageSquareText,
  PackageCheck,
  RefreshCw,
  Send,
  Truck,
  XCircle,
} from "lucide-react";
import toast from "react-hot-toast";

import { sellerOrdersApi } from "@/lib/api/endpoints/seller-orders";
import type {
  SellerOrder,
  SellerOrderMessage,
  SellerOrderPackage,
} from "@/types/api/seller-order";
import { Badge } from "./index";

const money = (value: number | string, currency = "TZS") =>
  new Intl.NumberFormat("en-TZ", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value || 0));

const errorMessage = (error: unknown) => {
  const candidate = error as {
    response?: { data?: { detail?: string } };
    message?: string;
  };
  return candidate.response?.data?.detail || candidate.message || "Request failed";
};

export default function SellerOrderDetail({ orderId }: { orderId: string }) {
  const [order, setOrder] = useState<SellerOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState("");

  const [packageInfo, setPackageInfo] = useState<SellerOrderPackage | null>(null);
  const [packageLoading, setPackageLoading] = useState(true);
  const [packageSaving, setPackageSaving] = useState(false);
  const [packageEditorOpen, setPackageEditorOpen] = useState(false);
  const [packageForm, setPackageForm] = useState({
    weight_kg: "",
    length_cm: "",
    width_cm: "",
    height_cm: "",
    package_count: "1",
    notes: "",
    is_ready: false,
    attachment_urls: [] as string[],
  });
  const [packageAttachmentDraft, setPackageAttachmentDraft] = useState("");

  const [messages, setMessages] = useState<SellerOrderMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(true);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [messageText, setMessageText] = useState("");
  const [attachmentUrls, setAttachmentUrls] = useState<string[]>([]);
  const [attachmentDraft, setAttachmentDraft] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setOrder(await sellerOrdersApi.get(orderId));
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const syncPackageForm = (value: SellerOrderPackage | null) => {
    setPackageForm({
      weight_kg: value?.weight_kg == null ? "" : String(value.weight_kg),
      length_cm: value?.length_cm == null ? "" : String(value.length_cm),
      width_cm: value?.width_cm == null ? "" : String(value.width_cm),
      height_cm: value?.height_cm == null ? "" : String(value.height_cm),
      package_count: String(value?.package_count || 1),
      notes: value?.notes || "",
      is_ready: Boolean(value?.is_ready),
      attachment_urls: value?.attachments?.map((item) => item.file_url) || [],
    });
  };

  const loadPackage = async () => {
    setPackageLoading(true);
    try {
      const value = await sellerOrdersApi.package(orderId);
      setPackageInfo(value);
      syncPackageForm(value);
    } catch (error) {
      const candidate = error as { response?: { status?: number } };
      if (candidate.response?.status === 404) {
        setPackageInfo(null);
        syncPackageForm(null);
      } else {
        toast.error(errorMessage(error));
      }
    } finally {
      setPackageLoading(false);
    }
  };

  const openPackageEditor = () => {
    syncPackageForm(packageInfo);
    setPackageAttachmentDraft("");
    setPackageEditorOpen(true);
  };

  const addPackageAttachment = () => {
    const value = packageAttachmentDraft.trim();
    if (!value) return;

    if (packageForm.attachment_urls.length >= 10) {
      toast.error("A maximum of 10 packaging evidence URLs is allowed.");
      return;
    }

    if (packageForm.attachment_urls.includes(value)) {
      toast.error("This attachment URL is already added.");
      return;
    }

    setPackageForm((current) => ({
      ...current,
      attachment_urls: [...current.attachment_urls, value],
    }));
    setPackageAttachmentDraft("");
  };

  const savePackage = async () => {
    const count = Number(packageForm.package_count);
    const weight = packageForm.weight_kg ? Number(packageForm.weight_kg) : null;
    const length = packageForm.length_cm ? Number(packageForm.length_cm) : null;
    const width = packageForm.width_cm ? Number(packageForm.width_cm) : null;
    const height = packageForm.height_cm ? Number(packageForm.height_cm) : null;

    if (!Number.isInteger(count) || count <= 0) {
      toast.error("Package count must be at least 1.");
      return;
    }

    for (const [label, value] of [
      ["Weight", weight],
      ["Length", length],
      ["Width", width],
      ["Height", height],
    ] as const) {
      if (value !== null && (!Number.isFinite(value) || value < 0)) {
        toast.error(`${label} must be zero or greater.`);
        return;
      }
    }

    if (packageForm.is_ready && (weight === null || weight <= 0)) {
      toast.error("Enter package weight before confirming Ready for Pickup.");
      return;
    }

    setPackageSaving(true);
    try {
      const saved = await sellerOrdersApi.savePackage(orderId, {
        weight_kg: weight,
        length_cm: length,
        width_cm: width,
        height_cm: height,
        package_count: count,
        notes: packageForm.notes.trim() || null,
        is_ready: packageForm.is_ready,
        attachment_urls: packageForm.attachment_urls,
      });

      setPackageInfo(saved);
      syncPackageForm(saved);
      setPackageEditorOpen(false);
      toast.success(
        saved.is_ready
          ? "Package confirmed and ready for pickup."
          : "Package details saved as a draft.",
      );
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setPackageSaving(false);
    }
  };

  const loadMessages = async () => {
    setMessagesLoading(true);
    try {
      setMessages(await sellerOrdersApi.messages(orderId));
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setMessagesLoading(false);
    }
  };

  useEffect(() => {
    void load();
    void loadMessages();
    void loadPackage();
  }, [orderId]);

  const run = async (fn: () => Promise<SellerOrder>, message: string) => {
    setBusy(true);
    try {
      setOrder(await fn());
      toast.success(message);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const dispatch = async () => {
    const carrier = prompt(
      "Carrier / logistics company name:",
      order?.shipping_carrier || "",
    );
    if (!carrier) return;

    const tracking = prompt("Tracking number:");
    if (!tracking) return;

    await run(
      () =>
        sellerOrdersApi.dispatch(orderId, {
          carrier_name: carrier,
          tracking_number: tracking,
          notes: notes || null,
        }),
      "Order dispatched",
    );
  };

  const cancel = async () => {
    const reason = prompt("Reason for cancellation request:");
    if (!reason) return;

    await run(
      () => sellerOrdersApi.cancel(orderId, reason, notes),
      "Cancellation requested",
    );
  };

  const addAttachmentUrl = () => {
    const value = attachmentDraft.trim();
    if (!value) return;
    if (attachmentUrls.length >= 10) {
      toast.error("A maximum of 10 attachment URLs is allowed per message.");
      return;
    }
    setAttachmentUrls((current) => [...current, value]);
    setAttachmentDraft("");
  };

  const sendMessage = async () => {
    const message = messageText.trim();
    if (!message) {
      toast.error("Enter a message first.");
      return;
    }

    setSendingMessage(true);
    try {
      const created = await sellerOrdersApi.sendMessage(orderId, {
        message,
        is_internal: false,
        attachment_urls: attachmentUrls,
      });

      setMessages((current) => [...current, created]);
      setMessageText("");
      setAttachmentUrls([]);
      setAttachmentDraft("");
      toast.success("Message sent.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSendingMessage(false);
    }
  };

  const orderedMessages = useMemo(
    () =>
      [...messages].sort(
        (a, b) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      ),
    [messages],
  );

  if (loading) {
    return (
      <div className="p-14 text-center text-slate-500">
        <RefreshCw className="mx-auto animate-spin" />
        <p className="mt-2">Loading order...</p>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="rounded-2xl border bg-white p-8">
        Seller order could not be loaded.
      </div>
    );
  }

  const status = order.seller_status;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 rounded-2xl border bg-white p-6 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link
            href="/seller/orders"
            className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500"
          >
            <ArrowLeft size={14} />
            Back to orders
          </Link>

          <h1 className="mt-3 text-2xl font-bold dark:text-white">
            Order #{order.order_id.slice(0, 8)}
          </h1>

          <div className="mt-2">
            <Badge status={status} />
          </div>
        </div>

        <div className="text-right">
          <p className="text-xs text-slate-400">Seller subtotal</p>
          <p className="text-2xl font-bold text-[#f7941d]">
            {money(order.seller_subtotal, order.currency)}
          </p>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.4fr_.8fr]">
        <div className="space-y-5">
          <section className="rounded-2xl border bg-white p-5 dark:border-white/10 dark:bg-[#1f2937]">
            <h2 className="font-bold dark:text-white">Items to fulfil</h2>

            <div className="mt-4 divide-y dark:divide-white/10">
              {order.items.map((item) => (
                <div
                  key={item.id}
                  className="flex justify-between gap-4 py-4"
                >
                  <div>
                    <b className="dark:text-white">{item.product_name}</b>
                    <p className="text-xs text-slate-400">
                      {item.variant_name || "Standard"} · Qty {item.quantity}
                    </p>
                  </div>

                  <b>{money(item.total_price, order.currency)}</b>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border bg-white p-5 dark:border-white/10 dark:bg-[#1f2937]">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="flex items-center gap-2 font-bold dark:text-white">
                  <PackageOpen size={18} />
                  Packaging & Ready for Pickup
                </h2>
                <p className="mt-1 text-xs leading-5 text-slate-400">
                  Record package weight, dimensions and packaging evidence before
                  marking this seller order Ready to Ship.
                </p>
              </div>

              {!["shipped", "delivered", "cancelled"].includes(status) && (
                <button
                  type="button"
                  onClick={openPackageEditor}
                  disabled={packageLoading || packageSaving}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-orange-200 bg-orange-50 px-4 py-2.5 text-xs font-semibold text-[#c66c0b] disabled:opacity-50"
                >
                  <PencilLine size={14} />
                  {packageInfo ? "Edit Package" : "Prepare Package"}
                </button>
              )}
            </div>

            {packageLoading ? (
              <div className="mt-5 rounded-xl border border-dashed p-7 text-center text-sm text-slate-500 dark:border-white/10">
                <RefreshCw size={18} className="mx-auto animate-spin" />
                <p className="mt-2">Loading package information...</p>
              </div>
            ) : packageInfo ? (
              <div className="mt-5 space-y-4">
                <div
                  className={`rounded-xl border p-4 ${
                    packageInfo.is_ready
                      ? "border-emerald-200 bg-emerald-50"
                      : "border-amber-200 bg-amber-50"
                  }`}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p
                        className={`font-semibold ${
                          packageInfo.is_ready
                            ? "text-emerald-800"
                            : "text-amber-800"
                        }`}
                      >
                        {packageInfo.is_ready
                          ? "Package confirmed — Ready for Pickup"
                          : "Package draft — Not ready yet"}
                      </p>
                      <p
                        className={`mt-1 text-xs ${
                          packageInfo.is_ready
                            ? "text-emerald-700"
                            : "text-amber-700"
                        }`}
                      >
                        {packageInfo.is_ready
                          ? "The fulfilment action can now move this order to Ready to Ship."
                          : "Review the package details and confirm readiness before handoff."}
                      </p>
                    </div>

                    {packageInfo.prepared_at && (
                      <span className="text-xs text-emerald-700">
                        Prepared {new Date(packageInfo.prepared_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <PackageMetric
                    icon={Scale}
                    label="Weight"
                    value={
                      packageInfo.weight_kg == null
                        ? "Not set"
                        : `${Number(packageInfo.weight_kg).toLocaleString()} kg`
                    }
                  />
                  <PackageMetric
                    icon={Ruler}
                    label="Dimensions"
                    value={
                      packageInfo.length_cm != null ||
                      packageInfo.width_cm != null ||
                      packageInfo.height_cm != null
                        ? `${packageInfo.length_cm ?? "—"} × ${packageInfo.width_cm ?? "—"} × ${packageInfo.height_cm ?? "—"} cm`
                        : "Not set"
                    }
                  />
                  <PackageMetric
                    icon={Box}
                    label="Packages"
                    value={String(packageInfo.package_count)}
                  />
                  <PackageMetric
                    icon={ImagePlus}
                    label="Evidence"
                    value={`${packageInfo.attachments?.length || 0} attachment${packageInfo.attachments?.length === 1 ? "" : "s"}`}
                  />
                </div>

                {packageInfo.notes && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/[0.03]">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
                      Packaging notes
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-600 dark:text-white/65">
                      {packageInfo.notes}
                    </p>
                  </div>
                )}

                {packageInfo.attachments?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500">
                      Packaging evidence
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {packageInfo.attachments.map((attachment) => (
                        <a
                          key={attachment.id}
                          href={attachment.file_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex max-w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 dark:border-white/10 dark:text-white/60 dark:hover:bg-white/5"
                        >
                          <ImagePlus size={13} />
                          <span className="max-w-[250px] truncate">
                            {attachment.file_name || attachment.file_url}
                          </span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="mt-5 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-7 text-center dark:border-white/10 dark:bg-white/[0.025]">
                <PackageOpen size={28} className="mx-auto text-slate-300" />
                <p className="mt-3 font-semibold text-slate-600 dark:text-white/70">
                  Package not prepared
                </p>
                <p className="mx-auto mt-1 max-w-lg text-sm leading-6 text-slate-400">
                  Add package weight and other fulfilment details. When everything
                  has been checked, confirm the package as Ready for Pickup.
                </p>
              </div>
            )}
          </section>

          <section className="rounded-2xl border bg-white p-5 dark:border-white/10 dark:bg-[#1f2937]">
            <h2 className="font-bold dark:text-white">Fulfilment action</h2>
            <p className="mt-1 text-xs text-slate-400">
              Actions follow the backend order state machine. The Ready to Ship
              action unlocks only after the package has been confirmed above.
            </p>

            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Optional seller notes..."
              className="mt-4 min-h-24 w-full rounded-xl border p-3 text-sm dark:border-white/10 dark:bg-white/5"
            />

            <div className="mt-4 flex flex-wrap gap-2">
              {status === "new" && (
                <Action
                  icon={CheckCircle2}
                  label="Accept order"
                  busy={busy}
                  onClick={() =>
                    run(
                      () => sellerOrdersApi.accept(orderId, notes),
                      "Order accepted",
                    )
                  }
                />
              )}

              {status === "accepted" && (
                <Action
                  icon={Box}
                  label="Start processing"
                  busy={busy}
                  onClick={() =>
                    run(
                      () => sellerOrdersApi.process(orderId, notes),
                      "Processing started",
                    )
                  }
                />
              )}

              {(status === "accepted" || status === "processing") && (
                <div className="flex flex-col items-start gap-1">
                  <Action
                    icon={PackageCheck}
                    label="Mark ready to ship"
                    busy={busy || packageLoading || !packageInfo?.is_ready}
                    onClick={() =>
                      run(
                        () => sellerOrdersApi.ready(orderId, notes),
                        "Ready to ship",
                      )
                    }
                  />
                  {!packageLoading && !packageInfo?.is_ready && (
                    <span className="text-[11px] text-amber-600">
                      Confirm package readiness first.
                    </span>
                  )}
                </div>
              )}

              {status === "ready_to_ship" && (
                <Action
                  icon={Truck}
                  label="Dispatch"
                  busy={busy}
                  onClick={dispatch}
                />
              )}

              {![
                "shipped",
                "delivered",
                "cancelled",
                "cancellation_requested",
              ].includes(status) && (
                <button
                  disabled={busy}
                  onClick={cancel}
                  className="inline-flex items-center gap-2 rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-600"
                >
                  <XCircle size={16} />
                  Request cancellation
                </button>
              )}
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border bg-white dark:border-white/10 dark:bg-[#1f2937]">
            <div className="flex flex-col gap-3 border-b px-5 py-4 dark:border-white/10 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="flex items-center gap-2 font-bold dark:text-white">
                  <MessageSquareText size={18} />
                  Order Conversation
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                  This conversation is permanently linked to this seller order.
                </p>
              </div>

              <button
                type="button"
                onClick={() => void loadMessages()}
                disabled={messagesLoading}
                className="inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold text-slate-600 disabled:opacity-50 dark:border-white/10 dark:text-white/60"
              >
                <RefreshCw
                  size={13}
                  className={messagesLoading ? "animate-spin" : ""}
                />
                Refresh
              </button>
            </div>

            <div className="max-h-[430px] overflow-y-auto bg-slate-50/60 p-4 dark:bg-white/[0.025]">
              {messagesLoading ? (
                <div className="py-10 text-center text-sm text-slate-500">
                  <RefreshCw size={18} className="mx-auto animate-spin" />
                  <p className="mt-2">Loading order messages...</p>
                </div>
              ) : orderedMessages.length ? (
                <div className="space-y-3">
                  {orderedMessages.map((message) => (
                    <MessageBubble key={message.id} message={message} />
                  ))}
                </div>
              ) : (
                <div className="py-10 text-center">
                  <MessageSquareText
                    size={28}
                    className="mx-auto text-slate-300"
                  />
                  <p className="mt-3 font-semibold text-slate-600 dark:text-white/70">
                    No messages yet
                  </p>
                  <p className="mt-1 text-sm text-slate-400">
                    Start the conversation when you need clarification about the
                    order or packaging.
                  </p>
                </div>
              )}
            </div>

            <div className="border-t p-4 dark:border-white/10">
              <textarea
                value={messageText}
                onChange={(event) => setMessageText(event.target.value)}
                placeholder="Write a message about this order..."
                className="min-h-24 w-full rounded-xl border border-slate-200 bg-white p-3 text-sm outline-none focus:border-orange-300 focus:ring-4 focus:ring-orange-50 dark:border-white/10 dark:bg-white/5 dark:text-white"
              />

              <div className="mt-3 rounded-xl border border-slate-200 p-3 dark:border-white/10">
                <div className="flex items-center gap-2">
                  <ImagePlus size={16} className="text-slate-400" />
                  <p className="text-xs font-semibold text-slate-600 dark:text-white/60">
                    Attachment URL
                  </p>
                </div>

                <div className="mt-2 flex gap-2">
                  <input
                    value={attachmentDraft}
                    onChange={(event) => setAttachmentDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        addAttachmentUrl();
                      }
                    }}
                    placeholder="https://.../packaging-photo.jpg"
                    className="h-10 flex-1 rounded-lg border border-slate-200 px-3 text-sm outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
                  />
                  <button
                    type="button"
                    onClick={addAttachmentUrl}
                    className="rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-600 dark:border-white/10 dark:text-white/60"
                  >
                    Add
                  </button>
                </div>

                {attachmentUrls.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {attachmentUrls.map((url) => (
                      <button
                        key={url}
                        type="button"
                        title="Remove attachment"
                        onClick={() =>
                          setAttachmentUrls((current) =>
                            current.filter((item) => item !== url),
                          )
                        }
                        className="max-w-full truncate rounded-full bg-slate-100 px-3 py-1 text-[11px] text-slate-600 dark:bg-white/10 dark:text-white/60"
                      >
                        {url}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  disabled={sendingMessage || !messageText.trim()}
                  onClick={() => void sendMessage()}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {sendingMessage ? (
                    <RefreshCw size={15} className="animate-spin" />
                  ) : (
                    <Send size={15} />
                  )}
                  {sendingMessage ? "Sending..." : "Send Message"}
                </button>
              </div>
            </div>
          </section>
        </div>

        <div className="space-y-5">
          <section className="rounded-2xl border bg-white p-5 dark:border-white/10 dark:bg-[#1f2937]">
            <h2 className="font-bold dark:text-white">Customer</h2>
            <p className="mt-3 font-semibold">{order.customer_name}</p>
            <p className="text-sm text-slate-500">
              {order.customer_phone || "No phone"}
            </p>
          </section>

          <section className="rounded-2xl border bg-white p-5 dark:border-white/10 dark:bg-[#1f2937]">
            <h2 className="flex items-center gap-2 font-bold dark:text-white">
              <MapPin size={17} />
              Delivery
            </h2>
            <p className="mt-3 text-sm">
              {order.shipping_method_name || "Shipping method pending"}
            </p>
            <p className="text-sm text-slate-500">
              {order.shipping_carrier || "Carrier pending"}
            </p>
            <Address value={order.shipping_address} />
          </section>

          {order.cancellation_reason && (
            <section className="rounded-2xl border border-red-200 bg-red-50 p-5">
              <b className="text-red-700">Cancellation reason</b>
              <p className="mt-2 text-sm text-red-700">
                {order.cancellation_reason}
              </p>
            </section>
          )}
        </div>
      </div>

      {packageEditorOpen && (
        <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm">
          <div className="flex max-h-[94vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-[#1f2937]">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-white/10">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f7941d]">
                  Seller Phase 6
                </p>
                <h2 className="mt-0.5 text-xl font-bold dark:text-white">
                  Prepare Package
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                  Order #{order.order_id.slice(0, 8)}
                </p>
              </div>

              <button
                type="button"
                disabled={packageSaving}
                onClick={() => setPackageEditorOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 dark:border-white/10"
              >
                <XCircle size={16} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 sm:p-6">
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-800">
                Package information is used for logistics handoff. Confirm
                <strong> Ready for Pickup</strong> only after the items have been
                checked and physically packaged.
              </div>

              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <PackageField
                  label="Weight (kg)"
                  required
                  hint="Required before confirming readiness."
                >
                  <input
                    type="number"
                    min={0}
                    step="0.001"
                    value={packageForm.weight_kg}
                    onChange={(event) =>
                      setPackageForm((current) => ({
                        ...current,
                        weight_kg: event.target.value,
                      }))
                    }
                    className={packageInputClass}
                    placeholder="e.g. 1.250"
                  />
                </PackageField>

                <PackageField label="Package count" required>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={packageForm.package_count}
                    onChange={(event) =>
                      setPackageForm((current) => ({
                        ...current,
                        package_count: event.target.value,
                      }))
                    }
                    className={packageInputClass}
                  />
                </PackageField>

                <PackageField label="Length (cm)">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={packageForm.length_cm}
                    onChange={(event) =>
                      setPackageForm((current) => ({
                        ...current,
                        length_cm: event.target.value,
                      }))
                    }
                    className={packageInputClass}
                    placeholder="Optional"
                  />
                </PackageField>

                <PackageField label="Width (cm)">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={packageForm.width_cm}
                    onChange={(event) =>
                      setPackageForm((current) => ({
                        ...current,
                        width_cm: event.target.value,
                      }))
                    }
                    className={packageInputClass}
                    placeholder="Optional"
                  />
                </PackageField>

                <PackageField label="Height (cm)">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={packageForm.height_cm}
                    onChange={(event) =>
                      setPackageForm((current) => ({
                        ...current,
                        height_cm: event.target.value,
                      }))
                    }
                    className={packageInputClass}
                    placeholder="Optional"
                  />
                </PackageField>
              </div>

              <div className="mt-4">
                <PackageField label="Packaging notes">
                  <textarea
                    value={packageForm.notes}
                    onChange={(event) =>
                      setPackageForm((current) => ({
                        ...current,
                        notes: event.target.value,
                      }))
                    }
                    className={`${packageInputClass} min-h-24 py-3`}
                    placeholder="Packaging condition, handling instructions, item checks..."
                  />
                </PackageField>
              </div>

              <div className="mt-4 rounded-xl border border-slate-200 p-4 dark:border-white/10">
                <div className="flex items-start gap-3">
                  <ImagePlus size={18} className="mt-0.5 text-slate-400" />
                  <div>
                    <p className="text-sm font-semibold dark:text-white">
                      Packaging evidence
                    </p>
                    <p className="mt-0.5 text-xs leading-5 text-slate-400">
                      The current backend accepts stored attachment URLs. A shared
                      order-media upload endpoint will be connected later for direct
                      image upload.
                    </p>
                  </div>
                </div>

                <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                  <input
                    type="url"
                    value={packageAttachmentDraft}
                    onChange={(event) =>
                      setPackageAttachmentDraft(event.target.value)
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        addPackageAttachment();
                      }
                    }}
                    className={`${packageInputClass} flex-1`}
                    placeholder="https://.../packaged-order.jpg"
                  />
                  <button
                    type="button"
                    onClick={addPackageAttachment}
                    className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-semibold text-slate-600 dark:border-white/10 dark:text-white/60"
                  >
                    Add Evidence
                  </button>
                </div>

                {packageForm.attachment_urls.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {packageForm.attachment_urls.map((url) => (
                      <div
                        key={url}
                        className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 dark:bg-white/5"
                      >
                        <span className="min-w-0 flex-1 truncate text-xs text-slate-600 dark:text-white/60">
                          {url}
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            setPackageForm((current) => ({
                              ...current,
                              attachment_urls: current.attachment_urls.filter(
                                (item) => item !== url,
                              ),
                            }))
                          }
                          className="text-red-500"
                          title="Remove packaging evidence"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <label
                className={`mt-5 flex cursor-pointer items-start gap-3 rounded-xl border p-4 ${
                  packageForm.is_ready
                    ? "border-emerald-200 bg-emerald-50"
                    : "border-slate-200 bg-slate-50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={packageForm.is_ready}
                  onChange={(event) =>
                    setPackageForm((current) => ({
                      ...current,
                      is_ready: event.target.checked,
                    }))
                  }
                  className="mt-1 h-4 w-4 accent-emerald-600"
                />
                <span>
                  <span
                    className={`block text-sm font-bold ${
                      packageForm.is_ready
                        ? "text-emerald-800"
                        : "text-slate-700"
                    }`}
                  >
                    Confirm package is Ready for Pickup
                  </span>
                  <span
                    className={`mt-1 block text-xs leading-5 ${
                      packageForm.is_ready
                        ? "text-emerald-700"
                        : "text-slate-500"
                    }`}
                  >
                    I have checked the ordered items, completed packaging and
                    confirm these details are ready for logistics handoff.
                  </span>
                </span>
              </label>
            </div>

            <div className="flex flex-col-reverse gap-2 border-t border-slate-200 px-5 py-4 sm:flex-row sm:justify-end dark:border-white/10">
              <button
                type="button"
                disabled={packageSaving}
                onClick={() => setPackageEditorOpen(false)}
                className="rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600 disabled:opacity-50 dark:border-white/10 dark:text-white/60"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={packageSaving}
                onClick={() => void savePackage()}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {packageSaving && (
                  <RefreshCw size={14} className="animate-spin" />
                )}
                {packageSaving
                  ? "Saving..."
                  : packageForm.is_ready
                    ? "Save & Confirm Ready"
                    : "Save Package Draft"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: SellerOrderMessage }) {
  const sellerMessage =
    (message.sender_role_label || "").toLowerCase() === "seller";

  return (
    <div className={`flex ${sellerMessage ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[82%] rounded-2xl px-4 py-3 ${
          sellerMessage
            ? "bg-[#fff3e7] text-[#6f4317] dark:bg-orange-400/10 dark:text-orange-100"
            : "border border-slate-200 bg-white text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-white/75"
        }`}
      >
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wide">
            {message.sender_role_label || "Order participant"}
          </span>
          {message.is_internal && (
            <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[9px] font-bold uppercase text-slate-600">
              Internal
            </span>
          )}
        </div>

        <p className="whitespace-pre-wrap text-sm leading-6">
          {message.message}
        </p>

        {message.attachments?.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {message.attachments.map((attachment) => (
              <a
                key={attachment.id}
                href={attachment.file_url}
                target="_blank"
                rel="noreferrer"
                className="block max-w-full truncate rounded-lg border border-current/10 bg-white/60 px-2.5 py-2 text-xs underline dark:bg-black/10"
              >
                {attachment.file_name || attachment.file_url}
              </a>
            ))}
          </div>
        )}

        <p className="mt-2 text-[10px] opacity-60">
          {new Date(message.created_at).toLocaleString()}
        </p>
      </div>
    </div>
  );
}

function PackageMetric({
  icon: Icon,
  label,
  value,
}: {
  icon: any;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex items-center gap-2 text-slate-400">
        <Icon size={14} />
        <p className="text-[10px] font-bold uppercase tracking-wide">{label}</p>
      </div>
      <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-white/75">
        {value}
      </p>
    </div>
  );
}

function PackageField({
  label,
  required = false,
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
      <span className="mb-1.5 block text-xs font-semibold text-slate-600 dark:text-white/65">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-slate-400">{hint}</span>}
    </label>
  );
}

const packageInputClass =
  "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-orange-300 focus:ring-4 focus:ring-orange-50 dark:border-white/10 dark:bg-white/5 dark:text-white";

function Action({
  icon: Icon,
  label,
  busy,
  onClick,
}: {
  icon: any;
  label: string;
  busy: boolean;
  onClick: () => void;
}) {
  return (
    <button
      disabled={busy}
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-xl bg-[#f7941d] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
    >
      <Icon size={16} />
      {label}
    </button>
  );
}

function Address({
  value,
}: {
  value?: Record<string, unknown> | null;
}) {
  if (!value) {
    return (
      <p className="mt-3 text-xs text-slate-400">
        Shipping address unavailable.
      </p>
    );
  }

  const parts = [
    value.recipient_name,
    value.street,
    value.ward,
    value.district,
    value.city,
    value.region,
    value.country,
  ]
    .filter(Boolean)
    .map(String);

  return (
    <p className="mt-3 text-xs leading-5 text-slate-500">
      {parts.join(", ")}
    </p>
  );
}
