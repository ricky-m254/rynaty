import { r as React, b as api, j as jsxRuntime } from "./index-D7ltaYVC.js";
import { F as FileText } from "./file-text-BMGjGS-3.js";
import { C as CircleCheck } from "./circle-check-CyyLgyEu.js";
import { C as CircleAlert } from "./circle-alert-QkR7CaoT.js";
import { C as Clock } from "./clock-Cjp0BcMI.js";
import { C as CreditCard } from "./credit-card-pJ6qZy3c.js";
import "./createLucideIcon-BLtbVmUp.js";

const { jsx, jsxs } = jsxRuntime;

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.07)",
};

const modalStyle = {
  background: "#0f172a",
  border: "1px solid rgba(148,163,184,0.22)",
  boxShadow: "0 32px 80px rgba(15,23,42,0.55)",
};

function formatCurrency(value) {
  return `KES ${Number(value ?? 0).toLocaleString()}`;
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
      PAID: "bg-emerald-500/15 text-emerald-300",
      PARTIAL: "bg-amber-500/15 text-amber-300",
      PARTIALLY_PAID: "bg-amber-500/15 text-amber-300",
      PENDING: "bg-sky-500/15 text-sky-300",
      OVERDUE: "bg-rose-500/15 text-rose-300",
    }[normalizeStatus(status)] ?? "bg-slate-500/15 text-slate-300"
  );
}

function flashClass(tone) {
  return (
    {
      success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
      warning: "border-amber-500/30 bg-amber-500/10 text-amber-200",
      error: "border-rose-500/30 bg-rose-500/10 text-rose-200",
      info: "border-sky-500/30 bg-sky-500/10 text-sky-200",
    }[tone] ?? "border-white/10 bg-white/[0.04] text-slate-200"
  );
}

function SummaryCard({ label, value, icon: Icon, color, background }) {
  return jsxs("div", {
    className: "flex items-center gap-4 rounded-2xl p-5",
    style: panelStyle,
    children: [
      jsx("div", {
        className: "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl",
        style: { background },
        children: jsx(Icon, { size: 18, style: { color } }),
      }),
      jsxs("div", {
        children: [
          jsx("p", {
            className: "text-[10px] uppercase tracking-wider text-slate-500",
            children: label,
          }),
          jsx("p", {
            className: "text-lg font-bold font-mono",
            style: { color },
            children: value,
          }),
        ],
      }),
    ],
  });
}

