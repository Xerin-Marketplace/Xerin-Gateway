import React from "react";

const Categories = ({ categories }) => {
  return (
    <div className="shadow-1 bg-white dark:bg-darkTheme-card rounded-xl mt-7.5">
      <div className="px-4 sm:px-6 py-4.5 border-b border-gray-3 dark:border-darkTheme-border-color">
        <h2 className="font-medium text-lg text-dark dark:text-white">Popular Category</h2>
      </div>

      <div className="p-4 sm:p-6">
        <div className="flex flex-col gap-3">
          <button className="group flex items-center justify-between ease-out duration-200 text-dark dark:text-darkTheme-body-color hover:text-blue">
            Desktop
            <span className="inline-flex rounded-[30px] bg-gray-2 dark:bg-darkTheme-secondary-bg text-custom-xs px-1.5 ease-out duration-200 group-hover:text-white group-hover:bg-blue">
              12
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default Categories;
