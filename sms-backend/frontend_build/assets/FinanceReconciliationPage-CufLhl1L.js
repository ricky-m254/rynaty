import { r as React, j as jsxRuntime, b as api } from "./index-D7ltaYVC.js";
import { a as downloadResponse, d as downloadBlob } from "./download-EzDvBC7h.js";
import { e as getErrorMessage } from "./forms-ZJa1TpnO.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";

const normalizeList = (payload) => (Array.isArray(payload) ? payload : payload?.results ?? []);
const money = (value) => Number(value ?? 0).toLocaleString(void 0, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const panelClass = "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-5 shadow-[0_24px_80px_rgba(15,23,42,0.45)]";

function Notice({ tone = "success", message }) {
  if (!message) return null;
  const classes =
    tone === "error"
      ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
      : "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
  return jsxRuntime.jsx("div", {
    className: `col-span-12 rounded-2xl border p-4 text-xs ${classes}`,
    children: message,
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

  const setFlash = (nextError, nextSuccess) => {
    setError(nextError);
    setSuccess(nextSuccess);
  };

  const runLineAction = async (lineId, action) => {
    if (loading || txAction !== null || eventAction !== null || lineAction !== null) return;
    setLineAction({ lineId, action });
    setFlash(null, null);
    try {
      await api.post(`/finance/reconciliation/bank-lines/${lineId}/${action}/`);
      setSuccess(`Line ${action} completed.`);
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
    setFlash(null, null);
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
    setFlash(null, null);
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
    setFlash(null, null);
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

  const filteredBankLines = bankLines.filter((line) => {
    const statusMatch = !bankStatus || line.status === bankStatus;
    const term = bankSearch.trim().toLowerCase();
    const searchMatch =
      !term ||
      `${line.reference ?? ""} ${line.narration ?? ""} ${line.source ?? ""}`.toLowerCase().includes(term);
    return statusMatch && searchMatch;
  });

  const canReprocessEvent = (row) =>
    (
      (row.provider === "mpesa" && row.event_type === "stk_callback") ||
      (row.provider === "stripe" && String(row.event_type || "").startsWith("checkout.session"))
    ) && (!row.processed || !!row.error);

  return jsxRuntime.jsxs("div", {
    className: "grid grid-cols-12 gap-6",
    children: [
      jsxRuntime.jsx(PageHero, {
        badge: "FINANCE MODULE",
        badgeColor: "emerald",
        title: "Gateway and Reconciliation",
        subtitle: "Track Stripe and M-Pesa collection events, reconcile bank lines, and replay stuck webhook callbacks.",
        icon: "💰",
      }),
      loading
        ? jsxRuntime.jsx("div", {
            className: `col-span-12 ${panelClass} text-sm text-slate-300`,
            children: "Loading reconciliation data...",
          })
        : null,
      jsxRuntime.jsx(Notice, { tone: "error", message: error }),
      jsxRuntime.jsx(Notice, { tone: "success", message: success }),
      jsxRuntime.jsxs("section", {
        className: `col-span-12 xl:col-span-6 ${panelClass}`,
        children: [
          jsxRuntime.jsxs("div", {
            className: "flex items-center justify-between gap-2",
            children: [
              jsxRuntime.jsx("h2", { className: "text-base font-semibold", children: "Gateway Transactions" }),
              jsxRuntime.jsxs("div", {
                className: "flex items-center gap-2",
                children: [
                  jsxRuntime.jsx("button", {
                    type: "button",
                    className: "rounded-lg border border-white/[0.09] px-3 py-1 text-xs text-slate-200",
                    onClick: exportTransactions,
                    children: "Export CSV",
                  }),
                  jsxRuntime.jsx("button", {
                    type: "button",
                    className: "rounded-lg border border-white/[0.09] px-3 py-1 text-xs text-slate-200",
                    onClick: loadWorkspace,
                    disabled: loading || txAction !== null || eventAction !== null || lineAction !== null,
                    children: "Refresh",
                  }),
                ],
              }),
            ],
          }),
          jsxRuntime.jsx("div", {
            className: "mt-3 overflow-x-auto rounded-xl border border-white/[0.07]",
            children: jsxRuntime.jsxs("table", {
              className: "min-w-[820px] w-full text-left text-sm",
              children: [
                jsxRuntime.jsx("thead", {
                  className: "bg-white/[0.03] text-xs uppercase tracking-wide text-slate-400",
                  children: jsxRuntime.jsxs("tr", {
                    children: [
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Provider" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "External ID" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Amount" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Status" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Reconciled" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Action" }),
                    ],
                  }),
                }),
                jsxRuntime.jsxs("tbody", {
                  className: "divide-y divide-slate-800",
                  children: [
                    transactions.map((row) =>
                      jsxRuntime.jsxs(
                        "tr",
                        {
                          className: "bg-slate-950/60",
                          children: [
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.provider }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.external_id }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: money(row.amount) }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.status }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.is_reconciled ? "Yes" : "No" }),
                            jsxRuntime.jsx("td", {
                              className: "px-3 py-2",
                              children: row.is_reconciled
                                ? jsxRuntime.jsx("span", { className: "text-xs text-slate-500", children: "-" })
                                : jsxRuntime.jsx("button", {
                                    type: "button",
                                    className: "rounded border border-white/[0.09] px-2 py-0.5 text-[11px] text-slate-200",
                                    onClick: () => markReconciled(row.id),
                                    disabled: loading || txAction !== null || eventAction !== null || lineAction !== null,
                                    children: txAction === row.id ? "Marking..." : "Mark reconciled",
                                  }),
                            }),
                          ],
                        },
                        row.id,
                      ),
                    ),
                    transactions.length === 0
                      ? jsxRuntime.jsx("tr", {
                          className: "bg-slate-950/60",
                          children: jsxRuntime.jsx("td", {
                            className: "px-3 py-4 text-xs text-slate-400",
                            colSpan: 6,
                            children: "No gateway transactions yet.",
                          }),
                        })
                      : null,
                  ],
                }),
              ],
            }),
          }),
        ],
      }),
      jsxRuntime.jsxs("section", {
        className: `col-span-12 xl:col-span-6 ${panelClass}`,
        children: [
          jsxRuntime.jsxs("div", {
            className: "flex items-center justify-between gap-2",
            children: [
              jsxRuntime.jsx("h2", { className: "text-base font-semibold", children: "Webhook Events" }),
              jsxRuntime.jsx("button", {
                type: "button",
                className: "rounded-lg border border-white/[0.09] px-3 py-1 text-xs text-slate-200",
                onClick: exportEvents,
                children: "Export CSV",
              }),
            ],
          }),
          jsxRuntime.jsx("div", {
            className: "mt-3 overflow-x-auto rounded-xl border border-white/[0.07]",
            children: jsxRuntime.jsxs("table", {
              className: "min-w-[860px] w-full text-left text-sm",
              children: [
                jsxRuntime.jsx("thead", {
                  className: "bg-white/[0.03] text-xs uppercase tracking-wide text-slate-400",
                  children: jsxRuntime.jsxs("tr", {
                    children: [
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Provider" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Type" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Event ID" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Processed" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Error" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Action" }),
                    ],
                  }),
                }),
                jsxRuntime.jsxs("tbody", {
                  className: "divide-y divide-slate-800",
                  children: [
                    events.map((row) =>
                      jsxRuntime.jsxs(
                        "tr",
                        {
                          className: "bg-slate-950/60",
                          children: [
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.provider }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.event_type }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.event_id }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.processed ? "Yes" : "No" }),
                            jsxRuntime.jsx("td", {
                              className: "px-3 py-2 text-xs text-rose-300",
                              children: row.error || "-",
                            }),
                            jsxRuntime.jsx("td", {
                              className: "px-3 py-2",
                              children: canReprocessEvent(row)
                                ? jsxRuntime.jsx("button", {
                                    type: "button",
                                    className: "rounded border border-amber-500/40 px-2 py-0.5 text-[11px] text-amber-200",
                                    onClick: () => reprocessEvent(row.id),
                                    disabled: loading || txAction !== null || eventAction !== null || lineAction !== null,
                                    children: eventAction === row.id ? "Reprocessing..." : "Reprocess",
                                  })
                                : jsxRuntime.jsx("span", { className: "text-xs text-slate-500", children: "-" }),
                            }),
                          ],
                        },
                        row.id,
                      ),
                    ),
                    events.length === 0
                      ? jsxRuntime.jsx("tr", {
                          className: "bg-slate-950/60",
                          children: jsxRuntime.jsx("td", {
                            className: "px-3 py-4 text-xs text-slate-400",
                            colSpan: 6,
                            children: "No webhook events recorded.",
                          }),
                        })
                      : null,
                  ],
                }),
              ],
            }),
          }),
        ],
      }),
      jsxRuntime.jsxs("section", {
        className: `col-span-12 ${panelClass}`,
        children: [
          jsxRuntime.jsxs("div", {
            className: "flex flex-wrap items-center justify-between gap-3",
            children: [
              jsxRuntime.jsx("h2", { className: "text-base font-semibold", children: "Bank Statement Lines" }),
              jsxRuntime.jsxs("div", {
                className: "flex flex-wrap gap-2",
                children: [
                  jsxRuntime.jsxs("label", {
                    className: "cursor-pointer rounded-xl border border-white/[0.09] px-3 py-2 text-xs text-slate-200",
                    children: [
                      importing ? "Importing..." : "Import CSV",
                      jsxRuntime.jsx("input", {
                        type: "file",
                        accept: ".csv,text/csv",
                        className: "hidden",
                        onChange: handleImport,
                        disabled: importing || loading || txAction !== null || eventAction !== null || lineAction !== null,
                      }),
                    ],
                  }),
                  jsxRuntime.jsx("button", {
                    type: "button",
                    className: "rounded-xl border border-white/[0.09] px-3 py-2 text-xs text-slate-200",
                    onClick: exportBankLines,
                    disabled: importing || loading || txAction !== null || eventAction !== null || lineAction !== null,
                    children: "Export CSV",
                  }),
                  jsxRuntime.jsx("input", {
                    value: bankSearch,
                    onChange: (event) => setBankSearch(event.target.value),
                    placeholder: "Search reference, narration, source",
                    className:
                      "w-72 rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-400",
                  }),
                  jsxRuntime.jsxs("select", {
                    value: bankStatus,
                    onChange: (event) => setBankStatus(event.target.value),
                    className:
                      "rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-400",
                    children: [
                      jsxRuntime.jsx("option", { value: "", children: "All statuses" }),
                      jsxRuntime.jsx("option", { value: "UNMATCHED", children: "UNMATCHED" }),
                      jsxRuntime.jsx("option", { value: "MATCHED", children: "MATCHED" }),
                      jsxRuntime.jsx("option", { value: "CLEARED", children: "CLEARED" }),
                      jsxRuntime.jsx("option", { value: "IGNORED", children: "IGNORED" }),
                    ],
                  }),
                  jsxRuntime.jsx("button", {
                    type: "button",
                    className: "rounded-xl border border-white/[0.09] px-3 py-2 text-xs text-slate-200",
                    onClick: () => {
                      setBankSearch("");
                      setBankStatus("");
                    },
                    children: "Reset",
                  }),
                ],
              }),
            ],
          }),
          jsxRuntime.jsx("div", {
            className: "mt-3 overflow-x-auto rounded-xl border border-white/[0.07]",
            children: jsxRuntime.jsxs("table", {
              className: "min-w-[1080px] w-full text-left text-sm",
              children: [
                jsxRuntime.jsx("thead", {
                  className: "bg-white/[0.03] text-xs uppercase tracking-wide text-slate-400",
                  children: jsxRuntime.jsxs("tr", {
                    children: [
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Date" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Amount" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Reference" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Status" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Matched Payment" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Matched Gateway Tx" }),
                      jsxRuntime.jsx("th", { className: "px-3 py-2", children: "Actions" }),
                    ],
                  }),
                }),
                jsxRuntime.jsxs("tbody", {
                  className: "divide-y divide-slate-800",
                  children: [
                    filteredBankLines.map((row) =>
                      jsxRuntime.jsxs(
                        "tr",
                        {
                          className: "bg-slate-950/60",
                          children: [
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.statement_date }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: money(row.amount) }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.reference || "-" }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.status }),
                            jsxRuntime.jsx("td", { className: "px-3 py-2", children: row.matched_payment_reference || "-" }),
                            jsxRuntime.jsx("td", {
                              className: "px-3 py-2",
                              children: row.matched_gateway_external_id || "-",
                            }),
                            jsxRuntime.jsx("td", {
                              className: "px-3 py-2",
                              children: jsxRuntime.jsxs("div", {
                                className: "flex flex-wrap gap-1",
                                children: [
                                  jsxRuntime.jsx("button", {
                                    type: "button",
                                    className: "rounded border border-white/[0.09] px-2 py-0.5 text-[11px] text-slate-200",
                                    onClick: () => runLineAction(row.id, "auto-match"),
                                    disabled: loading || txAction !== null || eventAction !== null || lineAction !== null,
                                    children:
                                      lineAction?.lineId === row.id && lineAction?.action === "auto-match"
                                        ? "Working..."
                                        : "Auto-match",
                                  }),
                                  jsxRuntime.jsx("button", {
                                    type: "button",
                                    className: "rounded border border-white/[0.09] px-2 py-0.5 text-[11px] text-slate-200",
                                    onClick: () => runLineAction(row.id, "clear"),
                                    disabled: loading || txAction !== null || eventAction !== null || lineAction !== null,
                                    children:
                                      lineAction?.lineId === row.id && lineAction?.action === "clear"
                                        ? "Working..."
                                        : "Clear",
                                  }),
                                  jsxRuntime.jsx("button", {
                                    type: "button",
                                    className: "rounded border border-white/[0.09] px-2 py-0.5 text-[11px] text-slate-200",
                                    onClick: () => runLineAction(row.id, "unmatch"),
                                    disabled: loading || txAction !== null || eventAction !== null || lineAction !== null,
                                    children:
                                      lineAction?.lineId === row.id && lineAction?.action === "unmatch"
                                        ? "Working..."
                                        : "Unmatch",
                                  }),
                                  jsxRuntime.jsx("button", {
                                    type: "button",
                                    className: "rounded border border-white/[0.09] px-2 py-0.5 text-[11px] text-slate-200",
                                    onClick: () => runLineAction(row.id, "ignore"),
                                    disabled: loading || txAction !== null || eventAction !== null || lineAction !== null,
                                    children:
                                      lineAction?.lineId === row.id && lineAction?.action === "ignore"
                                        ? "Working..."
                                        : "Ignore",
                                  }),
                                ],
                              }),
                            }),
                          ],
                        },
                        row.id,
                      ),
                    ),
                    filteredBankLines.length === 0
                      ? jsxRuntime.jsx("tr", {
                          className: "bg-slate-950/60",
                          children: jsxRuntime.jsx("td", {
                            className: "px-3 py-4 text-xs text-slate-400",
                            colSpan: 7,
                            children: "No bank statement lines match this filter.",
                          }),
                        })
                      : null,
                  ],
                }),
              ],
            }),
          }),
        ],
      }),
    ],
  });
}

export { FinanceReconciliationPage as default };