function ParentPortalFinancePage() {
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

  const refreshFinance = async () => {
    try {
      const [summaryResponse, invoiceResponse, paymentResponse] = await Promise.all([
        api.get("/parent-portal/finance/summary/"),
        api.get("/parent-portal/finance/invoices/"),
        api.get("/parent-portal/finance/payments/"),
      ]);
      setSummary(summaryResponse.data ?? {});
      setInvoices(Array.isArray(invoiceResponse.data) ? invoiceResponse.data : []);
      setPayments(Array.isArray(paymentResponse.data) ? paymentResponse.data : []);
      setStatementLoading(true);
      try {
        const statementResponse = await api.get("/parent-portal/finance/statement/");
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
  };

  const clearPolling = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  React.useEffect(() => {
    setLoading(true);
    refreshFinance();
    return () => {
      clearPolling();
    };
  }, []);

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
        refreshFinance();
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
  }, []);

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
  const nextDueInvoice = sortedOutstandingInvoices.find((invoice) => !!invoice.due_date) ?? sortedOutstandingInvoices[0] ?? null;
  const statementSummary = statement?.summary ?? {};
  const latestPayment = payments[0] ?? null;
  const openPortalDocument = (path) => {
    if (typeof window === "undefined") return;
    window.open(path, "_blank", "noopener,noreferrer");
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
          await refreshFinance();
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

  return jsxs("div", {
    className: "space-y-6",
    children: [
      jsxs("div", {
        children: [
          jsx("p", {
            className: "mb-1 text-[10px] font-bold uppercase tracking-widest text-amber-400",
            children: "FINANCE",
          }),
          jsx("h1", { className: "text-2xl font-display font-bold text-white", children: "Financial Information" }),
          jsx("p", {
            className: "mt-1 text-sm text-slate-500",
            children: "Fees, invoices, payment history, and live portal payment options for your child.",
          }),
        ],
      }),
      flash &&
        jsx("div", {
          className: `flex items-start gap-2 rounded-xl border px-4 py-3 text-sm ${flashClass(flash.tone)}`,
          children: jsxs(React.Fragment, {
            children: [
              jsx(CircleAlert, { size: 16, className: "mt-0.5 flex-shrink-0" }),
              jsx("span", { children: flash.message }),
            ],
          }),
        }),
      jsx("div", {
        className: "grid grid-cols-1 gap-3 sm:grid-cols-3",
        children: [
          {
            label: "Total Billed",
            value: formatCurrency(summary.total_billed),
            icon: FileText,
            color: "#38bdf8",
            background: "rgba(14,165,233,0.1)",
          },
          {
            label: "Total Paid",
            value: formatCurrency(summary.total_paid),
            icon: CircleCheck,
            color: "#10b981",
            background: "rgba(16,185,129,0.1)",
          },
          {
            label: "Outstanding Balance",
            value: formatCurrency(outstandingBalance),
            icon: outstandingBalance > 0 ? CircleAlert : CircleCheck,
            color: outstandingBalance > 0 ? "#f59e0b" : "#10b981",
            background: outstandingBalance > 0 ? "rgba(245,158,11,0.1)" : "rgba(16,185,129,0.1)",
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
            },
            card.label,
          ),
        ),
      }),
      jsx("div", {
        className: "grid grid-cols-1 gap-4 xl:grid-cols-[1.35fr,1fr]",
        children: [
          jsxs("section", {
            className: "rounded-2xl p-5",
            style: panelStyle,
            children: [
              jsxs("div", {
                className: "flex flex-wrap items-start justify-between gap-3",
                children: [
                  jsxs("div", {
                    children: [
                      jsx("p", {
                        className: "text-[10px] font-bold uppercase tracking-[0.28em] text-sky-300",
                        children: "Fee statement",
                      }),
                      jsx("h2", {
                        className: "mt-2 text-lg font-semibold text-white",
                        children: "Printable statement and summary",
                      }),
                      jsx("p", {
                        className: "mt-1 text-sm text-slate-400",
                        children: "Use the live statement summary to verify billed, paid, and balance before you pay.",
                      }),
                    ],
                  }),
                  jsx("button", {
                    type: "button",
                    onClick: refreshFinance,
                    className:
                      "rounded-xl border border-white/[0.09] px-4 py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/[0.04]",
                    children: statementLoading ? "Refreshing..." : "Refresh summary",
                  }),
                ],
              }),
              jsx("div", {
                className: "mt-4 grid gap-3 sm:grid-cols-3",
                children: [
                  {
                    label: "Billed",
                    value: formatCurrency(statementSummary.billed ?? summary.total_billed),
                    tone: "text-sky-300",
                  },
                  {
                    label: "Paid",
                    value: formatCurrency(statementSummary.paid ?? summary.total_paid),
                    tone: "text-emerald-300",
                  },
                  {
                    label: "Balance",
                    value: formatCurrency(statementSummary.balance ?? outstandingBalance),
                    tone: Number(statementSummary.balance ?? outstandingBalance) > 0 ? "text-amber-300" : "text-emerald-300",
                  },
                ].map((item) =>
                  jsxs(
                    "div",
                    {
                      className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4",
                      children: [
                        jsx("p", { className: "text-[11px] uppercase tracking-wide text-slate-500", children: item.label }),
                        jsx("p", { className: `mt-2 text-lg font-semibold ${item.tone}`, children: item.value }),
                      ],
                    },
                    item.label,
                  ),
                ),
              }),
              statementError
                ? jsx("p", { className: "mt-3 text-xs text-amber-200", children: statementError })
                : jsx("p", {
                    className: "mt-3 text-xs text-slate-500",
                    children: "Open the printable statement to review invoice and payment detail or save it as PDF for records.",
                  }),
              jsxs("div", {
                className: "mt-4 flex flex-wrap gap-2",
                children: [
                  jsx("button", {
                    type: "button",
                    onClick: () => openPortalDocument("/api/parent-portal/finance/statement/download/"),
                    className:
                      "rounded-xl bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-300",
                    children: "Printable statement",
                  }),
                  jsx("button", {
                    type: "button",
                    onClick: () => openPaymentModal(nextDueInvoice, "stripe"),
                    disabled: !outstandingBalance,
                    className:
                      "rounded-xl border border-white/[0.1] px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-white/[0.04] disabled:cursor-not-allowed disabled:opacity-50",
                    children: "Pay from statement",
                  }),
                ],
              }),
            ],
          }),
          jsxs("section", {
            className: "rounded-2xl p-5",
            style: panelStyle,
            children: [
              jsx("p", {
                className: "text-[10px] font-bold uppercase tracking-[0.28em] text-amber-300",
                children: "Payment planning",
              }),
              jsx("h2", {
                className: "mt-2 text-lg font-semibold text-white",
                children: "What needs attention next",
              }),
              jsx("div", {
                className: "mt-4 space-y-3",
                children: [
                  {
                    label: "Outstanding invoices",
                    value: String(outstandingInvoices.length),
                    detail: outstandingInvoices.length > 0 ? "Ready for M-Pesa, bank transfer, or Stripe" : "All caught up",
                  },
                  {
                    label: "Overdue invoices",
                    value: String(overdueInvoices.length),
                    detail: overdueInvoices.length > 0 ? "Settle these first to clear arrears" : "No overdue items right now",
                  },
                  {
                    label: "Next due",
                    value: nextDueInvoice?.due_date ? formatDate(nextDueInvoice.due_date) : "--",
                    detail: nextDueInvoice
                      ? `${nextDueInvoice.invoice_number || `Invoice #${nextDueInvoice.id}`} • ${formatCurrency(nextDueInvoice.balance_due)}`
                      : "No upcoming due invoice",
                  },
                  {
                    label: "Latest payment",
                    value: latestPayment?.payment_date ? formatDate(latestPayment.payment_date) : "--",
                    detail: latestPayment
                      ? `${formatCurrency(latestPayment.amount)} via ${latestPayment.payment_method || "payment"}`
                      : "No payment recorded yet",
                  },
                ].map((item) =>
                  jsxs(
                    "div",
                    {
                      className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4",
                      children: [
                        jsx("p", { className: "text-[11px] uppercase tracking-wide text-slate-500", children: item.label }),
                        jsx("p", { className: "mt-2 text-lg font-semibold text-white", children: item.value }),
                        jsx("p", { className: "mt-1 text-xs text-slate-500", children: item.detail }),
                      ],
                    },
                    item.label,
                  ),
                ),
              }),
              jsx("p", {
                className: "mt-4 text-xs text-slate-500",
                children: "If you need extra time, the printable statement gives the bursar the exact invoice trail to discuss a school-managed installment plan.",
              }),
              jsxs("div", {
                className: "mt-4 flex flex-wrap gap-2",
                children: [
                  jsx("button", {
                    type: "button",
                    onClick: () => openPaymentModal(nextDueInvoice, "mpesa"),
                    disabled: !nextDueInvoice,
                    className:
                      "rounded-xl border border-emerald-400/40 bg-emerald-400/12 px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/18 disabled:cursor-not-allowed disabled:opacity-50",
                    children: "Pay next invoice",
                  }),
                  jsx("button", {
                    type: "button",
                    onClick: () => openPaymentModal(nextDueInvoice, "bank"),
                    disabled: !nextDueInvoice,
                    className:
                      "rounded-xl border border-white/[0.1] px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-white/[0.04] disabled:cursor-not-allowed disabled:opacity-50",
                    children: "Create bank reference",
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
      outstandingBalance > 0 &&
        jsxs("div", {
          className: "flex flex-col gap-4 rounded-2xl px-5 py-4 sm:flex-row sm:items-center",
          style: { background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.22)" },
          children: [
            jsxs("div", {
              className: "flex flex-1 items-start gap-3",
              children: [
                jsx(CreditCard, { size: 18, className: "mt-0.5 flex-shrink-0 text-amber-400" }),
                jsxs("div", {
                  children: [
                    jsx("p", {
                      className: "text-sm font-semibold text-amber-100",
                      children: "Portal payments are ready",
                    }),
                    jsxs("p", {
                      className: "text-sm text-amber-200",
                      children: [
                        "Your child has an outstanding balance of ",
                        jsx("strong", { children: formatCurrency(outstandingBalance) }),
                        ". Choose M-Pesa, bank transfer, or continue to Stripe Checkout from this portal.",
                      ],
                    }),
                  ],
                }),
              ],
            }),
            jsx("button", {
              type: "button",
              onClick: () => openPaymentModal(null, "mpesa"),
              className:
                "w-full rounded-xl border border-emerald-400/40 bg-emerald-400/12 px-5 py-2.5 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/18 sm:w-auto",
              children: "Pay now",
            }),
          ],
        }),
      jsx("div", {
        className: "flex gap-2",
        children: ["invoices", "payments"].map((section) =>
          jsx(
            "button",
            {
              type: "button",
              onClick: () => setTab(section),
              className: `rounded-xl px-4 py-2 text-sm font-medium transition-all ${
                tab === section ? "bg-amber-500/20 text-amber-300" : "text-slate-500 hover:text-slate-300"
              }`,
              children:
                section === "invoices" ? `Invoices (${invoices.length})` : `Payments (${payments.length})`,
            },
            section,
          ),
        ),
      }),
      loading
        ? jsx("div", {
            className: "py-12 text-center text-sm text-slate-500",
            children: "Loading financial records...",
          })
        : tab === "invoices"
          ? jsx("div", {
              className: "space-y-3",
              children:
                invoices.length === 0
                  ? jsx("div", {
                      className: "rounded-2xl p-10 text-center text-sm text-slate-500",
                      style: panelStyle,
                      children: "No invoices found.",
                    })
                  : invoices.map((invoice) => {
                      const balanceDue = Number(invoice.balance_due ?? 0);
                      return jsx(
                        "div",
                        {
                          className: "rounded-2xl p-5",
                          style: panelStyle,
                          children: jsxs("div", {
                            className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between",
                            children: [
                              jsxs("div", {
                                className: "min-w-0 flex-1",
                                children: [
                                  jsxs("div", {
                                    className: "mb-1 flex flex-wrap items-center gap-2",
                                    children: [
                                      jsx("span", {
                                        className: `rounded-full px-2 py-0.5 text-[10px] font-bold ${invoiceBadgeClass(
                                          invoice.status,
                                        )}`,
                                        children: invoice.status || "PENDING",
                                      }),
                                      jsx("span", {
                                        className: "font-mono text-xs text-slate-500",
                                        children: `Invoice #${invoice.id}`,
                                      }),
                                    ],
                                  }),
                                  jsx("p", {
                                    className: "font-semibold text-slate-200",
                                    children: `School Fees Invoice #${invoice.id}`,
                                  }),
                                  jsxs("div", {
                                    className: "mt-1.5 flex flex-wrap gap-3 text-xs text-slate-500",
                                    children: [
                                      jsx("span", { children: `Issued: ${formatDate(invoice.invoice_date)}` }),
                                      jsx("span", {
                                        className: "flex items-center gap-1",
                                        children: [jsx(Clock, { size: 10 }), `Due: ${formatDate(invoice.due_date)}`],
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
                                        className: "text-sm font-bold text-white",
                                        children: formatCurrency(invoice.total_amount),
                                      }),
                                      jsx("p", {
                                        className: "text-xs text-emerald-400",
                                        children: `Paid: ${formatCurrency(
                                          Number(invoice.total_amount ?? 0) - balanceDue,
                                        )}`,
                                      }),
                                      balanceDue > 0 &&
                                        jsx("p", {
                                          className: "text-xs text-amber-400",
                                          children: `Due: ${formatCurrency(balanceDue)}`,
                                        }),
                                    ],
                                  }),
                                  jsxs("div", {
                                    className: "flex flex-wrap gap-2",
                                    children: [
                                      invoice.download_url &&
                                        jsx("a", {
                                          href: invoice.download_url,
                                          target: "_blank",
                                          rel: "noreferrer",
                                          className:
                                            "rounded-xl border border-white/[0.1] px-4 py-2 text-xs font-semibold text-slate-300 transition hover:bg-white/[0.04]",
                                          children: "Download",
                                        }),
                                      balanceDue > 0 &&
                                        jsx("button", {
                                          type: "button",
                                          onClick: () => openPaymentModal(invoice, "mpesa"),
                                          className:
                                            "rounded-xl border border-emerald-400/35 bg-emerald-400/10 px-4 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/15",
                                          children: "Pay now",
                                        }),
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
          : jsx("div", {
                          className: "overflow-x-auto rounded-2xl",
              style: panelStyle,
              children:
                payments.length === 0
                  ? jsx("p", {
                      className: "py-10 text-center text-sm text-slate-500",
                      children: "No payments recorded.",
                    })
                  : jsxs("table", {
                      className: "w-full text-sm",
                      children: [
                        jsx("thead", {
                          children: jsx("tr", {
                            className: "border-b border-white/[0.07]",
                            children: ["Date", "Amount", "Method", "Reference", "Receipt"].map((label) =>
                              jsx(
                                "th",
                                {
                                  className: "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500",
                                  children: label,
                                },
                                label,
                              ),
                            ),
                          }),
                        }),
                        jsx("tbody", {
                          className: "divide-y divide-white/[0.04]",
                          children: payments.map((payment, index) =>
                            jsxs(
                              "tr",
                              {
                                className: `hover:bg-white/[0.015] ${index % 2 !== 0 ? "bg-white/[0.008]" : ""}`,
                                children: [
                                  jsx("td", {
                                    className: "px-4 py-3 text-slate-400",
                                    children: formatDate(payment.payment_date),
                                  }),
                                  jsx("td", {
                                    className: "px-4 py-3 font-semibold text-emerald-300",
                                    children: formatCurrency(payment.amount),
                                  }),
                                  jsx("td", {
                                    className: "px-4 py-3 capitalize text-slate-400",
                                    children: payment.payment_method?.replace(/_/g, " ") ?? "--",
                                  }),
                                  jsx("td", {
                                    className: "px-4 py-3 font-mono text-xs text-slate-500",
                                    children: payment.reference_number || "--",
                                  }),
                                  jsx("td", {
                                    className: "px-4 py-3",
                                    children: payment.receipt_url
                                      ? jsx("a", {
                                          href: payment.receipt_url,
                                          target: "_blank",
                                          rel: "noreferrer",
                                          className:
                                            "inline-flex rounded-full border border-white/[0.1] px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-300 transition hover:bg-white/[0.04]",
                                          children: "Receipt",
                                        })
                                      : jsx("span", {
                                          className: "text-xs text-slate-600",
                                          children: "--",
                                        }),
                                  }),
                                ],
                              },
                              payment.id,
                            ),
                          ),
                        }),
                      ],
                    }),
            }),
      paymentOpen &&
        jsx("div", {
          className: "fixed inset-0 z-50 flex items-center justify-center p-4",
          style: { background: "rgba(2,6,23,0.78)" },
          children: jsx("div", {
            className: "w-full max-w-lg rounded-3xl p-6",
            style: modalStyle,
            children: jsxs("div", {
              className: "space-y-5",
              children: [
                jsxs("div", {
                  className: "flex items-start justify-between gap-4",
                  children: [
                    jsxs("div", {
                      children: [
                        jsx("h2", { className: "text-lg font-semibold text-white", children: "Make a payment" }),
                        jsx("p", {
                          className: "mt-1 text-xs text-slate-400",
                          children: selectedInvoice
                            ? `Invoice #${selectedInvoice.id} | Outstanding ${formatCurrency(selectedInvoice.balance_due)}`
                            : `Apply a payment against the overall outstanding balance of ${formatCurrency(outstandingBalance)}.`,
                        }),
                      ],
                    }),
                    jsx("button", {
                      type: "button",
                      onClick: closePaymentModal,
                      className: "text-xl text-slate-500 transition hover:text-slate-300",
                      children: "x",
                    }),
                  ],
                }),
                jsx("div", {
                  className: "grid grid-cols-3 gap-2 rounded-2xl bg-slate-900/70 p-1",
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
                        className: `rounded-xl px-3 py-2 text-sm font-semibold transition ${
                          paymentMethod === method.id
                            ? "bg-emerald-400/15 text-emerald-100"
                            : "text-slate-400 hover:text-slate-200"
                        }`,
                        children: method.label,
                      },
                      method.id,
                    ),
                  ),
                }),
                jsx("div", {
                  className: `rounded-2xl border px-4 py-3 text-xs ${flashClass(paymentMethod === "bank" ? "info" : paymentMethod === "stripe" ? "success" : "warning")}`,
                  children:
                    paymentMethod === "mpesa"
                      ? "We will send an STK push to the Safaricom number you enter. Keep this screen open while the portal checks for confirmation."
                      : paymentMethod === "stripe"
                        ? "Stripe opens a secure hosted card checkout. After payment, you will return here and the balance refreshes after webhook confirmation."
                        : "Bank transfer creates a narration reference for your slip or transfer note. The balance only updates after finance reconciles the bank line.",
                }),
                outstandingInvoices.length > 0 &&
                  jsxs("label", {
                    className: "block text-sm",
                    children: [
                      jsx("span", {
                        className: "mb-1 block text-xs text-slate-400",
                        children: "Apply to invoice",
                      }),
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
                        className:
                          "w-full rounded-xl border border-white/[0.08] bg-slate-950 px-4 py-2.5 text-sm text-white outline-none focus:border-emerald-400/40",
                        children: [
                          jsx("option", { value: "", children: "Overall outstanding balance" }),
                          ...outstandingInvoices.map((invoice) =>
                            jsx(
                              "option",
                              {
                                value: invoice.id,
                                children: `Invoice #${invoice.id} | ${formatCurrency(invoice.balance_due)}`,
                              },
                              invoice.id,
                            ),
                          ),
                        ],
                      }),
                    ],
                  }),
                jsxs("label", {
                  className: "block text-sm",
                  children: [
                    jsx("span", { className: "mb-1 block text-xs text-slate-400", children: "Amount (KES)" }),
                    jsx("input", {
                      type: "number",
                      min: "1",
                      max: selectedInvoice ? selectedInvoice.balance_due : outstandingBalance,
                      value: paymentAmount,
                      onChange: (event) => {
                        setPaymentAmount(event.target.value);
                        setPaymentError(null);
                      },
                      className:
                        "w-full rounded-xl border border-white/[0.08] bg-slate-950 px-4 py-2.5 text-sm text-white outline-none focus:border-emerald-400/40",
                    }),
                  ],
                }),
                paymentMethod === "mpesa" &&
                  jsxs("label", {
                    className: "block text-sm",
                    children: [
                      jsx("span", { className: "mb-1 block text-xs text-slate-400", children: "Safaricom phone number" }),
                      jsx("input", {
                        type: "tel",
                        value: phone,
                        onChange: (event) => {
                          setPhone(event.target.value);
                          setPaymentError(null);
                        },
                        placeholder: "e.g. 0712345678",
                        className:
                          "w-full rounded-xl border border-white/[0.08] bg-slate-950 px-4 py-2.5 text-sm text-white outline-none focus:border-emerald-400/40",
                      }),
                    ],
                  }),
                paymentMethod === "bank" &&
                  jsx("div", {
                    className: "rounded-xl border border-sky-500/25 bg-sky-500/10 px-4 py-3 text-xs text-sky-100",
                    children:
                      "Create a bank-transfer reference here, then include it in your transfer narration or deposit slip. The balance updates after reconciliation.",
                  }),
                paymentError &&
                  jsx("div", {
                    className: "rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200",
                    children: paymentError,
                  }),
                paymentStatus &&
                  jsx("div", {
                    className: `rounded-xl border px-4 py-3 text-sm ${flashClass(
                      paymentResult === "success"
                        ? "success"
                        : paymentResult === "failed"
                          ? "error"
                          : "info",
                    )}`,
                    children: paymentStatus,
                  }),
                jsxs("div", {
                  className: "flex flex-col gap-2 sm:flex-row",
                  children: [
                    jsx("button", {
                      type: "button",
                      onClick: submitPayment,
                      disabled: submitting || polling,
                      className:
                        "flex-1 rounded-xl bg-emerald-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60",
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
                        "rounded-xl border border-white/[0.1] px-4 py-2.5 text-sm font-semibold text-slate-300 transition hover:bg-white/[0.04]",
                      children: paymentResult === "success" ? "Close" : "Cancel",
                    }),
                  ],
                }),
              ],
            }),
          }),
        }),
    ],
  });
}

export { ParentPortalFinancePage as default };
