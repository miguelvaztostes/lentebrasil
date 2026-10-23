import type { Metadata } from "next";
import { HealthDashboard } from "@/components/HealthDashboard";

export const metadata: Metadata = { title: "Saúde" };
export default function Page() {
  return <div className="container-page py-16"><HealthDashboard code="3543402" /></div>;
}

