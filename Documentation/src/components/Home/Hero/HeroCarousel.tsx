"use client";

import { Swiper, SwiperSlide } from "swiper/react";
import { Autoplay, Pagination } from "swiper/modules";

import "swiper/css/pagination";
import "swiper/css";

import Image from "next/image";
import { ROUTES } from "@/constants/links";

const HeroCarousel = () => {
  return (
    <Swiper
      spaceBetween={30}
      centeredSlides
      autoplay={{
        delay: 3500,
        disableOnInteraction: false,
      }}
      pagination={{ clickable: true }}
      modules={[Autoplay, Pagination]}
      className="hero-carousel h-full"
    >
      <SwiperSlide className="h-auto">
        <div className="grid h-full min-h-[430px] items-center sm:grid-cols-[minmax(0,1.35fr)_minmax(220px,0.65fr)] lg:min-h-[470px] xl:min-h-[500px]">
          <div className="order-2 px-6 pb-12 pt-5 text-center sm:order-1 sm:px-8 sm:py-10 sm:text-left lg:px-10 xl:px-12">
            <div className="mb-5 flex items-center justify-center gap-4 sm:justify-start xl:mb-7">
              <span className="block text-4xl font-semibold leading-none text-blue sm:text-5xl xl:text-6xl">
                Xerin
              </span>
              <span className="block text-sm font-medium leading-5 text-dark sm:text-base xl:text-lg xl:leading-6">
                Market
                <br />
                Africa
              </span>
            </div>

            <h1 className="mb-3 max-w-[650px] text-2xl font-semibold leading-[1.15] text-dark sm:text-3xl lg:text-[34px] xl:text-[38px]">
              Africa&apos;s Premier E-Commerce Marketplace
            </h1>

            <p className="max-w-[650px] text-sm leading-6 text-dark-4 dark:text-darkTheme-secondary-muted sm:text-base xl:text-[17px]">
              Connecting buyers, sellers, and Xerin Logistics across Africa through trusted digital commerce.
            </p>

            <a
              href={ROUTES.shop}
              className="mt-6 inline-flex rounded-md bg-dark px-7 py-3 text-sm font-medium text-white transition hover:bg-blue sm:mt-8 xl:px-9"
            >
              Shop Now
            </a>
          </div>

          <div className="order-1 flex items-center justify-center px-5 pt-7 sm:order-2 sm:h-full sm:px-3 sm:pt-0 lg:px-5">
            <Image
              src="/images/hero/headphon.png"
              alt="Xerin Market shopping experience"
              width={351}
              height={358}
              className="h-[170px] w-auto object-contain sm:h-[250px] lg:h-[300px] xl:h-[340px]"
              sizes="(max-width: 640px) 170px, (max-width: 1024px) 250px, 340px"
              priority
            />
          </div>
        </div>
      </SwiperSlide>

      <SwiperSlide className="h-auto">
        <div className="grid h-full min-h-[430px] items-center sm:grid-cols-[minmax(0,1.35fr)_minmax(220px,0.65fr)] lg:min-h-[470px] xl:min-h-[500px]">
          <div className="order-2 px-6 pb-12 pt-5 text-center sm:order-1 sm:px-8 sm:py-10 sm:text-left lg:px-10 xl:px-12">
            <div className="mb-5 flex items-center justify-center gap-4 sm:justify-start xl:mb-7">
              <span className="block text-4xl font-semibold leading-none text-blue sm:text-5xl xl:text-6xl">
                Sell
              </span>
              <span className="block text-sm font-medium leading-5 text-dark sm:text-base xl:text-lg xl:leading-6">
                Across
                <br />
                Africa
              </span>
            </div>

            <h1 className="mb-3 max-w-[650px] text-2xl font-semibold leading-[1.15] text-dark sm:text-3xl lg:text-[34px] xl:text-[38px]">
              Grow Your Business With Xerin Market
            </h1>

            <p className="max-w-[650px] text-sm leading-6 text-dark-4 dark:text-darkTheme-secondary-muted sm:text-base xl:text-[17px]">
              List products, manage orders, and reach customers across African markets with a modern seller experience.
            </p>

            <a
              href={ROUTES.sellerRegister}
              className="mt-6 inline-flex rounded-md bg-dark px-7 py-3 text-sm font-medium text-white transition hover:bg-blue sm:mt-8 xl:px-9"
            >
              Start Selling
            </a>
          </div>

          <div className="order-1 flex items-center justify-center px-5 pt-7 sm:order-2 sm:h-full sm:px-3 sm:pt-0 lg:px-5">
            <Image
              src="/images/hero/Tshirtremove.png"
              alt="Sell on Xerin Market"
              width={351}
              height={358}
              className="h-[170px] w-auto object-contain sm:h-[250px] lg:h-[300px] xl:h-[340px]"
              sizes="(max-width: 640px) 170px, (max-width: 1024px) 250px, 340px"
            />
          </div>
        </div>
      </SwiperSlide>
    </Swiper>
  );
};

export default HeroCarousel;
