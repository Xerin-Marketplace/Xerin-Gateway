"use client";

import OrderList from "./OrderList";
import OrderTracking from "./OrderTracking";

const config: Record<string, { title: string; status?: string; subtitle: string }> = {
  all: {
    title: "All System Orders",
    subtitle:
      "A complete operational view of customer orders generated across the Xerin marketplace.",
  },
  pending: {
    title: "Pending Orders",
    status: "pending",
    subtitle:
      "Orders waiting for payment confirmation or the next fulfilment action.",
  },
  processing: {
    title: "Processing Orders",
    status: "processing",
    subtitle:
      "Orders currently being prepared by sellers or fulfilment teams.",
  },
  completed: {
    title: "Completed Orders",
    status: "delivered",
    subtitle:
      "Orders that have reached the customer and completed fulfilment.",
  },
  cancelled: {
    title: "Cancelled Orders",
    status: "cancelled",
    subtitle:
      "Orders cancelled during checkout or fulfilment for operational review.",
  },
};

export default function AdminOrdersDashboard({
  initialTab = "all",
}: {
  initialTab?: string;
}) {
  if (initialTab === "tracking") {
    return <OrderTracking />;
  }

  const view = config[initialTab] || config.all;

  return (
    <OrderList
      view={initialTab}
      status={view.status}
      title={view.title}
      subtitle={view.subtitle}
    />
  );
}
