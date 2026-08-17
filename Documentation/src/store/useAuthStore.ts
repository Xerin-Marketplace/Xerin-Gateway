import { create } from "zustand";
import { persist } from "zustand/middleware";

export type AuthUser = {
  id: string;
  first_name?: string;
  last_name?: string;
  name?: string;
  email?: string;
  phone?: string;
  is_verified?: boolean;
  status?: string;
  account_type?: string;
  is_seller?: boolean;
  seller_status?: string | null;
  roles?: string[];
  permissions?: string[];
};

export type AuthSession = {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  user?: any;
};

interface AuthState {
  user: any;
  accessToken: string | null;
  refreshToken: string | null;
  tokenType: string;
  isAuthenticated: boolean;
  hasHydrated: boolean;
  setHasHydrated: (value: boolean) => void;
  setSession: (session: AuthSession) => void;
  setUser: (user: any) => void;
  setTokens: (tokens: {
    access_token: string;
    refresh_token?: string;
    token_type?: string;
  }) => void;
  clearSession: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      tokenType: "bearer",
      isAuthenticated: false,
      hasHydrated: false,
      setHasHydrated: (value) => set({ hasHydrated: value }),

      setSession: (session) =>
        set({
          user: session.user ?? null,
          accessToken: session.access_token,
          refreshToken: session.refresh_token ?? null,
          tokenType: session.token_type ?? "bearer",
          isAuthenticated: true,
        }),

      setUser: (user) =>
        set((state) => ({
          user,
          isAuthenticated: Boolean(user && state.accessToken),
        })),

      setTokens: (tokens) =>
        set((state) => ({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token ?? state.refreshToken,
          tokenType: tokens.token_type ?? "bearer",
          isAuthenticated: Boolean(state.user),
        })),

      clearSession: () =>
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          tokenType: "bearer",
          isAuthenticated: false,
        }),
    }),
    {
      name: "xerin_auth_store",
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        tokenType: state.tokenType,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => state?.setHasHydrated(true),
    }
  )
);
