import axiosInstance from "@/lib/api/client";
import { API_BASE_URL } from "@/lib/api/endpoints";

export const resolveBackendDocumentUrl = (value?: string | null) => {
  if (!value) return "";

  if (/^https?:\/\//i.test(value) || value.startsWith("blob:")) {
    return value;
  }

  if (API_BASE_URL.startsWith("/")) {
    if (value.startsWith("/uploads/")) {
      return value.replace(/^\/uploads\//, "/backend-uploads/");
    }

    if (value.startsWith("uploads/")) {
      return `/backend-uploads/${value.replace(/^uploads\//, "")}`;
    }

    return value;
  }

  try {
    const api = new URL(API_BASE_URL);

    // API endpoint paths such as /sellers/... and /admin/... should remain
    // relative so axiosInstance keeps the /api/v1 base path.
    if (value.startsWith("/sellers/") || value.startsWith("/admin/")) {
      return value;
    }

    // Legacy/static upload paths live at the API host root.
    if (value.startsWith("/uploads/")) {
      return `${api.origin}${value}`;
    }

    if (value.startsWith("uploads/")) {
      return `${api.origin}/${value}`;
    }

    return value;
  } catch {
    return value;
  }
};

export const fetchBackendDocumentBlob = async (value: string) => {
  const url = resolveBackendDocumentUrl(value);

  const response = await axiosInstance.get<Blob>(url, {
    responseType: "blob",
    headers: {
      Accept: "application/pdf",
    },
  });

  const contentTypeHeader = response.headers["content-type"];
  const contentType =
    (typeof contentTypeHeader === "string" ? contentTypeHeader : undefined) ||
    response.data.type ||
    "application/pdf";

  const blob =
    response.data.type
      ? response.data
      : new Blob([response.data], { type: contentType });

  return {
    blobUrl: URL.createObjectURL(blob),
    contentType,
  };
};
