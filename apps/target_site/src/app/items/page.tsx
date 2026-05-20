import { ItemsPage } from "../../components/items-page";
import { getLocalRecords, paginateRecords } from "../../lib/data";
import { getPageNumber } from "../../lib/routes";
import { ITEM_PAGE_SIZE, LOCAL_RECORD_TOTAL } from "../../lib/site-contracts";

type PageProps = {
  searchParams?: Promise<{ page?: string | string[] }>;
};

export default async function Page({ searchParams }: PageProps) {
  const params = searchParams ? await searchParams : undefined;
  const records = getLocalRecords({ prefix: "normal", total: LOCAL_RECORD_TOTAL });
  const page = paginateRecords(records, getPageNumber(params), ITEM_PAGE_SIZE);

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
