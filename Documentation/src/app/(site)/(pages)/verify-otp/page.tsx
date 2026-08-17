import { Metadata } from "next";
import VerifyOtp from "@/components/Auth/VerifyOtp";

export const metadata: Metadata = {
  title: "Verify OTP | Xerin Market",
  description: "Verify your Xerin Market account using OTP.",
};

const VerifyOtpPage = () => {
  return (
    <main>
      <VerifyOtp />
    </main>
  );
};

export default VerifyOtpPage;
