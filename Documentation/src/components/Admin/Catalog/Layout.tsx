"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const CATALOG_TABS = [
  { href: "/admin/catalog", label: "Overview", exact: true },
  { href: "/admin/catalog/products", label: "Products" },
  { href: "/admin/catalog/categories", label: "Categories" },
  { href: "/admin/catalog/brands", label: "Brands" },
  { href: "/admin/catalog/reviews", label: "Reviews" },
];

const CatalogLayout = ({ children }: { children: React.ReactNode }) => {
  const pathname = usePathname();

  const isActive = (href: string, exact?: boolean) => {
    if (exact) return pathname === href;
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <div className="min-h-screen bg-[#f3f4f6]">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-[#111827]">Catalog Management</h1>
          <p className="text-sm text-gray-500">Manage products, categories, brands, and reviews</p>
        </div>

        <nav className="mb-6 flex flex-wrap gap-2 border-b border-gray-200 pb-1">
          {CATALOG_TABS.map((tab) => (
            <Link
              key={tab.href}
              href={tab.href}
              className={`rounded-t-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                isActive(tab.href, tab.exact)
                  ? "border-b-2 border-[#4b5563] text-[#4b5563]"
                  : "text-gray-600 hover:text-[#4b5563]"
              }`}
            >
              {tab.label}
            </Link>
          ))}
        </nav>

        {children}
      </div>
    </div>
  );
};

export default CatalogLayout;
