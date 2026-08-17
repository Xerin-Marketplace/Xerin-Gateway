import type { Metadata } from "next";
import SellerSignup from "@/components/Auth/SellerSignup";

export const metadata: Metadata = {
  title: "Seller Registration | Xerin Market",
  description: "Create a seller account, submit KYC, and start selling on Xerin Market.",
};

const SellerRegisterPage = () => {
  return (
    <main>
      <SellerSignup />
    </main>
  );
};

export default SellerRegisterPage;
