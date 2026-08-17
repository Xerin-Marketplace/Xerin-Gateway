import Link from "next/link";
import React from "react";

const Breadcrumb = ({ title, pages }: { title?: string; pages?: string[] }) => {
  return (
    <div className="overflow-hidden shadow-breadcrumb pt-[14px] sm:pt-[15px] lg:pt-[95px] xl:pt-[15px] dark:bg-darkTheme-bg">
      <div className="border-t border-gray-3 dark:border-darkTheme-border-color">
        <div className="max-w-[1170px] w-full mx-auto px-4 sm:px-8 xl:px-0 py-4 sm:py-5 xl:py-10">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-3">
            {title && (
              <h1 className="font-semibold text-dark dark:text-white text-lg sm:text-2xl xl:text-custom-2">
                {title}
              </h1>
            )}

            {pages && pages.length > 0 && (
              <ul className="flex items-center gap-2">
                <li className="text-custom-sm hover:text-blue">
                  <Link href="/">Home /</Link>
                </li>

                {pages.map((page, key) => (
                  <li className="text-custom-sm last:text-blue capitalize" key={key}>
                    {page}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Breadcrumb;
