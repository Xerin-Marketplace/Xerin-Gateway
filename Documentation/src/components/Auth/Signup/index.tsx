"use client";

import Image from "next/image";
import Link from "next/link";
import React, { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { authApi } from "@/lib/api/endpoints/auth";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/hooks/useAuth";
import type { AuthTokenResponse } from "@/types/api/auth";

const COUNTRY_CODE = "255";

const splitFullName = (fullName: string) => {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);

  const firstName = parts[0] || "";
  const lastName = parts.slice(1).join(" ") || "";

  return {
    first_name: firstName,
    last_name: lastName || firstName,
  };
};

const hasAuthToken = (response: unknown): response is AuthTokenResponse => {
  return (
    typeof response === "object" &&
    response !== null &&
    "access_token" in response &&
    typeof (response as { access_token?: unknown }).access_token === "string"
  );
};

// Tanzanian mobile numbers: 9 digits after the 255 country code,
// the local part starts with 6 or 7 (e.g. 712345678, 754123456)
const isValidLocalPhone = (localDigits: string) => /^[67]\d{8}$/.test(localDigits);

// --- simple inline icons (no extra dependency needed) ---
const EyeIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const EyeOffIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 7 11 7a13.16 13.16 0 0 1-3.19 3.94M6.61 6.61A13.14 13.14 0 0 0 1 11s4 7 11 7a9.14 9.14 0 0 0 5.39-1.61M9.53 9.53a3 3 0 0 0 4.24 4.24" />
    <path d="M1 1l22 22" />
  </svg>
);

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

interface PasswordRule {
  label: string;
  test: (value: string) => boolean;
}

const PASSWORD_RULES: PasswordRule[] = [
  { label: "At least 8 characters", test: (v) => v.length >= 8 },
  { label: "One uppercase letter (A-Z)", test: (v) => /[A-Z]/.test(v) },
  { label: "One lowercase letter (a-z)", test: (v) => /[a-z]/.test(v) },
  { label: "One number (0-9)", test: (v) => /\d/.test(v) },
  { label: "One special character (!@#$...)", test: (v) => /[^A-Za-z0-9]/.test(v) },
];

