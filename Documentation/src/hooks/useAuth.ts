import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  login as apiLogin,
  registerBuyer as apiRegisterBuyer,
  registerSeller as apiRegisterSeller,
  logout as apiLogout,
  sendOtp as apiSendOtp,
  verifyOtp as apiVerifyOtp,
  resendVerification as apiResendVerification,
  verifyAccountOtp as apiVerifyAccountOtp,
  forgotPassword as apiForgotPassword,
  resetPassword as apiResetPassword,
} from "@/lib/api/endpoints/auth";
import { useAuthStore } from "@/store/useAuthStore";
import { authStorage } from "@/lib/auth/storage";
import { authCookies } from "@/lib/auth/cookies";
import { isAdminUser, isSellerUser } from "@/guards/permissions";
import type { AuthTokenResponse } from "@/types/api/auth";
import { useRouter } from "next/navigation";
import { cartApi } from "@/lib/api/endpoints/commerce";
import { useCartStore } from "@/store/useCartStore";
import toast from "react-hot-toast";

export const useAuth = () => {
  const queryClient = useQueryClient();
  const router = useRouter();
  
  const user = useAuthStore((state) => state.user);
  const accessToken = useAuthStore((state) => state.accessToken);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  const storeSetSession = useAuthStore((state) => state.setSession);
  const storeClearSession = useAuthStore((state) => state.clearSession);

  const syncRoleCookies = (session: AuthTokenResponse) => {
    const sessionUser = session.user ?? null;

    authCookies.setAuth();

    if (isAdminUser(sessionUser)) {
      authCookies.setAdmin();
    } else {
      authCookies.clearAdmin();
    }

    if (isSellerUser(sessionUser)) {
      authCookies.setSeller();
    } else {
      authCookies.clearSeller();
    }
  };

  const setSession = (session: AuthTokenResponse) => {
    authStorage.setSession(session);
    syncRoleCookies(session);
    storeSetSession(session);
  };

  const clearSession = () => {
    authStorage.clearSession();
    authCookies.clearAll();
    storeClearSession();
  };

  const mergeGuestCart = async () => {
    const guestItems = useCartStore.getState().items;
    if (!guestItems.length) return;

    const result = await cartApi.merge(
      guestItems.map((item) => ({
        product_id: item.productId ?? String(item.id).split(":")[0],
        variant_id: item.variantId ?? null,
        quantity: item.quantity,
      })),
    );
    queryClient.setQueryData(["cart"], result.cart);

    const rejectedIds = new Set(result.rejected_items.map((item) => item.product_id));
    useCartStore.getState().setItems(
      guestItems.filter((item) => rejectedIds.has(item.productId ?? String(item.id).split(":")[0])),
    );
    if (result.rejected_items.length) {
      toast.error(`${result.rejected_items.length} guest cart item(s) could not be merged.`);
    }
  };

  const loginMutation = useMutation({
    mutationFn: apiLogin,
    onSuccess: async (data) => {
      setSession(data);
      if (!isAdminUser(data.user) && !isSellerUser(data.user)) {
        await mergeGuestCart().catch(() => {
          toast.error("Your guest cart could not be synced. It is still saved on this device.");
        });
      }
      const user = data.user;
      if (isAdminUser(user)) {
        router.push("/admin/dashboard");
      } else if (isSellerUser(user)) {
        router.push("/seller/dashboard");
      } else {
        router.push("/account");
      }
    },
  });

  const registerBuyerMutation = useMutation({
    mutationFn: apiRegisterBuyer,
    onSuccess: (data) => {
      const params = new URLSearchParams({
        phone: data.phone,
        email: data.email,
        purpose: data.verification_purpose || "register",
        next: "/signin",
      });
      router.push(`/verify-otp?${params.toString()}`);
    },
  });

  const registerSellerMutation = useMutation({
    mutationFn: apiRegisterSeller,
    onSuccess: (data) => {
      const params = new URLSearchParams({
        phone: data.phone,
        email: data.email,
        purpose: data.verification_purpose,
        next: "/signin",
      });
      router.push(`/verify-otp?${params.toString()}`);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      try {
        if (refreshToken) {
          await apiLogout({ refresh_token: refreshToken });
        }
      } finally {
        clearSession();
        queryClient.clear();
        router.push("/signin");
      }
    },
  });

  const sendOtpMutation = useMutation({
    mutationFn: apiSendOtp,
  });

  const verifyOtpMutation = useMutation({
    mutationFn: apiVerifyOtp,
  });

  const resendVerificationMutation = useMutation({
    mutationFn: apiResendVerification,
  });

  const verifyAccountOtpMutation = useMutation({
    mutationFn: apiVerifyAccountOtp,
  });

  const forgotPasswordMutation = useMutation({
    mutationFn: apiForgotPassword,
  });

  const resetPasswordMutation = useMutation({
    mutationFn: apiResetPassword,
  });

  return {
    user,
    accessToken,
    isAuthenticated,
    
    login: loginMutation.mutateAsync,
    isLoggingIn: loginMutation.isPending,
    loginError: loginMutation.error,

    registerBuyer: registerBuyerMutation.mutateAsync,
    isRegisteringBuyer: registerBuyerMutation.isPending,
    registerBuyerError: registerBuyerMutation.error,

    registerSeller: registerSellerMutation.mutateAsync,
    isRegisteringSeller: registerSellerMutation.isPending,
    registerSellerError: registerSellerMutation.error,

    logout: logoutMutation.mutateAsync,
    isLoggingOut: logoutMutation.isPending,

    sendOtp: sendOtpMutation.mutateAsync,
    isSendingOtp: sendOtpMutation.isPending,

    verifyOtp: verifyOtpMutation.mutateAsync,
    isVerifyingOtp: verifyOtpMutation.isPending,

    resendVerification: resendVerificationMutation.mutateAsync,
    isResendingVerification: resendVerificationMutation.isPending,

    verifyAccountOtp: verifyAccountOtpMutation.mutateAsync,
    isVerifyingAccountOtp: verifyAccountOtpMutation.isPending,

    forgotPassword: forgotPasswordMutation.mutateAsync,
    isSubmittingForgotPassword: forgotPasswordMutation.isPending,

    resetPassword: resetPasswordMutation.mutateAsync,
    isSubmittingResetPassword: resetPasswordMutation.isPending,
    setSession,
    mergeGuestCart,
    refreshSession: () => {},
  };
};
export default useAuth;
