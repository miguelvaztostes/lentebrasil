import type { Metadata } from "next";
import { Suspense } from "react";
import { EducationPortal } from "@/components/EducationPortal";
import { LoadingState } from "@/components/LoadingState";

export const metadata: Metadata = { title: "Educação" };
export default function Page() {
  return <div className="container-page py-16"><Suspense fallback={<LoadingState label="Abrindo painel educacional…" />}><EducationPortal /></Suspense></div>;
}

