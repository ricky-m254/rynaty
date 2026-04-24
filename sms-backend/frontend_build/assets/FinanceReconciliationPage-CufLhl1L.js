import { c as useLocation, r as React, j as jsxRuntime, b as api } from "./index-D7ltaYVC.js";
import { a as downloadResponse, d as downloadBlob } from "./download-EzDvBC7h.js";
import { e as getErrorMessage } from "./forms-ZJa1TpnO.js";

const { jsx, jsxs } = jsxRuntime;

const shellClass =
  "rounded-[32px] border border-slate-200/80 bg-[#f5f7fb] p-5 shadow-[0_28px_70px_rgba(15,23,42,0.08)] md:p-7 xl:p-8";
const surfaceClass =
  "rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-[0_22px_50px_rgba(15,23,42,0.06)]";
const insetClass = "rounded-[24px] border border-slate-200 bg-slate-50/85 p-4";
const inputClass =
  "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5";

const normalizeList = (payload) => (Array.isArray(payload) ? payload : payload?.results ?? []);

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
      processed: "border-emerald-200 bg-emerald-50 text-emerald-700",
      pending: "border-amber-200 bg-amber-50 text-amber-700",
      error: "border-rose-200 bg-rose-50 text-rose-700",
    }[String(value || "")] ?? "border-slate-200 bg-slate-100 text-slate-700"
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
  } catch {
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

function PortalSwitch({ active }) {
  const links = [
    { key: "student", label: "Student Portal", path: "/student-portal/fees" },
    { key: "parent", label: "Parent Portal", path: "/modules/parent-portal/finance" },
    { key: "bursar", label: "Bursar Portal", path: "/modules/finance" },
  ];

  return jsx("div", {
    className: "inline-flex rounded-full border border-slate-200 bg-white p-1 shadow-[0_12px_30px_rgba(15,23,42,0.06)]",
    children: links.map((link) =>
      jsx(
        "button",
        {
          type: "button",
          onClick: () => go(link.path),
          className: `rounded-full px-4 py-2 text-sm font-semibold transition ${
            active === link.key
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
          }`,
          children: link.label,
        },
        link.key,
      ),
    ),
  });
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

function MetricCard({ label, value, detail, tone = "text-slate-950" }) {
  return jsxs("div", {
    className: surfaceClass,
    children: [
      jsx("p", { className: "text-sm font-semibold text-slate-950", children: label }),
      jsx("p", { className: `mt-8 text-[2rem] font-semibold tracking-tight ${tone}`, children: value }),
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
  const location = useLocation();
  const pane = React.useMemo(() => {
    const params = new URLSearchParams(location.search || "");
    return params.get("pane") === "events" ? "events" : "reconciliation";
  }, [location.search]);

  const [transactions, setTransactions] = React.useState([]);
  const [events, setEvents] = React.useState([]);
  const [bankLines, setBankLines] = React.useState([]);
  const [bankStatus, setBankStatus] = React.useState("");
  const [bankSearch, setBankSearch] = React.useState("");
  const [eventProvider, setEventProvider] = React.useState("");
  const [eventState, setEventState] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [success, setSuccess] = React.useState(null);
  const [importing, setImporting] = React.useState(false);
  const [bulkMatching, setBulkMatching] = React.useState(false);
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
    if (loading || txAction !== null || eventAction !== null || lineAction !== null || bulkMatching) return;
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

  const bulkAutoMatch = async () => {
    const candidates = filteredBankLines.filter((line) => String(line.status || "").toUpperCase() === "UNMATCHED");
    if (candidates.length === 0 || loading || bulkMatching) return;
    setBulkMatching(true);
    setError(null);
    setSuccess(null);
    try {
      for (const line of candidates) {
        await api.post(`/finance/reconciliation/bank-lines/${line.id}/auto-match/`);
      }
      setSuccess(`Auto-match completed for ${candidates.length} bank line${candidates.length === 1 ? "" : "s"}.`);
      await loadWorkspace();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Bulk auto-match failed."));
    } finally {
      setBulkMatching(false);
    }
  };

  const markReconciled = async (transactionId) => {
    if (loading || txAction !== null || eventAction !== null || lineAction !== null || bulkMatching) return;
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
    if (loading || txAction !== null || eventAction !== null || lineAction !== null || bulkMatching) return;
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
        ["id", "provider", "external_id", "amount", "status", "is_reconciled", "student_name", "invoice_number", "created_at"],
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

  const filteredBankLines = React.useMemo(
    () =>
      bankLines.filter((line) => {
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
      }),
    [bankLines, bankSearch, bankStatus],
  );

  const filteredEvents = React.useMemo(
    () =>
      events.filter((row) => {
        const providerMatch = !eventProvider || row.provider === eventProvider;
        const stateLabel = row.error ? "error" : row.processed ? "processed" : "pending";
        const stateMatch = !eventState || eventState === stateLabel;
        return providerMatch && stateMatch;
      }),
    [eventProvider, eventState, events],
  );

  const unmatchedCount = bankLines.filter((line) => String(line.status || "").toUpperCase() === "UNMATCHED").length;
  const matchedCount = bankLines.filter((line) => String(line.status || "").toUpperCase() === "MATCHED").length;
  const clearedCount = bankLines.filter((line) => String(line.status || "").toUpperCase() === "CLEARED").length;
  const ignoredCount = bankLines.filter((line) => String(line.status || "").toUpperCase() === "IGNORED").length;

  const unprocessedEvents = events.filter((row) => !row.processed && !row.error).length;
  const failedEvents = events.filter((row) => Boolean(row.error)).length;
  const processedEvents = events.filter((row) => row.processed && !row.error).length;
  const providers = Array.from(new Set(events.map((row) => row.provider).filter(Boolean))).sort();
  const unreconciledTransactions = transactions.filter((row) => !row.is_reconciled);

  return jsxs("div", {
    className: "space-y-6",
    children: [
      jsxs("section", {
        className: shellClass,
        children: [
          jsxs("div", {
            className: "flex flex-col gap-4 border-b border-slate-200 pb-6 xl:flex-row xl:items-start xl:justify-between",
            children: [
              jsxs("div", {
                children: [
                  jsx("h1", {
                    className: "text-[2rem] font-semibold tracking-tight text-slate-950",
                    children: "School Payment Management System",
                  }),
                  jsx("p", {
                    className: "mt-1 text-lg text-slate-600",
                    children: pane === "events"
                      ? "Monitor payment gateway events and recover failed webhook or callback processing."
                      : "Review and reconcile bank statement lines with cleaner placement for matching and clearance.",
                  }),
                ],
              }),
              jsx(PortalSwitch, { active: "bursar" }),
            ],
          }),
          jsx("div", { className: "mt-6", children: jsx(FinanceTabs, { active: pane === "events" ? "events" : "reconciliation" }) }),
          jsx("div", {
            className: "mt-6 space-y-4",
            children: [jsx(Notice, { tone: "error", message: error }), jsx(Notice, { tone: "success", message: success })],
          }),
          pane === "events"
            ? jsx("div", {
                className: "mt-6 grid gap-4 md:grid-cols-3",
                children: [
                  jsx(MetricCard, {
                    label: "Unprocessed Events",
                    value: String(unprocessedEvents),
                    detail: "Awaiting processing.",
                    tone: "text-amber-600",
                  }),
                  jsx(MetricCard, {
                    label: "Failed Events",
                    value: String(failedEvents),
                    detail: "Require attention or reprocess.",
                    tone: "text-rose-600",
                  }),
                  jsx(MetricCard, {
                    label: "Processed",
                    value: String(processedEvents),
                    detail: "Successfully settled.",
                    tone: "text-emerald-600",
                  }),
                ],
              })
            : jsx("div", {
                className: "mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4",
                children: [
                  jsx(MetricCard, {
                    label: "Unmatched Lines",
                    value: String(unmatchedCount),
                    detail: money(
                      bankLines
                        .filter((line) => String(line.status || "").toUpperCase() === "UNMATCHED")
                        .reduce((sum, line) => sum + Number(line.amount ?? 0), 0),
                    ),
                    tone: "text-amber-600",
                  }),
                  jsx(MetricCard, {
                    label: "Matched",
                    value: String(matchedCount),
                    detail: "Pending clearance.",
                    tone: "text-sky-600",
                  }),
                  jsx(MetricCard, {
                    label: "Cleared",
                    value: String(clearedCount),
                    detail: "Reconciled bank lines.",
                    tone: "text-emerald-600",
                  }),
                  jsx(MetricCard, {
                    label: "Total Lines",
                    value: String(bankLines.length),
                    detail: `${ignoredCount} ignored during review.`,
                  }),
                ],
              }),
          pane === "events"
            ? jsxs("section", {
                className: `${surfaceClass} mt-6`,
                children: [
                  jsxs("div", {
                    className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between",
                    children: [
                      jsxs("div", {
                        children: [
                          jsx("h2", { className: "text-xl font-semibold text-slate-950", children: "Payment Gateway Events" }),
                          jsx("p", {
                            className: "mt-1 text-sm text-slate-500",
                            children: "Monitor and recover failed webhook or callback events with a compact payload viewer.",
                          }),
                        ],
                      }),
                      jsxs("div", {
                        className: "flex flex-wrap gap-2",
                        children: [
                          jsx("button", {
                            type: "button",
                            className:
                              "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                            onClick: loadWorkspace,
                            children: "Refresh",
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
                    ],
                  }),
                  jsx("div", {
                    className: "mt-5 grid gap-3 lg:grid-cols-2",
                    children: [
                      jsxs("select", {
                        className: inputClass,
                        value: eventProvider,
                        onChange: (event) => setEventProvider(event.target.value),
                        children: [
                          jsx("option", { value: "", children: "All providers" }),
                          providers.map((provider) => jsx("option", { value: provider, children: provider }, provider)),
                        ],
                      }),
                      jsxs("select", {
                        className: inputClass,
                        value: eventState,
                        onChange: (event) => setEventState(event.target.value),
                        children: [
                          jsx("option", { value: "", children: "All status" }),
                          jsx("option", { value: "pending", children: "Pending" }),
                          jsx("option", { value: "processed", children: "Processed" }),
                          jsx("option", { value: "error", children: "Failed" }),
                        ],
                      }),
                    ],
                  }),
                  jsx("div", {
                    className: "mt-5 overflow-x-auto rounded-[24px] border border-slate-200",
                    children: jsxs("table", {
                      className: "min-w-[980px] w-full text-left text-sm",
                      children: [
                        jsx("thead", {
                          className: "bg-slate-50 text-[11px] uppercase tracking-[0.2em] text-slate-500",
                          children: jsxs("tr", {
                            children: [
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Event ID" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Provider" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Type" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Received" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Status" }),
                              jsx("th", { className: "px-4 py-3 font-semibold", children: "Actions" }),
                            ],
                          }),
                        }),
                        jsx("tbody", {
                          className: "divide-y divide-slate-200",
                          children:
                            filteredEvents.length === 0
                              ? jsx("tr", {
                                  children: jsx("td", {
                                    className: "px-4 py-8 text-sm text-slate-500",
                                    colSpan: 6,
                                    children: loading ? "Loading events..." : "No webhook events found.",
                                  }),
                                })
                              : filteredEvents.map((row) => {
                                  const eventTone = row.error ? "error" : row.processed ? "processed" : "pending";
                                  const eventLabel = row.error ? "Failed" : row.processed ? "Processed" : "Pending";
                                  return jsxs(
                                    React.Fragment,
                                    {
                                      children: [
                                        jsxs("tr", {
                                          className: `align-top ${row.error ? "bg-rose-50/40" : ""}`,
                                          children: [
                                            jsx("td", {
                                              className: "px-4 py-4 font-mono text-xs text-slate-700",
                                              children: row.event_id || row.id,
                                            }),
                                            jsx("td", { className: "px-4 py-4 text-slate-700", children: row.provider || "--" }),
                                            jsx("td", {
                                              className: "px-4 py-4 text-slate-700",
                                              children: row.event_type || "--",
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-4 text-slate-600",
                                              children: formatDateTime(row.received_at),
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-4",
                                              children: jsxs("div", {
                                                className: "space-y-1",
                                                children: [
                                                  jsx("span", {
                                                    className: `inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${toneClass(eventTone)}`,
                                                    children: eventLabel,
                                                  }),
                                                  row.error
                                                    ? jsx("p", {
                                                        className: "max-w-[260px] text-xs text-rose-600",
                                                        children: row.error,
                                                      })
                                                    : null,
                                                ],
                                              }),
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
                                                      "rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50",
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
                                  );
                                }),
                        }),
                      ],
                    }),
                  }),
                ],
              })
            : jsxs(React.Fragment, {
                children: [
                  jsxs("section", {
                    className: `${surfaceClass} mt-6`,
                    children: [
                      jsxs("div", {
                        className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between",
                        children: [
                          jsxs("div", {
                            children: [
                              jsx("h2", { className: "text-xl font-semibold text-slate-950", children: "Bank Statement Lines" }),
                              jsx("p", {
                                className: "mt-1 text-sm text-slate-500",
                                children: "Review and reconcile bank transactions with a cleaner match-first layout.",
                              }),
                            ],
                          }),
                          jsxs("div", {
                            className: "flex flex-wrap gap-2",
                            children: [
                              jsx("label", {
                                className:
                                  "cursor-pointer rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
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
                                  "rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60",
                                onClick: bulkAutoMatch,
                                disabled: bulkMatching || filteredBankLines.length === 0,
                                children: bulkMatching ? "Auto-matching..." : "Auto-Match All",
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
                              jsx("option", { value: "", children: "All Statuses" }),
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
                          className: "min-w-[1180px] w-full text-left text-sm",
                          children: [
                            jsx("thead", {
                              className: "bg-slate-50 text-[11px] uppercase tracking-[0.2em] text-slate-500",
                              children: jsxs("tr", {
                                children: [
                                  jsx("th", { className: "px-4 py-3 font-semibold", children: "Date" }),
                                  jsx("th", { className: "px-4 py-3 font-semibold", children: "Amount" }),
                                  jsx("th", { className: "px-4 py-3 font-semibold", children: "Reference" }),
                                  jsx("th", { className: "px-4 py-3 font-semibold", children: "Narration" }),
                                  jsx("th", { className: "px-4 py-3 font-semibold", children: "Source" }),
                                  jsx("th", { className: "px-4 py-3 font-semibold", children: "Status" }),
                                  jsx("th", { className: "px-4 py-3 font-semibold", children: "Match" }),
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
                                        colSpan: 8,
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
                                              className: "px-4 py-4 text-slate-700",
                                              children: jsxs("div", {
                                                children: [
                                                  jsx("p", { className: "font-semibold text-slate-900", children: formatDateTime(line.statement_date) }),
                                                  jsx("p", {
                                                    className: "mt-1 text-xs text-slate-500",
                                                    children: `Value: ${formatDateTime(line.value_date)}`,
                                                  }),
                                                ],
                                              }),
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-4 font-semibold text-slate-900",
                                              children: money(line.amount),
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-4 text-slate-700",
                                              children: line.reference || "--",
                                            }),
                                            jsx("td", {
                                              className: "max-w-[280px] px-4 py-4 text-slate-600",
                                              children: line.narration || "--",
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-4",
                                              children: jsx("span", {
                                                className: "inline-flex rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700",
                                                children: line.source || "--",
                                              }),
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
                                                  jsx("button", {
                                                    type: "button",
                                                    className:
                                                      "rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50",
                                                    onClick: () => runLineAction(line.id, "auto-match"),
                                                    disabled: Boolean(lineAction),
                                                    children: "Match",
                                                  }),
                                                  jsx("button", {
                                                    type: "button",
                                                    className:
                                                      "rounded-full bg-slate-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50",
                                                    onClick: () => runLineAction(line.id, "clear"),
                                                    disabled: Boolean(lineAction),
                                                    children: "Clear",
                                                  }),
                                                  jsx("button", {
                                                    type: "button",
                                                    className:
                                                      "rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50",
                                                    onClick: () => runLineAction(line.id, "ignore"),
                                                    disabled: Boolean(lineAction),
                                                    children: "Ignore",
                                                  }),
                                                  jsx("button", {
                                                    type: "button",
                                                    className:
                                                      "rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50",
                                                    onClick: () => runLineAction(line.id, "unmatch"),
                                                    disabled: Boolean(lineAction),
                                                    children: "Unmatch",
                                                  }),
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
                  jsxs("section", {
                    className: `${surfaceClass} mt-6`,
                    children: [
                      jsxs("div", {
                        className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between",
                        children: [
                          jsxs("div", {
                            children: [
                              jsx("h2", { className: "text-xl font-semibold text-slate-950", children: "Gateway Settlement Watch" }),
                              jsx("p", {
                                className: "mt-1 text-sm text-slate-500",
                                children: "Keep unreconciled external transactions visible without crowding the main bank-lines table.",
                              }),
                            ],
                          }),
                          jsxs("div", {
                            className: "flex flex-wrap gap-2",
                            children: [
                              jsx("button", {
                                type: "button",
                                className:
                                  "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                                onClick: exportBankLines,
                                children: "Export bank lines",
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
                        ],
                      }),
                      jsx("div", {
                        className: "mt-4 space-y-3",
                        children:
                          unreconciledTransactions.length === 0
                            ? jsx("div", {
                                className: `${insetClass} text-sm text-slate-500`,
                                children: "All visible gateway transactions are already reconciled.",
                              })
                            : unreconciledTransactions.map((row) =>
                                jsxs(
                                  "div",
                                  {
                                    className: "rounded-[24px] border border-slate-200 bg-white p-4",
                                    children: [
                                      jsxs("div", {
                                        className: "flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between",
                                        children: [
                                          jsxs("div", {
                                            children: [
                                              jsx("p", {
                                                className: "text-base font-semibold text-slate-950",
                                                children: row.external_id || "--",
                                              }),
                                              jsx("p", {
                                                className: "mt-1 text-sm text-slate-500",
                                                children: `${row.provider || "--"} • ${formatDateTime(row.created_at)}`,
                                              }),
                                              jsx("p", {
                                                className: "mt-1 text-sm text-slate-600",
                                                children: row.student_name || row.invoice_number || "Gateway transaction",
                                              }),
                                            ],
                                          }),
                                          jsxs("div", {
                                            className: "flex flex-wrap items-center gap-3",
                                            children: [
                                              jsx("span", {
                                                className: "text-lg font-semibold text-slate-950",
                                                children: money(row.amount),
                                              }),
                                              jsx("span", {
                                                className: `inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${toneClass(row.status)}`,
                                                children: row.status || "--",
                                              }),
                                              jsx("button", {
                                                type: "button",
                                                className:
                                                  "rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50",
                                                onClick: () => markReconciled(row.id),
                                                disabled: Boolean(txAction),
                                                children: "Mark reconciled",
                                              }),
                                            ],
                                          }),
                                        ],
                                      }),
                                    ],
                                  },
                                  row.id,
                                ),
                              ),
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
