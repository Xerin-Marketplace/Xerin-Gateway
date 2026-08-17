"use client";
import React from "react";
import ProductItem from "@/components/Common/ProductItem";
import Image from "next/image";
import Link from "next/link";

import { Swiper, SwiperSlide } from "swiper/react";
import { useCallback, useRef } from "react";
import "swiper/css/navigation";
import "swiper/css";
import { useProducts } from "@/lib/products";

const RecentlyViewdItems = () => {
  const { products, isLoading, error } = useProducts({ limit: 8 });
  const sliderRef = useRef(null);

  const handlePrev = useCallback(() => {
    if (!sliderRef.current) return;
    sliderRef.current.swiper.slidePrev();
  }, []);

  const handleNext = useCallback(() => {
    if (!sliderRef.current) return;
    sliderRef.current.swiper.slideNext();
  }, []);

  return (
    <section className="overflow-hidden pt-10 sm:pt-17.5">
      <div className="max-w-[1170px] w-full mx-auto px-4 sm:px-8 xl:px-0 pb-10 sm:pb-15 border-b border-gray-3 dark:border-darkTheme-border-color">
        <div className="swiper categories-carousel common-carousel">
          {/* <!-- section title --> */}
          <div className="mb-5 sm:mb-10 flex items-center justify-between">
            <div>
              <span className="flex items-center gap-2 sm:gap-2.5 font-medium text-dark dark:text-darkTheme-body-color mb-1 sm:mb-1.5 text-sm sm:text-base">
                <Image
                  src="/images/icons/icon-05.svg"
                  width={15}
                  height={15}
                  alt="icon"
                />
                Categories
              </span>
              <h2 className="font-semibold text-base sm:text-xl xl:text-heading-5 text-dark dark:text-white">
                Browse by Category
              </h2>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              <button onClick={handlePrev} className="swiper-button-prev">
                <svg
                  className="fill-current"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    fillRule="evenodd"
                    clipRule="evenodd"
                    d="M15.4881 4.43057C15.8026 4.70014 15.839 5.17361 15.5694 5.48811L9.98781 12L15.5694 18.5119C15.839 18.8264 15.8026 19.2999 15.4881 19.5695C15.1736 19.839 14.7001 19.8026 14.4306 19.4881L8.43056 12.4881C8.18981 12.2072 8.18981 11.7928 8.43056 11.5119L14.4306 4.51192C14.7001 4.19743 15.1736 4.161 15.4881 4.43057Z"
                    fill=""
                  />
                </svg>
              </button>

              <button onClick={handleNext} className="swiper-button-next">
                <svg
                  className="fill-current"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    fillRule="evenodd"
                    clipRule="evenodd"
                    d="M8.51192 4.43057C8.82641 4.161 9.29989 4.19743 9.56946 4.51192L15.5695 11.5119C15.8102 11.7928 15.8102 12.2072 15.5695 12.4881L9.56946 19.4881C9.29989 19.8026 8.82641 19.839 8.51192 19.5695C8.19743 19.2999 8.161 18.8264 8.43057 18.5119L14.0122 12L8.43057 5.48811C8.161 5.17361 8.19743 4.70014 8.51192 4.43057Z"
                    fill=""
                  />
                </svg>
              </button>
            </div>
          </div>

          <Swiper
            ref={sliderRef}
            slidesPerView={4}
            spaceBetween={20}
            className="justify-between"
            breakpoints={{
              0: {
                slidesPerView: 2,
                spaceBetween: 12,
              },
              640: {
                slidesPerView: 3,
                spaceBetween: 16,
              },
              1024: {
                slidesPerView: 4,
                spaceBetween: 20,
              },
            }}
          >
            {products.map((item) => (
              <SwiperSlide key={item.id}>
                <ProductItem item={item} />
              </SwiperSlide>
            ))}
          </Swiper>
          {isLoading && <p className="py-8 text-center text-sm text-dark-4">Loading related products...</p>}
          {error && <p className="py-8 text-center text-sm text-red-600">Related products could not be loaded.</p>}
          {!isLoading && !error && products.length === 0 && <p className="py-8 text-center text-sm text-dark-4">No related products are available.</p>}
        </div>
      </div>
    </section>
  );
};

export default RecentlyViewdItems;
