import { IndicatorDetail } from "@/components/IndicatorDetail";

export default async function Page({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<{ municipality?: string }> }) {
  const { slug } = await params;
  const { municipality } = await searchParams;
  return <div className="container-page py-16"><IndicatorDetail code={slug} municipalityCode={municipality} /></div>;
}

