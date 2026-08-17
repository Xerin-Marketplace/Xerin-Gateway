"use client";

import { fetchBackendDocumentBlob } from "@/lib/documents/backend-document";
import { ExternalLink, FileText, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

type Props = {
  open: boolean;
  title: string;
  documentUrl: string;
  onClose: () => void;
};

export default function BackendDocumentPreview({
  open,
  title,
  documentUrl,
  onClose,
}: Props) {
  const [blobUrl, setBlobUrl] = useState("");
  const [contentType, setContentType] = useState("application/pdf");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !documentUrl) return;

    let active = true;
    let createdBlobUrl = "";

    setLoading(true);
    setError("");
    setBlobUrl("");

    void fetchBackendDocumentBlob(documentUrl)
      .then((result) => {
        if (!active) {
          URL.revokeObjectURL(result.blobUrl);
          return;
        }

        createdBlobUrl = result.blobUrl;
        setBlobUrl(result.blobUrl);
        setContentType(result.contentType);
      })
      .catch(() => {
        if (active) {
          setError(
            "Unable to load this submitted document from the backend. Please try again.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      if (createdBlobUrl) URL.revokeObjectURL(createdBlobUrl);
    };
  }, [documentUrl, open]);

  if (!open) return null;

  const isPdf =
    contentType.includes("pdf") ||
    documentUrl.toLowerCase().includes(".pdf");

  return (
    <div
      className="fixed inset-0 z-[100001] flex items-center bg-black/35 p-3 backdrop-blur-[2px] lg:right-[42rem] lg:justify-center lg:bg-black/20 lg:p-5"
      onMouseDown={onClose}
    >
      <div
        className="flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:bg-[#1f2937]"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#e7ebf0] px-5 py-4 dark:border-white/10">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f7941d]">
              Submitted Document
            </p>
            <h3 className="truncate text-base font-semibold text-[#111827] dark:text-white">
              {title}
            </h3>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#e7ebf0] text-[#64748b] hover:bg-slate-50 dark:border-white/10 dark:hover:bg-white/5"
            aria-label="Close document preview"
          >
            <X size={18} />
          </button>
        </div>

        <div className="min-h-[420px] flex-1 bg-slate-100 p-3 dark:bg-black/20 sm:p-4">
          {loading ? (
            <div className="flex h-[68vh] flex-col items-center justify-center text-[#64748b]">
              <Loader2 className="animate-spin text-[#f7941d]" size={28} />
              <p className="mt-3 text-sm">
                Loading submitted document from backend...
              </p>
            </div>
          ) : error ? (
            <div className="flex h-[68vh] flex-col items-center justify-center rounded-xl bg-white p-8 text-center dark:bg-white/5">
              <FileText size={36} className="text-[#94a3b8]" />
              <p className="mt-3 font-semibold text-[#111827] dark:text-white">
                Document preview unavailable
              </p>
              <p className="mt-1 max-w-md text-sm leading-6 text-[#64748b]">
                {error}
              </p>
            </div>
          ) : blobUrl && isPdf ? (
            <iframe
              src={blobUrl}
              title={title}
              className="h-[70vh] w-full rounded-lg bg-white"
            />
          ) : blobUrl ? (
            <div className="flex h-[70vh] items-center justify-center">
              <img
                src={blobUrl}
                alt={title}
                className="max-h-full max-w-full rounded-lg object-contain"
              />
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-between border-t border-[#e7ebf0] px-5 py-3 dark:border-white/10">
          <p className="text-xs text-[#94a3b8]">
            Loaded from the backend using your authenticated session.
          </p>

          {blobUrl && (
            <a
              href={blobUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#f7941d]"
            >
              <ExternalLink size={14} />
              Open preview
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
