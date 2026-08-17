import React from "react";
import HeroCarousel from "./HeroCarousel";
import Image from "next/image";
import { ROUTES } from "@/constants/links";
import Link from "next/link";

const Hero = () => {
  return (
    <section className="overflow-hidden bg-[#E5EAF4] pt-[154px] pb-8 dark:bg-darkTheme-secondary-bg sm:pt-[166px] lg:pt-[145px] lg:pb-10 xl:pt-[154px]">
      <div className="mx-auto w-full max-w-[1440px] px-4 sm:px-6 lg:px-8 xl:px-10 2xl:px-6">
        <div className="grid items-stretch gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)] xl:gap-5">
          {/* Main hero card - left */}
          <div className="min-w-0">
            <div className="relative z-1 h-full min-h-[430px] overflow-hidden rounded-[12px] bg-white shadow-sm dark:bg-darkTheme-card lg:min-h-[470px] xl:min-h-[500px]">
              <Image
                src="/images/hero/hero-bg.png"
                alt="hero bg shapes"
                className="absolute bottom-0 right-0 -z-1 hidden h-full w-auto object-cover sm:block"
                width={534}
                height={520}
                priority
              />
              <HeroCarousel />
            </div>
          </div>

          {/* Side cards - right */}
          <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-1 lg:grid-rows-2 xl:gap-5">
            <div className="relative flex min-h-[210px] items-center overflow-hidden rounded-[12px] bg-white p-5 shadow-sm transition-shadow duration-300 hover:shadow-md dark:bg-darkTheme-card sm:p-6 lg:min-h-0 xl:p-7">
              <div className="flex w-full items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <h2 className="mb-3 text-lg font-semibold leading-tight text-dark dark:text-white xl:text-2xl">
                    Top-rated sellers
                  </h2>
                  <p className="mb-2 max-w-[220px] text-sm font-medium leading-5 text-dark-4 dark:text-darkTheme-secondary-muted">
                    Curated stores with buyer protection
                  </p>
                  <div className="mb-4 flex flex-wrap items-baseline gap-2">
                    <span className="text-xl font-semibold text-blue xl:text-2xl">Secure</span>
                    <span className="text-xl font-medium text-dark-4 dark:text-darkTheme-secondary-muted xl:text-2xl">
                      Checkout
                    </span>
                  </div>
                  <Link
                    href={ROUTES.shop}
                    className="inline-flex rounded-md bg-blue px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-dark"
                  >
                    Shop Now
                  </Link>
                </div>

                <Image
                  src="/images/hero/phoneremove.png"
                  alt="Xerin Market promotion"
                  width={145}
                  height={190}
                  className="hidden h-[145px] w-auto flex-shrink-0 object-contain sm:block lg:h-[150px] xl:h-[175px]"
                />
              </div>
            </div>

            <div className="relative flex min-h-[210px] items-center overflow-hidden rounded-[12px] bg-white p-5 shadow-sm transition-shadow duration-300 hover:shadow-md dark:bg-darkTheme-card sm:p-6 lg:min-h-0 xl:p-7">
              <div className="flex w-full items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <h2 className="mb-3 text-lg font-semibold leading-tight text-dark dark:text-white xl:text-2xl">
                    Xerin Logistics
                  </h2>
                  <p className="mb-2 max-w-[220px] text-sm font-medium leading-5 text-dark-4 dark:text-darkTheme-secondary-muted">
                    Track every order from dispatch to doorstep
                  </p>
                  <div className="mb-4 flex flex-wrap items-baseline gap-2">
                    <span className="text-xl font-semibold text-green xl:text-2xl">Live</span>
                    <span className="text-xl font-medium text-dark-4 dark:text-darkTheme-secondary-muted xl:text-2xl">
                      Updates
                    </span>
                  </div>
                  <Link
                    href="#"
                    className="inline-flex rounded-md bg-dark px-5 py-2.5 text-sm font-medium text-white transition hover:bg-opacity-90 dark:bg-darkTheme-tertiary-bg"
                  >
                    Track Order
                  </Link>
                </div>

                <Image
                  src="/images/hero/headremove.png"
                  alt="Xerin Logistics"
                  width={145}
                  height={190}
                  className="hidden h-[145px] w-auto flex-shrink-0 object-contain sm:block lg:h-[150px] xl:h-[175px]"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
