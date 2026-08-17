import React from "react";
import type { CheckoutForm } from "./index";

interface BillingProps {
  form: CheckoutForm;
  updateField: (field: keyof CheckoutForm, value: string | boolean) => void;
}

const Billing = ({ form, updateField }: BillingProps) => {
  return (
    <div className="mt-9">
      <h2 className="font-medium text-dark dark:text-white text-xl sm:text-2xl mb-5.5">
        Delivery details
      </h2>

      <div className="bg-white dark:bg-darkTheme-card shadow-1 rounded-[10px] p-4 sm:p-8.5">
        <div className="flex flex-col lg:flex-row gap-5 sm:gap-8 mb-5">
          <div className="w-full">
            <label htmlFor="firstName" className="block mb-2.5 dark:text-darkTheme-body-color">
              First Name <span className="text-red">*</span>
            </label>
            <input
              type="text"
              id="firstName"
              value={form.firstName}
              onChange={(e) => updateField("firstName", e.target.value)}
              placeholder="John"
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>

          <div className="w-full">
            <label htmlFor="lastName" className="block mb-2.5 dark:text-darkTheme-body-color">
              Last Name <span className="text-red">*</span>
            </label>
            <input
              type="text"
              id="lastName"
              value={form.lastName}
              onChange={(e) => updateField("lastName", e.target.value)}
              placeholder="Doe"
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>
        </div>

        <div className="mb-5">
          <label htmlFor="companyName" className="block mb-2.5 dark:text-darkTheme-body-color">
            Business Name (optional)
          </label>
          <input
            type="text"
            id="companyName"
            value={form.companyName}
            onChange={(e) => updateField("companyName", e.target.value)}
            className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
          />
        </div>

        <div className="mb-5">
          <label htmlFor="country" className="block mb-2.5 dark:text-darkTheme-body-color">
            Country <span className="text-red">*</span>
          </label>
          <input
            type="text"
            id="country"
            value={form.country}
            onChange={(e) => updateField("country", e.target.value)}
            placeholder="Country"
            className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
          />
        </div>

        <div className="mb-5">
          <label htmlFor="street" className="block mb-2.5 dark:text-darkTheme-body-color">
            Delivery Address <span className="text-red">*</span>
          </label>
          <input
            type="text"
            id="street"
            value={form.street}
            onChange={(e) => updateField("street", e.target.value)}
            placeholder="House number and street name"
            className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
          />
          <div className="mt-5">
            <input
              type="text"
              id="street2"
              value={form.street2}
              onChange={(e) => updateField("street2", e.target.value)}
              placeholder="Apartment, suite, unit, etc. (optional)"
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>
        </div>

        <div className="flex flex-col lg:flex-row gap-5 sm:gap-8 mb-5">
          <div className="w-full">
            <label htmlFor="city" className="block mb-2.5 dark:text-darkTheme-body-color">
              City <span className="text-red">*</span>
            </label>
            <input
              type="text"
              id="city"
              value={form.city}
              onChange={(e) => updateField("city", e.target.value)}
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>

          <div className="w-full">
            <label htmlFor="region" className="block mb-2.5 dark:text-darkTheme-body-color">
              Region/State <span className="text-red">*</span>
            </label>
            <input
              type="text"
              id="region"
              value={form.region}
              onChange={(e) => updateField("region", e.target.value)}
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>
        </div>

        <div className="mb-5">
          <label htmlFor="postalCode" className="block mb-2.5 dark:text-darkTheme-body-color">
            Postal Code
          </label>
          <input
            type="text"
            id="postalCode"
            value={form.postalCode}
            onChange={(e) => updateField("postalCode", e.target.value)}
            className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
          />
        </div>

        <div className="flex flex-col lg:flex-row gap-5 sm:gap-8 mb-5">
          <div className="w-full">
            <label htmlFor="phone" className="block mb-2.5 dark:text-darkTheme-body-color">
              Phone Number <span className="text-red">*</span>
            </label>
            <input
              type="text"
              id="phone"
              value={form.phone}
              onChange={(e) => updateField("phone", e.target.value)}
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>

          <div className="w-full">
            <label htmlFor="email" className="block mb-2.5 dark:text-darkTheme-body-color">
              Email Address <span className="text-red">*</span>
            </label>
            <input
              type="email"
              id="email"
              value={form.email}
              onChange={(e) => updateField("email", e.target.value)}
              className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Billing;
