import { Metadata } from "next";
import ForgotPassword from "@/components/Auth/ForgotPassword";

export const metadata: Metadata = {
  title: "Forgot Password | Xerin Market",
  description: "Request password reset instructions for your Xerin Market account.",
};

const ForgotPasswordPage = () => {
  return (
    <main>
      <ForgotPassword />
    </main>
  );
};

export default ForgotPasswordPage;
