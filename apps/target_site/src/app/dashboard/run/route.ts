import { redirect } from "next/navigation";

import { createDashboardJobs, type DashboardJobSource } from "../../../lib/dashboard-api";

function normalizeSource(value: FormDataEntryValue | null): DashboardJobSource {
  if (
    value === "fake-target"
    || value === "books-to-scrape"
    || value === "globo-home"
    || value === "betano-football"
    || value === "all"
  ) {
    return value;
  }
  return "all";
}

export async function POST(request: Request) {
  const form = await request.formData();
  const source = normalizeSource(form.get("source"));
  let target = "/dashboard?created=erro";

  try {
    const jobIds = await createDashboardJobs(source);
    target = `/dashboard?created=${jobIds.join(",")}`;
  } catch {
    target = "/dashboard?created=erro";
  }

  redirect(target);
}
