"use client";

import { useEffect, useState } from "react";
import { adminService, type ProductReview } from "@/lib/api/endpoints/admin";
import UnavailableFeature from "@/components/Admin/Common/UnavailableFeature";

export default function AdminReviews() {
  const [rows, setRows] = useState<ProductReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = async () => { setLoading(true); setError(""); try { setRows(await adminService.listProductReviews()); } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load reviews."); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);

  return <div className="space-y-5">
    <UnavailableFeature title="Review moderation actions are not available yet" description="The backend exposes a read-only admin review list but has no publish, hide, reject, restore, reply or delete endpoints. Actions are therefore disabled rather than simulated." />
    <section className="overflow-hidden rounded-2xl border bg-white shadow-sm"><div className="flex justify-between border-b p-5"><h3 className="font-semibold">Customer reviews</h3><button onClick={() => void load()} className="rounded-xl border px-4 py-2 text-sm font-semibold">Refresh</button></div>{loading ? <p className="p-10 text-center text-gray-500">Loading reviews...</p> : error ? <p className="p-10 text-center text-red-600">{error}</p> : rows.length === 0 ? <p className="p-10 text-center text-gray-500">No reviews found.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-gray-50"><tr>{["Customer","Product","Rating","Review","Status","Date"].map(x => <th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody className="divide-y">{rows.map(row => <tr key={row.id}><td className="px-4 py-3">{row.user_id?.slice(0,8) ?? "—"}</td><td className="px-4 py-3">{row.product_id?.slice(0,8) ?? "—"}</td><td className="px-4 py-3">{row.rating}/5</td><td className="max-w-xs truncate px-4 py-3">{row.comment || "—"}</td><td className="px-4 py-3 capitalize">{row.status}</td><td className="px-4 py-3">{new Date(row.created_at).toLocaleDateString()}</td></tr>)}</tbody></table></div>}</section>
  </div>;
}
