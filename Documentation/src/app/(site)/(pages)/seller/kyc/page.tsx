import type { Metadata } from "next";
import SellerKyc from "@/components/Seller/Kyc";

export const metadata: Metadata = {
  title: "Seller KYC | Xerin Market",
  description: "Upload KYC documents and manage payout accounts for your seller account.",
};

const SellerKycPage = () => {
  return (
    <main>
      <SellerKyc />
    </main>
  );
};

export default SellerKycPage;
