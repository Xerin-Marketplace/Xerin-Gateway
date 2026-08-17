import type { AuthTokenResponse } from "@/types/api/auth";

const ACCESS_TOKEN_KEY = "xerin_access_token";
const REFRESH_TOKEN_KEY = "xerin_refresh_token";
const USER_KEY = "xerin_user";

const isBrowser = typeof window !== "undefined";

export const authStorage = {
  setSession: (session: AuthTokenResponse) => {
    if (!isBrowser) return;

    localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);

    if (session.refresh_token) {
      localStorage.setItem(REFRESH_TOKEN_KEY, session.refresh_token);
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }

    if (session.user) {
      localStorage.setItem(USER_KEY, JSON.stringify(session.user));
    }
  },

  getAccessToken: () => {
    if (!isBrowser) return null;
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },

  getRefreshToken: () => {
    if (!isBrowser) return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  getUser: <T = AuthTokenResponse["user"]>(): T | null => {
    if (!isBrowser) return null;

    try {
      const rawUser = localStorage.getItem(USER_KEY);
      return rawUser ? (JSON.parse(rawUser) as T) : null;
    } catch {
      localStorage.removeItem(USER_KEY);
      return null;
    }
  },

  getSession: (): AuthTokenResponse | null => {
    if (!isBrowser) return null;

    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!accessToken) return null;

    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    const user = authStorage.getUser<AuthTokenResponse["user"]>();

    return {
      access_token: accessToken,
      refresh_token: refreshToken ?? undefined,
      token_type: "bearer",
      ...(user ? { user } : {}),
    };
  },

  clearSession: () => {
    if (!isBrowser) return;

    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};
