"use client";

type Props = {
  status: string;
};

export default function StatusBadge({ status }: Props) {
  return (
    <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
      {status}
    </span>
  );
}
