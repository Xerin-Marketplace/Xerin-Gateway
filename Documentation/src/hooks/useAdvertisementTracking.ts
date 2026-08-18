"use client";

import { RefObject, useEffect, useMemo, useRef } from "react";
import { advertisementsApi } from "@/lib/api/endpoints/advertisements";

const SESSION_STORAGE_KEY = "xerin_ad_session_id";

const getSessionId = () => {
  if (typeof window === "undefined") return "";

  let sessionId = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (!sessionId) {
    sessionId =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random()
            .toString(36)
            .slice(2)}`;

    window.sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }

  return sessionId;
};

const impressionStorageKey = (advertisementId: string) =>
  `xerin_ad_impression:${advertisementId}`;

const newClientEventId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export const useAdvertisementTracking = (
  advertisementId: string,
  elementRef: RefObject<HTMLElement | null>,
) => {
  const impressionTimer = useRef<number | null>(null);
  const impressionSent = useRef(false);

  useEffect(() => {
    const element = elementRef.current;
    if (!element || !advertisementId || typeof window === "undefined") return;

    const stored = window.sessionStorage.getItem(
      impressionStorageKey(advertisementId),
    );
    if (stored === "1") {
      impressionSent.current = true;
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (impressionSent.current) return;

        if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
          if (impressionTimer.current !== null) return;

          // The creative must stay at least 50% visible for 800 ms.
          impressionTimer.current = window.setTimeout(() => {
            impressionTimer.current = null;

            if (impressionSent.current) return;
            impressionSent.current = true;

            window.sessionStorage.setItem(
              impressionStorageKey(advertisementId),
              "1",
            );

            void advertisementsApi
              .trackImpression(advertisementId, {
                session_id: getSessionId(),
                page_path: window.location.pathname,
              })
              .catch(() => {
                // Analytics must never break storefront rendering.
              });
          }, 800);
        } else if (impressionTimer.current !== null) {
          window.clearTimeout(impressionTimer.current);
          impressionTimer.current = null;
        }
      },
      {
        threshold: [0, 0.5, 1],
      },
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
      if (impressionTimer.current !== null) {
        window.clearTimeout(impressionTimer.current);
        impressionTimer.current = null;
      }
    };
  }, [advertisementId, elementRef]);

  const trackClick = useMemo(
    () => () => {
      if (typeof window === "undefined" || !advertisementId) return;

      void advertisementsApi
        .trackClick(advertisementId, {
          session_id: getSessionId(),
          client_event_id: newClientEventId(),
          page_path: window.location.pathname,
        })
        .catch(() => {
          // Navigation must continue even when analytics is unavailable.
        });
    },
    [advertisementId],
  );

  return { trackClick };
};
