"use client";

import React from "react";
import Image from "next/image";
import Link from "next/link";
import { useProducts } from "@/lib/products";
import { formatCurrency } from "@/lib/formatCurrency";

const LatestProducts = () => {
  const { products, isLoading, error } = useProducts({ limit: 3 });
  return (
    <div className="shadow-1 bg-white dark:bg-darkTheme-card rounded-xl mt-7.5">
      <div className="px-4 sm:px-6 py-4.5 border-b border-gray-3 dark:border-darkTheme-border-color">
        <h2 className="font-medium text-lg text-dark dark:text-white">Latest Products</h2>
      </div>

      <div className="p-4 sm:p-6">
        <div className="flex flex-col gap-6">
          {/* <!-- product item --> */}
          {isLoading && <p className="text-sm text-dark-4">Loading products...</p>}
          {error && <p className="text-sm text-red-600">Products could not be loaded.</p>}
          {!isLoading && !error && products.length === 0 && <p className="text-sm text-dark-4">No products are available.</p>}
          {products.map((product) => (
            <div className="flex items-center gap-6" key={product.id}>
              <div className="flex items-center justify-center rounded-[10px] bg-gray-3 dark:bg-darkTheme-secondary-bg max-w-[90px] w-full h-22.5">
                {product.imgs?.thumbnails?.[0] ? (
                  <Image src={product.imgs.thumbnails[0]} alt={product.title} width={74} height={74} />
                ) : (
                  <span className="px-2 text-center text-xs text-dark-4">No image</span>
                )}
              </div>

              <div>
                <h3 className="font-medium text-dark dark:text-darkTheme-body-color mb-1 ease-out duration-200 hover:text-blue">
                  <Link href={`/products/${product.id}`}> {product.title} </Link>
                </h3>
                <p className="text-custom-sm dark:text-darkTheme-secondary-muted">Price: {formatCurrency(product.discountedPrice)}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default LatestProducts;
