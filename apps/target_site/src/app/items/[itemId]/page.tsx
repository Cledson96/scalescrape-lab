import React from "react";

import { DetailPage } from "../../../components/detail-page";
import { findRecord } from "../../../lib/data";

type PageProps = {
  params: Promise<{ itemId: string }>;
};

export default async function Page({ params }: PageProps) {
  const { itemId } = await params;
  return <DetailPage record={await findRecord(itemId)} />;
}
