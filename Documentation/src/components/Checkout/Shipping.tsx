import React, { useState } from "react";
import type { CheckoutForm } from "./index";

interface ShippingProps {
  form: CheckoutForm;
  updateField: (field: keyof CheckoutForm, value: string | boolean) => void;
}

const Shipping = ({ form, updateField }: ShippingProps) => {
  const [dropdown, setDropdown] = useState(false);

  return (
    <div className="bg-white dark:bg-darkTheme-card shadow-1 rounded-[10px] mt-7.5">
      <div
        onClick={() => setDropdown(!dropdown)}
        className="cursor-pointer flex items-center gap-2.5 font-medium text-lg text-dark dark:text-white py-5 px-5.5"
      >
        Ship to a different address?
        <svg
          className={`fill-current ease-out duration-200 ${dropdown && "rotate-180"}`}
          width="22"
          height="22"
          viewBox="0 0 22 22"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            fillRule="evenodd"
            clipRule="evenodd"
            d="M4.06103 7.80259C4.30813 7.51431 4.74215 7.48092 5.03044 7.72802L10.9997 12.8445L16.9689 7.72802C17.2572 7.48092 17.6912 7.51431 17.9383 7.80259C18.1854 8.09088 18.1521 8.5249 17.8638 8.772L11.4471 14.272C11.1896 14.4927 10.8097 14.4927 10.5523 14.272L4.1356 8.772C3.84731 8.5249 3.81393 8.09088 4.06103 7.80259Z"
            fill=""
          />
        </svg>
      </div>

      <div className={`p-4 sm:p-8.5 ${dropdown ? "block" : "hidden"}`}>
        <div className="mb-5">
          <label htmlFor="shippingCountry" className="block mb-2.5 dark:text-darkTheme-body-color">
            Country <span className="text-red">*</span>
          </label>
          <input
            type="text"
            id="shippingCountry"
            value={form.shippingCountry}
            onChange={(e) => updateField("shippingCountry", e.target.value)}
            className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
          />
        </div>

        <div className="mb-5">
          <label htmlFor="shippingStreet" className="block mb-2.5 dark:text-darkTheme-body-color">
            Delivery Address <span className="text-red">*</span>
          </label>
          <input
            type="text"
            id="shippingStreet"
            value={form.shippingStreet}
            onChange={(e) => updateField("shippingStreet", e.target.value)}
            placeholder="House number and street name"
            className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
          />
          <div className="mt-5">
            <input
              type="text"
              id="shippingStreet2"
              value={form.shippingStreet2}
              onChange={(e) => updateField("shippingStreet2", e.target.value)}
              placeholder="Apartment, suite, unit, etc. (optional)"
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>
        </div>

        <div className="flex flex-col lg:flex-row gap-5 sm:gap-8 mb-5">
          <div className="w-full">
            <label htmlFor="shippingCity" className="block mb-2.5 dark:text-darkTheme-body-color">
              City <span className="text-red">*</span>
            </label>
            <input
              type="text"
              id="shippingCity"
              value={form.shippingCity}
              onChange={(e) => updateField("shippingCity", e.target.value)}
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>

          <div className="w-full">
            <label htmlFor="shippingRegion" className="block mb-2.5 dark:text-darkTheme-body-color">
              Region/State <span className="text-red">*</span>
            </label>
            <input
              type="text"
              id="shippingRegion"
              value={form.shippingRegion}
              onChange={(e) => updateField("shippingRegion", e.target.value)}
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>
        </div>

        <div className="mb-5">
          <label htmlFor="shippingPostalCode" className="block mb-2.5 dark:text-darkTheme-body-color">
            Postal Code
          </label>
          <input
            type="text"
            id="shippingPostalCode"
            value={form.shippingPostalCode}
            onChange={(e) => updateField("shippingPostalCode", e.target.value)}
            className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
          />
        </div>

        <div className="flex flex-col lg:flex-row gap-5 sm:gap-8">
          <div className="w-full">
            <label htmlFor="shippingPhone" className="block mb-2.5 dark:text-darkTheme-body-color">
              Phone Number <span className="text-red">*</span>
            </label>
            <input
              type="text"
              id="shippingPhone"
              value={form.shippingPhone}
              onChange={(e) => updateField("shippingPhone", e.target.value)}
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>

          <div className="w-full">
            <label htmlFor="shippingEmail" className="block mb-2.5 dark:text-darkTheme-body-color">
              Email Address <span className="text-red">*</span>
            </label>
            <input
              type="email"
              id="shippingEmail"
              value={form.shippingEmail}
              onChange={(e) => updateField("shippingEmail", e.target.value)}
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Shipping;
