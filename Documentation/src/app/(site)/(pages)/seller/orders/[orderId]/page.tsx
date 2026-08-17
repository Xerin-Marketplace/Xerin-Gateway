import type { Metadata } from "next";
import SellerOrderDetail from "@/components/Seller/Orders/OrderDetail";

type PageProps = {
  params: Promise<{ orderId: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { orderId } = await params;
  return {
    title: `Order ${orderId} | Seller Center`,
    description: "Seller order details",
  };
}

export default async function SellerOrderDetailPage({ params }: PageProps) {
  const { orderId } = await params;
  return (
    <main>
      <SellerOrderDetail orderId={orderId} />
    </main>
  );
}
