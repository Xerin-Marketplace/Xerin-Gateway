"use client";

import { ReactNode, useEffect } from "react";
import { authStorage } from "@/lib/auth/storage";
import { useAuthStore } from "@/store/useAuthStore";

type AuthBootstrapProps = {
  children: ReactNode;
};

export default function AuthBootstrap({ children }: AuthBootstrapProps) {
  const setSession = useAuthStore((state) => state.setSession);
  const setTokens = useAuthStore((state) => state.setTokens);

  useEffect(() => {
    const session = authStorage.getSession();

    if (!session?.access_token) return;

    if (session.user?.id) {
      setSession({
        access_token: session.access_token,
        refresh_token: session.refresh_token,
        token_type: session.token_type,
        user: {
          ...session.user,
          id: String(session.user.id),
        },
      });

      return;
    }

    setTokens({
      access_token: session.access_token,
      refresh_token: session.refresh_token,
      token_type: session.token_type,
    });
  }, [setSession, setTokens]);

  return <>{children}</>;
}
