import axios from "axios";

export type ApiFieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  readonly status: number;
  readonly data: unknown;
  readonly fieldErrors: ApiFieldErrors;
  readonly kind: "api" | "network" | "timeout";

  constructor(
    message: string,
    status: number,
    data: unknown,
    fieldErrors: ApiFieldErrors = {},
    kind: ApiError["kind"] = "api",
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.fieldErrors = fieldErrors;
    this.kind = kind;
  }
}

type ValidationDetail = { loc?: Array<string | number>; msg?: string };

const parseFields = (detail: unknown): ApiFieldErrors => {
  if (!Array.isArray(detail)) return {};
  return detail.reduce<ApiFieldErrors>((result, item: ValidationDetail) => {
    const field = item.loc?.filter((part) => part !== "body").join(".");
    if (!field || !item.msg) return result;
    result[field] = [...(result[field] || []), item.msg];
    return result;
  }, {});
};

export const toApiError = (error: unknown): ApiError => {
  if (error instanceof ApiError) return error;
  if (!axios.isAxiosError(error)) {
    return new ApiError(
      error instanceof Error ? error.message : "Unexpected request error.",
      0,
      null,
      {},
      "network",
    );
  }

  const data = error.response?.data as
    | { detail?: string | ValidationDetail[]; message?: string }
    | undefined;
  const detail = data?.detail;
  const fieldErrors = parseFields(detail);
  const validationMessage = Object.values(fieldErrors).flat().join(", ");
  const timedOut = error.code === "ECONNABORTED" || error.code === "ETIMEDOUT";
  const message =
    (typeof detail === "string" ? detail : undefined) ||
    validationMessage ||
    data?.message ||
    (timedOut
      ? "The request timed out. Please try again."
      : error.response
        ? "The server could not complete the request."
        : "Unable to reach the server. Check your connection.");

  return new ApiError(
    message,
    error.response?.status || 0,
    data,
    fieldErrors,
    timedOut ? "timeout" : error.response ? "api" : "network",
  );
};
