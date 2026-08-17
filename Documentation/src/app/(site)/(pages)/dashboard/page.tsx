import { Metadata } from "next";
import DashboardClient from "./DashboardClient";

export const metadata: Metadata = {
  title: "Dashboard | Xerin Market",
  description: "Access your Xerin Market buyer, seller, admin, logistics, and support modules.",
};

const DashboardPage = () => {
  return (
    <main>
      <DashboardClient />
    </main>
  );
};

export default DashboardPage;
