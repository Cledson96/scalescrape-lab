import React from "react";

import { DashboardPage } from "../../components/dashboard-page";
import { fetchDashboardData } from "../../lib/dashboard-api";

export const dynamic = "force-dynamic";

type PageProps = {
  searchParams?: Promise<{ created?: string }>;
};

export default async function Page({ searchParams }: PageProps) {
  const [data, params] = await Promise.all([
    fetchDashboardData(),
    searchParams ?? Promise.resolve(undefined)
  ]);

  return <DashboardPage {...data} createdJobs={params?.created} />;
}
