import { r as React, j as jsxRuntime } from "./index-D7ltaYVC.js";
import { p as publicClient } from "./publicClient-BdJTy9AM.js";
import { e as getErrorMessage } from "./forms-ZJa1TpnO.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";
import { R as ResponsiveContainer, E as BarChart, X as XAxis, Y as YAxis, F as Tooltip, H as Bar } from "./BarChart-CcHEhvSw.js";
import { C as CartesianGrid, L as Line } from "./Line-Cimfn-YW.js";
import { L as LineChart } from "./LineChart-BnyFOdmS.js";

const { jsx, jsxs, Fragment } = jsxRuntime;

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.07)",
};

const formatMoney = (value) =>
  `KES ${Number(value ?? 0).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const formatPercent = (value) =>
  `${Number(value ?? 0).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;

const formatDate = (value) => {
  if (!value) return "--";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString("en-KE", { month: "short", day: "numeric", year: "numeric" });
};

const formatMonth = (value) => {
  if (!value) return "--";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value).slice(0, 7) : parsed.toLocaleDateString("en-KE", { month: "short", year: "2-digit" });
};

const riskTone = (level) =>
  (
    {
      high: "border-rose-500/30 bg-rose-500/10 text-rose-200",
      medium: "border-amber-500/30 bg-amber-500/10 text-amber-200",
      low: "border-sky-500/30 bg-sky-500/10 text-sky-200",
    }[String(level || "").toLowerCase()] ?? "border-slate-500/30 bg-slate-500/10 text-slate-300"
  );

const confidenceTone = (value) =>
  (
    {
      high: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
      medium: "border-amber-500/30 bg-amber-500/10 text-amber-200",
      low: "border-slate-500/30 bg-slate-500/10 text-slate-300",
    }[String(value || "").toLowerCase()] ?? "border-slate-500/30 bg-slate-500/10 text-slate-300"
  );

const trendTone = (value) =>
  (
    {
      growing: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
      stable: "border-sky-500/30 bg-sky-500/10 text-sky-200",
      declining: "border-rose-500/30 bg-rose-500/10 text-rose-200",
    }[String(value || "").toLowerCase()] ?? "border-slate-500/30 bg-slate-500/10 text-slate-300"
  );

const segmentTone = (segment) =>
  (
    {
      active: "bg-emerald-500/15 text-emerald-300",
      trial: "bg-sky-500/15 text-sky-300",
      suspended: "bg-amber-500/15 text-amber-300",
      cancelled: "bg-rose-500/15 text-rose-300",
      archived: "bg-slate-500/15 text-slate-300",
      total: "bg-white/10 text-white",
    }[String(segment || "").toLowerCase()] ?? "bg-white/10 text-slate-300"
  );

function StatCard({ label, value, detail, tone = "text-white" }) {
  return jsxs("div", {
    className: "rounded-2xl p-4",
    style: panelStyle,
    children: [
      jsx("p", { className: "text-[11px] uppercase tracking-wide text-slate-500", children: label }),
      jsx("p", { className: `mt-2 text-2xl font-semibold ${tone}`, children: value }),
      jsx("p", { className: "mt-1 text-xs text-slate-500", children: detail }),
    ],
  });
}

