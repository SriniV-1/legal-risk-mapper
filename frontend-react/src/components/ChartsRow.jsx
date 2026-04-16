/**
 * ChartsRow — three Chart.js visualisations:
 * 1) Risks by category (bar)
 * 2) Severity breakdown (doughnut)
 * 3) Detection source (doughnut)
 */
import { Bar, Doughnut } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend);

export default function ChartsRow({ risks }) {
  if (!risks?.length) return null;

  // ── Aggregate ──
  const byCategory = {};
  const bySeverity = { High: 0, Medium: 0, Low: 0 };
  const bySource = { regex: 0, semantic: 0, both: 0 };
  risks.forEach((r) => {
    byCategory[r.risk_type] = (byCategory[r.risk_type] || 0) + 1;
    bySeverity[r.severity] = (bySeverity[r.severity] || 0) + 1;
    const srcs = r.sources || ["regex"];
    if (srcs.includes("regex") && srcs.includes("semantic")) bySource.both += 1;
    else if (srcs.includes("semantic")) bySource.semantic += 1;
    else bySource.regex += 1;
  });

  const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: "bottom", labels: { font: { size: 11, family: "Inter" }, padding: 12, usePointStyle: true } },
    },
  };

  const barData = {
    labels: Object.keys(byCategory),
    datasets: [{
      label: "Risks",
      data: Object.values(byCategory),
      backgroundColor: "rgba(37, 99, 235, 0.85)",
      borderRadius: 8,
      barThickness: 28,
    }],
  };

  const sevData = {
    labels: ["High", "Medium", "Low"],
    datasets: [{
      data: [bySeverity.High, bySeverity.Medium, bySeverity.Low],
      backgroundColor: ["#ef4444", "#f59e0b", "#10b981"],
      borderWidth: 0,
    }],
  };

  const srcData = {
    labels: ["Pattern only", "Semantic only", "Confirmed (both)"],
    datasets: [{
      data: [bySource.regex, bySource.semantic, bySource.both],
      backgroundColor: ["#6366f1", "#8b5cf6", "#2563eb"],
      borderWidth: 0,
    }],
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-fade-in">
      <ChartCard title="By Category">
        <Bar data={barData} options={{ ...chartOpts, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }} />
      </ChartCard>
      <ChartCard title="Severity">
        <Doughnut data={sevData} options={chartOpts} />
      </ChartCard>
      <ChartCard title="Detection Source">
        <Doughnut data={srcData} options={chartOpts} />
      </ChartCard>
    </div>
  );
}

function ChartCard({ title, children }) {
  return (
    <div className="card p-5">
      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">{title}</h3>
      <div className="h-56">{children}</div>
    </div>
  );
}
