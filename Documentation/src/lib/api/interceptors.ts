import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { toApiError } from "./errors";
import { useAuthStore } from "@/store/useAuthStore";
import { API_BASE_URL } from "./endpoints";

let isRefreshing = false;
type RefreshQueueItem = { resolve: (token: string | null) => void; reject: (error: unknown) => void };
type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };
let failedQueue: RefreshQueueItem[] = [];
let axiosInstance: AxiosInstance;

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

export const setupInterceptors = (instance: AxiosInstance) => {
  axiosInstance = instance;

  // Request interceptor
  axiosInstance.interceptors.request.use(
    (config) => {
      const token = useAuthStore.getState().accessToken;
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(toApiError(error)),
  );

  // Response interceptor
  axiosInstance.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as RetryConfig | undefined;
      const apiError = toApiError(error);
      const status = apiError.status;

      if (!originalRequest) return Promise.reject(apiError);

      if (status === 401 && !originalRequest._retry) {
        if (originalRequest.url === "/auth/refresh-token" || originalRequest.url?.includes("/auth/login")) {
          useAuthStore.getState().clearSession();
          return Promise.reject(apiError);
        }

        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          })
            .then((token) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              return axiosInstance(originalRequest);
            })
            .catch((err) => Promise.reject(err));
        }

        originalRequest._retry = true;
        isRefreshing = true;

        const refreshToken = useAuthStore.getState().refreshToken;
        if (!refreshToken) {
          useAuthStore.getState().clearSession();
          isRefreshing = false;
          return Promise.reject(apiError);
        }

        try {
          const res = await axios.post(`${API_BASE_URL}/auth/refresh-token`, {
            refresh_token: refreshToken,
          }, {
            timeout: 10_000,
          });

          const { access_token, refresh_token } = res.data;
          useAuthStore.getState().setTokens({
            access_token,
            refresh_token,
          });

          processQueue(null, access_token);
          isRefreshing = false;

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return axiosInstance(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError, null);
          useAuthStore.getState().clearSession();
          isRefreshing = false;
          if (typeof window !== "undefined") {
            window.location.href = "/signin";
          }
          return Promise.reject(apiError);
        }
      }

      return Promise.reject(apiError);
    }
  );
};
