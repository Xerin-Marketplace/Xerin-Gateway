import axiosInstance from "../client";

export type PublicAdvertisementPlacement =
  | "hero_side_top"
  | "hero_side_bottom"
  | "homepage_banner"
  | "category_banner"
  | "search_banner";

export type PublicAdvertisement = {
  id: string;
  advertiser_name: string;
  title: string;
  description: string | null;
  image_url: string;
  mobile_image_url: string | null;
  alt_text: string | null;
  target_url: string | null;
  cta_label: string | null;
  placement: PublicAdvertisementPlacement;
  starts_at: string;
  ends_at: string;
  sponsored: true;
};

export type AdvertisementTrackingPayload = {
  session_id: string;
  client_event_id?: string;
  page_path?: string;
};

export type AdvertisementTrackingResponse = {
  accepted: boolean;
  duplicate: boolean;
  event_type: "impression" | "click";
  impression_count: number;
  click_count: number;
};

export type PublicAdvertisementSlot = {
  placement: PublicAdvertisementPlacement;
  advertisement: PublicAdvertisement | null;
};

export const advertisementsApi = {
  trackImpression: async (
    advertisementId: string,
    payload: AdvertisementTrackingPayload,
  ): Promise<AdvertisementTrackingResponse> =>
    (
      await axiosInstance.post<AdvertisementTrackingResponse>(
        `/advertisements/${advertisementId}/impression`,
        payload,
      )
    ).data,

  trackClick: async (
    advertisementId: string,
    payload: AdvertisementTrackingPayload,
  ): Promise<AdvertisementTrackingResponse> =>
    (
      await axiosInstance.post<AdvertisementTrackingResponse>(
        `/advertisements/${advertisementId}/click`,
        payload,
      )
    ).data,

  homepageSlots: async (signal?: AbortSignal): Promise<PublicAdvertisementSlot[]> =>
    (
      await axiosInstance.get<PublicAdvertisementSlot[]>("/advertisements/slots", {
        signal,
      })
    ).data,
};
