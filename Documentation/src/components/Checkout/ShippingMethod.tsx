import { useMemo } from "react";
import {
  BadgeCheck,
  Clock3,
  PackageCheck,
  Truck,
} from "lucide-react";
import type {
  DeliveryMode,
  ShippingOption,
} from "@/types/api/commerce";
import { formatCurrency } from "@/lib/formatCurrency";

interface ShippingMethodProps {
  options: ShippingOption[];
  selected: string;
  onChange: (value: string) => void;
  selectedCompanyId: string;
  onCompanyChange: (value: string) => void;
  deliveryMode: DeliveryMode;
  isLoading?: boolean;
}

const ShippingMethod = ({
  options,
  selected,
  onChange,
  selectedCompanyId,
  onCompanyChange,
  deliveryMode,
  isLoading,
}: ShippingMethodProps) => {
  const companies = useMemo(() => {
    const rows = new Map<string, string>();
    options.forEach((option) => {
      const id =
        option.logistics_company_id ||
        `carrier:${option.logistics_company_name}`;
      rows.set(id, option.logistics_company_name);
    });
    return Array.from(rows.entries()).map(([id, name]) => ({ id, name }));
  }, [options]);

  const companyOptions = options.filter((option) => {
    const id =
      option.logistics_company_id ||
      `carrier:${option.logistics_company_name}`;
    return id === selectedCompanyId;
  });

  const selectedOption = options.find((option) => option.id === selected);

  return (
    <section className="mt-7.5 rounded-2xl border border-[#e7ebf0] bg-white shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
      <div className="border-b border-gray-3 px-5 py-5 dark:border-white/10 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange/10 text-orange">
            <Truck size={17} />
          </span>
          <div>
            <h3 className="font-bold text-dark dark:text-white">
              Logistics & Delivery Service
            </h3>
            <p className="mt-0.5 text-xs text-dark-4">
              {deliveryMode === "local"
                ? "Available Tanzania logistics providers"
                : "Available international logistics providers"}
            </p>
          </div>
        </div>
      </div>

      <div className="p-5 sm:p-6">
        {isLoading ? (
          <p className="text-sm text-dark-4">
            Finding logistics companies and rates…
          </p>
        ) : options.length ? (
          <>
            <label className="block text-xs font-semibold text-dark-4">
              Logistics company
              <select
                value={selectedCompanyId}
                onChange={(event) => onCompanyChange(event.target.value)}
                className="mt-1.5 h-11 w-full rounded-xl border border-gray-3 bg-white px-3 text-sm text-dark outline-none focus:border-orange dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </label>

            <p className="mt-5 text-xs font-bold uppercase tracking-wide text-dark-4">
              Delivery service
            </p>

            <div className="mt-3 space-y-3">
              {companyOptions.map((option) => (
                <label
                  key={option.id}
                  className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition ${
                    selected === option.id
                      ? "border-orange bg-orange/5"
                      : "border-gray-3 dark:border-white/10"
                  }`}
                >
                  <input
                    type="radio"
                    name="shipping"
                    checked={selected === option.id}
                    onChange={() => onChange(option.id)}
                    className="mt-1 accent-orange"
                  />

                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-dark dark:text-white">
                        {option.service_name}
                      </span>
                      {option.supports_cod && (
                        <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold uppercase text-emerald-700">
                          COD
                        </span>
                      )}
                      {option.tracking_supported && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-[10px] font-bold uppercase text-blue-700">
                          <PackageCheck size={10} />
                          Tracking
                        </span>
                      )}
                    </span>

                    <span className="mt-1 flex items-center gap-1 text-xs text-dark-4">
                      <Clock3 size={12} />
                      Estimated {option.estimated_min_days}–
                      {option.estimated_max_days} business days
                    </span>

                    <span className="mt-3 block">
                      {option.free_shipping_applied &&
                      Number(option.original_amount) > 0 ? (
                        <>
                          <span className="mr-2 text-sm text-dark-4 line-through">
                            {formatCurrency(
                              Number(option.original_amount),
                              option.currency,
                            )}
                          </span>
                          <span className="font-bold text-emerald-700">
                            FREE
                          </span>
                          <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold uppercase text-emerald-700">
                            <BadgeCheck size={10} />
                            {option.promotion_code || "Promotion"}
                          </span>
                        </>
                      ) : (
                        <span className="font-bold">
                          {formatCurrency(
                            Number(option.amount),
                            option.currency,
                          )}
                        </span>
                      )}
                    </span>
                  </span>
                </label>
              ))}
            </div>

            {selectedOption && (
              <div className="mt-4 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-600 dark:bg-white/5 dark:text-white/60">
                <b>{selectedOption.logistics_company_name}</b> ·{" "}
                {selectedOption.service_name}
                {selectedOption.supports_cod
                  ? " · Cash on Delivery eligible"
                  : " · Online payment required"}
              </div>
            )}
          </>
        ) : (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-800">
            No logistics service currently serves this address for the selected
            delivery type. Try another saved address or contact support.
          </div>
        )}
      </div>
    </section>
  );
};

export default ShippingMethod;
