import React from "react";

import { ItemsPage } from "../../components/items-page";
import { getLocalRecords, paginateRecords } from "../../lib/data";
import { getPageNumber } from "../../lib/routes";

type PageProps = {
  searchParams?: Promise<{ page?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const params = searchParams ? await searchParams : undefined;
  const records = getLocalRecords({ prefix: "normal", total: 240 });
  const page = paginateRecords(records, getPageNumber(params), 12);

  return (
    <ItemsPage
      title="Dataset publico sintetico"
      subtitle="Fonte local estavel para scraping paginado."
      page={page}
      route="/items"
      detailRoute="/items"
    />
  );
}
