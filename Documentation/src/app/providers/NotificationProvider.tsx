"use client";

import { ReactNode } from "react";
import { Toaster } from "react-hot-toast";

export default function NotificationProvider({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
        }}
      />
    </>
  );
}
