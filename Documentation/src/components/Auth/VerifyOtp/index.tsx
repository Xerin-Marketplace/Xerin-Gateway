"use client";

import Image from "next/image";
import Link from "next/link";
import React, { FormEvent, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import type { OtpPurpose } from "@/types/api/auth";

const getApiErrorMessage = (error: unknown, fallback: string) => {
  const apiError = error as {
    message?: string;
    response?: { data?: { detail?: unknown; message?: string } };
  };

  const detail = apiError.response?.data?.detail;
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object") {
    const first = detail[0] as { msg?: string };
    if (first.msg) return first.msg;
  }

  return apiError.response?.data?.message || apiError.message || fallback;
};

const ShieldIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);

const VerifyOtp = () => {
  const {
    sendOtp,
    verifyOtp,
    resendVerification,
    verifyAccountOtp,
    isSendingOtp,
    isVerifyingOtp,
    isResendingVerification,
    isVerifyingAccountOtp,
  } = useAuth();

  const router = useRouter();
  const searchParams = useSearchParams();

  const phoneParam = searchParams.get("phone");
  const emailParam = searchParams.get("email");
  const identifierParam = searchParams.get("identifier");
  const purposeParam = searchParams.get("purpose");
  const recoveryMode = searchParams.get("recover") === "1";

  const phone =
    phoneParam && phoneParam !== "undefined" && phoneParam !== "null"
      ? phoneParam.trim()
      : "";

  const email =
    emailParam && emailParam !== "undefined" && emailParam !== "null"
      ? emailParam.trim()
      : "";

  const purpose = useMemo<OtpPurpose>(() => {
    if (
      purposeParam === "register" ||
      purposeParam === "register_seller" ||
      purposeParam === "password_reset"
    ) {
      return purposeParam;
    }
    return "generic";
  }, [purposeParam]);

  const nextPath = searchParams.get("next") || "/signin";

  const [identifier, setIdentifier] = useState(
    identifierParam && identifierParam !== "undefined" && identifierParam !== "null"
      ? identifierParam
      : email || phone,
  );
  const [otpCode, setOtpCode] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const cleanOtp = otpCode.replace(/\D/g, "").slice(0, 6);
  const cleanIdentifier = identifier.trim();

  const registrationContext =
    !recoveryMode && Boolean(phone) && purpose !== "generic";

  const accountRecoveryContext =
    recoveryMode || (!registrationContext && Boolean(cleanIdentifier));

  const isBusy =
    isSendingOtp ||
    isVerifyingOtp ||
    isResendingVerification ||
    isVerifyingAccountOtp;

  const maskedPhone = phone
    ? phone.length > 7
      ? `${phone.slice(0, 4)}••••${phone.slice(-3)}`
      : phone
    : "";

  const title = recoveryMode
    ? "Verify your account"
    : purpose === "register_seller"
      ? "Verify your seller account"
      : purpose === "register"
        ? "Verify your account"
        : "Account verification";

  const subtitle = recoveryMode
    ? "Your account is registered but not verified. Enter your OTP below, or use your registered email or phone number to request a fresh code."
    : purpose === "register_seller"
      ? "Enter the verification code sent after seller registration."
      : "Enter the verification code sent after registration.";

  const redirectAfterSuccess = () => {
    const target = nextPath.startsWith("/") ? nextPath : "/signin";
    const separator = target.includes("?") ? "&" : "?";
    const prefillEmail =
      email || (cleanIdentifier.includes("@") ? cleanIdentifier : "");
    const verifiedTarget =
      `${target}${separator}verified=1` +
      (prefillEmail ? `&email=${encodeURIComponent(prefillEmail)}` : "");

    window.setTimeout(() => router.push(verifiedTarget), 700);
  };

  const handleResend = async () => {
    setErrorMessage("");
    setSuccessMessage("");

    try {
      if (registrationContext && phone) {
        await sendOtp({ phone, purpose });
      } else {
        if (!cleanIdentifier) {
          setErrorMessage("Enter your registered email address or phone number.");
          return;
        }

        await resendVerification({ identifier: cleanIdentifier });
      }

      setSuccessMessage(
        "A fresh verification code has been sent to your registered contact details.",
      );
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(error, "Unable to resend the verification code."),
      );
    }
  };

  const handleVerify = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    if (cleanOtp.length < 4) {
      setErrorMessage("Enter the verification code sent to you.");
      return;
    }

    try {
      if (registrationContext && phone) {
        await verifyOtp({
          phone,
          otp_code: cleanOtp,
          purpose,
        });
      } else {
        if (!cleanIdentifier) {
          setErrorMessage("Enter your registered email address or phone number.");
          return;
        }

        await verifyAccountOtp({
          identifier: cleanIdentifier,
          otp_code: cleanOtp,
        });
      }

      setSuccessMessage("Account verified successfully. Redirecting to sign in...");
      redirectAfterSuccess();
    } catch (error) {
      const message = getApiErrorMessage(error, "Unable to verify this code.");
      setErrorMessage(
        message.toLowerCase().includes("expired")
          ? "This OTP has expired. Enter your registered email or phone below and request a new OTP."
          : message,
      );
    }
  };

  return (
    <section className="min-h-screen grid bg-white dark:bg-darkTheme-bg lg:grid-cols-2">
      <div className="flex min-h-screen flex-col px-6 py-8 sm:px-10 xl:px-20">
        <Link href="/" className="inline-flex w-fit items-center gap-2.5">
          <Image
            src="/images/logo/logo.png"
            alt="XerinMarket"
            width={32}
            height={32}
            priority
            className="object-contain"
          />
          <span className="text-lg font-semibold text-dark dark:text-white">
            XerinMarket
          </span>
        </Link>

        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[430px]">
            <div className="mb-8 text-center">
              <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-orange/10 text-orange">
                <ShieldIcon />
              </div>

              <h1 className="mb-2 text-2xl font-semibold text-dark dark:text-white">
                {title}
              </h1>

              <p className="mx-auto max-w-[390px] text-sm leading-6 text-dark-4 dark:text-darkTheme-secondary-muted">
                {subtitle}
              </p>
            </div>

            {registrationContext && (
              <div className="mb-6 rounded-xl border border-gray-3 bg-gray-1 p-4 dark:border-darkTheme-border-color dark:bg-darkTheme-secondary-bg">
                <p className="text-xs font-medium uppercase tracking-wider text-dark-4 dark:text-darkTheme-secondary-muted">
                  Verification sent to
                </p>
                <p className="mt-1 font-semibold text-dark dark:text-white">
                  {maskedPhone}
                </p>
                {email && (
                  <p className="mt-1 break-all text-sm text-dark-4 dark:text-darkTheme-secondary-muted">
                    {email}
                  </p>
                )}
              </div>
            )}

            {successMessage && (
              <div className="mb-5 rounded-lg border border-green/20 bg-green-light-6 px-4 py-3 text-sm text-green">
                {successMessage}
              </div>
            )}

            {errorMessage && (
              <div className="mb-5 rounded-lg border border-red/20 bg-red-light-6 px-4 py-3 text-sm text-red">
                {errorMessage}
              </div>
            )}

            <form onSubmit={handleVerify}>
              {accountRecoveryContext && !registrationContext && (
                <div className="mb-5">
                  <label
                    htmlFor="verification-identifier"
                    className="mb-2 block text-sm font-medium text-dark dark:text-white"
                  >
                    Registered Email or Phone Number
                  </label>

                  <input
                    id="verification-identifier"
                    type="text"
                    value={identifier}
                    onChange={(event) => setIdentifier(event.target.value)}
                    placeholder="you@example.com or 255712345678"
                    autoComplete="username"
                    disabled={isBusy}
                    className="h-12 w-full rounded-lg border border-gray-3 bg-gray-1 px-4 text-sm text-dark outline-none transition focus:border-orange focus:bg-white focus:ring-4 focus:ring-orange/10 dark:border-darkTheme-border-color dark:bg-darkTheme-secondary-bg dark:text-white"
                  />

                  <p className="mt-2 text-xs leading-5 text-dark-4 dark:text-darkTheme-secondary-muted">
                    Use the same email address or phone number registered on your account.
                  </p>
                </div>
              )}

              <div className="mb-5">
                <label
                  htmlFor="otpCode"
                  className="mb-2 block text-sm font-medium text-dark dark:text-white"
                >
                  Verification Code
                </label>

                <input
                  id="otpCode"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={otpCode}
                  onChange={(event) =>
                    setOtpCode(event.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                  placeholder="000000"
                  maxLength={6}
                  autoFocus
                  required
                  disabled={isBusy}
                  className="h-16 w-full rounded-xl border border-gray-3 bg-gray-1 px-5 text-center text-2xl font-semibold tracking-[0.45em] text-dark outline-none transition placeholder:text-dark-4 placeholder:opacity-40 focus:border-orange focus:bg-white focus:ring-4 focus:ring-orange/10 dark:border-darkTheme-border-color dark:bg-darkTheme-secondary-bg dark:text-white"
                />
              </div>

              <button
                type="submit"
                disabled={
                  isBusy ||
                  cleanOtp.length < 4 ||
                  (!registrationContext && !cleanIdentifier)
                }
                className="flex h-12 w-full items-center justify-center rounded-lg bg-orange px-6 text-sm font-semibold text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isVerifyingOtp || isVerifyingAccountOtp
                  ? "Verifying..."
                  : "Verify & Continue"}
              </button>

              <div className="mt-5 rounded-xl border border-gray-3 p-4 dark:border-darkTheme-border-color">
                <p className="text-center text-sm text-dark-4 dark:text-darkTheme-secondary-muted">
                  OTP expired or didn&apos;t arrive?
                </p>

                {registrationContext && (
                  <p className="mt-1 text-center text-xs text-dark-4 dark:text-darkTheme-secondary-muted">
                    We&apos;ll resend it using the phone number from your registration.
                  </p>
                )}

                <button
                  type="button"
                  onClick={handleResend}
                  disabled={
                    isBusy || (!registrationContext && !cleanIdentifier)
                  }
                  className="mt-3 flex h-11 w-full items-center justify-center rounded-lg border border-orange px-5 text-sm font-semibold text-orange transition hover:bg-orange/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSendingOtp || isResendingVerification
                    ? "Sending..."
                    : "Resend OTP"}
                </button>
              </div>
            </form>

            <div className="mt-7 text-center">
              <Link
                href="/signin"
                className="text-sm font-medium text-dark-4 hover:text-orange dark:text-darkTheme-secondary-muted"
              >
                ← Back to Sign In
              </Link>
            </div>

            <p className="mt-6 text-center text-xs leading-5 text-dark-4 dark:text-darkTheme-secondary-muted">
              Never share your verification code with anyone.
            </p>
          </div>
        </div>
      </div>

      <div className="relative hidden min-h-screen overflow-hidden bg-dark lg:block">
        <Image
          src="/images/bg6-dark.jpg"
          alt=""
          fill
          priority
          sizes="50vw"
          className="object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/50 to-black/25" />

        <div className="relative flex h-full flex-col justify-between p-12 xl:p-16">
          <Link href="/" className="inline-flex w-fit items-center gap-2.5">
            <Image
              src="/images/logo/logo.png"
              alt="XerinMarket"
              width={32}
              height={32}
              className="object-contain"
            />
            <span className="text-lg font-semibold text-white">XerinMarket</span>
          </Link>

          <div className="max-w-md">
            <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 text-white">
              <ShieldIcon />
            </div>

            <h2 className="mb-4 text-3xl font-bold leading-tight text-white xl:text-4xl">
              Secure your XerinMarket account
            </h2>

            <p className="leading-relaxed text-white/75">
              Verification protects customers and sellers from unauthorized access and keeps marketplace activity secure.
            </p>
          </div>

          <div className="text-sm text-white/65">
            Secure verification • XerinMarket
          </div>
        </div>
      </div>
    </section>
  );
};

export default VerifyOtp;
