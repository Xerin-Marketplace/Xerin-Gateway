import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usersApi } from "@/lib/api/endpoints/users";
import type { UpdateUserRequest } from "@/types/api/user";

export const userProfileQueryKey = ["user-profile"];

export const useUserProfile = () => {
  const queryClient = useQueryClient();

  const profileQuery = useQuery({
    queryKey: userProfileQueryKey,
    queryFn: usersApi.getMe,
  });

  const updateProfileMutation = useMutation({
    mutationFn: (payload: UpdateUserRequest) => usersApi.updateMe(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(userProfileQueryKey, data);
    },
  });

  return {
    profile: profileQuery.data,
    isLoadingProfile: profileQuery.isLoading,
    isFetchingProfile: profileQuery.isFetching,
    profileError: profileQuery.error,
    refetchProfile: profileQuery.refetch,

    updateProfile: updateProfileMutation.mutateAsync,
    isUpdatingProfile: updateProfileMutation.isPending,
    updateProfileError: updateProfileMutation.error,
  };
};

export default useUserProfile;
