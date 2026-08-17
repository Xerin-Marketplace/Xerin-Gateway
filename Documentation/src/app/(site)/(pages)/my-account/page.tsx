import { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = {
  title: "My Account | Xerin Market",
  description: "Manage your Xerin Market profile, orders, addresses, and account settings.",
};

const MyAccountPage = () => {
  redirect("/account");
};

export default MyAccountPage;
