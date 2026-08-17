import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { storeApi } from "@/lib/api/endpoints/store";
import type { UpdateStorePayload } from "@/types/api/store";

export const useMyStore = () => {
  return useQuery({
    queryKey: ["store", "me"],
    queryFn: () => storeApi.getMyStore(),
  });
};

export const useUpdateMyStore = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateStorePayload) => storeApi.updateMyStore(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["store", "me"] });
    },
  });
};

export const useUploadStoreLogo = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => storeApi.uploadStoreLogo(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["store", "me"] });
    },
  });
};

export const useUploadStoreBanner = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => storeApi.uploadStoreBanner(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["store", "me"] });
    },
  });
};
