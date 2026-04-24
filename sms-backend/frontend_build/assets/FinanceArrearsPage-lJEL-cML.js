import { u as useNavigate, r as React, b as api, j as jsxRuntime } from "./index-D7ltaYVC.js";

const { jsx, jsxs } = jsxRuntime;

const shellClass =
  "rounded-[32px] border border-slate-200/80 bg-[#f5f7fb] p-5 shadow-[0_28px_70px_rgba(15,23,42,0.08)] md:p-7 xl:p-8";
const surfaceClass =
  "rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-[0_22px_50px_rgba(15,23,42,0.06)]";
const inputClass =
  "rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5";

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

function daysOverdue(value) {
  if (!value) return 0;
  const due = new Date(value);
  if (Number.isNaN(due.getTime())) return 0;
  const today = new Date();
  const diff = Math.floor((today.setHours(0, 0, 0, 0) - due.setHours(0, 0, 0, 0)) / 86400000);
  return Math.max(0, diff);
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

function groupStudentBalances(rows) {
  const grouped = new Map();
  rows.forEach((row) => {
    const key = `${row.student_name}::${row.admission_number}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        key,
        student_name: row.student_name,
        admission_number: row.admission_number,
        class_name: row.class_name,
        total_balance: 0,
        max_overdue_days: 0,
        invoices: [],
      });
    }
    const entry = grouped.get(key);
    entry.total_balance += Number(row.balance_due ?? 0);
    entry.max_overdue_days = Math.max(entry.max_overdue_days, daysOverdue(row.due_date));
    entry.invoices.push(row);
  });

  return Array.from(grouped.values()).sort((left, right) => right.total_balance - left.total_balance);
}

function FinanceArrearsPage() {
  const navigate = useNavigate();
  const [terms, setTerms] = React.useState([]);
  const [term, setTerm] = React.useState("");
  const [rows, setRows] = React.useState([]);
  const [carryForwards, setCarryForwards] = React.useState([]);
  const [showCarryForwards, setShowCarryForwards] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [carryLoading, setCarryLoading] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    let active = true;

    (async () => {
      try {
        const [termsResponse, arrearsResponse] = await Promise.all([
          api.get("/finance/terms/"),
          api.get("/finance/reports/arrears/", { params: term ? { term, group_by: "student" } : { group_by: "student" } }),
        ]);
        if (!active) return;
        setTerms(Array.isArray(termsResponse.data?.results) ? termsResponse.data.results : termsResponse.data ?? []);
        setRows(Array.isArray(arrearsResponse.data?.results) ? arrearsResponse.data.results : []);
      } catch (loadError) {
        if (active) {
          setError("Unable to load the arrears view right now.");
        }
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [term]);

  React.useEffect(() => {
    if (!showCarryForwards) return undefined;
    let active = true;
    setCarryLoading(true);

    api
      .get("/finance/carry-forwards/")
      .then((response) => {
        if (active) {
          setCarryForwards(Array.isArray(response.data?.results) ? response.data.results : response.data ?? []);
        }
      })
      .catch(() => {
        if (active) setCarryForwards([]);
      })
      .finally(() => {
        if (active) setCarryLoading(false);
      });

    return () => {
      active = false;
    };
  }, [showCarryForwards]);

  const studentBalances = groupStudentBalances(rows);
  const totalOutstanding = studentBalances.reduce((sum, row) => sum + row.total_balance, 0);
  const overdueStudents = studentBalances.filter((row) => row.max_overdue_days > 0);
  const longestOverdue = overdueStudents.reduce((max, row) => Math.max(max, row.max_overdue_days), 0);

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
                    children: "Arrears follow-up, outstanding balances, and carry-forward visibility.",
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
                label: "Students With Balances",
                value: String(studentBalances.length),
                detail: "Active accounts that need bursar follow-up",
                tone: "text-slate-950",
              },
              {
                label: "Total Arrears",
                value: money(totalOutstanding),
                detail: "Open balance across overdue and partial invoices",
                tone: "text-red-600",
              },
              {
                label: "Overdue Students",
                value: String(overdueStudents.length),
                detail: longestOverdue > 0 ? `${longestOverdue} days is the longest ageing` : "No aged balances today",
                tone: "text-orange-600",
              },
              {
                label: "Carry Forwards",
                value: String(carryForwards.length),
                detail: showCarryForwards ? "Desk currently visible below" : "Open the desk when you need term carry-forward history",
                tone: "text-slate-950",
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
          jsx("div", { className: "mt-6", children: jsx(FinanceTabs, { active: "arrears" }) }),
          jsxs("section", {
            className: `${surfaceClass} mt-6`,
            children: [
              jsxs("div", {
                className: "flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between",
                children: [
                  jsxs("div", {
                    children: [
                      jsx("h2", {
                        className: "text-[1.35rem] font-semibold text-slate-950",
                        children: "Students with Arrears",
                      }),
                      jsx("p", {
                        className: "mt-1 text-lg text-slate-500",
                        children: "Outstanding balances requiring follow-up",
                      }),
                    ],
                  }),
                  jsxs("div", {
                    className: "flex flex-wrap gap-3",
                    children: [
                      jsxs("select", {
                        className: inputClass,
                        value: term,
                        onChange: (event) => setTerm(event.target.value),
                        children: [
                          jsx("option", { value: "", children: "All Terms" }),
                          terms.map((item) =>
                            jsx("option", { value: item.id, children: item.name }, item.id),
                          ),
                        ],
                      }),
                      jsx("button", {
                        type: "button",
                        onClick: () => setShowCarryForwards((current) => !current),
                        className:
                          "rounded-full border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-950",
                        children: showCarryForwards ? "Hide Carry Forwards" : "Show Carry Forwards",
                      }),
                    ],
                  }),
                ],
              }),
              loading
                ? jsx("div", {
                    className: "mt-6 rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500",
                    children: "Loading arrears records...",
                  })
                : studentBalances.length === 0
                  ? jsx("div", {
                      className: "mt-6 rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500",
                      children: "No arrears were found for the selected term.",
                    })
                  : jsxs("div", {
                      className: "mt-6 space-y-4",
                      children: [
                        jsx("div", {
                          className: "flex justify-end",
                          children: jsx("span", {
                            className: "inline-flex rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-600",
                            children: `${studentBalances.length} Students`,
                          }),
                        }),
                        studentBalances.map((row) =>
                          jsxs(
                            "div",
                            {
                              className: "rounded-[24px] border border-slate-200 bg-white p-4 shadow-[0_14px_35px_rgba(15,23,42,0.04)]",
                              children: [
                                jsxs("div", {
                                  className: "flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between",
                                  children: [
                                    jsxs("div", {
                                      children: [
                                        jsx("p", {
                                          className: "text-[1.35rem] font-semibold text-slate-950",
                                          children: row.student_name,
                                        }),
                                        jsx("p", {
                                          className: "mt-1 text-base text-slate-500",
                                          children: `${row.class_name || "Class pending"} • ${row.admission_number || "Admission pending"}`,
                                        }),
                                      ],
                                    }),
                                    row.max_overdue_days > 0
                                      ? jsx("span", {
                                          className: "inline-flex rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-600",
                                          children: `${row.max_overdue_days} days overdue`,
                                        })
                                      : jsx("span", {
                                          className: "inline-flex rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-500",
                                          children: "Not past due",
                                        }),
                                  ],
                                }),
                                jsxs("button", {
                                  type: "button",
                                  className:
                                    "mt-4 block w-full rounded-[18px] bg-rose-50 px-5 py-4 text-left transition hover:bg-rose-100",
                                  onClick: () => navigate(`/modules/finance/ledger?student=${encodeURIComponent(row.admission_number || "")}`),
                                  children: [
                                    jsx("span", {
                                      className: "text-sm text-slate-500",
                                      children: "Total Arrears",
                                    }),
                                    jsx("span", {
                                      className: "float-right text-[1.75rem] font-semibold tracking-tight text-red-600",
                                      children: money(row.total_balance),
                                    }),
                                  ],
                                }),
                              ],
                            },
                            row.key,
                          ),
                        ),
                      ],
                    }),
            ],
          }),
          showCarryForwards
            ? jsxs("section", {
                className: `${surfaceClass} mt-6`,
                children: [
                  jsx("h2", {
                    className: "text-[1.35rem] font-semibold text-slate-950",
                    children: "Carry Forward Desk",
                  }),
                  jsx("p", {
                    className: "mt-1 text-lg text-slate-500",
                    children: "Term-to-term balances already recorded in the system.",
                  }),
                  carryLoading
                    ? jsx("div", {
                        className: "mt-6 rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500",
                        children: "Loading carry forwards...",
                      })
                    : carryForwards.length === 0
                      ? jsx("div", {
                          className: "mt-6 rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500",
                          children: "No carry forwards are recorded yet.",
                        })
                      : jsx("div", {
                          className: "mt-6 overflow-x-auto rounded-[24px] border border-slate-200",
                          children: jsxs("table", {
                            className: "min-w-[880px] w-full text-left text-sm",
                            children: [
                              jsx("thead", {
                                className: "bg-slate-50 text-[11px] uppercase tracking-[0.18em] text-slate-500",
                                children: jsxs("tr", {
                                  children: [
                                    jsx("th", { className: "px-4 py-3 font-semibold", children: "Student" }),
                                    jsx("th", { className: "px-4 py-3 font-semibold", children: "Admission No." }),
                                    jsx("th", { className: "px-4 py-3 font-semibold", children: "From Term" }),
                                    jsx("th", { className: "px-4 py-3 font-semibold", children: "To Term" }),
                                    jsx("th", { className: "px-4 py-3 font-semibold", children: "Amount" }),
                                    jsx("th", { className: "px-4 py-3 font-semibold", children: "Notes" }),
                                  ],
                                }),
                              }),
                              jsx("tbody", {
                                className: "divide-y divide-slate-200",
                                children: carryForwards.map((row) =>
                                  jsxs(
                                    "tr",
                                    {
                                      children: [
                                        jsx("td", { className: "px-4 py-4 font-medium text-slate-950", children: row.student_name }),
                                        jsx("td", { className: "px-4 py-4 text-slate-600", children: row.student_admission_number }),
                                        jsx("td", { className: "px-4 py-4 text-slate-600", children: row.from_term_name }),
                                        jsx("td", { className: "px-4 py-4 text-slate-600", children: row.to_term_name }),
                                        jsx("td", { className: "px-4 py-4 font-semibold text-slate-950", children: money(row.amount) }),
                                        jsx("td", { className: "px-4 py-4 text-slate-600", children: row.notes || "—" }),
                                      ],
                                    },
                                    row.id,
                                  ),
                                ),
                              }),
                            ],
                          }),
                        }),
                ],
              })
            : null,
        ],
      }),
    ],
  });
}

export { FinanceArrearsPage as default };
