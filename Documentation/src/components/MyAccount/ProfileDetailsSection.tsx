"use client";

import React, { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { useUserProfile } from "@/hooks/useUserProfile";

type ProfileDetailsSectionProps = {
  isActive: boolean;
};

const getStringValue = (value: unknown) => {
  return typeof value === "string" ? value.trim() : "";
};

const getErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
};

const ProfileDetailsSection = ({ isActive }: ProfileDetailsSectionProps) => {
  const { profile, isLoadingProfile, isFetchingProfile, updateProfile, isUpdatingProfile } =
    useUserProfile();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");

  useEffect(() => {
    if (!profile) {
      return;
    }

    setFirstName(getStringValue(profile.first_name));
    setLastName(getStringValue(profile.last_name));
    setPhone(getStringValue(profile.phone));
  }, [profile]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    try {
      await updateProfile({
        first_name: firstName.trim() || null,
        last_name: lastName.trim() || null,
        phone: phone.trim() || null,
      });

      toast.success("Profile updated successfully.");
    } catch (error) {
      toast.error(getErrorMessage(error, "Unable to update profile."));
    }
  };

  return (
    <div
      className={`xl:max-w-[770px] w-full bg-white dark:bg-darkTheme-card rounded-xl shadow-1 py-9.5 px-4 sm:px-7.5 xl:px-10 ${
        isActive ? "block" : "hidden"
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-5 mb-7">
        <div>
          <h3 className="text-xl font-semibold text-dark dark:text-white">
            Account Details
          </h3>
          <p className="mt-2 text-custom-sm text-dark-4 dark:text-darkTheme-secondary-muted">
            Update your buyer profile information from your Xerin account.
          </p>
        </div>

        {isFetchingProfile && (
          <span className="text-custom-xs text-dark-4 dark:text-darkTheme-secondary-muted">
            Refreshing profile...
          </span>
        )}
      </div>

      {isLoadingProfile ? (
        <div className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color p-5 text-custom-sm text-dark-4 dark:text-darkTheme-secondary-muted">
          Loading profile...
        </div>
      ) : (
        <>
          <div className="mb-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color p-5">
              <p className="text-custom-sm text-dark-4 dark:text-darkTheme-secondary-muted">
                Email
              </p>
              <p className="mt-2 font-medium text-dark dark:text-white">
                {profile?.email ?? "No email available"}
              </p>
            </div>

            <div className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color p-5">
              <p className="text-custom-sm text-dark-4 dark:text-darkTheme-secondary-muted">
                Account Status
              </p>
              <p className="mt-2 font-medium text-dark dark:text-white">
                {profile?.status ?? "Active"}
              </p>
            </div>

            <div className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color p-5">
              <p className="text-custom-sm text-dark-4 dark:text-darkTheme-secondary-muted">
                Verification
              </p>
              <p className="mt-2 font-medium text-dark dark:text-white">
                {profile?.is_verified ? "Verified" : "Not verified"}
              </p>
            </div>

            <div className="rounded-lg border border-gray-3 dark:border-darkTheme-border-color p-5">
              <p className="text-custom-sm text-dark-4 dark:text-darkTheme-secondary-muted">
                Account Type
              </p>
              <p className="mt-2 font-medium text-dark dark:text-white">
                {profile?.account_type ?? "customer"}
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-5">
              <div>
                <label htmlFor="profileFirstName" className="block mb-2.5 dark:text-darkTheme-body-color">
                  First Name
                </label>

                <input
                  type="text"
                  id="profileFirstName"
                  value={firstName}
                  onChange={(event) => setFirstName(event.target.value)}
                  disabled={isUpdatingProfile}
                  placeholder="First name"
                  className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20 disabled:opacity-70"
                />
              </div>

              <div>
                <label htmlFor="profileLastName" className="block mb-2.5 dark:text-darkTheme-body-color">
                  Last Name
                </label>

                <input
                  type="text"
                  id="profileLastName"
                  value={lastName}
                  onChange={(event) => setLastName(event.target.value)}
                  disabled={isUpdatingProfile}
                  placeholder="Last name"
                  className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20 disabled:opacity-70"
                />
              </div>
            </div>

            <div className="mb-6">
              <label htmlFor="profilePhone" className="block mb-2.5 dark:text-darkTheme-body-color">
                Phone
              </label>

              <input
                type="text"
                id="profilePhone"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                disabled={isUpdatingProfile}
                placeholder="+255..."
                className="rounded-md border border-gray-3 dark:border-darkTheme-border-color bg-gray-1 dark:bg-darkTheme-secondary-bg dark:text-darkTheme-body-color placeholder:text-dark-4 dark:placeholder:text-darkTheme-secondary-muted w-full py-2.5 px-5 outline-none duration-200 focus:border-transparent focus:shadow-input focus:ring-2 focus:ring-blue/20 disabled:opacity-70"
              />
            </div>

            <button
              type="submit"
              disabled={isUpdatingProfile}
              className="inline-flex font-medium text-white bg-blue py-3 px-7 rounded-md ease-out duration-200 hover:bg-blue-dark disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {isUpdatingProfile ? "Saving..." : "Save Profile"}
            </button>
          </form>
        </>
      )}
    </div>
  );
};

export default ProfileDetailsSection;
