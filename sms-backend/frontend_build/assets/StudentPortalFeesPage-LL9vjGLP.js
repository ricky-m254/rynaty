import { r as React, j as jsxRuntime, b as api } from "./index-D7ltaYVC.js";
import { C as CircleAlert } from "./circle-alert-QkR7CaoT.js";
import { C as CreditCard } from "./credit-card-pJ6qZy3c.js";
import { C as Clock } from "./clock-Cjp0BcMI.js";
import { C as CircleCheckBig } from "./circle-check-big-gKc9ia_Q.js";
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

function toAmountInput(value) {
  const amount = Number(value ?? 0);
  if (!Number.isFinite(amount) || amount <= 0) return "";
  return Number.isInteger(amount) ? String(amount) : amount.toFixed(2);
}

function formatDate(value) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
}

function normalizeStatus(value) {
  return String(value || "").toLowerCase();
}

function normalizeGatewayStatus(value) {
  return String(value || "").toUpperCase();
}

function invoiceBadgeClass(status) {
  return (
    {
      paid: "bg-emerald-500/15 text-emerald-300",
      partial: "bg-amber-500/15 text-amber-300",
      partially_paid: "bg-amber-500/15 text-amber-300",
      pending: "bg-sky-500/15 text-sky-300",
      overdue: "bg-rose-500/15 text-rose-300",
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

function statusIcon(status) {
  const normalized = normalizeStatus(status);
  if (normalized === "paid") {
    return jsx(CircleCheckBig, { size: 13, className: "text-emerald-400" });
  }
  if (normalized === "partial" || normalized === "partially_paid" || normalized === "pending") {
    return jsx(Clock, { size: 13, className: "text-amber-300" });
  }
  return jsx(CircleAlert, { size: 13, className: "text-rose-300" });
}

function FeesPage() {
  const [invoices, setInvoices] = React.useState([]);
  const [payments, setPayments] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [flash, setFlash] = React.useState(null);
  const [paymentOpen, setPaymentOpen] = React.useState(false);
  const [selectedInvoice, setSelectedInvoice] = React.useState(null);
  const [paymentMethod, setPaymentMethod] = React.useState("mpesa");
  const [paymentAmount, setPaymentAmount] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [paymentError, setPaymentError] = React.useState(null);
  const [paymentStatus, setPaymentStatus] = React.useState(null);
  const [paymentResult, setPaymentResult] = React.useState(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [polling, setPolling] = React.useState(false);
  const pollRef = React.useRef(null);

  const refreshFees = async () => {
    try {
      const [invoiceResponse, paymentResponse] = await Promise.all([
        api.get("/student-portal/my-invoices/"),
        api.get("/student-portal/my-payments/"),
      ]);
      setInvoices(Array.isArray(invoiceResponse.data) ? invoiceResponse.data : []);
      setPayments(Array.isArray(paymentResponse.data) ? paymentResponse.data : []);
      setError(null);
    } catch (loadError) {
      setError("Could not load fee information. Please contact the school office.");
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
    refreshFees();
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
        message: "Stripe checkout completed. If your balance does not update immediately, give it a moment and refresh.",
      });
      refreshTimer = window.setTimeout(() => {
        refreshFees();
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

  const totalBilled = invoices.reduce((sum, invoice) => sum + Number(invoice.amount ?? 0), 0);
  const totalPaid = invoices.reduce((sum, invoice) => sum + Number(invoice.amount_paid ?? 0), 0);
  const balanceDue = invoices.reduce((sum, invoice) => sum + Number(invoice.balance ?? 0), 0);
  const hasOverdue = invoices.some((invoice) => normalizeStatus(invoice.status) === "overdue");
  const outstandingInvoices = invoices.filter((invoice) => Number(invoice.balance ?? 0) > 0);

  const openPaymentModal = (invoice, preferredMethod = "mpesa") => {
    clearPolling();
    setSelectedInvoice(invoice);
    setPaymentMethod(preferredMethod);
    setPaymentAmount(toAmountInput(invoice?.balance));
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
          `/student-portal/finance/mpesa-status/?checkout_request_id=${encodeURIComponent(checkoutRequestId)}`,
        );
        const status = normalizeGatewayStatus(response.data?.status);
        if (status === "SUCCEEDED" || status === "COMPLETED") {
          clearPolling();
          setPolling(false);
          setPaymentResult("success");
          setPaymentStatus(response.data?.message || "Payment confirmed.");
          await refreshFees();
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
    const invoice = selectedInvoice;
    const numericAmount = Number(paymentAmount);

    if (!invoice?.id) {
      setPaymentError("Select an invoice before attempting payment.");
      return;
    }
    if (!paymentAmount || Number.isNaN(numericAmount) || numericAmount <= 0) {
      setPaymentError("Enter a valid amount.");
      return;
    }
    if (numericAmount > Number(invoice.balance ?? 0)) {
      setPaymentError("Amount cannot exceed the outstanding balance on this invoice.");
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
        invoice_id: invoice.id,
        amount: paymentAmount,
        payment_method: requestedPaymentMethod,
      };

      if (paymentMethod === "mpesa") {
        payload.phone = phone.trim();
      } else if (paymentMethod === "stripe") {
        payload.success_url = "/student-portal/fees?stripe=success&session_id={CHECKOUT_SESSION_ID}";
        payload.cancel_url = "/student-portal/fees?stripe=cancel";
      }

      const response = await api.post("/student-portal/finance/pay/", payload);
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

  if (loading) {
    return jsx("div", {
      className: "flex items-center justify-center py-24",
      children: jsxs("div", {
        className: "space-y-3 text-center",
        children: [
          jsx("div", {
            className: "mx-auto h-8 w-8 animate-spin rounded-full border-t-2 border-emerald-500",
          }),
          jsx("p", { className: "text-sm text-slate-500", children: "Loading fee information..." }),
        ],
      }),
    });
  }

  return jsxs("div", {
    className: "mx-auto max-w-5xl space-y-6",
    children: [
      jsxs("div", {
        children: [
          jsx("h1", { className: "text-2xl font-display font-bold text-white", children: "My Fees" }),
          jsx("p", {
            className: "mt-1 text-sm text-slate-500",
            children: "View your invoices, payment history, and pay outstanding balances from the portal.",
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
      error &&
        jsxs("div", {
          className: "flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300",
          children: [jsx(CircleAlert, { size: 16, className: "mt-0.5 flex-shrink-0" }), error],
        }),
      hasOverdue &&
        jsxs("div", {
          className: "flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300",
          children: [
            jsx(CircleAlert, { size: 16, className: "mt-0.5 flex-shrink-0" }),
            "One or more invoices are overdue. You can still settle them here via M-Pesa, bank transfer, or Stripe Checkout.",
          ],
        }),
      balanceDue > 0 &&
        jsxs("div", {
          className: "flex flex-col gap-4 rounded-2xl px-5 py-4 sm:flex-row sm:items-center",
          style: { background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.18)" },
          children: [
            jsxs("div", {
              className: "flex items-start gap-3",
              children: [
                jsx(CreditCard, { size: 18, className: "mt-0.5 flex-shrink-0 text-emerald-300" }),
                jsxs("div", {
                  children: [
                    jsx("p", { className: "text-sm font-semibold text-emerald-100", children: "Payments are live in the student portal" }),
                    jsx("p", {
                      className: "text-xs text-emerald-200/80",
                      children: `Outstanding across your invoices: ${formatCurrency(balanceDue)}.`,
                    }),
                  ],
                }),
              ],
            }),
            outstandingInvoices[0] &&
              jsx("button", {
                type: "button",
                onClick: () => openPaymentModal(outstandingInvoices[0], "mpesa"),
                className:
                  "w-full rounded-xl border border-emerald-400/40 bg-emerald-400/15 px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/20 sm:ml-auto sm:w-auto",
                children: "Pay now",
              }),
          ],
        }),
      jsx("div", {
        className: "grid gap-3 md:grid-cols-3",
        children: [
          { label: "Total Billed", value: formatCurrency(totalBilled), color: "text-white" },
          { label: "Total Paid", value: formatCurrency(totalPaid), color: "text-emerald-400" },
          {
            label: "Balance Due",
            value: formatCurrency(balanceDue),
            color: balanceDue > 0 ? "text-rose-400" : "text-emerald-400",
          },
        ].map((card) =>
          jsxs(
            "div",
            {
              className: "rounded-2xl p-4",
              style: panelStyle,
              children: [
                jsx("p", { className: `text-xl font-bold ${card.color}`, children: card.value }),
                jsx("p", { className: "mt-1 text-xs text-slate-500", children: card.label }),
              ],
            },
            card.label,
          ),
        ),
      }),
      invoices.length === 0
        ? jsxs("div", {
            className: "rounded-2xl p-8 text-center",
            style: panelStyle,
            children: [
              jsx(CreditCard, { className: "mx-auto mb-3 text-slate-600", size: 32 }),
              jsx("p", { className: "text-sm text-slate-400", children: "No fee invoices found for your account." }),
              jsx("p", {
                className: "mt-1 text-xs text-slate-600",
                children: "Contact the school office if you believe this is an error.",
              }),
            ],
          })
        : jsxs("div", {
            className: "space-y-3",
            children: [
              jsx("h2", { className: "text-sm font-semibold text-slate-300", children: "Invoices" }),
              invoices.map((invoice) => {
                const invoiceBalance = Number(invoice.balance ?? 0);
                const invoiceStatus = normalizeStatus(invoice.status);
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
                              className: "flex flex-wrap items-center gap-2",
                              children: [
                                jsx("p", {
                                  className: "text-sm font-semibold text-slate-200",
                                  children: invoice.description || invoice.invoice_number || `Invoice #${invoice.id}`,
                                }),
                                jsxs("span", {
                                  className: `inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${invoiceBadgeClass(
                                    invoiceStatus,
                                  )}`,
                                  children: [statusIcon(invoiceStatus), String(invoice.status || "Pending").replace("_", " ")],
                                }),
                              ],
                            }),
                            jsxs("div", {
                              className: "mt-2 flex flex-wrap gap-4 text-xs text-slate-500",
                              children: [
                                jsx("span", { children: invoice.invoice_number || `Invoice #${invoice.id}` }),
                                invoice.term && jsxs("span", { children: ["Term: ", invoice.term] }),
                                invoice.academic_year && jsxs("span", { children: ["Year: ", invoice.academic_year] }),
                                invoice.due_date &&
                                  jsxs("span", {
                                    className: "inline-flex items-center gap-1",
                                    children: [jsx(Clock, { size: 12 }), "Due: ", formatDate(invoice.due_date)],
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
                                jsx("p", { className: "text-sm font-bold text-white", children: formatCurrency(invoice.amount) }),
                                jsx("p", {
                                  className: "text-xs text-emerald-400",
                                  children: `Paid: ${formatCurrency(invoice.amount_paid)}`,
                                }),
                                invoiceBalance > 0 &&
                                  jsx("p", {
                                    className: "text-xs text-rose-400",
                                    children: `Due: ${formatCurrency(invoiceBalance)}`,
                                  }),
                              ],
                            }),
                            invoiceBalance > 0 &&
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
                  },
                  invoice.id,
                );
              }),
            ],
          }),
      payments.length > 0 &&
        jsxs("div", {
          className: "space-y-3",
          children: [
            jsx("h2", { className: "text-sm font-semibold text-slate-300", children: "Payment History" }),
            jsx("div", {
              className: "overflow-x-auto rounded-2xl",
              style: panelStyle,
              children: jsxs("table", {
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
                    children: payments.map((payment, index) =>
                      jsxs(
                        "tr",
                        {
                          className: `border-b border-white/[0.04] ${index % 2 === 0 ? "" : "bg-white/[0.01]"}`,
                          children: [
                            jsx("td", {
                              className: "whitespace-nowrap px-4 py-3 text-slate-400",
                              children: formatDate(payment.payment_date),
                            }),
                            jsx("td", {
                              className: "px-4 py-3 font-semibold text-emerald-300",
                              children: formatCurrency(payment.amount_paid),
                            }),
                            jsx("td", {
                              className: "px-4 py-3 capitalize text-slate-400",
                              children: payment.payment_method?.replace(/_/g, " ") ?? "--",
                            }),
                            jsx("td", {
                              className: "px-4 py-3 font-mono text-xs text-slate-500",
                              children: payment.transaction_reference || "--",
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
          ],
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
                        jsx("h2", { className: "text-lg font-semibold text-white", children: "Pay invoice" }),
                        jsx("p", {
                          className: "mt-1 text-xs text-slate-400",
                          children: selectedInvoice
                            ? `${selectedInvoice.invoice_number || `Invoice #${selectedInvoice.id}`} | Outstanding ${formatCurrency(
                                selectedInvoice.balance,
                              )}`
                            : "Select an invoice to continue.",
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
                jsxs("div", {
                  className: "space-y-3",
                  children: [
                    jsxs("label", {
                      className: "block text-sm",
                      children: [
                        jsx("span", { className: "mb-1 block text-xs text-slate-400", children: "Amount (KES)" }),
                        jsx("input", {
                          type: "number",
                          min: "1",
                          max: selectedInvoice?.balance || undefined,
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
                          "Create a bank-transfer reference here, then include it in your bank narration or deposit slip. Your balance updates after reconciliation.",
                      }),
                  ],
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

export { FeesPage as default };
