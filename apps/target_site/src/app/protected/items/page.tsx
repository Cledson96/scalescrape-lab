import { cookies, headers } from "next/headers";
import React from "react";

import { ChallengePage } from "../../../components/challenge-page";
import { ItemsPage } from "../../../components/items-page";
import { antibotSimulator, AntibotAction } from "../../../lib/antibot";
import { captchaStore } from "../../../lib/captcha";
import { getLocalRecords, paginateRecords } from "../../../lib/data";
import { getPageNumber } from "../../../lib/routes";

type PageProps = {
  searchParams?: Promise<{ page?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const [params, headerStore, cookieStore] = await Promise.all([
    searchParams ?? Promise.resolve(undefined),
    headers(),
    cookies()
  ]);
  const pageNumber = getPageNumber(params);
  const proxyId = headerStore.get("x-lab-proxy-id") ?? "direct";
  const sessionId = cookieStore.get("lab_session")?.value ?? `anonymous-${proxyId}`;
  const decision = antibotSimulator.evaluate({
    sessionId,
    proxyId,
    path: "/protected/items",
    userAgent: headerStore.get("user-agent"),
    hasClearanceCookie: cookieStore.get("lab_clearance")?.value === "ok"
  });

  if (decision.action === AntibotAction.Delay) {
    await new Promise((resolve) => setTimeout(resolve, 400));
  }

  if (decision.action === AntibotAction.Challenge || decision.action === AntibotAction.Forbid) {
    const challenge = captchaStore.create();
    return <ChallengePage challengeId={challenge.challengeId} />;
  }

  const records = getLocalRecords({ prefix: "protected", total: 240 });
  const page = paginateRecords(records, pageNumber, 12);
  return (
    <ItemsPage
      title="Dataset protegido"
      subtitle="Mesmo conteudo sintetico sob avaliacao anti-bot local."
      page={page}
      route="/protected/items"
      detailRoute="/items"
    />
  );
}
