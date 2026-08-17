import axios from "axios";
import { API_BASE_URL } from "./endpoints";
import { setupInterceptors } from "./interceptors";
export { ApiError } from "./errors";

export const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  headers: {
    Accept: "application/json",
  },
});

// Initialize interceptors
setupInterceptors(axiosInstance);

export default axiosInstance;
