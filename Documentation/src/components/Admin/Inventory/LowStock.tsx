import UnavailableFeature from "@/components/Admin/Common/UnavailableFeature";
export default function AdminLowStock() { return <UnavailableFeature title="Cross-seller low-stock data is not available yet" description="The available low-stock endpoint is scoped to a seller. Admin-wide low-stock records are not inferred or replaced with zeros." />; }
