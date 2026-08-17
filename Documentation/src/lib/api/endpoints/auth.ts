import axiosInstance from "../client";
import { API_ENDPOINTS } from "../endpoints";
import type {
  AuthTokenResponse,
  ForgotPasswordRequest,
  LoginRequest,
  RegisterBuyerRequest,
  RegistrationResponse,
  RegisterSellerRequest,
  SellerRegistrationResponse,
  ResetPasswordRequest,
  SendOtpRequest,
  VerifyOtpRequest,
  RefreshTokenRequest,
  ResendVerificationRequest,
  VerifyAccountOtpRequest,
  ChangePasswordRequest,
} from "@/types/api/auth";
import type { ApiMessageResponse } from "@/types/api/common";

export const login = async (payload: LoginRequest): Promise<AuthTokenResponse> => {
  const res = await axiosInstance.post<AuthTokenResponse>(API_ENDPOINTS.auth.login, payload);
  return res.data;
};

export const registerBuyer = async (payload: RegisterBuyerRequest): Promise<RegistrationResponse> => {
  const res = await axiosInstance.post<RegistrationResponse>(API_ENDPOINTS.auth.register, payload);
  return res.data;
};

export const registerSeller = async (payload: RegisterSellerRequest): Promise<SellerRegistrationResponse> => {
  const res = await axiosInstance.post<SellerRegistrationResponse>(API_ENDPOINTS.auth.registerSeller, payload);
  return res.data;
};

export const logout = async (payload: RefreshTokenRequest): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.post<ApiMessageResponse>(API_ENDPOINTS.auth.logout, payload);
  return res.data;
};

export const sendOtp = async (payload: SendOtpRequest): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.post<ApiMessageResponse>(API_ENDPOINTS.auth.sendOtp, payload);
  return res.data;
};

export const verifyOtp = async (payload: VerifyOtpRequest): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.post<ApiMessageResponse>(API_ENDPOINTS.auth.verifyOtp, payload);
  return res.data;
};

export const resendVerification = async (
  payload: ResendVerificationRequest,
): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.post<ApiMessageResponse>(
    API_ENDPOINTS.auth.resendVerification,
    payload,
  );
  return res.data;
};

export const verifyAccountOtp = async (
  payload: VerifyAccountOtpRequest,
): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.post<ApiMessageResponse>(
    API_ENDPOINTS.auth.verifyAccountOtp,
    payload,
  );
  return res.data;
};

export const forgotPassword = async (payload: ForgotPasswordRequest): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.post<ApiMessageResponse>(API_ENDPOINTS.auth.forgotPassword, payload);
  return res.data;
};

export const resetPassword = async (payload: ResetPasswordRequest): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.post<ApiMessageResponse>(API_ENDPOINTS.auth.resetPassword, payload);
  return res.data;
};


export const changePassword = async (
  payload: ChangePasswordRequest,
): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.post<ApiMessageResponse>(
    API_ENDPOINTS.auth.changePassword,
    payload,
  );
  return res.data;
};

export const authApi = {
  login,
  registerBuyer,
  registerSeller,
  logout,
  sendOtp,
  verifyOtp,
  resendVerification,
  verifyAccountOtp,
  forgotPassword,
  resetPassword,
  changePassword,
};
