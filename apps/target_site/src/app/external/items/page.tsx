import { ItemsPage } from "../../../components/items-page";
import { getExternalRecords, paginateRecords } from "../../../lib/data";
import { getPageNumber } from "../../../lib/routes";
import { EXTERNAL_RECORD_TOTAL, ITEM_PAGE_SIZE } from "../../../lib/site-contracts";

type PageProps = {
  searchParams?: Promise<{ page?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const params = searchParams ? await searchParams : undefined;
  const records = await getExternalRecords(EXTERNAL_RECORD_TOTAL);
  const page = paginateRecords(records, getPageNumber(params), ITEM_PAGE_SIZE);

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
