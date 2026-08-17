"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type SubMenuItem = {
  id: string;
  title: string;
  path: string;
  newTab?: boolean;
};

type MenuItem = {
  id: number;
  title: string;
  path?: string;
  submenu?: SubMenuItem[];
};

type DropdownProps = {
  menuItem: MenuItem;
  stickyMenu: boolean;
};

const Dropdown = ({ menuItem, stickyMenu }: DropdownProps) => {
  const pathname = usePathname();

  const [isOpen, setIsOpen] = useState(false);

  return (
    <li
      className="group relative"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      {/* Parent Menu */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`flex items-center gap-1.5 text-custom-sm font-medium text-dark dark:text-darkTheme-body-color hover:text-blue transition-colors ${
          stickyMenu ? "xl:py-4" : "xl:py-6"
        }`}
      >
        {menuItem.title}

        <svg
          className={`w-4 h-4 transition-transform duration-200 ${
            isOpen ? "rotate-180" : ""
          }`}
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            fillRule="evenodd"
            clipRule="evenodd"
            d="M2.95363 5.67461C3.13334 5.46495 3.44899 5.44067 3.65866 5.62038L7.99993 9.34147L12.3412 5.62038C12.5509 5.44067 12.8665 5.46495 13.0462 5.67461C13.2259 5.88428 13.2017 6.19993 12.992 6.37964L8.32532 10.3796C8.13808 10.5401 7.86178 10.5401 7.67453 10.3796L3.00787 6.37964C2.7982 6.19993 2.77392 5.88428 2.95363 5.67461Z"
            fill="currentColor"
          />
        </svg>
      </button>

      {/* Dropdown */}
      <div
        className={`absolute left-0 top-full z-50 min-w-[240px] rounded-lg border border-gray-200 dark:border-darkTheme-border-color bg-white dark:bg-darkTheme-card shadow-lg transition-all duration-200 ${
          isOpen
            ? "visible opacity-100 translate-y-0"
            : "invisible opacity-0 translate-y-3"
        }`}
      >
        <ul className="py-2">
          {menuItem.submenu?.map((item) => {
            const active = pathname === item.path;

            return (
              <li key={item.id}>
                <Link
                  href={item.path}
                  target={item.newTab ? "_blank" : "_self"}
                  className={`block px-4 py-2.5 text-sm transition-colors ${
                    active
                      ? "bg-gray-100 dark:bg-darkTheme-secondary-bg text-blue font-medium"
                      : "text-dark dark:text-darkTheme-body-color hover:bg-gray-100 dark:hover:bg-darkTheme-secondary-bg hover:text-blue"
                  }`}
                  onClick={() => setIsOpen(false)}
                >
                  {item.title}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </li>
  );
};

export default Dropdown;