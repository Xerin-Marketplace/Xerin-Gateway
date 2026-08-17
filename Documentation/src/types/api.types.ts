import type { PaginationMeta } from "./pagination.types";

export type ApiListResponse<T> = {
  results: T[];
  meta?: PaginationMeta;
};
