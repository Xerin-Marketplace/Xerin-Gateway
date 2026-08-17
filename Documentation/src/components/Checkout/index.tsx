"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Breadcrumb from "../Common/Breadcrumb";
import Billing from "./Billing";
import Shipping from "./Shipping";
import ShippingMethod from "./ShippingMethod";
import DeliveryModeSelector from "./DeliveryMode";
import PaymentMethod from "./PaymentMethod";
import Coupon from "./Coupon";
import { useBackendCart, mapBackendCartToUi } from "@/hooks/useCartActions";
import { useCreateOrder } from "@/hooks/useCommerce";
import { useAddresses } from "@/hooks/useAddresses";
import {
  checkoutApi,
  paymentsApi,
} from "@/lib/api/endpoints/commerce";
import type { DeliveryMode } from "@/types/api/commerce";
import { formatCurrency } from "@/lib/formatCurrency";
import toast from "react-hot-toast";
import { useAuthStore } from "@/store/useAuthStore";
import { Globe2, MapPin } from "lucide-react";

export type CheckoutForm = {
  firstName: string;
  lastName: string;
  companyName: string;
  country: string;
  street: string;
  street2: string;
  city: string;
  region: string;
  postalCode: string;
  phone: string;
  email: string;
  notes: string;
  shippingCountry: string;
  shippingStreet: string;
  shippingStreet2: string;
  shippingCity: string;
  shippingRegion: string;
  shippingPostalCode: string;
  shippingPhone: string;
  shippingEmail: string;
  shippingMethod: string;
  paymentMethod: string;
  useDifferentShipping: boolean;
};

const initialForm: CheckoutForm = {
  firstName: "",
  lastName: "",
  companyName: "",
  country: "",
  street: "",
  street2: "",
  city: "",
  region: "",
  postalCode: "",
  phone: "",
  email: "",
  notes: "",
  shippingCountry: "",
  shippingStreet: "",
  shippingStreet2: "",
  shippingCity: "",
  shippingRegion: "",
  shippingPostalCode: "",
  shippingPhone: "",
  shippingEmail: "",
  shippingMethod: "",
  paymentMethod: "",
  useDifferentShipping: false,
};

const isTanzania = (country?: string | null) =>
  ["tanzania", "united republic of tanzania", "tz"].includes(
    (country || "").trim().toLowerCase(),
  );

