import React from "react";

import { ItemsPage } from "../../../components/items-page";
import { getLocalRecords, paginateRecords } from "../../../lib/data";
import { getPageNumber } from "../../../lib/routes";
import { ITEM_PAGE_SIZE, UNSTABLE_RECORD_TOTAL } from "../../../lib/site-contracts";

type PageProps = {
  searchParams?: Promise<{ page?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const params = searchParams ? await searchParams : undefined;
  const pageNumber = getPageNumber(params);
  if (pageNumber % 2 === 0) {
    throw new Error("erro intermitente simulado");
  }

  const records = getLocalRecords({ prefix: "unstable", total: UNSTABLE_RECORD_TOTAL });
  const page = paginateRecords(records, pageNumber, ITEM_PAGE_SIZE);
  return (
    <ItemsPage
      title="Fonte instavel"
      subtitle="Paginas pares retornam erro para validar retry."
      page={page}
      route="/unstable/items"
      detailRoute="/items"
    />
  );
}
