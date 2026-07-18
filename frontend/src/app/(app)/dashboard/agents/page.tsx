import AgentDashboard from "@/components/AgentGraph/AgentDashboard";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Giám sát Multi-Agent | SchoolAI Analytics",
  description: "Sơ đồ định tuyến và số liệu vận hành thật của hệ thống Multi-Agent",
};

export default function AgentsDashboardPage() {
  return (
    <div className="p-6 h-[calc(100vh-64px)] w-full max-w-[1600px] mx-auto">
      <AgentDashboard />
    </div>
  );
}
