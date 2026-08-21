"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Breadcrumb from "../Common/Breadcrumb";
import Billing from "./Billing";
import Shipping from "./Shipping";
import ShippingMethod from "./ShippingMethod";
import MapPinConfirmation from "./MapPinConfirmation";
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
    refetchAddresses,
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

  const eligibleLogistics = useQuery({
    queryKey: [
      "checkout",
      "eligible-logistics",
      selectedAddressId,
      deliveryMode,
    ],
    queryFn: ({ signal }) =>
      checkoutApi.eligibleLogistics(
        {
          address_id: selectedAddressId,
          delivery_mode: deliveryMode,
        },
        signal,
      ),
    enabled: Boolean(selectedAddressId && selectedAddress?.delivery_ready && isAuthenticated && cartItems.length),
    retry: false,
  });

  const deliveryPricing = useQuery({
    queryKey: ["checkout", "multi-seller-pricing", selectedAddressId, selectedCompanyId, deliveryMode, cart?.total, cart?.coupon_code, cart?.promotion_code],
    queryFn: ({ signal }) => checkoutApi.multiSellerPricing({
      address_id: selectedAddressId,
      logistics_company_id: selectedCompanyId,
      delivery_mode: deliveryMode,
    }, signal),
    enabled: Boolean(selectedAddress?.delivery_ready && selectedCompanyId && cartItems.length),
    retry: false,
  });

  const selectedShipping = deliveryPricing.data?.options.find(
    (option) => option.rate_id === form.shippingMethod,
  );

  const frozenQuote = useQuery({
    queryKey: ["checkout", "frozen-delivery-quote", selectedAddressId, selectedCompanyId, form.shippingMethod, deliveryMode, cart?.total, cart?.coupon_code, cart?.promotion_code],
    queryFn: () => checkoutApi.freezeDeliveryQuote({
      address_id: selectedAddressId,
      logistics_company_id: selectedCompanyId,
      rate_id: form.shippingMethod,
      delivery_mode: deliveryMode,
    }),
    enabled: Boolean(selectedAddress?.delivery_ready && selectedCompanyId && form.shippingMethod),
    retry: false,
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

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
    const companies = eligibleLogistics.data?.results ?? [];
    if (!companies.length) {
      setSelectedCompanyId("");
      setForm((current) => ({ ...current, shippingMethod: "" }));
      return;
    }
    if (!companies.some((company) => company.logistics_company_id === selectedCompanyId)) {
      setSelectedCompanyId(companies[0].logistics_company_id);
      setForm((current) => ({ ...current, shippingMethod: "" }));
    }
  }, [eligibleLogistics.data, selectedCompanyId]);

  useEffect(() => {
    const options = deliveryPricing.data?.options ?? [];
    if (!options.length) {
      setForm((current) => current.shippingMethod ? { ...current, shippingMethod: "" } : current);
      return;
    }
    if (!options.some((option) => option.rate_id === form.shippingMethod)) {
      setForm((current) => ({ ...current, shippingMethod: options[0].rate_id }));
    }
  }, [deliveryPricing.data, form.shippingMethod]);

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
    ? Number(selectedShipping.delivery_amount)
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
    setForm((current) => ({
      ...current,
      shippingMethod: "",
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

    if (!selectedAddress?.delivery_ready) {
      toast.error("Confirm the exact delivery map pin before continuing");
      return;
    }

    if (!frozenQuote.data) {
      toast.error("Wait for the protected delivery quote to finish");
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
        shipping_rate_id: selectedShipping.rate_id,
        delivery_quote_id: frozenQuote.data.id,
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

      <section className="overflow-hidden bg-gray-2 pb-8 pt-5 dark:bg-darkTheme-bg sm:py-12 lg:py-16">
        <div className="mx-auto w-full max-w-[1220px] px-3 sm:px-6 lg:px-8">
          <form onSubmit={handleSubmit}>
            <div className="grid gap-5 sm:gap-7 lg:grid-cols-[minmax(0,1fr)_420px] xl:grid-cols-[minmax(0,1fr)_440px]">
              <div className="min-w-0 space-y-4 sm:space-y-6">
                <DeliveryModeSelector
                  value={deliveryMode}
                  onChange={changeDeliveryMode}
                  config={deliveryConfig.data}
                />

                <section className="rounded-2xl border border-[#e7ebf0] bg-white p-4 shadow-sm dark:border-white/10 dark:bg-darkTheme-card sm:p-6">
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
                        className="mt-4 h-12 w-full rounded-xl border border-gray-3 bg-white px-3 text-base outline-none focus:border-orange dark:border-white/10 dark:bg-white/5 dark:text-white sm:mt-5 sm:px-4 sm:text-sm"
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
                        <><div className="mt-3 break-words rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-600 dark:bg-white/5 dark:text-white/60">
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
                        </div><MapPinConfirmation address={selectedAddress} onConfirmed={() => { void refetchAddresses(); }} /></>
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

                <div className="rounded-2xl border border-[#e7ebf0] bg-white p-4 shadow-sm dark:border-white/10 dark:bg-darkTheme-card sm:p-6">
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
                    className="w-full rounded-xl border border-gray-3 bg-gray-1 p-3 text-base outline-none focus:border-orange dark:border-white/10 dark:bg-white/5 dark:text-white sm:p-4 sm:text-sm"
                  />
                </div>
              </div>

              <aside className="min-w-0">
                <div className="rounded-2xl border border-[#e7ebf0] bg-white shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
                  <div className="border-b border-gray-3 px-4 py-4 dark:border-white/10 sm:px-5 sm:py-5">
                    <h3 className="text-lg font-bold text-dark dark:text-white sm:text-xl">
                      Your Order
                    </h3>
                  </div>

                  <div className="px-4 pb-4 pt-1 sm:px-5 sm:pb-6 sm:pt-2">
                    {cartItems.map((item) => (
                      <div
                        key={item.cartItemId}
                        className="flex items-start justify-between gap-3 border-b border-gray-3 py-3 dark:border-white/10 sm:items-center sm:gap-4 sm:py-4"
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
                      label="Delivery"
                      value={
                        shippingAmount === null
                          ? "Select delivery"
                          : formatCurrency(shippingAmount, selectedShipping?.currency)
                      }
                    />

                    <div className="mt-2 border-t border-gray-3 pt-2 dark:border-white/10">
                      <SummaryRow
                        label="Grand Total"
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
                      {frozenQuote.data && <p className="pb-2 text-right text-[10px] leading-4 text-emerald-700">Protected quote ready · expires {new Date(frozenQuote.data.expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>}
                    </div>
                  </div>
                </div>

                {(eligibleLogistics.error || deliveryPricing.error || frozenQuote.error) && <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-700">{errorText(eligibleLogistics.error || deliveryPricing.error || frozenQuote.error)}</div>}

                <ShippingMethod
                  companies={eligibleLogistics.data?.results ?? []}
                  excludedCompanies={eligibleLogistics.data?.excluded_companies ?? []}
                  options={deliveryPricing.data?.options ?? []}
                  selected={form.shippingMethod}
                  onChange={(value) =>
                    updateField("shippingMethod", value)
                  }
                  selectedCompanyId={selectedCompanyId}
                  onCompanyChange={changeCompany}
                  deliveryMode={deliveryMode}
                  isLoadingCompanies={eligibleLogistics.isLoading || eligibleLogistics.isFetching}
                  isLoadingPricing={deliveryPricing.isLoading || deliveryPricing.isFetching}
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

                <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-[11px] leading-5 text-blue-800 sm:mt-7.5 sm:p-4 sm:text-xs">
                  <b>Final checkout protection:</b> when you place the order, the
                  backend rechecks the current product prices, stock, seller
                  promotion, platform coupon, delivery address, logistics scope,
                  shipment weight and selected shipping rate. The amount stored on
                  the Order becomes the payment source of truth.
                </div>

                <div className="xerin-checkout-mobile-cta mt-4 sm:mt-7.5">
                <button
                  type="submit"
                  disabled={
                    createOrder.isPending ||
                    isCreatingAddress ||
                    eligibleLogistics.isFetching ||
                    deliveryPricing.isFetching ||
                    frozenQuote.isFetching ||
                    !selectedAddressId ||
                    !selectedAddress?.delivery_ready ||
                    !form.paymentMethod ||
                    !form.shippingMethod ||
                    !frozenQuote.data
                  }
                  className="flex h-12 w-full items-center justify-center rounded-xl bg-orange px-5 text-base font-semibold text-white shadow-sm transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50 sm:text-sm"
                >
                  {createOrder.isPending || isCreatingAddress
                    ? "Processing..."
                    : "Place Order & Continue to Payment"}
                </button>
                </div>

                <p className="mt-3 text-center text-[11px] leading-5 text-dark-4">
                  Products + delivery = Grand Total. The backend freezes and
                  revalidates this quote before creating the order.
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
    <div className="flex items-center justify-between gap-3 py-2.5 sm:gap-4 sm:py-3">
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
            ? "text-base font-bold text-dark dark:text-white sm:text-lg"
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

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Delivery quotation could not be completed. Check the address pin and try again.";
}

export default Checkout;
