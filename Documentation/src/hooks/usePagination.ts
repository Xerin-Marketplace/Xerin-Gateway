"use client";

import { useMemo } from "react";

export const usePagination = (page: number, pageSize: number, total: number) => {
  return useMemo(() => {
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    return {
      page,
      pageSize,
      total,
      totalPages,
      hasNext: page < totalPages,
      hasPrev: page > 1,
    };
  }, [page, pageSize, total]);
};
