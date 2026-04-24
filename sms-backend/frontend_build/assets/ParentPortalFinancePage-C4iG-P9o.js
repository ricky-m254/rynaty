import { r as React, b as api, j as jsxRuntime } from "./index-D7ltaYVC.js";
import { F as FileText } from "./file-text-BMGjGS-3.js";
import { C as CircleCheck } from "./circle-check-CyyLgyEu.js";
import { C as CircleAlert } from "./circle-alert-QkR7CaoT.js";
import { C as Clock } from "./clock-Cjp0BcMI.js";
import { C as CreditCard } from "./credit-card-pJ6qZy3c.js";
import "./createLucideIcon-BLtbVmUp.js";

const { jsx, jsxs } = jsxRuntime;

const shellClass =
  "rounded-[32px] border border-slate-200/80 bg-[#f6f7fb] p-5 shadow-[0_30px_80px_rgba(15,23,42,0.08)] md:p-7 xl:p-8";
const surfaceClass =
  "rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-[0_22px_50px_rgba(15,23,42,0.06)]";
const insetClass = "rounded-[24px] border border-slate-200 bg-slate-50/80 p-4";
const inputClass =
  "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5";
const modalClass =
  "w-full max-w-xl rounded-[30px] border border-slate-200 bg-white p-6 shadow-[0_30px_80px_rgba(15,23,42,0.25)]";