function PlatformRevenueAnalyticsPage() {
  const [overview, setOverview] = React.useState(null);
  const [kpis, setKpis] = React.useState(null);
  const [revenue, setRevenue] = React.useState(null);
  const [growth, setGrowth] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    let active = true;

    (async () => {
      setLoading(true);
      setError(null);
      const [overviewResult, kpiResult, revenueResult, growthResult] = await Promise.allSettled([
        publicClient.get("/platform/analytics/overview/"),
        publicClient.get("/platform/analytics/business-kpis/"),
        publicClient.get("/platform/analytics/revenue/"),
        publicClient.get("/platform/analytics/tenant-growth/"),
      ]);

      if (!active) return;

      if (overviewResult.status === "fulfilled") {
        setOverview(overviewResult.value.data);
      }
      if (kpiResult.status === "fulfilled") {
        setKpis(kpiResult.value.data);
      }
      if (revenueResult.status === "fulfilled") {
        setRevenue(revenueResult.value.data);
      }
      if (growthResult.status === "fulfilled") {
        setGrowth(growthResult.value.data);
      }

      const failedResult = [overviewResult, kpiResult, revenueResult, growthResult].find((result) => result.status === "rejected");
      if (failedResult) {
        setError(getErrorMessage(failedResult.reason, "Unable to load revenue analytics."));
      }

      setLoading(false);
    })();

    return () => {
      active = false;
    };
  }, []);

  const trendPoints = React.useMemo(
    () =>
      (revenue?.points ?? []).map((row) => ({
        month: formatMonth(row.month),
        paid: Number(row.paid || 0),
        invoiced: Number(row.invoiced || 0),
      })),
    [revenue],
  );

  const growthPoints = React.useMemo(
    () =>
      (growth?.by_month ?? []).map((row) => ({
        month: formatMonth(row.month),
        created: Number(row.count || row.created || 0),
      })),
    [growth],
  );

  const planBreakdown = React.useMemo(
    () =>
      (revenue?.plan_breakdown ?? []).map((row) => ({
        plan: row.plan__name ?? row.plan__code ?? "No plan",
        code: row.plan__code ?? "NO_PLAN",
        count: Number(row.count || 0),
        total: Number(row.total || 0),
      })),
    [revenue],
  );

  const forecast = kpis?.forecast ?? revenue?.forecast ?? {};
  const riskSummary = kpis?.risk_summary ?? revenue?.risk_summary ?? { total: 0, high: 0, medium: 0, low: 0 };
  const riskSignals = revenue?.risk_signals ?? [];
  const tenantSegments = kpis?.tenant_segments ?? overview?.tenants ?? {};
  const currentMonthPaid = Number(overview?.revenue?.paid_this_month || 0);
  const currentMonthInvoiced = Number(overview?.revenue?.invoiced_this_month || 0);
  const currentMonthGap = Math.max(0, currentMonthInvoiced - currentMonthPaid);
  const planContributionTotal = planBreakdown.reduce((sum, row) => sum + row.total, 0);

  return jsxs("div", {
    className: "grid grid-cols-12 gap-6",
    children: [
      jsx(PageHero, {
        badge: "PLATFORM",
        badgeColor: "violet",
        title: "Revenue Analytics",
        subtitle: "Track subscription health, collection pace, forecast direction, and the tenants most likely to churn or miss renewal.",
        icon: "KES",
      }),
      error
        ? jsx("div", {
            className: "col-span-12 rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200",
            children: error,
          })
        : null,
      loading
        ? jsx("div", {
            className: "col-span-12 rounded-2xl p-6 text-center text-sm text-slate-400",
            style: panelStyle,
            children: "Loading revenue analytics...",
          })
        : null,
      !loading
        ? jsxs(Fragment, {
            children: [
              jsx("section", {
                className: "col-span-12 grid gap-3 lg:grid-cols-6",
                children: [
                  {
                    label: "MRR",
                    value: formatMoney(kpis?.kpis?.mrr),
                    detail: "Current monthly recurring run rate",
                    tone: "text-emerald-200",
                  },
                  {
                    label: "ARR",
                    value: formatMoney(kpis?.kpis?.arr),
                    detail: "Annualized recurring revenue",
                    tone: "text-sky-200",
                  },
                  {
                    label: "ARPT",
                    value: formatMoney(kpis?.kpis?.arpt),
                    detail: "Average recurring revenue per tenant",
                    tone: "text-white",
                  },
                  {
                    label: "Collected This Month",
                    value: formatMoney(currentMonthPaid),
                    detail: `${overview?.revenue?.overdue_invoices ?? 0} overdue invoice(s) still open`,
                    tone: "text-emerald-200",
                  },
                  {
                    label: "Invoiced This Month",
                    value: formatMoney(currentMonthInvoiced),
                    detail: currentMonthGap > 0 ? `${formatMoney(currentMonthGap)} still waiting to settle` : "Collections are matching current invoicing",
                    tone: currentMonthGap > 0 ? "text-amber-200" : "text-sky-200",
                  },
                  {
                    label: "At-Risk Tenants",
                    value: String(riskSummary.total ?? 0),
                    detail: `${riskSummary.high ?? 0} high risk, ${riskSummary.medium ?? 0} medium risk`,
                    tone: (riskSummary.high ?? 0) > 0 ? "text-rose-200" : "text-white",
                  },
                ].map((item) =>
                  jsx(
                    StatCard,
                    {
                      label: item.label,
                      value: item.value,
                      detail: item.detail,
                      tone: item.tone,
                    },
                    item.label,
                  ),
                ),
              }),
              jsx("section", {
                className: "col-span-12 grid gap-4 xl:grid-cols-[1.35fr,0.65fr]",
                children: [
                  jsxs("div", {
                    className: "rounded-2xl p-6",
                    style: panelStyle,
                    children: [
                      jsx("p", {
                        className: "text-[11px] uppercase tracking-wide text-slate-500",
                        children: "Collection pulse",
                      }),
                      jsx("h2", {
                        className: "mt-2 text-lg font-semibold text-white",
                        children: "Paid versus invoiced trend",
                      }),
                      jsx("p", {
                        className: "mt-1 text-sm text-slate-400",
                        children: "Use the gap between these lines to spot months where billing issuance is outrunning collections.",
                      }),
                      trendPoints.length > 0
                        ? jsx("div", {
                            className: "mt-5 h-72",
                            children: jsx(ResponsiveContainer, {
                              width: "100%",
                              height: "100%",
                              children: jsxs(LineChart, {
                                data: trendPoints,
                                children: [
                                  jsx(CartesianGrid, { stroke: "#1e293b", strokeDasharray: "3 3" }),
                                  jsx(XAxis, { dataKey: "month", tick: { fill: "#94a3b8", fontSize: 11 } }),
                                  jsx(YAxis, {
                                    tick: { fill: "#94a3b8", fontSize: 11 },
                                    tickFormatter: (value) => Number(value).toLocaleString("en-KE", { maximumFractionDigits: 0 }),
                                  }),
                                  jsx(Tooltip, {
                                    formatter: (value, name) => [formatMoney(value), name === "paid" ? "Paid" : "Invoiced"],
                                  }),
                                  jsx(Line, {
                                    type: "monotone",
                                    dataKey: "invoiced",
                                    stroke: "#f59e0b",
                                    strokeWidth: 2,
                                    dot: false,
                                  }),
                                  jsx(Line, {
                                    type: "monotone",
                                    dataKey: "paid",
                                    stroke: "#10b981",
                                    strokeWidth: 2,
                                    dot: false,
                                  }),
                                ],
                              }),
                            }),
                          })
                        : jsx("p", {
                            className: "mt-5 rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4 text-sm text-slate-400",
                            children: "No monthly billing data available yet.",
                          }),
                    ],
                  }),
                  jsxs("div", {
                    className: "rounded-2xl p-6",
                    style: panelStyle,
                    children: [
                      jsx("p", {
                        className: "text-[11px] uppercase tracking-wide text-slate-500",
                        children: "Forecast desk",
                      }),
                      jsx("h2", {
                        className: "mt-2 text-lg font-semibold text-white",
                        children: "Forward-looking revenue posture",
                      }),
                      jsxs("div", {
                        className: "mt-4 flex flex-wrap gap-2",
                        children: [
                          jsx("span", {
                            className: `inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${trendTone(forecast.trend)}`,
                            children: String(forecast.trend || "stable").toUpperCase(),
                          }),
                          jsx("span", {
                            className: `inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${confidenceTone(forecast.confidence)}`,
                            children: `${String(forecast.confidence || "low").toUpperCase()} CONFIDENCE`,
                          }),
                        ],
                      }),
                      jsx("div", {
                        className: "mt-4 grid gap-3",
                        children: [
                          { label: "Next month forecast", value: formatMoney(forecast.next_month_revenue) },
                          { label: "Next quarter forecast", value: formatMoney(forecast.next_quarter_revenue) },
                          { label: "Growth rate", value: formatPercent(forecast.growth_rate_percent) },
                          { label: "Basis months", value: String(forecast.basis_months ?? 0) },
                        ].map((item) =>
                          jsxs(
                            "div",
                            {
                              className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4",
                              children: [
                                jsx("p", { className: "text-xs uppercase tracking-wide text-slate-500", children: item.label }),
                                jsx("p", { className: "mt-2 text-lg font-semibold text-white", children: item.value }),
                              ],
                            },
                            item.label,
                          ),
                        ),
                      }),
                      jsx("div", {
                        className: "mt-4 rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4 text-sm text-slate-300",
                        children: jsxs("div", {
                          className: "grid gap-3 sm:grid-cols-2",
                          children: [
                            jsxs("div", {
                              children: [
                                jsx("p", { className: "text-xs uppercase tracking-wide text-slate-500", children: "Collection gap" }),
                                jsx("p", { className: `mt-2 text-lg font-semibold ${currentMonthGap > 0 ? "text-amber-200" : "text-emerald-200"}`, children: formatMoney(currentMonthGap) }),
                              ],
                            }),
                            jsxs("div", {
                              children: [
                                jsx("p", { className: "text-xs uppercase tracking-wide text-slate-500", children: "New tenants this month" }),
                                jsx("p", { className: "mt-2 text-lg font-semibold text-sky-200", children: String(overview?.growth?.new_tenants_this_month ?? 0) }),
                              ],
                            }),
                          ],
                        }),
                      }),
                    ],
                  }),
                ],
              }),
              jsx("section", {
                className: "col-span-12 grid gap-4 xl:grid-cols-[0.8fr,1.2fr]",
                children: [
                  jsxs("div", {
                    className: "rounded-2xl p-6",
                    style: panelStyle,
                    children: [
                      jsx("p", {
                        className: "text-[11px] uppercase tracking-wide text-slate-500",
                        children: "Plan mix",
                      }),
                      jsx("h2", {
                        className: "mt-2 text-lg font-semibold text-white",
                        children: "Recurring revenue by plan",
                      }),
                      jsx("div", {
                        className: "mt-4 space-y-4",
                        children:
                          planBreakdown.length > 0
                            ? planBreakdown.map((row) => {
                                const share = planContributionTotal > 0 ? Math.round((row.total / planContributionTotal) * 100) : 0;
                                return jsxs(
                                  "div",
                                  {
                                    children: [
                                      jsxs("div", {
                                        className: "mb-2 flex items-center justify-between gap-3 text-sm",
                                        children: [
                                          jsxs("div", {
                                            children: [
                                              jsx("p", { className: "font-semibold text-white", children: row.plan }),
                                              jsx("p", { className: "text-xs text-slate-500", children: `${row.count} tenant(s)` }),
                                            ],
                                          }),
                                          jsx("p", { className: "font-medium text-emerald-300", children: formatMoney(row.total) }),
                                        ],
                                      }),
                                      jsx("div", {
                                        className: "h-2 rounded-full bg-white/10",
                                        children: jsx("div", {
                                          className: "h-2 rounded-full bg-emerald-500",
                                          style: { width: `${share}%` },
                                        }),
                                      }),
                                      jsx("p", { className: "mt-1 text-[11px] text-slate-500", children: `${share}% of active recurring value` }),
                                    ],
                                  },
                                  row.code,
                                );
                              })
                            : jsx("p", {
                                className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4 text-sm text-slate-400",
                                children: "No active plan contribution data yet.",
                              }),
                      }),
                    ],
                  }),
                  jsxs("div", {
                    className: "rounded-2xl p-6",
                    style: panelStyle,
                    children: [
                      jsx("p", {
                        className: "text-[11px] uppercase tracking-wide text-slate-500",
                        children: "Growth and segments",
                      }),
                      jsx("h2", {
                        className: "mt-2 text-lg font-semibold text-white",
                        children: "Tenant growth curve",
                      }),
                      growthPoints.length > 0
                        ? jsx("div", {
                            className: "mt-5 h-64",
                            children: jsx(ResponsiveContainer, {
                              width: "100%",
                              height: "100%",
                              children: jsxs(BarChart, {
                                data: growthPoints,
                                children: [
                                  jsx(CartesianGrid, { stroke: "#1e293b", strokeDasharray: "3 3" }),
                                  jsx(XAxis, { dataKey: "month", tick: { fill: "#94a3b8", fontSize: 11 } }),
                                  jsx(YAxis, { tick: { fill: "#94a3b8", fontSize: 11 } }),
                                  jsx(Tooltip, { formatter: (value) => [value, "New tenants"] }),
                                  jsx(Bar, { dataKey: "created", fill: "#38bdf8", radius: [4, 4, 0, 0] }),
                                ],
                              }),
                            }),
                          })
                        : jsx("p", {
                            className: "mt-5 rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4 text-sm text-slate-400",
                            children: "No tenant growth series available yet.",
                          }),
                      jsx("div", {
                        className: "mt-5 grid gap-3 md:grid-cols-3",
                        children: Object.entries(tenantSegments).map(([segment, count]) =>
                          jsxs(
                            "div",
                            {
                              className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4",
                              children: [
                                jsx("p", { className: "text-xs uppercase tracking-wide text-slate-500", children: segment.replace(/_/g, " ") }),
                                jsx("span", {
                                  className: `mt-3 inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${segmentTone(segment)}`,
                                  children: `${count} tenant(s)`,
                                }),
                              ],
                            },
                            segment,
                          ),
                        ),
                      }),
                    ],
                  }),
                ],
              }),
              jsx("section", {
                className: "col-span-12 grid gap-4 xl:grid-cols-[0.55fr,1.45fr]",
                children: [
                  jsxs("div", {
                    className: "rounded-2xl p-6",
                    style: panelStyle,
                    children: [
                      jsx("p", {
                        className: "text-[11px] uppercase tracking-wide text-slate-500",
                        children: "Risk summary",
                      }),
                      jsx("h2", {
                        className: "mt-2 text-lg font-semibold text-white",
                        children: "Renewal and churn watchlist",
                      }),
                      jsx("div", {
                        className: "mt-4 grid gap-3",
                        children: [
                          { label: "High risk", value: riskSummary.high ?? 0, tone: "text-rose-200" },
                          { label: "Medium risk", value: riskSummary.medium ?? 0, tone: "text-amber-200" },
                          { label: "Low risk", value: riskSummary.low ?? 0, tone: "text-sky-200" },
                        ].map((item) =>
                          jsxs(
                            "div",
                            {
                              className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4",
                              children: [
                                jsx("p", { className: "text-xs uppercase tracking-wide text-slate-500", children: item.label }),
                                jsx("p", { className: `mt-2 text-2xl font-semibold ${item.tone}`, children: String(item.value) }),
                              ],
                            },
                            item.label,
                          ),
                        ),
                      }),
                      jsx("p", {
                        className: "mt-4 text-sm text-slate-400",
                        children: "Risk scoring combines overdue invoices, tenant status, settlement recency, and how near the next billing date is.",
                      }),
                    ],
                  }),
                  jsxs("div", {
                    className: "rounded-2xl p-6",
                    style: panelStyle,
                    children: [
                      jsx("p", {
                        className: "text-[11px] uppercase tracking-wide text-slate-500",
                        children: "Operator queue",
                      }),
                      jsx("h2", {
                        className: "mt-2 text-lg font-semibold text-white",
                        children: "Tenants needing billing follow-up",
                      }),
                      jsx("div", {
                        className: "mt-4 space-y-3",
                        children:
                          riskSignals.length > 0
                            ? riskSignals.map((signal) => {
                                const highlights = [];
                                if (signal.overdue_invoices) {
                                  highlights.push(`${signal.overdue_invoices} overdue invoice(s)`);
                                }
                                if (Number(signal.overdue_amount || 0) > 0) {
                                  highlights.push(`${formatMoney(signal.overdue_amount)} outstanding`);
                                }
                                if (signal.days_to_due != null) {
                                  highlights.push(
                                    signal.days_to_due < 0
                                      ? `${Math.abs(signal.days_to_due)} day(s) past due`
                                      : `${signal.days_to_due} day(s) to renewal`,
                                  );
                                }
                                if (highlights.length === 0 && Array.isArray(signal.reasons) && signal.reasons.length > 0) {
                                  highlights.push(signal.reasons[0]);
                                }

                                return jsxs(
                                  "article",
                                  {
                                    className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4",
                                    children: [
                                      jsxs("div", {
                                        className: "flex flex-wrap items-start justify-between gap-3",
                                        children: [
                                          jsxs("div", {
                                            children: [
                                              jsx("h3", { className: "text-base font-semibold text-white", children: signal.tenant_name }),
                                              jsx("p", {
                                                className: "mt-1 text-xs text-slate-500",
                                                children: `${signal.schema_name} | ${signal.plan_name}`,
                                              }),
                                            ],
                                          }),
                                          jsx("span", {
                                            className: `inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${riskTone(signal.risk_level)}`,
                                            children: `${String(signal.risk_level || "low").toUpperCase()} RISK`,
                                          }),
                                        ],
                                      }),
                                      jsx("div", {
                                        className: "mt-4 grid gap-3 md:grid-cols-4",
                                        children: [
                                          { label: "Risk score", value: String(signal.risk_score ?? 0) },
                                          { label: "Tenant status", value: signal.status || "--" },
                                          { label: "Next billing", value: formatDate(signal.next_billing_date || signal.paid_until) },
                                          { label: "Paid until", value: formatDate(signal.paid_until) },
                                        ].map((item) =>
                                          jsxs(
                                            "div",
                                            {
                                              children: [
                                                jsx("p", { className: "text-[11px] uppercase tracking-wide text-slate-500", children: item.label }),
                                                jsx("p", { className: "mt-1 text-sm font-medium text-slate-200", children: item.value }),
                                              ],
                                            },
                                            item.label,
                                          ),
                                        ),
                                      }),
                                      jsx("div", {
                                        className: "mt-4 flex flex-wrap gap-2",
                                        children: highlights.map((item) =>
                                          jsx(
                                            "span",
                                            {
                                              className: "rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-xs text-slate-300",
                                              children: item,
                                            },
                                            item,
                                          ),
                                        ),
                                      }),
                                    ],
                                  },
                                  signal.tenant_id,
                                );
                              })
                            : jsx("p", {
                                className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4 text-sm text-slate-400",
                                children: "No at-risk tenants are currently flagged by the analytics engine.",
                              }),
                      }),
                    ],
                  }),
                ],
              }),
            ],
          })
        : null,
    ],
  });
}

export { PlatformRevenueAnalyticsPage as default };
