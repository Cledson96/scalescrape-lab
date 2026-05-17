import React from "react";

import { ItemsPage } from "../../../components/items-page";
import { getLocalRecords, paginateRecords } from "../../../lib/data";
import { getPageNumber } from "../../../lib/routes";

type PageProps = {
  searchParams?: Promise<{ page?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const params = searchParams ? await searchParams : undefined;
  const pageNumber = getPageNumber(params);
  if (pageNumber % 2 === 0) {
    throw new Error("erro intermitente simulado");
  }

  const records = getLocalRecords({ prefix: "unstable", total: 120 });
  const page = paginateRecords(records, pageNumber, 12);
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
