import type { Menu } from "@/types/Menu";

export const menuData: Menu[] = [
  {
    id: 1,
    title: "Home",
    path: "/",
    newTab: false,
  },
  {
    id: 2,
    title: "Shop",
    path: "/shop-with-sidebar",
    newTab: false,
  },
  {
    id: 3,
    title: "Categories",
    path: "#",
    newTab: false,
    submenu: [],
  },
];
