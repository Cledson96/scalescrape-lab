import React from "react";

import { ItemsPage } from "../../../components/items-page";
import { getExternalRecords, paginateRecords } from "../../../lib/data";
import { getPageNumber } from "../../../lib/routes";

type PageProps = {
  searchParams?: Promise<{ page?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const params = searchParams ? await searchParams : undefined;
  const records = await getExternalRecords(500);
  const page = paginateRecords(records, getPageNumber(params), 12);

  return (
    <ItemsPage
      title="Fonte fake externa em massa"
      subtitle="RandomUser normalizado com cache e fallback local."
      page={page}
      route="/external/items"
      detailRoute="/external/items"
    />
  );
}
