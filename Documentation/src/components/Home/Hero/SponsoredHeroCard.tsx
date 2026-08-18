"use client";

import { useRef } from "react";
import { useAdvertisementTracking } from "@/hooks/useAdvertisementTracking";
import type { PublicAdvertisement } from "@/lib/api/endpoints/advertisements";

type Props = {
  advertisement: PublicAdvertisement;
};

const isExternal = (url: string) => /^https?:\/\//i.test(url);

export default function SponsoredHeroCard({ advertisement }: Props) {
  const href = advertisement.target_url || "#";
  const cardRef = useRef<HTMLAnchorElement | null>(null);
  const { trackClick } = useAdvertisementTracking(advertisement.id, cardRef);

  if (!advertisement.target_url) {
    return (
      <article className="group relative min-h-0 overflow-hidden rounded-2xl bg-[#111827] shadow-sm">
        <SponsoredCardContents advertisement={advertisement} />
      </>
    );
  }

  return (
    <a
      ref={cardRef}
      href={href}
      target={isExternal(href) ? "_blank" : undefined}
      rel={isExternal(href) ? "noopener noreferrer sponsored" : "sponsored"}
      onClick={trackClick}
      aria-label={`${advertisement.title}. ${advertisement.cta_label || "Learn more"}`}
      className="group relative block min-h-0 overflow-hidden rounded-2xl bg-[#111827] shadow-sm outline-none ring-[#f47524] focus-visible:ring-2 focus-visible:ring-offset-2"
    >
      <SponsoredCardContents advertisement={advertisement} />
    </a>
  );
}

function SponsoredCardContents({
  advertisement,
}: {
  advertisement: PublicAdvertisement;
}) {
  return (
      <img
        src={advertisement.image_url}
        alt={advertisement.alt_text || advertisement.title}
        className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-[1.02]"
      />

      <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/50 to-black/10" />

      <div className="relative z-10 flex h-full min-h-[220px] flex-col justify-between p-5 xl:min-h-[235px] xl:p-7">
        <div>
          <div className="mb-3 flex items-center gap-2">
            <span className="rounded-full bg-white/95 px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#111827]">
              Sponsored
            </span>
            <span className="truncate text-xs font-semibold text-white/80">
              {advertisement.advertiser_name}
            </span>
          </div>

          <h2 className="max-w-[270px] text-xl font-bold leading-tight text-white xl:text-2xl">
            {advertisement.title}
          </h2>
          {advertisement.description ? (
            <p className="mt-2 line-clamp-2 max-w-[280px] text-sm leading-5 text-white/80">
              {advertisement.description}
            </p>
          ) : null}
        </div>

        {advertisement.target_url ? (
          <span className="mt-4 inline-flex w-fit items-center rounded-lg bg-[#f47524] px-4 py-2.5 text-sm font-bold text-white transition group-hover:bg-[#df6519]">
            {advertisement.cta_label || "Learn More"}
          </span>
        ) : null}
      </div>
    </>
  );
}
