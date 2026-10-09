import { IndicatorDetail } from "@/components/IndicatorDetail";

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <div className="container-page py-16"><IndicatorDetail code={slug} /></div>;
}

