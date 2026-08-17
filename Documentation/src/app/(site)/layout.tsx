"use client";
import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import "../css/euclid-circular-a-font.css";
import "../css/style.css";
import Header from "../../components/Header";
import Footer from "../../components/Footer";

import { ModalProvider } from "../context/QuickViewModalContext";
import { CartModalProvider } from "../context/CartSidebarModalContext";
import AuthProvider from "@/app/providers/AuthProvider";
import QueryProvider from "@/app/providers/QueryProvider";
import QuickViewModal from "@/components/Common/QuickViewModal";
import CartSidebarModal from "@/components/Common/CartSidebarModal";
import { PreviewSliderProvider } from "../context/PreviewSliderContext";
import PreviewSliderModal from "@/components/Common/PreviewSlider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import NotificationProvider from "@/app/providers/NotificationProvider";
import ChatBot from "@/components/Common/ChatBot";
// import ScrollToTop from "@/components/Common/ScrollToTop";
import PreLoader from "@/components/Common/PreLoader";
import BuyerAccountFooter from "@/components/BuyerAccount/BuyerAccountFooter";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [loading, setLoading] = useState<boolean>(true);
  const pathname = usePathname();

  const hideStorefrontChrome =
    pathname === "/signin" ||
    pathname === "/signup" ||
    pathname === "/seller/register" ||
    pathname === "/forgot-password" ||
    pathname === "/reset-password" ||
    pathname === "/verify-otp" ||
    pathname.startsWith("/seller/") ||
    pathname === "/admin/login" ||
    pathname === "/admin" ||
    pathname.startsWith("/admin/");
  const isBuyerAccount = pathname === "/account" || pathname.startsWith("/account/") || pathname === "/my-account";

  useEffect(() => {
    setTimeout(() => setLoading(false), 1000);
  }, []);

  return (
    <ThemeProvider>
      <NotificationProvider>
        <QueryProvider>
          <AuthProvider>
            <CartModalProvider>
              <ModalProvider>
                <PreviewSliderProvider>
                  {loading ? (
                    <PreLoader />
                  ) : (
                    <>
                      {!hideStorefrontChrome ? <Header /> : null}
                      {children}
                      {!hideStorefrontChrome && !isBuyerAccount ? <Footer /> : null}
                      {!hideStorefrontChrome && isBuyerAccount ? <BuyerAccountFooter /> : null}
                      {!hideStorefrontChrome ? <QuickViewModal /> : null}
                      {!hideStorefrontChrome ? <CartSidebarModal /> : null}
                      {!hideStorefrontChrome ? <PreviewSliderModal /> : null}
                    </>
                  )}
                </PreviewSliderProvider>
              </ModalProvider>
            </CartModalProvider>
          </AuthProvider>
        </QueryProvider>
      </NotificationProvider>
      {/* <ScrollToTop /> */}
      <ChatBot />
    </ThemeProvider>
  );
}
