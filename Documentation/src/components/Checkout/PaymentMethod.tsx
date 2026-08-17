import type { PaymentOption } from "@/types/api/commerce";
import {
  Banknote,
  CreditCard,
  ShieldCheck,
  Smartphone,
} from "lucide-react";

interface PaymentMethodProps {
  options: PaymentOption[];
  selected: string;
  onChange: (value: string) => void;
  isLoading?: boolean;
  provider: string;
  phoneNumber: string;
  onProviderChange: (value: string) => void;
  onPhoneNumberChange: (value: string) => void;
}

const iconFor = (method: string) => {
  if (method === "mobile_money") return Smartphone;
  if (method === "cash_on_delivery") return Banknote;
  return CreditCard;
};

const PaymentMethod = ({
  options,
  selected,
  onChange,
  isLoading,
  provider,
  phoneNumber,
  onProviderChange,
  onPhoneNumberChange,
}: PaymentMethodProps) => {
  const selectedOption = options.find((item) => item.id === selected);

  return (
    <section className="mt-7.5 rounded-2xl border border-[#e7ebf0] bg-white shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
      <div className="border-b border-gray-3 px-5 py-5 dark:border-white/10 sm:px-6">
        <h3 className="font-bold text-dark dark:text-white">
          Payment Method
        </h3>
        <p className="mt-1 text-xs leading-5 text-dark-4">
          Online payments are processed by AzamPay. Cash on Delivery only appears
          when the selected local logistics service is eligible.
        </p>
      </div>

      <div className="p-5 sm:p-6">
        {isLoading ? (
          <p className="text-dark-4">Loading payment options…</p>
        ) : options.length ? (
          <div className="space-y-3">
            {options.map((method) => {
              const Icon = iconFor(method.id);
              return (
                <label
                  key={method.id}
                  className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition ${
                    selected === method.id
                      ? "border-orange bg-orange/5"
                      : "border-gray-3 dark:border-white/10"
                  }`}
                >
                  <input
                    type="radio"
                    name="payment"
                    checked={selected === method.id}
                    onChange={() => onChange(method.id)}
                    className="mt-1 accent-orange"
                  />
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                    <Icon size={17} />
                  </span>
                  <span>
                    <span className="font-semibold text-dark dark:text-white">
                      {method.label}
                    </span>
                    <span className="mt-1 block text-xs leading-5 text-dark-4">
                      {method.id === "cash_on_delivery"
                        ? "Pay when the logistics company delivers your local order."
                        : method.id === "mobile_money"
                          ? "Secure mobile-money checkout through AzamPay."
                          : "Secure card checkout through AzamPay."}
                    </span>
                  </span>
                </label>
              );
            })}

            {selectedOption?.requires_phone && (
              <div className="mt-4 grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-2 dark:bg-white/5">
                <label className="text-sm font-medium text-dark dark:text-white">
                  Mobile network
                  <select
                    value={provider}
                    onChange={(event) =>
                      onProviderChange(event.target.value)
                    }
                    className="mt-2 w-full rounded-xl border border-gray-3 bg-white p-3 dark:border-white/10 dark:bg-white/5"
                  >
                    <option value="">Select network</option>
                    {selectedOption.providers.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="text-sm font-medium text-dark dark:text-white">
                  Payment phone
                  <input
                    type="tel"
                    value={phoneNumber}
                    onChange={(event) =>
                      onPhoneNumberChange(event.target.value)
                    }
                    placeholder="+255 7XX XXX XXX"
                    className="mt-2 w-full rounded-xl border border-gray-3 bg-white p-3 dark:border-white/10 dark:bg-white/5"
                  />
                </label>
              </div>
            )}

            {selected === "cash_on_delivery" && (
              <div className="flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs leading-5 text-emerald-800">
                <ShieldCheck size={15} className="mt-0.5 shrink-0" />
                No digital escrow is created until money is actually collected.
                Xerin still records the COD payment and fulfilment state.
              </div>
            )}
          </div>
        ) : (
          <p className="text-red">No payment method is currently enabled.</p>
        )}
      </div>
    </section>
  );
};

export default PaymentMethod;
