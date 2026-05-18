import React from "react";

import { LoginPage } from "../../components/login-page";
import { normalizeNextPath } from "../../lib/auth";
import { captchaStore } from "../../lib/captcha";

type PageProps = {
  searchParams?: Promise<{ next?: string | string[]; error?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const params = searchParams ? await searchParams : undefined;
  const rawNext = Array.isArray(params?.next) ? params?.next[0] : params?.next;
  const rawError = Array.isArray(params?.error) ? params?.error[0] : params?.error;
  const challenge = captchaStore.create();
  return (
    <LoginPage
      challengeId={challenge.challengeId}
      nextPath={normalizeNextPath(rawNext)}
      error={rawError}
    />
  );
}