const Checkout = () => {
  const router = useRouter();
  const [form, setForm] = useState<CheckoutForm>(initialForm);
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>("local");
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [paymentProvider, setPaymentProvider] = useState("");
  const [paymentPhone, setPaymentPhone] = useState("");

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);

  const {
    data: cart,
    isLoading: isLoadingCart,
    error: cartError,
  } = useBackendCart(isAuthenticated);

  const {
    addresses,
    isCreatingAddress,
    isLoadingAddresses,
  } = useAddresses(isAuthenticated);

  const createOrder = useCreateOrder();
  const cartItems = cart ? mapBackendCartToUi(cart) : [];
  const cartProductTotal = Number(cart?.total ?? 0);

  const deliveryConfig = useQuery({
    queryKey: ["checkout", "delivery-config"],
    queryFn: checkoutApi.deliveryConfig,
    enabled: isAuthenticated,
  });

  const matchingAddresses = useMemo(
    () =>
      addresses.filter((address) =>
        deliveryMode === "local"
          ? isTanzania(address.country)
          : !isTanzania(address.country),
      ),
    [addresses, deliveryMode],
  );

  useEffect(() => {
    const currentStillMatches = matchingAddresses.some(
      (address) => String(address.id) === selectedAddressId,
    );
    if (currentStillMatches) return;

    const preferred =
      matchingAddresses.find((address) => address.is_default) ||
      matchingAddresses[0];
    const nextAddressId = preferred ? String(preferred.id) : "";

    // Do nothing when the derived selection is already the current state.
    // This prevents a render loop while addresses are still loading/empty.
    if (nextAddressId === selectedAddressId) return;

    setSelectedAddressId(nextAddressId);
    setSelectedCompanyId("");
    setForm((current) =>
      current.shippingMethod
        ? { ...current, shippingMethod: "" }
        : current,
    );
  }, [matchingAddresses, selectedAddressId]);

  const selectedAddress = matchingAddresses.find(
    (address) => String(address.id) === selectedAddressId,
  );

  const shippingOptions = useQuery({
    queryKey: [
      "checkout",
      "shipping-options",
      selectedAddressId,
      deliveryMode,
      cart?.promotion_code,
    ],
    queryFn: ({ signal }) =>
      checkoutApi.shippingOptions(
        {
          address_id: selectedAddressId,
          delivery_mode: deliveryMode,
        },
        signal,
      ),
    enabled: Boolean(selectedAddressId && isAuthenticated && cartItems.length),
    retry: false,
  });

  const selectedShipping = shippingOptions.data?.find(
    (option) => option.id === form.shippingMethod,
  );

  const paymentOptions = useQuery({
    queryKey: [
      "checkout",
      "payment-options",
      Boolean(selectedShipping?.supports_cod),
    ],
    queryFn: () =>
      checkoutApi.paymentOptions(Boolean(selectedShipping?.supports_cod)),
    enabled: isAuthenticated,
  });

  useEffect(() => {
    const options = shippingOptions.data ?? [];
    if (!options.length) {
      setSelectedCompanyId("");
      setForm((current) => ({ ...current, shippingMethod: "" }));
      return;
    }

    const currentOption = options.find(
      (option) => option.id === form.shippingMethod,
    );
    if (currentOption) {
      setSelectedCompanyId(
        currentOption.logistics_company_id ||
          `carrier:${currentOption.logistics_company_name}`,
      );
      return;
    }

    const first = options[0];
    setSelectedCompanyId(
      first.logistics_company_id ||
        `carrier:${first.logistics_company_name}`,
    );
    setForm((current) => ({
      ...current,
      shippingMethod: first.id,
    }));
  }, [shippingOptions.data, form.shippingMethod]);

  useEffect(() => {
    const options = paymentOptions.data ?? [];
    if (
      options.length &&
      !options.some((option) => option.id === form.paymentMethod)
    ) {
      setForm((current) => ({
        ...current,
        paymentMethod: options[0].id,
      }));
    }
  }, [paymentOptions.data, form.paymentMethod]);

  useEffect(() => {
    const selectedOption = paymentOptions.data?.find(
      (option) => option.id === form.paymentMethod,
    );
    if (!selectedOption) return;

    if (
      selectedOption.requires_phone &&
      !selectedOption.providers.includes(paymentProvider)
    ) {
      setPaymentProvider(selectedOption.providers[0] ?? "");
    } else if (!selectedOption.requires_phone) {
      setPaymentProvider(
        selectedOption.id === "cash_on_delivery"
          ? ""
          : selectedOption.providers[0] ?? "azampay",
      );
    }
  }, [form.paymentMethod, paymentOptions.data, paymentProvider]);

  const shippingAmount = selectedShipping
    ? Number(selectedShipping.amount)
    : null;

  const checkoutTotal =
    shippingAmount === null ? null : cartProductTotal + shippingAmount;

  const updateField = (
    field: keyof CheckoutForm,
    value: string | boolean,
  ) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const changeDeliveryMode = (mode: DeliveryMode) => {
    setDeliveryMode(mode);
    setSelectedAddressId("");
    setSelectedCompanyId("");
    setForm((current) => ({
      ...current,
      shippingMethod: "",
    }));
  };

  const changeCompany = (companyId: string) => {
    setSelectedCompanyId(companyId);
    const option = (shippingOptions.data ?? []).find((row) => {
      const rowCompany =
        row.logistics_company_id ||
        `carrier:${row.logistics_company_name}`;
      return rowCompany === companyId;
    });

    setForm((current) => ({
      ...current,
      shippingMethod: option?.id || "",
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (cartItems.length === 0) {
      toast.error("Your cart is empty");
      return;
    }

    if (!selectedAddressId) {
      toast.error(
        deliveryMode === "local"
          ? "Add or select a Tanzania delivery address"
          : "Add or select an international delivery address",
      );
      return;
    }

    if (!selectedShipping) {
      toast.error("Select a logistics company and delivery service");
      return;
    }

    const required = [
      "firstName",
      "lastName",
      "country",
      "street",
      "city",
      "region",
      "phone",
      "email",
    ] as const;

    for (const key of required) {
      if (!form[key]) {
        toast.error(
          `Please fill in ${key.replace(/([A-Z])/g, " $1").trim()}`,
        );
        return;
      }
    }

    let createdOrderId: string | null = null;

    try {
      const selectedPayment = paymentOptions.data?.find(
        (option) => option.id === form.paymentMethod,
      );

      const phoneNumber = paymentPhone.trim() || form.phone.trim();

      if (
        selectedPayment?.requires_phone &&
        (!paymentProvider || !phoneNumber)
      ) {
        throw new Error(
          "Select a mobile network and enter the AzamPay payment phone number",
        );
      }

      const order = await createOrder.mutateAsync({
        shipping_address_id: selectedAddressId,
        shipping_rate_id: selectedShipping.id,
        delivery_mode: deliveryMode,
        coupon_code: cart?.coupon_code || undefined,
        promotion_code: cart?.promotion_code || undefined,
        notes: form.notes || undefined,
      });

      const paymentRetryKey = `xerin:payment-retry:${order.id}`;
      const paymentRetryContext = {
        method: form.paymentMethod,
        provider:
          form.paymentMethod === "cash_on_delivery"
            ? undefined
            : paymentProvider || "azampay",
        phone_number:
          selectedPayment?.requires_phone
            ? phoneNumber
            : undefined,
      };

      if (typeof window !== "undefined") {
        sessionStorage.setItem(
          paymentRetryKey,
          JSON.stringify(paymentRetryContext),
        );
      }

      createdOrderId = String(order.id);

      const confirmedTotal = Number(order.total || 0);
      if (
        checkoutTotal !== null &&
        Math.abs(confirmedTotal - checkoutTotal) >= 0.01
      ) {
        toast(
          `Checkout was refreshed by the backend. Confirmed order total: ${formatCurrency(
            confirmedTotal,
            order.currency,
          )}`,
        );
      }

      const successUrl = `${window.location.origin}/order-success/${order.id}?payment=success`;
      const failureUrl = `${window.location.origin}/order-success/${order.id}?payment=failed&retryable=1`;

      const isCod = form.paymentMethod === "cash_on_delivery";

      const payment = await paymentsApi.initiate({
        order_id: String(order.id),
        method: form.paymentMethod,
        provider: isCod ? undefined : paymentProvider || "azampay",
        phone_number: selectedPayment?.requires_phone
          ? phoneNumber
          : undefined,
        success_url:
          form.paymentMethod === "card" ? successUrl : undefined,
        failure_url:
          form.paymentMethod === "card" ? failureUrl : undefined,
      });

      if (isCod) {
        if (typeof window !== "undefined") {
          sessionStorage.removeItem(paymentRetryKey);
        }
        toast.success(
          "Order placed with Cash on Delivery. Payment will be collected at delivery.",
        );
        router.push(`/order-success/${order.id}?payment=cod`);
        return;
      }

      const checkoutUrl = payment.provider_response?.checkout_url;
      if (form.paymentMethod === "card" && checkoutUrl) {
        window.location.assign(checkoutUrl);
        return;
      }

      toast.success(
        payment.status === "processing"
          ? "Payment request sent to AzamPay. Complete the payment on your phone."
          : "Order placed successfully",
      );
      router.push(
        `/order-success/${order.id}?payment_id=${payment.id}&payment=${payment.status}`,
      );
    } catch (error: unknown) {
      const candidate = error as {
        response?: {
          status?: number;
          data?: {
            detail?:
              | string
              | {
                  code?: string;
                  message?: string;
                  order_id?: string;
                  payment_id?: string;
                  retryable?: boolean;
                };
          };
        };
        message?: string;
      };

      const detail = candidate.response?.data?.detail;
      const detailMessage =
        typeof detail === "string"
          ? detail
          : detail?.message;

      if (createdOrderId) {
        const retryable =
          typeof detail === "object"
            ? detail?.retryable !== false
            : true;

        toast.error(
          detailMessage ||
            "Your order was created, but payment could not be started.",
        );

        const failedPaymentId =
          typeof detail === "object" ? detail?.payment_id : undefined;
        const paymentIdQuery = failedPaymentId
          ? `&payment_id=${encodeURIComponent(failedPaymentId)}`
          : "";

        router.push(
          `/order-success/${createdOrderId}?payment=failed&retryable=${
            retryable ? "1" : "0"
          }${paymentIdQuery}`,
        );
        return;
      }

      toast.error(
        detailMessage ||
          candidate.message ||
          "Checkout failed",
      );
    }
  };

  if (hasHydrated && !isAuthenticated) {
    router.replace("/signin?redirect=/checkout");
    return null;
  }

  if (isLoadingCart || isLoadingAddresses || deliveryConfig.isLoading) {
    return (
      <section className="py-20 text-center">
        Loading secure checkout…
      </section>
    );
  }

  if (cartError) {
    return (
      <section className="py-20 text-center text-red">
        Checkout could not load your cart. Please retry.
      </section>
    );
  }

  if (cartItems.length === 0) {
    return (
      <>
        <Breadcrumb title="Checkout" pages={["checkout"]} />
        <section className="bg-gray-2 py-20 text-center dark:bg-darkTheme-bg">
          <p className="mb-4 text-dark dark:text-white">
            Your cart is empty.
          </p>
          <a href="/search" className="font-medium text-blue">
            Continue Shopping
          </a>
        </section>
      </>
    );
  }

  return (
    <>
      <Breadcrumb title="Checkout" pages={["checkout"]} />

      <section className="overflow-hidden bg-gray-2 py-12 dark:bg-darkTheme-bg sm:py-16">
        <div className="mx-auto w-full max-w-[1220px] px-4 sm:px-8">
          <form onSubmit={handleSubmit}>
            <div className="grid gap-7 lg:grid-cols-[1fr_440px]">
              <div className="space-y-6">
                <DeliveryModeSelector
                  value={deliveryMode}
                  onChange={changeDeliveryMode}
                  config={deliveryConfig.data}
                />

                <section className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card sm:p-6">
                  <div className="flex items-start gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                      {deliveryMode === "local" ? (
                        <MapPin size={18} />
                      ) : (
                        <Globe2 size={18} />
                      )}
                    </span>
                    <div>
                      <h2 className="font-bold text-dark dark:text-white">
                        Delivery Address
                      </h2>
                      <p className="mt-1 text-xs leading-5 text-dark-4">
                        {deliveryMode === "local"
                          ? "Only Tanzania addresses are shown for local delivery."
                          : "Only non-Tanzania addresses are shown for international delivery."}
                      </p>
                    </div>
                  </div>

                  {matchingAddresses.length ? (
                    <>
                      <select
                        value={selectedAddressId}
                        onChange={(event) =>
                          setSelectedAddressId(event.target.value)
                        }
                        className="mt-5 h-12 w-full rounded-xl border border-gray-3 bg-white px-4 text-sm outline-none focus:border-orange dark:border-white/10 dark:bg-white/5 dark:text-white"
                      >
                        {matchingAddresses.map((address) => (
                          <option
                            key={String(address.id)}
                            value={String(address.id)}
                          >
                            {address.label
                              ? `${address.label} · `
                              : ""}
                            {address.street}, {address.city},{" "}
                            {address.region}, {address.country}
                          </option>
                        ))}
                      </select>

                      {selectedAddress && (
                        <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-600 dark:bg-white/5 dark:text-white/60">
                          {selectedAddress.recipient_name && (
                            <b>{selectedAddress.recipient_name} · </b>
                          )}
                          {selectedAddress.street},{" "}
                          {selectedAddress.city},{" "}
                          {selectedAddress.region},{" "}
                          {selectedAddress.country}
                          {selectedAddress.recipient_phone
                            ? ` · ${selectedAddress.recipient_phone}`
                            : ""}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-800">
                      You do not have a{" "}
                      {deliveryMode === "local"
                        ? "Tanzania"
                        : "non-Tanzania"}{" "}
                      delivery address yet.
                    </div>
                  )}

                  <a
                    href="/account/addresses"
                    className="mt-4 inline-block text-sm font-semibold text-orange"
                  >
                    Manage delivery addresses
                  </a>
                </section>

                <Billing form={form} updateField={updateField} />
                <Shipping form={form} updateField={updateField} />

                <div className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card sm:p-6">
                  <label
                    htmlFor="notes"
                    className="mb-2.5 block font-semibold dark:text-darkTheme-body-color"
                  >
                    Delivery / Order Notes (optional)
                  </label>
                  <textarea
                    id="notes"
                    rows={5}
                    value={form.notes}
                    onChange={(event) =>
                      updateField("notes", event.target.value)
                    }
                    placeholder="Building access, delivery instructions, package notes..."
                    className="w-full rounded-xl border border-gray-3 bg-gray-1 p-4 outline-none focus:border-orange dark:border-white/10 dark:bg-white/5 dark:text-white"
                  />
                </div>
              </div>

              <aside className="min-w-0">
                <div className="rounded-2xl border border-[#e7ebf0] bg-white shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
                  <div className="border-b border-gray-3 px-5 py-5 dark:border-white/10">
                    <h3 className="text-xl font-bold text-dark dark:text-white">
                      Your Order
                    </h3>
                  </div>

                  <div className="px-5 pb-6 pt-2">
                    {cartItems.map((item) => (
                      <div
                        key={item.cartItemId}
                        className="flex items-center justify-between gap-4 border-b border-gray-3 py-4 dark:border-white/10"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {item.title}
                          </p>
                          <p className="text-xs text-dark-4">
                            Qty {item.quantity}
                          </p>
                        </div>
                        <p className="shrink-0 text-sm font-semibold">
                          {formatCurrency(
                            item.discountedPrice * item.quantity,
                            cart?.currency,
                          )}
                        </p>
                      </div>
                    ))}

                    <SummaryRow
                      label="Product subtotal"
                      value={formatCurrency(
                        Number(cart?.subtotal || 0),
                        cart?.currency,
                      )}
                    />

                    {Number(cart?.promotion_discount_amount || 0) > 0 && (
                      <SummaryRow
                        label="Seller promotion"
                        value={`-${formatCurrency(
                          Number(cart?.promotion_discount_amount || 0),
                          cart?.currency,
                        )}`}
                        saving
                      />
                    )}

                    {Number(cart?.coupon_discount_amount || 0) > 0 && (
                      <SummaryRow
                        label="Platform coupon"
                        value={`-${formatCurrency(
                          Number(cart?.coupon_discount_amount || 0),
                          cart?.currency,
                        )}`}
                        saving
                      />
                    )}

                    <SummaryRow
                      label="Shipping"
                      value={
                        shippingAmount === null
                          ? "Select delivery"
                          : selectedShipping?.free_shipping_applied &&
                              Number(selectedShipping.original_amount) > 0
                            ? "FREE"
                            : formatCurrency(
                                shippingAmount,
                                selectedShipping?.currency,
                              )
                      }
                      saving={Boolean(
                        selectedShipping?.free_shipping_applied,
                      )}
                    />

                    {selectedShipping?.free_shipping_applied && (
                      <div className="rounded-lg bg-emerald-50 p-3 text-xs leading-5 text-emerald-700">
                        {selectedShipping.promotion_name ||
                          selectedShipping.promotion_code ||
                          "Seller promotion"}{" "}
                        removed{" "}
                        {formatCurrency(
                          Number(
                            selectedShipping.shipping_discount_amount,
                          ),
                          selectedShipping.currency,
                        )}{" "}
                        from delivery.
                      </div>
                    )}

                    <div className="mt-2 border-t border-gray-3 pt-2 dark:border-white/10">
                      <SummaryRow
                        label="Checkout total"
                        value={
                          checkoutTotal === null
                            ? "Pending delivery quote"
                            : formatCurrency(
                                checkoutTotal,
                                selectedShipping?.currency ||
                                  cart?.currency,
                              )
                        }
                        strong
                      />
                    </div>
                  </div>
                </div>

                <ShippingMethod
                  options={shippingOptions.data ?? []}
                  selected={form.shippingMethod}
                  onChange={(value) =>
                    updateField("shippingMethod", value)
                  }
                  selectedCompanyId={selectedCompanyId}
                  onCompanyChange={changeCompany}
                  deliveryMode={deliveryMode}
                  isLoading={
                    shippingOptions.isLoading ||
                    shippingOptions.isFetching
                  }
                />

                <Coupon />

                <PaymentMethod
                  options={paymentOptions.data ?? []}
                  selected={form.paymentMethod}
                  onChange={(value) =>
                    updateField("paymentMethod", value)
                  }
                  isLoading={paymentOptions.isLoading}
                  provider={paymentProvider}
                  phoneNumber={paymentPhone}
                  onProviderChange={setPaymentProvider}
                  onPhoneNumberChange={setPaymentPhone}
                />

                <div className="mt-7.5 rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-800">
                  <b>Final checkout protection:</b> when you place the order, the
                  backend rechecks the current product prices, stock, seller
                  promotion, platform coupon, delivery address, logistics scope,
                  shipment weight and selected shipping rate. The amount stored on
                  the Order becomes the payment source of truth.
                </div>

                <button
                  type="submit"
                  disabled={
                    createOrder.isPending ||
                    isCreatingAddress ||
                    shippingOptions.isFetching ||
                    !selectedAddressId ||
                    !form.paymentMethod ||
                    !form.shippingMethod
                  }
                  className="mt-7.5 flex w-full justify-center rounded-xl bg-orange px-6 py-3 font-semibold text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {createOrder.isPending || isCreatingAddress
                    ? "Processing..."
                    : "Continue with Selected Delivery"}
                </button>

                <p className="mt-3 text-center text-[11px] leading-5 text-dark-4">
                  The backend revalidates the selected zone, logistics service,
                  shipment weight and delivery rate when the order is created.
                </p>
              </aside>
            </div>
          </form>
        </div>
      </section>
    </>
  );
};

function SummaryRow({
  label,
  value,
  saving = false,
  strong = false,
}: {
  label: string;
  value: string;
  saving?: boolean;
  strong?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <span
        className={
          strong
            ? "font-bold text-dark dark:text-white"
            : "text-sm text-dark-4"
        }
      >
        {label}
      </span>
      <span
        className={`text-right ${
          strong
            ? "text-lg font-bold text-dark dark:text-white"
            : saving
              ? "text-sm font-bold text-emerald-700"
              : "text-sm font-semibold"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export default Checkout;
