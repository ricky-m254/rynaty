import { r as React, j as jsxRuntime, b as api } from "./index-D7ltaYVC.js";
import { n as normalizePaginated } from "./pagination-DjjjzeDo.js";

const { jsx, jsxs } = jsxRuntime;

const shellClass =
  "rounded-[32px] border border-slate-200/80 bg-[#f5f7fb] p-5 shadow-[0_28px_70px_rgba(15,23,42,0.08)] md:p-7 xl:p-8";
const surfaceClass =
  "rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-[0_22px_50px_rgba(15,23,42,0.06)]";
const mutedCardClass = "rounded-[24px] border border-slate-200 bg-slate-50/90 p-4";

function go(path) {
  if (typeof window !== "undefined") {
    window.location.assign(path);
  }
}

function money(value) {
  return `Ksh ${Number(value ?? 0).toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function shortDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("en-KE", { month: "short", day: "numeric" });
}

function numberLabel(value, noun) {
  const count = Number(value ?? 0);
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function daysOverdue(value) {
  if (!value) return 0;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 0;
  const today = new Date();
  const diff = Math.floor((today.setHours(0, 0, 0, 0) - date.setHours(0, 0, 0, 0)) / 86400000);
  return Math.max(0, diff);
}

function aggregateByDate(payments) {
  const totals = new Map();
  payments.forEach((payment) => {
    const rawDate = payment.payment_date || payment.created_at;
    if (!rawDate) return;
    const key = new Date(rawDate).toISOString().slice(0, 10);
    totals.set(key, (totals.get(key) ?? 0) + Number(payment.amount ?? 0));
  });
  return Array.from(totals.entries())
    .sort((left, right) => left[0].localeCompare(right[0]))
    .slice(-8)
    .map(([date, amount]) => ({
      date,
      label: shortDate(date),
      amount,
    }));
}

function buildSparklinePath(points, width, height, padding = 18) {
  if (points.length === 0) return "";
  if (points.length === 1) {
    return `M ${padding} ${height - padding} L ${width - padding} ${height - padding}`;
  }
  const max = Math.max(...points.map((point) => point.amount), 1);
  const step = (width - padding * 2) / (points.length - 1);
  return points
    .map((point, index) => {
      const x = padding + step * index;
      const y = height - padding - (point.amount / max) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function buildMethodBreakdown(payments) {
  const palette = ["#10b981", "#3b82f6", "#f59e0b", "#0f172a", "#ef4444"];
  const rows = [];
  const lookup = new Map();

  payments.forEach((payment) => {
    const method = String(payment.payment_method || "Unknown").trim() || "Unknown";
    if (!lookup.has(method)) {
      const row = { method, amount: 0, count: 0, color: palette[rows.length % palette.length] };
      lookup.set(method, row);
      rows.push(row);
    }
    const row = lookup.get(method);
    row.amount += Number(payment.amount ?? 0);
    row.count += 1;
  });

  const total = rows.reduce((sum, row) => sum + row.amount, 0);
  let currentAngle = 0;
  const segments = rows.map((row) => {
    const start = currentAngle;
    currentAngle += total > 0 ? (row.amount / total) * 360 : 0;
    return {
      ...row,
      share: total > 0 ? Math.round((row.amount / total) * 100) : 0,
      start,
      end: currentAngle,
    };
  });

  return { rows: segments, total };
}

function FinanceTabs({ active }) {
  const tabs = [
    { key: "overview", label: "Overview", path: "/modules/finance" },
    { key: "record", label: "Record Payment", path: "/modules/finance/payments/new" },
    { key: "payments", label: "Payments", path: "/modules/finance/payments" },
    { key: "reconciliation", label: "Reconciliation", path: "/modules/finance/reconciliation" },
    { key: "events", label: "Gateway Events", path: "/modules/finance/reconciliation?pane=events" },
    { key: "arrears", label: "Arrears", path: "/modules/finance/arrears" },
  ];

  return jsx("div", {
    className: "rounded-full border border-slate-200 bg-[#e8ebf3] p-1",
    children: tabs.map((tab) =>
      jsx(
        "button",
        {
          type: "button",
          onClick: () => go(tab.path),
          className: `rounded-full px-4 py-2 text-sm font-semibold transition ${
            active === tab.key ? "bg-white text-slate-950 shadow-sm" : "text-slate-700 hover:text-slate-950"
          }`,
          children: tab.label,
        },
        tab.key,
      ),
    ),
  });
}

function MetricCard({ label, value, detail, tone }) {
  return jsxs("div", {
    className: surfaceClass,
    children: [
      jsx("p", { className: "text-sm font-semibold text-slate-950", children: label }),
      jsx("p", { className: `mt-8 text-[2rem] font-semibold tracking-tight ${tone}`, children: value }),
      jsx("p", { className: "mt-2 text-sm text-slate-500", children: detail }),
    ],
  });
}

function FinanceSummaryPage() {
  const [summary, setSummary] = React.useState(null);
  const [payments, setPayments] = React.useState([]);
  const [invoices, setInvoices] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    let active = true;

    (async () => {
      try {
        const [summaryResponse, paymentsResponse, invoicesResponse] = await Promise.all([
          api.get("/finance/summary/"),
          api.get("/finance/payments/"),
          api.get("/finance/invoices/"),
        ]);
        if (!active) return;
        setSummary(summaryResponse.data ?? {});
        setPayments(normalizePaginated(paymentsResponse.data).items);
        setInvoices(normalizePaginated(invoicesResponse.data).items);
      } catch (loadError) {
        if (active) {
          setError("Unable to load the bursar overview right now.");
        }
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  const totalCollected = Number(summary?.cash_collected ?? payments.reduce((sum, row) => sum + Number(row.amount ?? 0), 0));
  const totalInvoiced = Number(
    summary?.revenue_billed ?? invoices.reduce((sum, row) => sum + Number(row.total_amount ?? row.amount ?? 0), 0),
  );
  const outstanding = Number(
    summary?.outstanding_receivables ??
      invoices.reduce((sum, row) => sum + Number(row.balance_due ?? row.balance ?? 0), 0),
  );
  const overdueInvoices = invoices.filter(
    (invoice) =>
      Number(invoice.balance_due ?? invoice.balance ?? 0) > 0 &&
      (String(invoice.status || "").toUpperCase() === "OVERDUE" || daysOverdue(invoice.due_date) > 0),
  );
  const overdueTotal = overdueInvoices.reduce((sum, row) => sum + Number(row.balance_due ?? row.balance ?? 0), 0);
  const collectionRate = totalInvoiced > 0 ? Math.round((totalCollected / totalInvoiced) * 100) : 0;
  const series = aggregateByDate(payments);
  const sparklinePath = buildSparklinePath(series, 520, 250, 26);
  const target = series.length > 0 ? series.reduce((sum, row) => sum + row.amount, 0) / series.length : 0;
  const maxSeriesValue = Math.max(...series.map((row) => row.amount), target, 1);
  const targetY = 250 - 26 - (target / maxSeriesValue) * (250 - 52);
  const distribution = buildMethodBreakdown(payments);
  const conic = distribution.rows.length
    ? `conic-gradient(${distribution.rows
        .map((row) => `${row.color} ${row.start}deg ${row.end}deg`)
        .join(", ")})`
    : "conic-gradient(#cbd5e1 0deg 360deg)";

  return jsxs("div", {
    className: "space-y-6",
    children: [
      jsxs("section", {
        className: shellClass,
        children: [
          jsxs("div", {
            className: "border-b border-slate-200 pb-6",
            children: [
              jsxs("div", {
                children: [
                  jsx("h1", {
                    className: "text-[2rem] font-semibold tracking-tight text-slate-950",
                    children: "School Payment Management System",
                  }),
                  jsx("p", {
                    className: "mt-1 text-lg text-slate-600",
                    children: "Collections, billing, reconciliation, and arrears in one bursar flow.",
                  }),
                ],
              }),
            ],
          }),
          error
            ? jsx("div", {
                className: "mt-5 rounded-[22px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700",
                children: error,
              })
            : null,
          jsx("div", {
            className: "mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4",
            children: [
              {
                label: "Total Collected",
                value: money(totalCollected),
                detail: `${collectionRate}% collection rate`,
                tone: "text-emerald-600",
              },
              {
                label: "Total Invoiced",
                value: money(totalInvoiced),
                detail:
                  invoices.length > 0
                    ? `${shortDate(invoices[invoices.length - 1]?.invoice_date)} to ${shortDate(invoices[0]?.invoice_date)}`
                    : "Current invoice register",
                tone: "text-slate-950",
              },
              {
                label: "Outstanding",
                value: money(outstanding),
                detail: "Pending collections",
                tone: "text-orange-600",
              },
              {
                label: "Overdue Fees",
                value: money(overdueTotal),
                detail: overdueInvoices.length > 0 ? "Requires attention" : "No overdue fees right now",
                tone: "text-red-600",
              },
            ].map((card) =>
              jsx(
                MetricCard,
                {
                  label: card.label,
                  value: card.value,
                  detail: card.detail,
                  tone: card.tone,
                },
                card.label,
              ),
            ),
          }),
          jsx("div", { className: "mt-6", children: jsx(FinanceTabs, { active: "overview" }) }),
          loading
            ? jsx("div", {
                className: `${surfaceClass} mt-6 text-sm text-slate-500`,
                children: "Loading overview metrics...",
              })
            : jsxs("div", {
                className: "mt-6 grid gap-6 xl:grid-cols-2",
                children: [
                  jsxs("section", {
                    className: surfaceClass,
                    children: [
                      jsx("h2", {
                        className: "text-[1.35rem] font-semibold text-slate-950",
                        children: "Payment Methods Distribution",
                      }),
                      jsx("p", {
                        className: "mt-1 text-lg text-slate-500",
                        children: "Breakdown by payment channel",
                      }),
                      jsxs("div", {
                        className: "mt-8 grid gap-6 lg:grid-cols-[240px,1fr]",
                        children: [
                          jsx("div", {
                            className: "mx-auto flex h-[240px] w-[240px] items-center justify-center rounded-full border border-slate-200 bg-slate-50",
                            children: jsx("div", {
                              className: "relative h-[160px] w-[160px] rounded-full",
                              style: { background: conic },
                              children: jsx("div", {
                                className: "absolute inset-[28px] rounded-full bg-white",
                              }),
                            }),
                          }),
                          jsx("div", {
                            className: "space-y-3",
                            children:
                              distribution.rows.length > 0
                                ? distribution.rows.map((row) =>
                                    jsxs(
                                      "div",
                                      {
                                        className: mutedCardClass,
                                        children: [
                                          jsxs("div", {
                                            className: "flex items-center justify-between gap-3",
                                            children: [
                                              jsxs("div", {
                                                className: "flex items-center gap-3",
                                                children: [
                                                  jsx("span", {
                                                    className: "h-3 w-3 rounded-full",
                                                    style: { background: row.color },
                                                  }),
                                                  jsx("span", {
                                                    className: "text-sm font-semibold text-slate-950",
                                                    children: row.method,
                                                  }),
                                                ],
                                              }),
                                              jsx("span", {
                                                className: "text-sm font-semibold text-slate-950",
                                                children: `${row.share}%`,
                                              }),
                                            ],
                                          }),
                                          jsxs("div", {
                                            className: "mt-3 flex items-center justify-between text-sm text-slate-500",
                                            children: [jsx("span", { children: money(row.amount) }), jsx("span", { children: numberLabel(row.count, "txn") })],
                                          }),
                                        ],
                                      },
                                      row.method,
                                    ),
                                  )
                                : jsx("p", {
                                    className: "text-sm text-slate-500",
                                    children: "No payment-method distribution is available yet.",
                                  }),
                          }),
                        ],
                      }),
                    ],
                  }),
                  jsxs("section", {
                    className: surfaceClass,
                    children: [
                      jsx("h2", {
                        className: "text-[1.35rem] font-semibold text-slate-950",
                        children: "Daily Collection Trend",
                      }),
                      jsx("p", {
                        className: "mt-1 text-lg text-slate-500",
                        children: "Last 8 payment days",
                      }),
                      jsx("div", {
                        className: "mt-6 rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-6",
                        children:
                          series.length > 0
                            ? jsx("svg", {
                                viewBox: "0 0 520 250",
                                className: "h-[320px] w-full",
                                children: [
                                  [58, 108, 158, 208].map((y) =>
                                    jsx(
                                      "line",
                                      {
                                        x1: "26",
                                        x2: "494",
                                        y1: String(y),
                                        y2: String(y),
                                        stroke: "#d7deea",
                                        strokeDasharray: "4 6",
                                      },
                                      y,
                                    ),
                                  ),
                                  jsx("line", {
                                    x1: "26",
                                    x2: "494",
                                    y1: String(targetY),
                                    y2: String(targetY),
                                    stroke: "#94a3b8",
                                    strokeDasharray: "6 8",
                                  }),
                                  jsx("path", {
                                    d: sparklinePath,
                                    fill: "none",
                                    stroke: "#10b981",
                                    strokeWidth: "3",
                                    strokeLinecap: "round",
                                    strokeLinejoin: "round",
                                  }),
                                  series.map((point, index) => {
                                    const step = series.length > 1 ? (520 - 52) / (series.length - 1) : 0;
                                    const x = 26 + step * index;
                                    const y = 250 - 26 - (point.amount / maxSeriesValue) * (250 - 52);
                                    return jsxs(
                                      "g",
                                      {
                                        children: [
                                          jsx("circle", {
                                            cx: String(x),
                                            cy: String(y),
                                            r: "4",
                                            fill: "#ffffff",
                                            stroke: "#10b981",
                                            strokeWidth: "2",
                                          }),
                                          jsx("text", {
                                            x: String(x),
                                            y: "236",
                                            textAnchor: "middle",
                                            fontSize: "12",
                                            fill: "#64748b",
                                            children: point.label,
                                          }),
                                        ],
                                      },
                                      point.date,
                                    );
                                  }),
                                ],
                              })
                            : jsx("p", {
                                className: "text-sm text-slate-500",
                                children: "No collection trend is available yet.",
                              }),
                      }),
                      jsx("div", {
                        className: "mt-4 flex flex-wrap gap-4 text-sm",
                        children: [
                          jsxs("span", {
                            className: "inline-flex items-center gap-2 text-emerald-600",
                            children: [jsx("span", { className: "h-2.5 w-2.5 rounded-full bg-emerald-500" }), "Collected"],
                          }),
                          jsxs("span", {
                            className: "inline-flex items-center gap-2 text-slate-500",
                            children: [jsx("span", { className: "h-2.5 w-2.5 rounded-full bg-slate-400" }), "Target"],
                          }),
                        ],
                      }),
                    ],
                  }),
                ],
              }),
        ],
      }),
    ],
  });
}

export { FinanceSummaryPage as default };
