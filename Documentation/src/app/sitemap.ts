import type { MetadataRoute } from "next";
import { siteConfig } from "@/lib/site-config";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  const staticRoutes = [
    "",
    "/shop-with-sidebar",
    "/shop-without-sidebar",
    "/cart",
    "/checkout",
    "/signin",
    "/signup",
    "/seller/register",
    "/contact",
  ];

  return staticRoutes.map((path) => ({
    url: `${siteConfig.url}${path}`,
    lastModified,
    changeFrequency: path === "" ? "daily" : "weekly",
    priority: path === "" ? 1.0 : 0.7,
  }));
}