const Signup = () => {
  const router = useRouter();
  const { setSession } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState(""); // local part only, no country code
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);

  const isPasswordMismatch = useMemo(() => {
    return Boolean(confirmPassword) && password !== confirmPassword;
  }, [password, confirmPassword]);

  const passwordChecks = useMemo(
    () => PASSWORD_RULES.map((rule) => ({ ...rule, passed: rule.test(password) })),
    [password]
  );

  const isPasswordStrong = useMemo(
    () => passwordChecks.every((check) => check.passed),
    [passwordChecks]
  );

  const isPhoneValid = useMemo(() => {
    if (!phone) return true; // optional field, empty is fine
    return isValidLocalPhone(phone);
  }, [phone]);

  const handlePhoneChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    // keep digits only, strip a leading 0 (people often type 0712... instead of 712...)
    let digits = event.target.value.replace(/\D/g, "");
    if (digits.startsWith("0")) {
      digits = digits.slice(1);
    }
    digits = digits.slice(0, 9);
    setPhone(digits);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!fullName.trim() || !email.trim() || !password || !confirmPassword) {
      toast.error("Please fill in all required fields.");
      return;
    }

    if (phone && !isValidLocalPhone(phone)) {
      toast.error("Enter a valid phone number, e.g. 712 345 678.");
      return;
    }

    if (!isPasswordStrong) {
      toast.error("Please choose a stronger password that meets all requirements.");
      return;
    }

    if (password !== confirmPassword) {
      toast.error("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      const nameParts = splitFullName(fullName);

      const response = await authApi.registerBuyer({
        ...nameParts,
        email: email.trim(),
        phone: phone ? `${COUNTRY_CODE}${phone}` : undefined,
        password,
      });

      if (hasAuthToken(response)) {
        setSession(response);
        toast.success("Account created successfully.");
        router.push("/my-account");
        return;
      }

      toast.success("Account created successfully. Please sign in.");
      router.push("/signin");
    } catch (error) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Unable to create account. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="overflow-hidden py-20 bg-gray-2 dark:bg-darkTheme-bg min-h-screen flex items-center">
      <div className="max-w-[1170px] w-full mx-auto px-4 sm:px-8 xl:px-0">
        <div className="max-w-[570px] w-full mx-auto rounded-xl bg-white dark:bg-darkTheme-card shadow-1 p-4 sm:p-7.5 xl:p-11">
          <div className="text-center mb-8">
            {/* Xerin Logo */}
            <Link href="/" className="inline-flex justify-center mb-6">
              <Image
                src="/images/logo/logo.png"
                alt="Xerin Marketplace Logo"
                width={180}
                height={60}
                priority
                className="object-contain"
              />
            </Link>

            <h2 className="font-semibold text-xl sm:text-2xl xl:text-heading-5 text-dark dark:text-white mb-1.5">
              Create an Account
            </h2>

            <p className="dark:text-darkTheme-body-color">Enter your details below</p>
          </div>

          {/* Seller Registration Notice */}
          <div className="mb-8 rounded-xl border border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/30 p-4">
            <div className="flex items-start gap-3">
              <div className="text-2xl">💡</div>

              <div className="text-left">
                <h3 className="font-semibold text-dark dark:text-white mb-1">Are you a seller?</h3>

                <p className="text-sm text-dark-4 dark:text-darkTheme-secondary-muted leading-relaxed">
                  If you want to sell products on Xerin Marketplace, please create a seller account
                  instead.
                </p>

                <Link
                  href="/seller/register"
                  className="inline-flex mt-3 text-sm font-medium text-blue hover:underline"
                >
                  Register as Seller →
                </Link>
              </div>
            </div>
          </div>

          <div className="mt-5.5">
            <form onSubmit={handleSubmit}>
              <div className="mb-5">
                <label htmlFor="name" className="block mb-2.5 dark:text-darkTheme-body-color">
                  Full Name <span className="text-red">*</span>
                </label>

                <input
                  type="text"
                  name="name"
                  id="name"
                  placeholder="Enter your full name"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  autoComplete="name"
                  disabled={isSubmitting}
                  className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-3 px-5 outline-none duration-200 focus:border-transparent focus:ring-2 focus:ring-blue/20 disabled:cursor-not-allowed disabled:opacity-70"
                />
              </div>

              <div className="mb-5">
                <label htmlFor="email" className="block mb-2.5 dark:text-darkTheme-body-color">
                  Email Address <span className="text-red">*</span>
                </label>

                <input
                  type="email"
                  name="email"
                  id="email"
                  placeholder="Enter your email address"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  disabled={isSubmitting}
                  className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-3 px-5 outline-none duration-200 focus:border-transparent focus:ring-2 focus:ring-blue/20 disabled:cursor-not-allowed disabled:opacity-70"
                />
              </div>

              <div className="mb-5">
                <label htmlFor="phone" className="block mb-2.5 dark:text-darkTheme-body-color">
                  Phone Number{" "}
                  <span className="text-dark-4 dark:text-darkTheme-secondary-muted">(optional)</span>
                </label>

                <div
                  className={`flex items-stretch rounded-lg border bg-gray-1 dark:bg-darkTheme-secondary-bg overflow-hidden focus-within:ring-2 focus-within:ring-blue/20 ${
                    phone && !isPhoneValid
                      ? "border-red"
                      : "border-gray-3 dark:border-darkTheme-border-color"
                  }`}
                >
                  <span className="flex items-center gap-1 px-4 text-dark-4 dark:text-darkTheme-secondary-muted bg-gray-2 dark:bg-darkTheme-bg border-r border-gray-3 dark:border-darkTheme-border-color select-none">
                    🇹🇿 +{COUNTRY_CODE}
                  </span>

                  <input
                    type="tel"
                    inputMode="numeric"
                    name="phone"
                    id="phone"
                    placeholder="712 345 678"
                    value={phone}
                    onChange={handlePhoneChange}
                    autoComplete="tel-national"
                    disabled={isSubmitting}
                    aria-invalid={phone ? !isPhoneValid : false}
                    className="flex-1 min-w-0 py-3 px-4 bg-transparent outline-none dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted disabled:cursor-not-allowed disabled:opacity-70"
                  />
                </div>

                {phone && !isPhoneValid && (
                  <p className="mt-2 text-sm text-red">
                    Enter a valid number without the leading 0, e.g. 712345678.
                  </p>
                )}
              </div>

              <div className="mb-5">
                <label htmlFor="password" className="block mb-2.5 dark:text-darkTheme-body-color">
                  Password <span className="text-red">*</span>
                </label>

                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    id="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="new-password"
                    disabled={isSubmitting}
                    className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-3 pl-5 pr-12 outline-none duration-200 focus:border-transparent focus:ring-2 focus:ring-blue/20 disabled:cursor-not-allowed disabled:opacity-70"
                  />

                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    tabIndex={-1}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute inset-y-0 right-0 flex items-center px-4 text-dark-4 dark:text-darkTheme-secondary-muted hover:text-dark dark:hover:text-white"
                  >
                    {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                  </button>
                </div>

                {/* Password strength checklist */}
                {password && (
                  <ul className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5">
                    {passwordChecks.map((check) => (
                      <li
                        key={check.label}
                        className={`flex items-center gap-2 text-sm ${
                          check.passed
                            ? "text-green-600 dark:text-green-400"
                            : "text-dark-4 dark:text-darkTheme-secondary-muted"
                        }`}
                      >
                        <span
                          className={`flex items-center justify-center w-4 h-4 rounded-full border shrink-0 ${
                            check.passed
                              ? "bg-green-600 border-green-600 text-white"
                              : "border-gray-3 dark:border-darkTheme-border-color"
                          }`}
                        >
                          {check.passed && <CheckIcon />}
                        </span>
                        {check.label}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="mb-5.5">
                <label
                  htmlFor="re-type-password"
                  className="block mb-2.5 dark:text-darkTheme-body-color"
                >
                  Re-type Password <span className="text-red">*</span>
                </label>

                <div className="relative">
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    name="re-type-password"
                    id="re-type-password"
                    placeholder="Re-type your password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    autoComplete="new-password"
                    disabled={isSubmitting}
                    aria-invalid={isPasswordMismatch}
                    className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-3 pl-5 pr-12 outline-none duration-200 focus:border-transparent focus:ring-2 focus:ring-blue/20 disabled:cursor-not-allowed disabled:opacity-70"
                  />

                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((prev) => !prev)}
                    tabIndex={-1}
                    aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                    className="absolute inset-y-0 right-0 flex items-center px-4 text-dark-4 dark:text-darkTheme-secondary-muted hover:text-dark dark:hover:text-white"
                  >
                    {showConfirmPassword ? <EyeOffIcon /> : <EyeIcon />}
                  </button>
                </div>

                {isPasswordMismatch && (
                  <p className="mt-2 text-sm text-red">Passwords do not match.</p>
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex justify-center font-medium text-white bg-dark py-3 px-6 rounded-lg ease-out duration-200 hover:bg-blue mt-7.5 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isSubmitting ? "Creating account..." : "Create Account"}
              </button>

              <p className="text-center mt-6">
                <span className="dark:text-darkTheme-body-color">Already have an account?</span>

                <Link
                  href="/signin"
                  className="text-dark dark:text-darkTheme-body-color hover:text-blue pl-2"
                >
                  Sign in Now
                </Link>
              </p>

              <p className="text-center mt-3 text-sm">
                <span className="dark:text-darkTheme-body-color">Want to sell on Xerin?</span>

                <Link
                  href="/seller/register"
                  className="text-dark dark:text-darkTheme-body-color hover:text-blue pl-2"
                >
                  Register as Seller
                </Link>
              </p>

              <p className="text-center mt-3 text-sm">
                <span className="dark:text-darkTheme-body-color">Already have an OTP?</span>

                <Link
                  href="/verify-otp"
                  className="text-dark dark:text-darkTheme-body-color hover:text-blue pl-2"
                >
                  Verify Account
                </Link>
              </p>
            </form>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Signup;