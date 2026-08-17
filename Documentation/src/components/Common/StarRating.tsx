"use client";

import React from "react";

const StarRating = ({
  rating,
  max = 5,
  size = 15,
  reviewCount,
}: {
  rating?: number | null;
  max?: number;
  size?: number;
  reviewCount?: number | null;
}) => {
  const normalized = Math.max(0, Math.min(max, Math.round((rating || 0) * 2) / 2));

  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: max }).map((_, i) => {
        const fill = Math.max(0, Math.min(1, normalized - i));
        return (
          <svg
            key={i}
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="flex-shrink-0"
          >
            <defs>
              <linearGradient id={`star-grad-${i}`}>
                <stop offset="0%" stopColor="#FFA41C" />
                <stop offset={`${fill * 100}%`} stopColor="#FFA41C" />
                <stop offset={`${fill * 100}%`} stopColor="#D1D5DB" />
                <stop offset="100%" stopColor="#D1D5DB" />
              </linearGradient>
            </defs>
            <path
              d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"
              fill={`url(#star-grad-${i})`}
              stroke="#B45309"
              strokeWidth="1"
              strokeLinejoin="round"
            />
          </svg>
        );
      })}
      {typeof reviewCount === "number" && (
        <span className="text-custom-sm text-dark-4 dark:text-darkTheme-secondary-muted ml-1">
          ({reviewCount})
        </span>
      )}
    </div>
  );
};

export default StarRating;
