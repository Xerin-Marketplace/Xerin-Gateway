export const siteConfig = {
  name: "Xerin Market",
  shortName: "Xerin",
  tagline: "Your Trusted Marketplace",
  description:
    "Xerin Market is a modern online marketplace connecting buyers and sellers across Africa. Shop quality products, manage your store, and grow your business.",
  url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
  locale: "en_US",
  themeColor: "#2563eb",
  keywords: [
    "Xerin Market",
    "online marketplace",
    "Africa marketplace",
    "ecommerce",
    "online shopping",
    "sell online",
    "buy online",
    "XerinMarket",
  ],
  authors: {
    name: "Xerin Market",
    url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
  },
  creator: "Xerin Market",
  publisher: "Xerin Market",
  contact: {
    email: "support@xerinmarket.com",
    phone: "",
  },
  social: {
    facebook: "https://facebook.com/xerinmarket",
    twitter: "https://twitter.com/xerinmarket",
    instagram: "https://instagram.com/xerinmarket",
    linkedin: "https://linkedin.com/company/xerinmarket",
  },
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    docsUrl: process.env.NEXT_PUBLIC_API_DOCS_URL || "http://localhost:8000/docs",
  },
  navigation: {
    primary: [
      { label: "Home", href: "/" },
      { label: "Shop", href: "/shop-with-sidebar" },
      { label: "Sell on Xerin", href: "/seller/register" },
      { label: "Contact", href: "/contact" },
    ],
  },
  footer: {
    copyrightYear: new Date().getFullYear(),
    legalLinks: [
      { label: "Privacy Policy", href: "/privacy-policy" },
      { label: "Terms of Use", href: "/terms" },
      { label: "Cookie Policy", href: "/cookie-policy" },
    ],
  },
} as const;

export type SiteConfig = typeof siteConfig;
