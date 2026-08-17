import { Metadata } from "next";
import ResetPassword from "@/components/Auth/ResetPassword";

export const metadata: Metadata = {
  title: "Reset Password | Xerin Market",
  description: "Reset your Xerin Market account password using OTP or reset token.",
};

const ResetPasswordPage = () => {
  return (
    <main>
      <ResetPassword />
    </main>
  );
};

export default ResetPasswordPage;
