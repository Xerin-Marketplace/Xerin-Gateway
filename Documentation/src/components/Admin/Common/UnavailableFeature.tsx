import { CircleSlash2 } from "lucide-react";

export default function UnavailableFeature({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center shadow-sm">
      <CircleSlash2 className="mx-auto text-amber-600" size={30} />
      <h3 className="mt-3 text-lg font-semibold text-gray-900">{title}</h3>
      <p className="mx-auto mt-2 max-w-2xl text-sm text-amber-800">{description}</p>
    </section>
  );
}
