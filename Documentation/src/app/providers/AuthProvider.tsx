"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { authStorage } from "@/lib/auth/storage";
import { authCookies } from "@/lib/auth/cookies";
import { useAuthStore } from "@/store/useAuthStore";
import { isAdminUser, isSellerUser } from "@/guards/permissions";
import type { AuthTokenResponse } from "@/types/api/auth";

type AuthUser = {
  id?: string | number;
  email?: string;
  account_type?: string;
  roles?: string[];
  [key: string]: unknown;
};

type AuthContextValue = {
  user: AuthUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  setSession: (session: AuthTokenResponse) => void;
  refreshSession: () => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export default function AuthProvider({ children }: { children: ReactNode }) {
  const storeSetSession = useAuthStore((state) => state.setSession);
  const storeSetTokens = useAuthStore((state) => state.setTokens);
  const storeClearSession = useAuthStore((state) => state.clearSession);

  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  const syncCookies = useCallback((user: AuthUser | null, accessToken: string | null) => {
    if (!accessToken) {
      authCookies.clearAll();
      return;
    }

    authCookies.setAuth();

    if (isAdminUser(user as any)) {
      authCookies.setAdmin();
    } else {
      authCookies.clearAdmin();
    }

    if (isSellerUser(user as any)) {
      authCookies.setSeller();
    } else {
      authCookies.clearSeller();
    }
  }, []);

  const applySession = useCallback(
    (session: AuthTokenResponse) => {
      const sessionUser = session.user as AuthUser | undefined;

      setAccessToken(session.access_token);
      setUser(sessionUser ?? null);
      syncCookies(sessionUser ?? null, session.access_token);

      if (sessionUser?.id) {
        storeSetSession({
          access_token: session.access_token,
          refresh_token: session.refresh_token,
          token_type: session.token_type,
          user: {
            ...sessionUser,
            id: String(sessionUser.id),
          },
        });

        return;
      }

      storeSetTokens({
        access_token: session.access_token,
        refresh_token: session.refresh_token,
        token_type: session.token_type,
      });
    },
    [storeSetSession, storeSetTokens, syncCookies]
  );

  const refreshSession = useCallback(() => {
    const session = authStorage.getSession();

    if (!session?.access_token) {
      setAccessToken(null);
      setUser(null);
      syncCookies(null, null);
      storeClearSession();
      return;
    }

    applySession(session);
  }, [applySession, storeClearSession]);

  const setSession = useCallback(
    (session: AuthTokenResponse) => {
      authStorage.setSession(session);
      applySession(session);
    },
    [applySession]
  );

  const logout = useCallback(() => {
    authStorage.clearSession();
    authCookies.clearAll();
    setAccessToken(null);
    setUser(null);
    storeClearSession();
  }, [storeClearSession]);

  useEffect(() => {
    refreshSession();

    const handleStorageChange = () => {
      refreshSession();
    };

    window.addEventListener("storage", handleStorageChange);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
    };
  }, [refreshSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken,
      isAuthenticated: Boolean(accessToken),
      setSession,
      refreshSession,
      logout,
    }),
    [user, accessToken, setSession, refreshSession, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuthContext = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuthContext must be used within AuthProvider");
  return context;
};
