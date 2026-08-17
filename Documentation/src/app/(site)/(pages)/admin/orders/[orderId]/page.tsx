import { Metadata } from "next";
import { notFound } from "next/navigation";
import OrdersLayout from "@/components/Admin/Orders/Layout";
import OrderDetails from "@/components/Admin/Orders/OrderDetails";

type PageProps = {
  params: Promise<{ orderId: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { orderId } = await params;
  return {
    title: `Order ${orderId} | Admin`,
    description: "Order details",
  };
}

export default async function OrderDetailsPage({ params }: PageProps) {
  const { orderId } = await params;
  if (!orderId) return notFound();

  return (
    <OrdersLayout>
      <OrderDetails orderId={orderId} />
    </OrdersLayout>
  );
}
