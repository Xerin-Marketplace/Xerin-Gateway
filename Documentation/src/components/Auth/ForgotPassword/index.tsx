"use client";

import Image from "next/image";
import Link from "next/link";
import React, { FormEvent, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const getApiErrorMessage = (error: unknown, fallback: string) => {
  const apiError = error as {
    message?: string;
    response?: {
      data?: {
        detail?: unknown;
        message?: string;
      };
    };
  };

  const detail = apiError.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object") {
    const first = detail[0] as { msg?: string };

    if (first.msg) {
      return first.msg;
    }
  }

  return apiError.response?.data?.message || apiError.message || fallback;
};

const MailIcon = () => (
  <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="4" width="20" height="16" rx="2" />
    <path d="m22 6-10 7L2 6" />
  </svg>
);

const LockIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

const ShieldIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z" />
  </svg>
);

const TruckIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="1" y="6" width="14" height="11" rx="1" />
    <path d="M15 10h4l3 3v4h-7z" />
    <circle cx="6" cy="19" r="1.6" />
    <circle cx="17.5" cy="19" r="1.6" />
  </svg>
);

const WalletIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 7a2 2 0 0 1 2-2h13a1 1 0 0 1 1 1v3" />
    <path d="M3 7v11a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1h-4a2 2 0 1 0 0 4" />
  </svg>
);

const TrendingUpIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="m23 6-9.5 9.5-5-5L1 18" />
    <path d="M17 6h6v6" />
  </svg>
);

const UsersIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const StarIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none">
    <path d="M12 2.5l2.9 6.3 6.9.7-5.2 4.7 1.5 6.8L12 17.7 5.9 21l1.5-6.8L2.2 9.5l6.9-.7L12 2.5Z" />
  </svg>
);

const FEATURES = [
  { icon: <ShieldIcon />, title: "Secure Accounts", description: "Protected verification and password recovery" },
  { icon: <TruckIcon />, title: "Delivery Options", description: "See available shipping options during checkout" },
  { icon: <WalletIcon />, title: "Seller Wallet", description: "Fast payouts to bank or mobile money" },
  { icon: <TrendingUpIcon />, title: "Grow Your Business", description: "Reach thousands of customers across the region" },
];

const ForgotPassword = () => {
  const { forgotPassword, isSubmittingForgotPassword } = useAuth();

  const [email, setEmail] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setSuccessMessage("");
    setErrorMessage("");

    const cleanEmail = email.trim().toLowerCase();

    if (!cleanEmail) {
      setErrorMessage("Enter your registered email address.");
      return;
    }

    try {
      await forgotPassword({
        email: cleanEmail,
      });

      setSuccessMessage(
        "Password reset instructions have been sent. Check your email, then continue to reset your password."
      );
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Failed to submit password reset request. Please try again."
        )
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
          <div className="w-full max-w-[420px]">
            <div className="mb-8 text-center">
              <Image
                src="/images/logo/logo.png"
                alt="XerinMarket"
                width={58}
                height={58}
                priority
                className="mx-auto mb-4 object-contain"
              />

              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-orange/10 text-orange">
                <LockIcon />
              </div>

              <h1 className="mb-2 text-2xl font-semibold text-dark dark:text-white">
                Forgot your password?
              </h1>

              <p className="mx-auto max-w-[360px] text-sm leading-6 text-dark-4 dark:text-darkTheme-secondary-muted">
                Enter the email address registered with your XerinMarket account.
                We&apos;ll send instructions to help you reset your password.
              </p>
            </div>

            {successMessage && (
              <div role="status" className="mb-5 rounded-lg border border-green/20 bg-green-light-6 px-4 py-3 text-sm text-green">
                {successMessage}
              </div>
            )}

            {errorMessage && (
              <div role="alert" className="mb-5 rounded-lg border border-red/20 bg-red-light-6 px-4 py-3 text-sm text-red">
                {errorMessage}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div className="mb-6">
                <label htmlFor="forgot-email" className="mb-2 block text-sm font-medium text-dark dark:text-white">
                  Email Address
                </label>

                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-4 text-dark-4 dark:text-darkTheme-secondary-muted">
                    <MailIcon />
                  </span>

                  <input
                    id="forgot-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    required
                    disabled={isSubmittingForgotPassword}
                    className="h-12 w-full rounded-lg border border-gray-3 bg-gray-1 pl-11 pr-4 text-sm text-dark outline-none transition focus:border-orange focus:bg-white focus:ring-4 focus:ring-orange/10 disabled:cursor-not-allowed disabled:opacity-70 dark:border-darkTheme-border-color dark:bg-darkTheme-secondary-bg dark:text-white dark:placeholder:text-darkTheme-secondary-muted"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmittingForgotPassword || !email.trim()}
                className="flex h-12 w-full items-center justify-center rounded-lg bg-orange px-6 text-sm font-semibold text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSubmittingForgotPassword
                  ? "Sending instructions..."
                  : "Send Reset Instructions"}
              </button>
            </form>

            <div className="my-6 flex items-center gap-4">
              <span className="h-px flex-1 bg-gray-3 dark:bg-darkTheme-border-color" />
              <span className="text-xs uppercase tracking-wider text-dark-4 dark:text-darkTheme-secondary-muted">
                Account recovery
              </span>
              <span className="h-px flex-1 bg-gray-3 dark:bg-darkTheme-border-color" />
            </div>

            <div className="flex flex-col items-center justify-between gap-3 text-sm sm:flex-row">
              <Link
                href="/signin"
                className="font-medium text-dark-4 transition hover:text-orange dark:text-darkTheme-secondary-muted"
              >
                ← Back to Sign In
              </Link>

              <Link
                href="/reset-password"
                className="font-medium text-orange transition hover:text-orange-dark"
              >
                Already have OTP?
              </Link>
            </div>

            <p className="mt-7 text-center text-xs leading-5 text-dark-4 dark:text-darkTheme-secondary-muted">
              For your security, password reset instructions are only sent to the
              email associated with your account.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-xs text-dark-4 dark:text-darkTheme-secondary-muted">
          <Link href="/help" className="hover:text-dark dark:hover:text-white">Help Center</Link>
          <span>•</span>
          <Link href="/terms" className="hover:text-dark dark:hover:text-white">Terms</Link>
          <span>•</span>
          <Link href="/privacy" className="hover:text-dark dark:hover:text-white">Privacy</Link>
          <span>•</span>
          <span>© {new Date().getFullYear()} XerinMarket</span>
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
            <h2 className="mb-4 text-3xl font-bold leading-tight text-white xl:text-4xl">
              Secure access to your XerinMarket account
            </h2>

            <p className="mb-9 leading-relaxed text-white/80">
              Recover your account safely and continue shopping, selling, managing
              orders and tracking deliveries with confidence.
            </p>

            <ul className="space-y-5">
              {FEATURES.map((feature) => (
                <li key={feature.title} className="flex items-start gap-3.5">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/10 text-white">
                    {feature.icon}
                  </span>

                  <div>
                    <p className="text-sm font-semibold text-white">{feature.title}</p>
                    <p className="text-sm text-white/70">{feature.description}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex items-center gap-6 text-sm text-white/80">
            <span className="flex items-center gap-1.5">
              <UsersIcon />
              Seller marketplace
            </span>

            <span className="flex items-center gap-1.5">
              <span className="text-yellow-400">
                <StarIcon />
              </span>
              Backend-sourced reviews
            </span>

            <span>Live order records</span>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ForgotPassword;
