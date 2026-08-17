import { redirect } from "next/navigation";

const AdminLoginPage = () => {
  redirect("/signin?redirect=/admin/dashboard");
};

export default AdminLoginPage;
