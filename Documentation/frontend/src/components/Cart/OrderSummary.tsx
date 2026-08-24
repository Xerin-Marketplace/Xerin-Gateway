import { useCartView } from "@/hooks/useCartActions";
import React from "react";
import PriceDisplay from "@/components/shared/PriceDisplay";
import Link from "next/link";

const OrderSummary = () => {
  const {
    items: cartItems,
    total: totalPrice,
    isAuthenticated,
  } = useCartView();
  const isGuest = !isAuthenticated;

  return (
    <div className="lg:max-w-[455px] w-full">
      {/* <!-- order list box --> */}
      <div className="bg-white dark:bg-darkTheme-card shadow-1 rounded-[10px]">
        <div className="border-b border-gray-3 dark:border-darkTheme-border-color py-5 px-4 sm:px-8.5">
          <h3 className="font-medium text-xl text-dark dark:text-white">Order Summary</h3>
        </div>

        <div className="pt-2.5 pb-8.5 px-4 sm:px-8.5">
          {/* <!-- title --> */}
          <div className="flex items-center justify-between py-5 border-b border-gray-3 dark:border-darkTheme-border-color">
            <div>
              <h4 className="font-medium text-dark dark:text-darkTheme-body-color">Product</h4>
            </div>
            <div>
              <h4 className="font-medium text-dark dark:text-darkTheme-body-color text-right">Subtotal</h4>
            </div>
          </div>

          {/* <!-- product item --> */}
          {cartItems.map((item, key) => (
            <div key={key} className="flex items-center justify-between py-5 border-b border-gray-3 dark:border-darkTheme-border-color">
              <div>
                <p className="text-dark dark:text-darkTheme-body-color">{item.title}</p>
              </div>
              <div>
                <p className="text-dark dark:text-darkTheme-body-color text-right">
                  <PriceDisplay amount={item.discountedPrice * item.quantity} sourceCurrency="TZS" />
                </p>
              </div>
            </div>
          ))}

          {/* <!-- total --> */}
          <div className="flex items-center justify-between pt-5">
            <div>
              <p className="font-medium text-lg text-dark dark:text-white">Total</p>
            </div>
            <div>
              <p className="font-medium text-lg text-dark dark:text-white text-right">
                <PriceDisplay amount={totalPrice} sourceCurrency="TZS" />
              </p>
            </div>
          </div>

          {/* <!-- checkout button --> */}
          <Link
            href={isGuest ? "/signin?redirect=/checkout" : "/checkout"}
            className="w-full flex justify-center font-medium text-white bg-blue py-3 px-6 rounded-md ease-out duration-200 hover:bg-blue-dark mt-7.5"
          >
            {isGuest ? "Sign in to Checkout" : "Process to Checkout"}
          </Link>
        </div>
      </div>
    </div>
  );
};

export default OrderSummary;
