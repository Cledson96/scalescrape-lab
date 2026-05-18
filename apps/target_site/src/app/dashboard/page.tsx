import React from "react";

import { DashboardPage } from "../../components/dashboard-page";
import { fetchDashboardData } from "../../lib/dashboard-api";

export const dynamic = "force-dynamic";

type PageProps = {
  searchParams?: Promise<{
    created?: string;
    tab?: string;
    fakePage?: string;
    booksPage?: string;
    globoPage?: string;
    betanoPage?: string;
  }>;
};

function pageNumber(value: string | undefined): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

function dashboardTab(value: string | undefined) {
  if (value === "books" || value === "globo" || value === "betano") {
    return value;
  }
  return "fake";
}

export default async function Page({ searchParams }: PageProps) {
  const params = await (searchParams ?? Promise.resolve(undefined));
  const data = await fetchDashboardData({
    fakePage: pageNumber(params?.fakePage),
    booksPage: pageNumber(params?.booksPage),
    globoPage: pageNumber(params?.globoPage),
    betanoPage: pageNumber(params?.betanoPage)
  });

  return <DashboardPage {...data} activeTab={dashboardTab(params?.tab)} createdJobs={params?.created} />;
}
