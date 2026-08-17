import UnavailableFeature from "@/components/Admin/Common/UnavailableFeature";
export default function AdminWarehouseDetails({ warehouseId: _warehouseId }: { warehouseId?: string }) { return <UnavailableFeature title="Warehouse details are not available yet" description="Warehouse details, capacity, staff and movements require backend warehouse APIs." />; }
