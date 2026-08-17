import { useAuthStore } from "@/store/useAuthStore";
import { navigation } from "@/constants/navigation";
import { hasPermission } from "@/guards/permissions";

export const useNavigation = () => {
  const user = useAuthStore((state) => state.user);

  return navigation.filter((item) => {
    return hasPermission(user, item.permission);
  });
};
