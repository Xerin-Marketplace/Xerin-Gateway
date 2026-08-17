import UnavailableFeature from "@/components/Admin/Common/UnavailableFeature";

export default function AdminDisputes() {
  return (
    <UnavailableFeature
      title="Dispute management is not available yet"
      description="The backend does not currently expose dispute listing, details or resolution operations. No sample disputes are displayed."
    />
  );
}
