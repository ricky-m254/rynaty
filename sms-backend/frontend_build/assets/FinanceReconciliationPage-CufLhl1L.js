import { r as React, j as jsxRuntime, b as api } from "./index-D7ltaYVC.js";
import { a as downloadResponse, d as downloadBlob } from "./download-EzDvBC7h.js";
import { e as getErrorMessage } from "./forms-ZJa1TpnO.js";

const { jsx, jsxs } = jsxRuntime;

const shellClass =
  "rounded-[32px] border border-slate-200/80 bg-[#f6f7fb] p-5 shadow-[0_30px_80px_rgba(15,23,42,0.08)] md:p-7 xl:p-8";
const surfaceClass =
  "rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-[0_22px_50px_rgba(15,23,42,0.06)]";
const insetClass = "rounded-[24px] border border-slate-200 bg-slate-50/80 p-4";
const inputClass =
  "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5";

const normalizeList = (payload) => (Array.isArray(payload) ? payload : payload?.results ?? []);

function money(value) {
  return `KES ${Number(value ?? 0).toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function toneClass(value) {
  return (
    {
      SUCCEEDED: "border-emerald-200 bg-emerald-50 text-emerald-700",
      CLEARED: "border-emerald-200 bg-emerald-50 text-emerald-700",
      MATCHED: "border-sky-200 bg-sky-50 text-sky-700",
      PENDING: "border-amber-200 bg-amber-50 text-amber-700",
      UNMATCHED: "border-amber-200 bg-amber-50 text-amber-700",
      FAILED: "border-rose-200 bg-rose-50 text-rose-700",
      IGNORED: "border-slate-200 bg-slate-100 text-slate-700",
    }[String(value || "").toUpperCase()] ?? "border-slate-200 bg-slate-100 text-slate-700"
  );
}

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function stringifyPayload(value) {
  if (value == null) return "No payload captured.";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch (error) {
    return String(value);
  }
}

function Notice({ tone = "success", message }) {
  if (!message) return null;
  const classes =
    tone === "error"
      ? "border-rose-200 bg-rose-50 text-rose-700"
      : "border-emerald-200 bg-emerald-50 text-emerald-700";
  return jsx("div", {
    className: `rounded-[22px] border px-4 py-3 text-sm ${classes}`,
    children: message,
  });
}

function ActionChip({ active, onClick, children }) {
  return jsx("button", {
    type: "button",
    onClick,
    className: `rounded-full px-4 py-2 text-xs font-semibold transition ${
      active
        ? "bg-slate-900 text-white shadow-[0_12px_30px_rgba(15,23,42,0.16)]"
        : "border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
    }`,
    children,
  });
}

function MetricCard({ label, value, detail }) {
  return jsxs("div", {
    className: surfaceClass,
    children: [
      jsx("p", {
        className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
        children: label,
      }),
      jsx("p", { className: "mt-3 text-2xl font-semibold text-slate-950", children: value }),
      jsx("p", { className: "mt-2 text-sm text-slate-500", children: detail }),
    ],
  });
}

function exportRows(rows, filename) {
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  downloadBlob(blob, filename);
}

function FinanceReconciliationPage() {
  const [transactions, setTransactions] = React.useState([]);
  const [events, setEvents] = React.useState([]);
  const [bankLines, setBankLines] = React.useState([]);
  const [bankStatus, setBankStatus] = React.useState("");
  const [bankSearch, setBankSearch] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [success, setSuccess] = React.useState(null);
  const [importing, setImporting] = React.useState(false);
  const [lineAction, setLineAction] = React.useState(null);
  const [txAction, setTxAction] = React.useState(null);
  const [eventAction, setEventAction] = React.useState(null);
  const [expandedEventId, setExpandedEventId] = React.useState(null);

  const loadWorkspace = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [txResponse, eventResponse, bankResponse] = await Promise.all([
        api.get("/finance/gateway/transactions/"),
        api.get("/finance/gateway/events/"),
        api.get("/finance/reconciliation/bank-lines/"),
      ]);
      setTransactions(normalizeList(txResponse.data));
      setEvents(normalizeList(eventResponse.data));
      setBankLines(normalizeList(bankResponse.data));
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to load reconciliation workspace."));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  const runLineAction = async (lineId, action) => {
    if (loading || txAction !== null || eventAction !== null || lineAction !== null) return;
    setLineAction({ lineId, action });
    setError(null);
    setSuccess(null);
    try {
      await api.post(`/finance/reconciliation/bank-lines/${lineId}/${action}/`);
      setSuccess(`Bank line ${action} completed.`);
      await loadWorkspace();
    } catch (requestError) {
      setError(getErrorMessage(requestError, `Line ${action} failed.`));
    } finally {
      setLineAction(null);
    }
  };

  const markReconciled = async (transactionId) => {
    if (loading || txAction !== null || eventAction !== null || lineAction !== null) return;
    setTxAction(transactionId);
    setError(null);
    setSuccess(null);
    try {
      await api.post(`/finance/gateway/transactions/${transactionId}/mark-reconciled/`);
      setSuccess("Transaction marked reconciled.");
      await loadWorkspace();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to mark transaction reconciled."));
    } finally {
      setTxAction(null);
    }
  };

  const reprocessEvent = async (eventId) => {
    if (loading || txAction !== null || eventAction !== null || lineAction !== null) return;
    setEventAction(eventId);
    setError(null);
    setSuccess(null);
    try {
      const response = await api.post(`/finance/gateway/events/${eventId}/reprocess/`);
      if (response.data?.already_processed) {
        setSuccess("Event was already processed.");
      } else if (response.data?.processed) {
        setSuccess("Webhook event reprocessed successfully.");
      } else {
        setError(response.data?.error || "Webhook reprocess did not complete.");
      }
      await loadWorkspace();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to reprocess webhook event."));
    } finally {
      setEventAction(null);
    }
  };

  const handleImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = new FormData();
      payload.append("file", file);
      const response = await api.post("/finance/reconciliation/bank-lines/import-csv/", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setSuccess(`Import completed. Created=${response.data?.created ?? 0}, Failed=${response.data?.failed ?? 0}.`);
      await loadWorkspace();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to import CSV. Ensure columns include statement_date and amount."));
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  const exportTransactions = () => {
    exportRows(
      [
        [
          "id",
          "provider",
          "external_id",
          "amount",
          "status",
          "is_reconciled",
          "student_name",
          "invoice_number",
          "created_at",
        ],
        ...transactions.map((row) => [
          row.id,
          row.provider,
          row.external_id,
          row.amount,
          row.status,
          row.is_reconciled ? "true" : "false",
          row.student_name ?? "",
          row.invoice_number ?? "",
          row.created_at ?? "",
        ]),
      ],
      "finance_gateway_transactions.csv",
    );
  };

  const exportEvents = () => {
    exportRows(
      [
        ["id", "provider", "event_type", "event_id", "processed", "error", "received_at"],
        ...events.map((row) => [
          row.id,
          row.provider,
          row.event_type,
          row.event_id,
          row.processed ? "true" : "false",
          row.error ?? "",
          row.received_at ?? "",
        ]),
      ],
      "finance_gateway_events.csv",
    );
  };

  const exportBankLines = async () => {
    try {
      const response = await api.get("/finance/reconciliation/bank-lines/export-csv/", { responseType: "blob" });
      downloadResponse(response, "finance_bank_statement_lines.csv");
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to export bank statement lines CSV."));
    }
  };

  const filteredBankLines = bankLines.filter((line) => {
    const statusMatch = !bankStatus || line.status === bankStatus;
    const term = bankSearch.trim().toLowerCase();
    const searchMatch =
      !term ||
      [line.reference, line.narration, line.source, line.matched_payment_reference, line.matched_gateway_external_id]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(term);
    return statusMatch && searchMatch;
  });

  const unmatchedCount = bankLines.filter((line) => String(line.status || "").toUpperCase() === "UNMATCHED").length;
  const unclearedTransactions = transactions.filter((row) => !row.is_reconciled).length;
  const failedEvents = events.filter((row) => !row.processed || row.error).length;

  return jsxs("div", {
    className: "space-y-6",
    children: [
      jsxs("section", {
        className: shellClass,
        children: [
          jsxs("div", {
            className: "flex flex-col gap-5 border-b border-slate-200 pb-6 lg:flex-row lg:items-end lg:justify-between",
            children: [
              jsxs("div", {
                className: "max-w-3xl",
                children: [
                  jsx("p", {
                    className: "text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400",
                    children: "Payment Management System",
                  }),
                  jsx("h1", {
                    className: "mt-3 text-3xl font-semibold tracking-tight text-slate-950 md:text-[2.5rem]",
                    children: "Reconciliation & gateway recovery",
                  }),
                  jsx("p", {
                    className: "mt-3 max-w-2xl text-sm leading-6 text-slate-600",
                    children:
                      "Import statement lines, match funds cleanly, inspect webhook failures, and recover gateway events without leaving the bursar flow.",
                  }),
                ],
              }),
              jsxs("div", {
                className: "flex flex-wrap gap-2",
                children: [
                  jsx(ActionChip, { active: false, onClick: () => window.location.assign("/modules/finance"), children: "Overview" }),
                  jsx(ActionChip, {
                    active: false,
                    onClick: () => window.location.assign("/modules/finance/payments/new"),
                    children: "Record Payment",
                  }),
                  jsx(ActionChip, {
                    active: false,
                    onClick: () => window.location.assign("/modules/finance/payments"),
                    children: "Payments",
                  }),
                  jsx(ActionChip, { active: true, onClick: () => {}, children: "Reconciliation" }),
                ],
              }),
            ],
          }),
          jsx("div", {
            className: "mt-6 space-y-4",
            children: [jsx(Notice, { tone: "error", message: error }), jsx(Notice, { tone: "success", message: success })],
          }),
          jsx("div", {
            className: "mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4",
            children: [
              {
                label: "Imported bank lines",
                value: String(bankLines.length),
                detail: `${unmatchedCount} still need review or matching.`,
              },
              {
                label: "Gateway transactions",
                value: String(transactions.length),
                detail: `${unclearedTransactions} not yet marked reconciled.`,
              },
              {
                label: "Webhook events",
                value: String(events.length),
                detail: `${failedEvents} need operator attention or reprocess.`,
              },
              {
                label: "Visible bank value",
                value: money(filteredBankLines.reduce((sum, line) => sum + Number(line.amount ?? 0), 0)),
                detail: "Current search and status filters applied.",
              },
            ].map((card) =>
              jsx(MetricCard, { label: card.label, value: card.value, detail: card.detail }, card.label),
            ),
          }),
          jsxs("section", {
            className: `${surfaceClass} mt-6`,
            children: [
              jsxs("div", {
                className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between",
                children: [
                  jsxs("div", {
                    children: [
                      jsx("p", {
                        className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                        children: "Bank Reconciliation",
                      }),
                      jsx("h2", {
                        className: "mt-2 text-xl font-semibold text-slate-950",
                        children: "Statement line workspace",
                      }),
                      jsx("p", {
                        className: "mt-1 text-sm text-slate-500",
                        children:
                          "Import CSV files, filter unmatched items, and use auto-match, clear, ignore, or unmatch with a cleaner review table.",
                      }),
                    ],
                  }),
                  jsxs("div", {
                    className: "flex flex-wrap gap-2",
                    children: [
                      jsx("label", {
                        className:
                          "cursor-pointer rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800",
                        children: [
                          importing ? "Importing..." : "Import CSV",
                          jsx("input", {
                            type: "file",
                            accept: ".csv",
                            className: "hidden",
                            onChange: handleImport,
                            disabled: importing,
                          }),
                        ],
                      }),
                      jsx("button", {
                        type: "button",
                        className:
                          "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                        onClick: exportBankLines,
                        children: "Export bank lines",
                      }),
                    ],
                  }),
                ],
              }),
              jsx("div", {
                className: "mt-5 grid gap-3 lg:grid-cols-[1fr,1fr,auto]",
                children: [
                  jsxs("select", {
                    className: inputClass,
                    value: bankStatus,
                    onChange: (event) => setBankStatus(event.target.value),
                    children: [
                      jsx("option", { value: "", children: "All statuses" }),
                      jsx("option", { value: "UNMATCHED", children: "Unmatched" }),
                      jsx("option", { value: "MATCHED", children: "Matched" }),
                      jsx("option", { value: "CLEARED", children: "Cleared" }),
                      jsx("option", { value: "IGNORED", children: "Ignored" }),
                    ],
                  }),
                  jsx("input", {
                    className: inputClass,
                    placeholder: "Search narration, reference, source, or matched IDs",
                    value: bankSearch,
                    onChange: (event) => setBankSearch(event.target.value),
                  }),
                  jsx("div", {
                    className: `${insetClass} flex items-center justify-center text-xs leading-5 text-slate-500`,
                    children: "CSV requires statement_date and amount. Optional fields: value_date, reference, narration, source.",
                  }),
                ],
              }),
              jsx("div", {
                className: "mt-5 overflow-x-auto rounded-[24px] border border-slate-200",
                children: jsxs("table", {
                  className: "min-w-[1200px] w-full text-left text-sm",
                  children: [
                    jsx("thead", {
                      className: "bg-slate-50 text-[11px] uppercase tracking-[0.2em] text-slate-500",
                      children: jsxs("tr", {
                        children: [
                          jsx("th", { className: "px-4 py-3 font-semibold", children: "Statement Date" }),
                          jsx("th", { className: "px-4 py-3 font-semibold", children: "Amount" }),
                          jsx("th", { className: "px-4 py-3 font-semibold", children: "Reference" }),
                          jsx("th", { className: "px-4 py-3 font-semibold", children: "Narration" }),
                          jsx("th", { className: "px-4 py-3 font-semibold", children: "Status" }),
                          jsx("th", { className: "px-4 py-3 font-semibold", children: "Matched" }),
                          jsx("th", { className: "px-4 py-3 font-semibold", children: "Actions" }),
                        ],
                      }),
                    }),
                    jsx("tbody", {
                      className: "divide-y divide-slate-200",
                      children:
                        filteredBankLines.length === 0
                          ? jsx("tr", {
                              children: jsx("td", {
                                className: "px-4 py-8 text-sm text-slate-500",
                                colSpan: 7,
                                children: loading ? "Loading bank lines..." : "No bank lines match the current filters.",
                              }),
                            })
                          : filteredBankLines.map((line) =>
                              jsxs(
                                "tr",
                                {
                                  className: "align-top hover:bg-slate-50/80",
                                  children: [
                                    jsx("td", {
                                      className: "px-4 py-4 text-slate-600",
                                      children: formatDateTime(line.statement_date),
                                    }),
                                    jsx("td", {
                                      className: "px-4 py-4 font-semibold text-slate-900",
                                      children: money(line.amount),
                                    }),
                                    jsx("td", {
                                      className: "px-4 py-4",
                                      children: jsxs("div", {
                                        children: [
                                          jsx("p", { className: "font-medium text-slate-900", children: line.reference || "--" }),
                                          jsx("p", {
                                            className: "mt-1 text-xs text-slate-500",
                                            children: `Value date: ${line.value_date || "--"} • Source: ${line.source || "--"}`,
                                          }),
                                        ],
                                      }),
                                    }),
                                    jsx("td", {
                                      className: "px-4 py-4 text-slate-600",
                                      children: line.narration || "--",
                                    }),
                                    jsx("td", {
                                      className: "px-4 py-4",
                                      children: jsx("span", {
                                        className: `inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${toneClass(line.status)}`,
                                        children: line.status || "--",
                                      }),
                                    }),
                                    jsx("td", {
                                      className: "px-4 py-4",
                                      children: jsxs("div", {
                                        children: [
                                          jsx("p", {
                                            className: "text-sm font-medium text-slate-900",
                                            children: line.matched_payment_reference || "--",
                                          }),
                                          jsx("p", {
                                            className: "mt-1 text-xs text-slate-500",
                                            children: line.matched_gateway_external_id || "No gateway match",
                                          }),
                                        ],
                                      }),
                                    }),
                                    jsx("td", {
                                      className: "px-4 py-4",
                                      children: jsxs("div", {
                                        className: "flex flex-wrap gap-2",
                                        children: [
                                          ["auto-match", "clear", "ignore", "unmatch"].map((action) =>
                                            jsx(
                                              "button",
                                              {
                                                type: "button",
                                                className:
                                                  "rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50",
                                                onClick: () => runLineAction(line.id, action),
                                                disabled: Boolean(lineAction),
                                                children: action,
                                              },
                                              action,
                                            ),
                                          ),
                                        ],
                                      }),
                                    }),
                                  ],
                                },
                                line.id,
                              ),
                            ),
                    }),
                  ],
                }),
              }),
            ],
          }),
          jsxs("div", {
            className: "mt-6 grid gap-6 xl:grid-cols-2",
            children: [
              jsxs("section", {
                className: surfaceClass,
                children: [
                  jsxs("div", {
                    className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between",
                    children: [
                      jsxs("div", {
                        children: [
                          jsx("p", {
                            className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                            children: "Gateway Transactions",
                          }),
                          jsx("h2", {
                            className: "mt-2 text-xl font-semibold text-slate-950",
                            children: "Settlement monitor",
                          }),
                          jsx("p", {
                            className: "mt-1 text-sm text-slate-500",
                            children: "Track pending or successful external payments and mark them reconciled when the bank or ledger match is confirmed.",
                          }),
                        ],
                      }),
                      jsx("button", {
                        type: "button",
                        className:
                          "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                        onClick: exportTransactions,
                        children: "Export transactions",
                      }),
                    ],
                  }),
                  jsx("div", {
                    className: "mt-5 overflow-x-auto rounded-[24px] border border-slate-200",
                    children: jsxs("table", {
                      className: "min-w-[900px] w-full text-left text-sm",
                      children: [
                        jsx("thead", {
                          className: "bg-slate-50 text-[11px] uppercase tracking-[0.2em] text-slate-500",
                          children: jsxs("tr", {
                            children: [
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Provider" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "External ID" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Amount" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Status" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Reconciled" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Action" }),
                            ],
                          }),
                        }),
                        jsx("tbody", {
                          className: "divide-y divide-slate-200",
                          children:
                            transactions.length === 0
                              ? jsx("tr", {
                                  children: jsx("td", {
                                    className: "px-4 py-8 text-sm text-slate-500",
                                    colSpan: 6,
                                    children: loading ? "Loading transactions..." : "No gateway transactions found.",
                                  }),
                                })
                              : transactions.map((row) =>
                                  jsxs(
                                    "tr",
                                    {
                                      className: "hover:bg-slate-50/80",
                                      children: [
                                        jsx("td", { className: "px-4 py-4 text-slate-700", children: row.provider || "--" }),
                                        jsx("td", {
                                          className: "px-4 py-4 font-mono text-xs text-slate-600",
                                          children: row.external_id || "--",
                                        }),
                                        jsx("td", {
                                          className: "px-4 py-4 font-semibold text-slate-900",
                                          children: money(row.amount),
                                        }),
                                        jsx("td", {
                                          className: "px-4 py-4",
                                          children: jsx("span", {
                                            className: `inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${toneClass(row.status)}`,
                                            children: row.status || "--",
                                          }),
                                        }),
                                        jsx("td", {
                                          className: "px-4 py-4 text-slate-600",
                                          children: row.is_reconciled ? "Yes" : "No",
                                        }),
                                        jsx("td", {
                                          className: "px-4 py-4",
                                          children: jsx("button", {
                                            type: "button",
                                            className:
                                              "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50",
                                            onClick: () => markReconciled(row.id),
                                            disabled: Boolean(txAction) || row.is_reconciled,
                                            children: row.is_reconciled ? "Reconciled" : "Mark reconciled",
                                          }),
                                        }),
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
              }),
              jsxs("section", {
                className: surfaceClass,
                children: [
                  jsxs("div", {
                    className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between",
                    children: [
                      jsxs("div", {
                        children: [
                          jsx("p", {
                            className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                            children: "Gateway Events",
                          }),
                          jsx("h2", {
                            className: "mt-2 text-xl font-semibold text-slate-950",
                            children: "Webhook recovery desk",
                          }),
                          jsx("p", {
                            className: "mt-1 text-sm text-slate-500",
                            children: "Inspect raw event payloads, see processing errors, and re-run supported failures directly from this table.",
                          }),
                        ],
                      }),
                      jsx("button", {
                        type: "button",
                        className:
                          "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                        onClick: exportEvents,
                        children: "Export events",
                      }),
                    ],
                  }),
                  jsx("div", {
                    className: "mt-5 overflow-x-auto rounded-[24px] border border-slate-200",
                    children: jsxs("table", {
                      className: "min-w-[900px] w-full text-left text-sm",
                      children: [
                        jsx("thead", {
                          className: "bg-slate-50 text-[11px] uppercase tracking-[0.2em] text-slate-500",
                          children: jsxs("tr", {
                            children: [
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Provider" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Event" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Received" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Processed" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Error" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Actions" }),
                            ],
                          }),
                        }),
                        jsx("tbody", {
                          className: "divide-y divide-slate-200",
                          children:
                            events.length === 0
                              ? jsx("tr", {
                                  children: jsx("td", {
                                    className: "px-4 py-8 text-sm text-slate-500",
                                    colSpan: 6,
                                    children: loading ? "Loading events..." : "No webhook events found.",
                                  }),
                                })
                              : events.map((row) =>
                                  jsxs(
                                    React.Fragment,
                                    {
                                      children: [
                                        jsxs("tr", {
                                          className: "align-top hover:bg-slate-50/80",
                                          children: [
                                            jsx("td", { className: "px-4 py-4 text-slate-700", children: row.provider || "--" }),
                                            jsx("td", {
                                              className: "px-4 py-4",
                                              children: jsxs("div", {
                                                children: [
                                                  jsx("p", { className: "font-medium text-slate-900", children: row.event_type || "--" }),
                                                  jsx("p", {
                                                    className: "mt-1 font-mono text-xs text-slate-500",
                                                    children: row.event_id || "--",
                                                  }),
                                                ],
                                              }),
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-4 text-slate-600",
                                              children: formatDateTime(row.received_at),
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-4",
                                              children: jsx("span", {
                                                className: `inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${
                                                  row.processed ? toneClass("SUCCEEDED") : toneClass("FAILED")
                                                }`,
                                                children: row.processed ? "Processed" : "Pending",
                                              }),
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-4 text-slate-600",
                                              children: row.error || "--",
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-4",
                                              children: jsxs("div", {
                                                className: "flex flex-wrap gap-2",
                                                children: [
                                                  jsx("button", {
                                                    type: "button",
                                                    className:
                                                      "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                                                    onClick: () =>
                                                      setExpandedEventId((current) => (current === row.id ? null : row.id)),
                                                    children: expandedEventId === row.id ? "Hide payload" : "View payload",
                                                  }),
                                                  jsx("button", {
                                                    type: "button",
                                                    className:
                                                      "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50",
                                                    onClick: () => reprocessEvent(row.id),
                                                    disabled: Boolean(eventAction),
                                                    children: "Reprocess",
                                                  }),
                                                ],
                                              }),
                                            }),
                                          ],
                                        }),
                                        expandedEventId === row.id
                                          ? jsx("tr", {
                                              children: jsx("td", {
                                                colSpan: 6,
                                                className: "bg-slate-50/80 px-4 py-4",
                                                children: jsx("pre", {
                                                  className:
                                                    "max-h-[360px] overflow-auto rounded-[22px] border border-slate-200 bg-white p-4 text-xs leading-6 text-slate-700",
                                                  children: stringifyPayload(row.payload),
                                                }),
                                              }),
                                            })
                                          : null,
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
              }),
            ],
          }),
        ],
      }),
    ],
  });
}

export { FinanceReconciliationPage as default };