function formatCurrency(value) {
  return `KES ${Number(value ?? 0).toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatDate(value) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
}

function toAmountInput(value) {
  const amount = Number(value ?? 0);
  if (!Number.isFinite(amount) || amount <= 0) return "";
  return Number.isInteger(amount) ? String(amount) : amount.toFixed(2);
}

function normalizeStatus(value) {
  return String(value || "").toUpperCase();
}

function invoiceBadgeClass(status) {
  return (
    {
      PAID: "border-emerald-200 bg-emerald-50 text-emerald-700",
      PARTIAL: "border-amber-200 bg-amber-50 text-amber-700",
      PARTIALLY_PAID: "border-amber-200 bg-amber-50 text-amber-700",
      PENDING: "border-sky-200 bg-sky-50 text-sky-700",
      OVERDUE: "border-rose-200 bg-rose-50 text-rose-700",
    }[normalizeStatus(status)] ?? "border-slate-200 bg-slate-100 text-slate-700"
  );
}

function flashClass(tone) {
  return (
    {
      success: "border-emerald-200 bg-emerald-50 text-emerald-700",
      warning: "border-amber-200 bg-amber-50 text-amber-700",
      error: "border-rose-200 bg-rose-50 text-rose-700",
      info: "border-sky-200 bg-sky-50 text-sky-700",
    }[tone] ?? "border-slate-200 bg-slate-100 text-slate-700"
  );
}

function SummaryCard({ label, value, icon: Icon, color, background, detail }) {
  return jsxs("div", {
    className: surfaceClass,
    children: [
      jsxs("div", {
        className: "flex items-start justify-between gap-3",
        children: [
          jsxs("div", {
            children: [
              jsx("p", {
                className: "text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400",
                children: label,
              }),
              jsx("p", {
                className: "mt-3 text-2xl font-semibold text-slate-950",
                children: value,
              }),
            ],
          }),
          jsx("div", {
            className: "flex h-11 w-11 items-center justify-center rounded-2xl",
            style: { background },
            children: jsx(Icon, { size: 18, style: { color } }),
          }),
        ],
      }),
      detail ? jsx("p", { className: "mt-3 text-sm text-slate-500", children: detail }) : null,
    ],
  });
}

function ParentPortalFinancePage() {
  const [profile, setProfile] = React.useState({ children: [], selected_child: null });
  const [selectedChildId, setSelectedChildId] = React.useState("");
  const [summary, setSummary] = React.useState({});
  const [invoices, setInvoices] = React.useState([]);
  const [payments, setPayments] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [tab, setTab] = React.useState("invoices");
  const [flash, setFlash] = React.useState(null);
  const [paymentOpen, setPaymentOpen] = React.useState(false);
  const [paymentMethod, setPaymentMethod] = React.useState("mpesa");
  const [selectedInvoiceId, setSelectedInvoiceId] = React.useState("");
  const [paymentAmount, setPaymentAmount] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [paymentError, setPaymentError] = React.useState(null);
  const [paymentStatus, setPaymentStatus] = React.useState(null);
  const [paymentResult, setPaymentResult] = React.useState(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [polling, setPolling] = React.useState(false);
  const [statement, setStatement] = React.useState(null);
  const [statementError, setStatementError] = React.useState(null);
  const [statementLoading, setStatementLoading] = React.useState(false);
  const pollRef = React.useRef(null);

  const activeChild =
    profile.children?.find((item) => String(item.id) === String(selectedChildId)) ||
    profile.selected_child ||
    null;

  const queryForChild = (path, childId = selectedChildId || activeChild?.id) => {
    if (!childId) return path;
    const separator = path.includes("?") ? "&" : "?";
    return `${path}${separator}child_id=${encodeURIComponent(childId)}`;
  };

  const clearPolling = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const refreshFinance = React.useCallback(
    async (childId = selectedChildId) => {
      setLoading(true);
      try {
        const dashboardResponse = await api.get("/parent-portal/dashboard/", {
          params: childId ? { child_id: childId } : undefined,
        });
        const dashboardData = dashboardResponse.data ?? { children: [], selected_child: null };
        setProfile(dashboardData);
        const resolvedChildId = String(childId || dashboardData?.selected_child?.id || "");
        if (resolvedChildId && resolvedChildId !== String(selectedChildId)) {
          setSelectedChildId(resolvedChildId);
        }
        if (!resolvedChildId) {
          setSummary({});
          setInvoices([]);
          setPayments([]);
          setStatement(null);
          setStatementError("No linked child is available for this parent account.");
          setLoading(false);
          return;
        }

        const params = { child_id: resolvedChildId };
        const [summaryResponse, invoiceResponse, paymentResponse] = await Promise.all([
          api.get("/parent-portal/finance/summary/", { params }),
          api.get("/parent-portal/finance/invoices/", { params }),
          api.get("/parent-portal/finance/payments/", { params }),
        ]);
        setSummary(summaryResponse.data ?? {});
        setInvoices(Array.isArray(invoiceResponse.data) ? invoiceResponse.data : []);
        setPayments(Array.isArray(paymentResponse.data) ? paymentResponse.data : []);
        setStatementLoading(true);
        try {
          const statementResponse = await api.get("/parent-portal/finance/statement/", { params });
          setStatement(statementResponse.data ?? null);
          setStatementError(null);
        } catch (statementLoadError) {
          setStatementError("Fee statement summary is unavailable right now.");
        } finally {
          setStatementLoading(false);
        }
      } catch (error) {
        setFlash((current) => current ?? { tone: "error", message: "Unable to load finance records right now." });
      } finally {
        setLoading(false);
      }
    },
    [selectedChildId],
  );

  React.useEffect(() => {
    refreshFinance("");
    return () => {
      clearPolling();
    };
  }, [refreshFinance]);

  React.useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const params = new URLSearchParams(window.location.search);
    const stripeState = params.get("stripe");
    if (!stripeState) return undefined;

    let refreshTimer = null;
    if (stripeState === "success") {
      setFlash({
        tone: "success",
        message: "Stripe checkout completed. If your balance does not refresh immediately, give it a moment and refresh.",
      });
      refreshTimer = window.setTimeout(() => {
        refreshFinance(selectedChildId);
      }, 2500);
    } else if (stripeState === "cancel") {
      setFlash({
        tone: "warning",
        message: "Stripe checkout was canceled before payment completed.",
      });
    }

    params.delete("stripe");
    params.delete("session_id");
    const nextQuery = params.toString();
    const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}${window.location.hash || ""}`;
    window.history.replaceState({}, document.title, nextUrl);

    return () => {
      if (refreshTimer) {
        window.clearTimeout(refreshTimer);
      }
    };
  }, [refreshFinance, selectedChildId]);

  const outstandingBalance = Number(summary.outstanding_balance ?? 0);
  const outstandingInvoices = invoices.filter((invoice) => Number(invoice.balance_due ?? 0) > 0);
  const selectedInvoice =
    outstandingInvoices.find((invoice) => String(invoice.id) === String(selectedInvoiceId)) ?? null;
  const overdueInvoices = outstandingInvoices.filter((invoice) => normalizeStatus(invoice.status) === "OVERDUE");
  const sortedOutstandingInvoices = [...outstandingInvoices].sort((left, right) => {
    const leftDate = left?.due_date ? new Date(left.due_date).getTime() : Number.POSITIVE_INFINITY;
    const rightDate = right?.due_date ? new Date(right.due_date).getTime() : Number.POSITIVE_INFINITY;
    return leftDate - rightDate;
  });
  const nextDueInvoice =
    sortedOutstandingInvoices.find((invoice) => !!invoice.due_date) ?? sortedOutstandingInvoices[0] ?? null;
  const statementSummary = statement?.summary ?? {};
  const latestPayment = payments[0] ?? null;

  const openPortalDocument = (path) => {
    if (typeof window === "undefined") return;
    window.open(queryForChild(path), "_blank", "noopener,noreferrer");
  };

  const openPaymentModal = (invoice = null, preferredMethod = "mpesa") => {
    clearPolling();
    setPaymentMethod(preferredMethod);
    setSelectedInvoiceId(invoice ? String(invoice.id) : "");
    setPaymentAmount(toAmountInput(invoice ? invoice.balance_due : outstandingBalance));
    setPhone("");
    setPaymentError(null);
    setPaymentStatus(null);
    setPaymentResult(null);
    setSubmitting(false);
    setPolling(false);
    setPaymentOpen(true);
  };

  const closePaymentModal = () => {
    clearPolling();
    setPaymentOpen(false);
    setSubmitting(false);
    setPolling(false);
  };

  const startMpesaPolling = (checkoutRequestId) => {
    clearPolling();
    setPolling(true);
    setPaymentResult("pending");
    let attempts = 0;

    pollRef.current = window.setInterval(async () => {
      attempts += 1;
      try {
        const response = await api.get(
          `/parent-portal/finance/mpesa-status/?checkout_request_id=${encodeURIComponent(checkoutRequestId)}`,
        );
        const status = normalizeStatus(response.data?.status);
        if (status === "SUCCEEDED" || status === "COMPLETED") {
          clearPolling();
          setPolling(false);
          setPaymentResult("success");
          setPaymentStatus(response.data?.message || "Payment confirmed.");
          await refreshFinance(selectedChildId);
          return;
        }
        if (status === "FAILED" || status === "CANCELLED" || status === "CANCELED") {
          clearPolling();
          setPolling(false);
          setPaymentResult("failed");
          setPaymentStatus(response.data?.message || "Payment failed. Please try again.");
          return;
        }
        setPaymentStatus(response.data?.message || "Waiting for M-Pesa confirmation...");
      } catch (pollError) {
        if (attempts >= 20) {
          clearPolling();
          setPolling(false);
          setPaymentResult("pending");
          setPaymentStatus("M-Pesa confirmation is taking longer than expected. Check your payment history shortly.");
        }
        return;
      }

      if (attempts >= 20) {
        clearPolling();
        setPolling(false);
        setPaymentResult("pending");
        setPaymentStatus("M-Pesa confirmation is taking longer than expected. Check your payment history shortly.");
      }
    }, 4000);
  };

  const submitPayment = async () => {
    const numericAmount = Number(paymentAmount);
    const maximumAmount = selectedInvoice ? Number(selectedInvoice.balance_due ?? 0) : outstandingBalance;

    if (!paymentAmount || Number.isNaN(numericAmount) || numericAmount <= 0) {
      setPaymentError("Enter a valid amount.");
      return;
    }
    if (numericAmount > maximumAmount) {
      setPaymentError("Amount cannot exceed the selected outstanding balance.");
      return;
    }
    if (paymentMethod === "mpesa" && !phone.trim()) {
      setPaymentError("Phone number is required for M-Pesa payment.");
      return;
    }

    setSubmitting(true);
    setPaymentError(null);
    setPaymentStatus(null);
    setPaymentResult(null);

    try {
      const requestedPaymentMethod = paymentMethod === "bank" ? "Bank Transfer" : paymentMethod;
      const payload = {
        amount: paymentAmount,
        payment_method: requestedPaymentMethod,
        child_id: activeChild?.id,
      };

      if (selectedInvoiceId) {
        payload.invoice_id = Number(selectedInvoiceId);
      }

      if (paymentMethod === "mpesa") {
        payload.phone = phone.trim();
      } else if (paymentMethod === "stripe") {
        payload.success_url = "/modules/parent-portal/finance?stripe=success&session_id={CHECKOUT_SESSION_ID}";
        payload.cancel_url = "/modules/parent-portal/finance?stripe=cancel";
      }

      const response = await api.post("/parent-portal/finance/pay/", payload);
      if (paymentMethod === "stripe") {
        const checkoutUrl = response.data?.checkout_url;
        if (checkoutUrl && typeof window !== "undefined") {
          window.location.assign(checkoutUrl);
          return;
        }
        setPaymentResult("pending");
        setPaymentStatus("Stripe checkout link created, but the redirect URL was not returned.");
        return;
      }

      if (paymentMethod === "bank") {
        setPaymentResult("success");
        setPaymentStatus(
          response.data?.message ||
            `Bank transfer initiated. Use reference ${response.data?.reference_number || "from the portal"} when sending funds.`,
        );
        return;
      }

      const checkoutRequestId = response.data?.checkout_request_id;
      setPaymentStatus(response.data?.message || "STK push sent. Please confirm the payment on your phone.");
      if (checkoutRequestId) {
        startMpesaPolling(checkoutRequestId);
      }
    } catch (submitError) {
      setPaymentError(
        submitError?.response?.data?.error ||
          submitError?.response?.data?.detail ||
          "Unable to initiate payment right now.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && !activeChild) {
    return jsx("div", {
      className: "py-16 text-center text-sm text-slate-500",
      children: "Loading family finance records...",
    });
  }

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
                    children: "Parent Portal",
                  }),
                  jsx("h1", {
                    className: "mt-3 text-3xl font-semibold tracking-tight text-slate-950 md:text-[2.5rem]",
                    children: "Family Account Overview",
                  }),
                  jsx("p", {
                    className: "mt-3 max-w-2xl text-sm leading-6 text-slate-600",
                    children:
                      "Review outstanding invoices, open a fee statement, and pay the correct child account with clearer portal guidance.",
                  }),
                ],
              }),
              activeChild
                ? jsx("div", {
                    className: "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700",
                    children: `${activeChild.name} • ${activeChild.admission_number || "Admission pending"}`,
                  })
                : null,
            ],
          }),
          jsx("div", {
            className: "mt-6 space-y-4",
            children: [
              flash
                ? jsx("div", {
                    className: `rounded-[22px] border px-4 py-3 text-sm ${flashClass(flash.tone)}`,
                    children: flash.message,
                  })
                : null,
              profile.children?.length > 0
                ? jsxs("div", {
                    children: [
                      jsx("p", {
                        className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                        children: "Child Accounts",
                      }),
                      jsx("div", {
                        className: "mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4",
                        children: profile.children.map((child) => {
                          const active = String(child.id) === String(activeChild?.id);
                          return jsx(
                            "button",
                            {
                              type: "button",
                              onClick: async () => {
                                setSelectedChildId(String(child.id));
                                setPaymentOpen(false);
                                await refreshFinance(String(child.id));
                              },
                              className: `rounded-[24px] border p-4 text-left transition ${
                                active
                                  ? "border-slate-900 bg-slate-900 text-white shadow-[0_20px_45px_rgba(15,23,42,0.2)]"
                                  : "border-slate-200 bg-white text-slate-900 hover:-translate-y-[1px] hover:border-slate-300 hover:shadow-[0_18px_40px_rgba(15,23,42,0.08)]"
                              }`,
                              children: jsxs("div", {
                                children: [
                                  jsx("p", { className: "text-sm font-semibold", children: child.name }),
                                  jsx("p", {
                                    className: `mt-1 text-xs ${active ? "text-slate-200" : "text-slate-500"}`,
                                    children: child.admission_number || "No admission number",
                                  }),
                                ],
                              }),
                            },
                            child.id,
                          );
                        }),
                      }),
                    ],
                  })
                : null,
            ],
          }),
          jsx("div", {
            className: "mt-6 grid gap-4 md:grid-cols-3",
            children: [
              {
                label: "Total billed",
                value: formatCurrency(summary.total_billed),
                icon: FileText,
                color: "#0f766e",
                background: "rgba(20,184,166,0.12)",
                detail: `${summary.invoice_count ?? invoices.length} invoice${(summary.invoice_count ?? invoices.length) === 1 ? "" : "s"} in this account.`,
              },
              {
                label: "Total paid",
                value: formatCurrency(summary.total_paid),
                icon: CircleCheck,
                color: "#059669",
                background: "rgba(16,185,129,0.12)",
                detail: latestPayment ? `Latest payment on ${formatDate(latestPayment.payment_date)}.` : "No payment recorded yet.",
              },
              {
                label: "Outstanding balance",
                value: formatCurrency(outstandingBalance),
                icon: outstandingBalance > 0 ? CircleAlert : CircleCheck,
                color: outstandingBalance > 0 ? "#d97706" : "#059669",
                background: outstandingBalance > 0 ? "rgba(245,158,11,0.12)" : "rgba(16,185,129,0.12)",
                detail: outstandingBalance > 0 ? "Ready for M-Pesa, bank transfer, or Stripe Checkout." : "This child account is fully settled.",
              },
            ].map((card) =>
              jsx(
                SummaryCard,
                {
                  label: card.label,
                  value: card.value,
                  icon: card.icon,
                  color: card.color,
                  background: card.background,
                  detail: card.detail,
                },
                card.label,
              ),
            ),
          }),
          jsx("div", {
            className: "mt-6 grid gap-4 xl:grid-cols-[1.35fr,1fr]",
            children: [
              jsxs("section", {
                className: surfaceClass,
                children: [
                  jsx("p", {
                    className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                    children: "Account Snapshot",
                  }),
                  jsx("h2", {
                    className: "mt-2 text-xl font-semibold text-slate-950",
                    children: activeChild ? activeChild.name : "Family account",
                  }),
                  jsx("div", {
                    className: "mt-4 grid gap-3 sm:grid-cols-2",
                    children: [
                      {
                        label: "Admission No.",
                        value: activeChild?.admission_number || "--",
                      },
                      {
                        label: "Outstanding invoices",
                        value: String(outstandingInvoices.length),
                      },
                      {
                        label: "Overdue invoices",
                        value: String(overdueInvoices.length),
                      },
                      {
                        label: "Next due",
                        value: nextDueInvoice?.due_date ? formatDate(nextDueInvoice.due_date) : "--",
                      },
                    ].map((item) =>
                      jsxs(
                        "div",
                        {
                          className: insetClass,
                          children: [
                            jsx("p", {
                              className: "text-[11px] uppercase tracking-[0.22em] text-slate-400",
                              children: item.label,
                            }),
                            jsx("p", {
                              className: "mt-2 text-sm font-semibold text-slate-900",
                              children: item.value,
                            }),
                          ],
                        },
                        item.label,
                      ),
                    ),
                  }),
                  jsx("p", {
                    className: "mt-4 text-sm text-slate-500",
                    children:
                      "Use this child selector whenever a family has more than one learner. Every payment, statement, and balance view below follows the currently active child account.",
                  }),
                ],
              }),
              jsxs("section", {
                className: surfaceClass,
                children: [
                  jsx("p", {
                    className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                    children: "Statement & Actions",
                  }),
                  jsx("h2", {
                    className: "mt-2 text-xl font-semibold text-slate-950",
                    children: "Printable fee statement",
                  }),
                  jsx("div", {
                    className: "mt-4 grid gap-3 sm:grid-cols-3",
                    children: [
                      { label: "Billed", value: formatCurrency(statementSummary.billed ?? summary.total_billed) },
                      { label: "Paid", value: formatCurrency(statementSummary.paid ?? summary.total_paid) },
                      { label: "Balance", value: formatCurrency(statementSummary.balance ?? outstandingBalance) },
                    ].map((item) =>
                      jsxs(
                        "div",
                        {
                          className: insetClass,
                          children: [
                            jsx("p", {
                              className: "text-[11px] uppercase tracking-[0.22em] text-slate-400",
                              children: item.label,
                            }),
                            jsx("p", { className: "mt-2 text-sm font-semibold text-slate-900", children: item.value }),
                          ],
                        },
                        item.label,
                      ),
                    ),
                  }),
                  jsx("p", {
                    className: `mt-4 text-sm ${statementError ? "text-amber-600" : "text-slate-500"}`,
                    children: statementError
                      ? statementError
                      : "Open the printable statement when you need invoice and payment detail for this child account.",
                  }),
                  jsxs("div", {
                    className: "mt-4 flex flex-wrap gap-2",
                    children: [
                      jsx("button", {
                        type: "button",
                        onClick: () => openPortalDocument("/api/parent-portal/finance/statement/download/"),
                        className:
                          "rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800",
                        children: statementLoading ? "Refreshing..." : "Open statement",
                      }),
                      jsx("button", {
                        type: "button",
                        onClick: () => openPaymentModal(nextDueInvoice, "mpesa"),
                        disabled: !outstandingBalance,
                        className:
                          "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50",
                        children: "Pay now",
                      }),
                    ],
                  }),
                ],
              }),
            ],
          }),
          outstandingBalance > 0
            ? jsxs("div", {
                className: "mt-6 flex flex-col gap-4 rounded-[28px] border border-amber-200 bg-amber-50 p-5 lg:flex-row lg:items-center lg:justify-between",
                children: [
                  jsxs("div", {
                    className: "flex items-start gap-3",
                    children: [
                      jsx(CreditCard, { size: 18, className: "mt-0.5 flex-shrink-0 text-amber-600" }),
                      jsxs("div", {
                        children: [
                          jsx("p", {
                            className: "text-sm font-semibold text-amber-800",
                            children: "Portal payments are ready",
                          }),
                          jsx("p", {
                            className: "mt-1 text-sm text-amber-700",
                            children: `Outstanding for ${activeChild?.name || "this child"}: ${formatCurrency(outstandingBalance)}.`,
                          }),
                        ],
                      }),
                    ],
                  }),
                  jsxs("div", {
                    className: "flex flex-wrap gap-2",
                    children: [
                      jsx("button", {
                        type: "button",
                        onClick: () => openPaymentModal(nextDueInvoice, "mpesa"),
                        className:
                          "rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800",
                        children: "Pay with M-Pesa",
                      }),
                      jsx("button", {
                        type: "button",
                        onClick: () => openPaymentModal(nextDueInvoice, "bank"),
                        className:
                          "rounded-full border border-amber-300 bg-white px-4 py-2 text-sm font-semibold text-amber-700 transition hover:border-amber-400 hover:bg-amber-100",
                        children: "Create bank reference",
                      }),
                    ],
                  }),
                ],
              })
            : null,
          jsx("div", {
            className: "mt-6 flex flex-wrap gap-2",
            children: [
              { id: "invoices", label: `Outstanding Invoices (${invoices.length})` },
              { id: "payments", label: `Payment History (${payments.length})` },
              { id: "statement", label: "Summary" },
            ].map((item) =>
              jsx(
                "button",
                {
                  type: "button",
                  onClick: () => setTab(item.id),
                  className: `rounded-full px-4 py-2 text-sm font-semibold transition ${
                    tab === item.id
                      ? "bg-slate-900 text-white shadow-[0_12px_30px_rgba(15,23,42,0.16)]"
                      : "border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
                  }`,
                  children: item.label,
                },
                item.id,
              ),
            ),
          }),
          loading
            ? jsx("div", {
                className: "mt-6 py-12 text-center text-sm text-slate-500",
                children: "Loading financial records...",
              })
            : tab === "invoices"
              ? jsx("div", {
                  className: "mt-6 space-y-4",
                  children:
                    invoices.length === 0
                      ? jsx("div", {
                          className: `${surfaceClass} text-center text-sm text-slate-500`,
                          children: "No invoices found for this child account.",
                        })
                      : invoices.map((invoice) => {
                          const balanceDue = Number(invoice.balance_due ?? 0);
                          return jsx(
                            "div",
                            {
                              className: surfaceClass,
                              children: jsxs("div", {
                                className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between",
                                children: [
                                  jsxs("div", {
                                    className: "min-w-0 flex-1",
                                    children: [
                                      jsxs("div", {
                                        className: "flex flex-wrap items-center gap-2",
                                        children: [
                                          jsx("span", {
                                            className: `inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${invoiceBadgeClass(invoice.status)}`,
                                            children: invoice.status || "PENDING",
                                          }),
                                          jsx("span", {
                                            className: "rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-500",
                                            children: invoice.invoice_number || `Invoice #${invoice.id}`,
                                          }),
                                        ],
                                      }),
                                      jsx("p", {
                                        className: "mt-3 text-lg font-semibold text-slate-950",
                                        children: `School fees for ${activeChild?.name || "this child"}`,
                                      }),
                                      jsxs("div", {
                                        className: "mt-2 flex flex-wrap gap-4 text-sm text-slate-500",
                                        children: [
                                          jsx("span", { children: `Issued: ${formatDate(invoice.invoice_date)}` }),
                                          jsx("span", {
                                            className: "inline-flex items-center gap-1",
                                            children: [jsx(Clock, { size: 12 }), `Due: ${formatDate(invoice.due_date)}`],
                                          }),
                                        ],
                                      }),
                                    ],
                                  }),
                                  jsxs("div", {
                                    className: "flex flex-col gap-3 lg:items-end",
                                    children: [
                                      jsxs("div", {
                                        className: "text-left lg:text-right",
                                        children: [
                                          jsx("p", {
                                            className: "text-lg font-semibold text-slate-950",
                                            children: formatCurrency(invoice.total_amount),
                                          }),
                                          jsx("p", {
                                            className: "mt-1 text-sm text-emerald-600",
                                            children: `Paid: ${formatCurrency(Number(invoice.total_amount ?? 0) - balanceDue)}`,
                                          }),
                                          balanceDue > 0
                                            ? jsx("p", {
                                                className: "mt-1 text-sm text-amber-600",
                                                children: `Due: ${formatCurrency(balanceDue)}`,
                                              })
                                            : null,
                                        ],
                                      }),
                                      jsxs("div", {
                                        className: "flex flex-wrap gap-2",
                                        children: [
                                          invoice.download_url
                                            ? jsx("a", {
                                                href: invoice.download_url,
                                                target: "_blank",
                                                rel: "noreferrer",
                                                className:
                                                  "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                                                children: "Download",
                                              })
                                            : null,
                                          balanceDue > 0
                                            ? jsx("button", {
                                                type: "button",
                                                onClick: () => openPaymentModal(invoice, "mpesa"),
                                                className:
                                                  "rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800",
                                                children: "Pay this invoice",
                                              })
                                            : null,
                                        ],
                                      }),
                                    ],
                                  }),
                                ],
                              }),
                            },
                            invoice.id,
                          );
                        }),
                })
              : tab === "payments"
                ? jsx("div", {
                    className: "mt-6 space-y-4",
                    children:
                      payments.length === 0
                        ? jsx("div", {
                            className: `${surfaceClass} text-center text-sm text-slate-500`,
                            children: "No payments recorded for this child account yet.",
                          })
                        : payments.map((payment) =>
                            jsx(
                              "div",
                              {
                                className: surfaceClass,
                                children: jsxs("div", {
                                  className: "flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between",
                                  children: [
                                    jsxs("div", {
                                      children: [
                                        jsx("p", {
                                          className: "text-sm font-semibold text-slate-950",
                                          children: payment.reference_number || payment.transaction_reference || "Payment",
                                        }),
                                        jsx("p", {
                                          className: "mt-1 text-sm text-slate-500",
                                          children: `${formatDate(payment.payment_date)} • ${payment.payment_method?.replace(/_/g, " ") ?? "--"}`,
                                        }),
                                      ],
                                    }),
                                    jsxs("div", {
                                      className: "flex flex-wrap items-center gap-3",
                                      children: [
                                        jsx("span", {
                                          className: "text-lg font-semibold text-emerald-600",
                                          children: formatCurrency(payment.amount),
                                        }),
                                        payment.receipt_url
                                          ? jsx("a", {
                                              href: payment.receipt_url,
                                              target: "_blank",
                                              rel: "noreferrer",
                                              className:
                                                "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                                              children: "Receipt",
                                            })
                                          : null,
                                      ],
                                    }),
                                  ],
                                }),
                              },
                              payment.id,
                            ),
                          ),
                  })
                : jsx("div", {
                    className: "mt-6 grid gap-4 xl:grid-cols-[1.05fr,0.95fr]",
                    children: [
                      jsxs("section", {
                        className: surfaceClass,
                        children: [
                          jsx("p", {
                            className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                            children: "Statement Summary",
                          }),
                          jsx("h2", {
                            className: "mt-2 text-xl font-semibold text-slate-950",
                            children: "What the bursar will see",
                          }),
                          jsx("div", {
                            className: "mt-4 space-y-3",
                            children: [
                              {
                                label: "Total billed",
                                value: formatCurrency(statementSummary.billed ?? summary.total_billed),
                              },
                              {
                                label: "Total paid",
                                value: formatCurrency(statementSummary.paid ?? summary.total_paid),
                              },
                              {
                                label: "Balance",
                                value: formatCurrency(statementSummary.balance ?? outstandingBalance),
                              },
                            ].map((item) =>
                              jsxs(
                                "div",
                                {
                                  className: insetClass,
                                  children: [
                                    jsx("p", {
                                      className: "text-[11px] uppercase tracking-[0.22em] text-slate-400",
                                      children: item.label,
                                    }),
                                    jsx("p", {
                                      className: "mt-2 text-sm font-semibold text-slate-900",
                                      children: item.value,
                                    }),
                                  ],
                                },
                                item.label,
                              ),
                            ),
                          }),
                        ],
                      }),
                      jsxs("section", {
                        className: surfaceClass,
                        children: [
                          jsx("p", {
                            className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                            children: "Payment Planning",
                          }),
                          jsx("h2", {
                            className: "mt-2 text-xl font-semibold text-slate-950",
                            children: "What needs attention next",
                          }),
                          jsx("div", {
                            className: "mt-4 space-y-3",
                            children: [
                              {
                                label: "Outstanding invoices",
                                value: String(outstandingInvoices.length),
                              },
                              {
                                label: "Overdue invoices",
                                value: String(overdueInvoices.length),
                              },
                              {
                                label: "Next due invoice",
                                value: nextDueInvoice
                                  ? `${nextDueInvoice.invoice_number || `Invoice #${nextDueInvoice.id}`} • ${formatCurrency(nextDueInvoice.balance_due)}`
                                  : "No upcoming due invoice",
                              },
                            ].map((item) =>
                              jsxs(
                                "div",
                                {
                                  className: insetClass,
                                  children: [
                                    jsx("p", {
                                      className: "text-[11px] uppercase tracking-[0.22em] text-slate-400",
                                      children: item.label,
                                    }),
                                    jsx("p", {
                                      className: "mt-2 text-sm font-semibold text-slate-900",
                                      children: item.value,
                                    }),
                                  ],
                                },
                                item.label,
                              ),
                            ),
                          }),
                        ],
                      }),
                    ],
                  }),
        ],
      }),
      paymentOpen
        ? jsx("div", {
            className: "fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4",
            children: jsx("div", {
              className: modalClass,
              children: jsxs("div", {
                className: "space-y-5",
                children: [
                  jsxs("div", {
                    className: "flex items-start justify-between gap-4",
                    children: [
                      jsxs("div", {
                        children: [
                          jsx("p", {
                            className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                            children: "Pay Account",
                          }),
                          jsx("h2", {
                            className: "mt-2 text-xl font-semibold text-slate-950",
                            children: "Make a payment",
                          }),
                          jsx("p", {
                            className: "mt-1 text-sm text-slate-500",
                            children: selectedInvoice
                              ? `${selectedInvoice.invoice_number || `Invoice #${selectedInvoice.id}`} • Outstanding ${formatCurrency(selectedInvoice.balance_due)}`
                              : `Apply payment to ${activeChild?.name || "this account"} with a balance of ${formatCurrency(outstandingBalance)}.`,
                          }),
                        ],
                      }),
                      jsx("button", {
                        type: "button",
                        onClick: closePaymentModal,
                        className: "text-2xl leading-none text-slate-400 transition hover:text-slate-700",
                        children: "×",
                      }),
                    ],
                  }),
                  jsx("div", {
                    className: "grid grid-cols-3 gap-2 rounded-[24px] border border-slate-200 bg-slate-50 p-1",
                    children: [
                      { id: "mpesa", label: "M-Pesa" },
                      { id: "stripe", label: "Card / Stripe" },
                      { id: "bank", label: "Bank transfer" },
                    ].map((method) =>
                      jsx(
                        "button",
                        {
                          type: "button",
                          onClick: () => {
                            setPaymentMethod(method.id);
                            setPaymentError(null);
                          },
                          className: `rounded-[20px] px-3 py-2 text-sm font-semibold transition ${
                            paymentMethod === method.id
                              ? "bg-slate-900 text-white"
                              : "text-slate-500 hover:text-slate-900"
                          }`,
                          children: method.label,
                        },
                        method.id,
                      ),
                    ),
                  }),
                  jsx("div", {
                    className: `rounded-[22px] border px-4 py-3 text-sm ${flashClass(
                      paymentMethod === "bank" ? "info" : paymentMethod === "stripe" ? "success" : "warning",
                    )}`,
                    children:
                      paymentMethod === "mpesa"
                        ? "We will send an STK push to the Safaricom number you enter. Keep this screen open while the portal checks for confirmation."
                        : paymentMethod === "stripe"
                          ? "Stripe opens a secure hosted card checkout. After payment, you will return here and the balance refreshes after webhook confirmation."
                          : "Bank transfer creates a narration reference for your slip or transfer note. The balance updates after finance reconciles the bank line.",
                  }),
                  outstandingInvoices.length > 0
                    ? jsxs("label", {
                        className: "block text-sm text-slate-700",
                        children: [
                          jsx("span", { className: "font-medium", children: "Apply to invoice" }),
                          jsx("select", {
                            value: selectedInvoiceId,
                            onChange: (event) => {
                              const nextId = event.target.value;
                              const nextInvoice =
                                outstandingInvoices.find((invoice) => String(invoice.id) === String(nextId)) ?? null;
                              setSelectedInvoiceId(nextId);
                              setPaymentAmount(toAmountInput(nextInvoice ? nextInvoice.balance_due : outstandingBalance));
                              setPaymentError(null);
                            },
                            className: `mt-2 ${inputClass}`,
                            children: [
                              jsx("option", { value: "", children: "Overall outstanding balance" }),
                              ...outstandingInvoices.map((invoice) =>
                                jsx(
                                  "option",
                                  {
                                    value: invoice.id,
                                    children: `${invoice.invoice_number || `Invoice #${invoice.id}`} • ${formatCurrency(invoice.balance_due)}`,
                                  },
                                  invoice.id,
                                ),
                              ),
                            ],
                          }),
                        ],
                      })
                    : null,
                  jsxs("label", {
                    className: "block text-sm text-slate-700",
                    children: [
                      jsx("span", { className: "font-medium", children: "Amount (KES)" }),
                      jsx("input", {
                        type: "number",
                        min: "1",
                        max: selectedInvoice ? selectedInvoice.balance_due : outstandingBalance,
                        value: paymentAmount,
                        onChange: (event) => {
                          setPaymentAmount(event.target.value);
                          setPaymentError(null);
                        },
                        className: `mt-2 ${inputClass}`,
                      }),
                    ],
                  }),
                  paymentMethod === "mpesa"
                    ? jsxs("label", {
                        className: "block text-sm text-slate-700",
                        children: [
                          jsx("span", { className: "font-medium", children: "Safaricom phone number" }),
                          jsx("input", {
                            type: "tel",
                            value: phone,
                            onChange: (event) => {
                              setPhone(event.target.value);
                              setPaymentError(null);
                            },
                            placeholder: "e.g. 0712345678",
                            className: `mt-2 ${inputClass}`,
                          }),
                        ],
                      })
                    : null,
                  paymentMethod === "bank"
                    ? jsx("div", {
                        className: "rounded-[22px] border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700",
                        children:
                          "Create a bank-transfer reference here, then include it in the transfer narration or deposit slip. Balance updates after reconciliation.",
                      })
                    : null,
                  paymentError
                    ? jsx("div", {
                        className: "rounded-[22px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700",
                        children: paymentError,
                      })
                    : null,
                  paymentStatus
                    ? jsx("div", {
                        className: `rounded-[22px] border px-4 py-3 text-sm ${flashClass(
                          paymentResult === "success"
                            ? "success"
                            : paymentResult === "failed"
                              ? "error"
                              : "info",
                        )}`,
                        children: paymentStatus,
                      })
                    : null,
                  jsxs("div", {
                    className: "flex flex-col gap-2 sm:flex-row",
                    children: [
                      jsx("button", {
                        type: "button",
                        onClick: submitPayment,
                        disabled: submitting || polling,
                        className:
                          "flex-1 rounded-full bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60",
                        children:
                          paymentMethod === "stripe"
                            ? submitting
                              ? "Preparing checkout..."
                              : "Continue to Stripe"
                            : paymentMethod === "bank"
                              ? submitting
                                ? "Creating transfer reference..."
                                : "Create bank reference"
                              : submitting
                                ? "Sending STK push..."
                                : "Send M-Pesa prompt",
                      }),
                      jsx("button", {
                        type: "button",
                        onClick: closePaymentModal,
                        className:
                          "rounded-full border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                        children: paymentResult === "success" ? "Close" : "Cancel",
                      }),
                    ],
                  }),
                ],
              }),
            }),
          })
        : null,
    ],
  });
}

export { ParentPortalFinancePage as default };
