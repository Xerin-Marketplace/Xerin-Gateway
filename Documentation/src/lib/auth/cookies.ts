const AUTH_COOKIE_NAME = "xerin_auth_present";
const ADMIN_COOKIE_NAME = "xerin_admin_present";
const SELLER_COOKIE_NAME = "xerin_seller_present";

const ONE_WEEK_SECONDS = 60 * 60 * 24 * 7;

const setCookie = (name: string, value: string, maxAge: number) => {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=${value}; path=/; max-age=${maxAge}; SameSite=Lax`;
};

const clearCookie = (name: string) => {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
};

export const authCookies = {
  setAuth: () => setCookie(AUTH_COOKIE_NAME, "1", ONE_WEEK_SECONDS),
  clearAuth: () => clearCookie(AUTH_COOKIE_NAME),

  setAdmin: () => setCookie(ADMIN_COOKIE_NAME, "1", ONE_WEEK_SECONDS),
  clearAdmin: () => clearCookie(ADMIN_COOKIE_NAME),

  setSeller: () => setCookie(SELLER_COOKIE_NAME, "1", ONE_WEEK_SECONDS),
  clearSeller: () => clearCookie(SELLER_COOKIE_NAME),

  clearAll: () => {
    clearCookie(AUTH_COOKIE_NAME);
    clearCookie(ADMIN_COOKIE_NAME);
    clearCookie(SELLER_COOKIE_NAME);
  },
};
