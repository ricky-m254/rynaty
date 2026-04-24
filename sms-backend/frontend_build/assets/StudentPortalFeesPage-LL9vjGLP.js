import { r as React, j as jsxRuntime, b as api } from "./index-D7ltaYVC.js";
import { C as CircleAlert } from "./circle-alert-QkR7CaoT.js";
import { C as CreditCard } from "./credit-card-pJ6qZy3c.js";
import { C as Clock } from "./clock-Cjp0BcMI.js";
import { C as CircleCheckBig } from "./circle-check-big-gKc9ia_Q.js";
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
      paid: "border-emerald-200 bg-emerald-50 text-emerald-700",
      partial: "border-amber-200 bg-amber-50 text-amber-700",
      partially_paid: "border-amber-200 bg-amber-50 text-amber-700",
      pending: "border-sky-200 bg-sky-50 text-sky-700",
      overdue: "border-rose-200 bg-rose-50 text-rose-700",
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

function statusIcon(status) {
  const normalized = normalizeStatus(status);
  if (normalized === "paid") {
    return jsx(CircleCheckBig, { size: 13, className: "text-emerald-600" });
  }
  if (normalized === "partial" || normalized === "partially_paid" || normalized === "pending") {
    return jsx(Clock, { size: 13, className: "text-amber-600" });
  }
  return jsx(CircleAlert, { size: 13, className: "text-rose-600" });
}

function MetricCard({ label, value, detail, tone = "text-slate-950" }) {
  return jsxs("div", {
    className: surfaceClass,
    children: [
      jsx("p", {
        className: "text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400",
        children: label,
      }),
      jsx("p", { className: `mt-3 text-2xl font-semibold ${tone}`, children: value }),
      detail ? jsx("p", { className: "mt-2 text-sm text-slate-500", children: detail }) : null,
    ],
  });
}

function FeesPage() {
  const [profile, setProfile] = React.useState(null);
  const [invoices, setInvoices] = React.useState([]);
  const [payments, setPayments] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [flash, setFlash] = React.useState(null);
  const [tab, setTab] = React.useState("invoices");
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

  const refreshFees = React.useCallback(async () => {
    try {
      const [profileResponse, invoiceResponse, paymentResponse] = await Promise.all([
        api.get("/student-portal/profile/"),
        api.get("/student-portal/my-invoices/"),
        api.get("/student-portal/my-payments/"),
      ]);
      setProfile(profileResponse.data ?? null);
      setInvoices(Array.isArray(invoiceResponse.data) ? invoiceResponse.data : []);
      setPayments(Array.isArray(paymentResponse.data) ? paymentResponse.data : []);
      setError(null);
    } catch (loadError) {
      setError("Could not load fee information. Please contact the school office.");
    } finally {
      setLoading(false);
    }
  }, []);

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
  }, [refreshFees]);

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
  }, [refreshFees]);

  const totalBilled = invoices.reduce((sum, invoice) => sum + Number(invoice.amount ?? 0), 0);
  const totalPaid = invoices.reduce((sum, invoice) => sum + Number(invoice.amount_paid ?? 0), 0);
  const balanceDue = invoices.reduce((sum, invoice) => sum + Number(invoice.balance ?? 0), 0);
  const outstandingInvoices = invoices.filter((invoice) => Number(invoice.balance ?? 0) > 0);
  const overdueInvoices = outstandingInvoices.filter((invoice) => normalizeStatus(invoice.status) === "overdue");
  const overdueAmount = overdueInvoices.reduce((sum, invoice) => sum + Number(invoice.balance ?? 0), 0);
  const sortedOutstandingInvoices = [...outstandingInvoices].sort((left, right) => {
    const leftDate = left?.due_date ? new Date(left.due_date).getTime() : Number.POSITIVE_INFINITY;
    const rightDate = right?.due_date ? new Date(right.due_date).getTime() : Number.POSITIVE_INFINITY;
    return leftDate - rightDate;
  });
  const nextDueInvoice = sortedOutstandingInvoices.find((invoice) => !!invoice.due_date) ?? sortedOutstandingInvoices[0] ?? null;
  const latestPayment = payments[0] ?? null;

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
            className: "mx-auto h-8 w-8 animate-spin rounded-full border-t-2 border-slate-900",
          }),
          jsx("p", { className: "text-sm text-slate-500", children: "Loading fee information..." }),
        ],
      }),
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
                    children: "Student Portal",
                  }),
                  jsx("h1", {
                    className: "mt-3 text-3xl font-semibold tracking-tight text-slate-950 md:text-[2.5rem]",
                    children: "My School Fees",
                  }),
                  jsx("p", {
                    className: "mt-3 max-w-2xl text-sm leading-6 text-slate-600",
                    children:
                      "Track invoices, check what is overdue, and complete payments from one cleaner student account view.",
                  }),
                ],
              }),
              profile
                ? jsx("div", {
                    className: "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700",
                    children: `${profile.first_name || ""} ${profile.last_name || ""}`.trim()
                      ? `${`${profile.first_name || ""} ${profile.last_name || ""}`.trim()} • ${profile.admission_number || "No admission number"}`
                      : profile.admission_number || "Student account",
                  })
                : null,
            ],
          }),
          jsxs("div", {
            className: "mt-6 space-y-4",
            children: [
              flash
                ? jsx("div", {
                    className: `rounded-[22px] border px-4 py-3 text-sm ${flashClass(flash.tone)}`,
                    children: flash.message,
                  })
                : null,
              error
                ? jsx("div", {
                    className: `rounded-[22px] border px-4 py-3 text-sm ${flashClass("error")}`,
                    children: error,
                  })
                : null,
              overdueInvoices.length > 0
                ? jsx("div", {
                    className: `rounded-[22px] border px-4 py-3 text-sm ${flashClass("warning")}`,
                    children:
                      "One or more invoices are overdue. You can still settle them here via M-Pesa, bank transfer, or Stripe Checkout.",
                  })
                : null,
            ],
          }),
          jsx("div", {
            className: "mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4",
            children: [
              {
                label: "Total balance",
                value: formatCurrency(balanceDue),
                detail: "Outstanding across all open invoices.",
                tone: balanceDue > 0 ? "text-amber-700" : "text-emerald-700",
              },
              {
                label: "Amount paid",
                value: formatCurrency(totalPaid),
                detail: latestPayment ? `Latest payment on ${formatDate(latestPayment.payment_date)}.` : "No recent payment yet.",
                tone: "text-emerald-700",
              },
              {
                label: "Overdue amount",
                value: formatCurrency(overdueAmount),
                detail: overdueInvoices.length > 0 ? `${overdueInvoices.length} overdue invoice(s).` : "Nothing overdue right now.",
                tone: overdueAmount > 0 ? "text-rose-700" : "text-slate-950",
              },
              {
                label: "Next due date",
                value: nextDueInvoice?.due_date ? formatDate(nextDueInvoice.due_date) : "--",
                detail: nextDueInvoice ? `${nextDueInvoice.invoice_number || `Invoice #${nextDueInvoice.id}`}` : "No next due invoice.",
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
                    children: profile
                      ? `${`${profile.first_name || ""} ${profile.last_name || ""}`.trim() || "Student account"}`
                      : "Student account",
                  }),
                  jsx("div", {
                    className: "mt-4 grid gap-3 sm:grid-cols-2",
                    children: [
                      { label: "Admission No.", value: profile?.admission_number || "--" },
                      { label: "Class", value: profile?.class_section || "--" },
                      { label: "Outstanding invoices", value: String(outstandingInvoices.length) },
                      { label: "Guardians on file", value: String(profile?.guardians?.length ?? 0) },
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
                    children: "Quick Pay",
                  }),
                  jsx("h2", {
                    className: "mt-2 text-xl font-semibold text-slate-950",
                    children: "Pay the next invoice fast",
                  }),
                  jsx("p", {
                    className: "mt-2 text-sm text-slate-500",
                    children: nextDueInvoice
                      ? `${nextDueInvoice.invoice_number || `Invoice #${nextDueInvoice.id}`} is the next recommended item to settle.`
                      : "There is no outstanding invoice requiring action right now.",
                  }),
                  jsx("div", {
                    className: "mt-4 space-y-3",
                    children: [
                      {
                        label: "Pay by M-Pesa",
                        note: "Send a prompt to your phone and keep this page open while we confirm it.",
                        action: () => openPaymentModal(nextDueInvoice, "mpesa"),
                        disabled: !nextDueInvoice,
                      },
                      {
                        label: "Use Stripe",
                        note: "Continue to secure hosted card checkout and return here after confirmation.",
                        action: () => openPaymentModal(nextDueInvoice, "stripe"),
                        disabled: !nextDueInvoice,
                      },
                      {
                        label: "Create bank reference",
                        note: "Use the generated reference in your transfer narration while finance reconciles it.",
                        action: () => openPaymentModal(nextDueInvoice, "bank"),
                        disabled: !nextDueInvoice,
                      },
                    ].map((item) =>
                      jsxs(
                        "button",
                        {
                          type: "button",
                          onClick: item.action,
                          disabled: item.disabled,
                          className:
                            "w-full rounded-[24px] border border-slate-200 bg-white p-4 text-left transition hover:-translate-y-[1px] hover:border-slate-300 hover:shadow-[0_18px_40px_rgba(15,23,42,0.08)] disabled:cursor-not-allowed disabled:opacity-50",
                          children: [
                            jsx("p", { className: "text-sm font-semibold text-slate-950", children: item.label }),
                            jsx("p", { className: "mt-2 text-sm leading-6 text-slate-500", children: item.note }),
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
          jsx("div", {
            className: "mt-6 inline-flex flex-wrap gap-1 rounded-full border border-slate-200 bg-[#e8ebf3] p-1",
            children: [
              { id: "invoices", label: `Invoices (${invoices.length})` },
              { id: "payments", label: `Payment History (${payments.length})` },
            ].map((item) =>
              jsx(
                "button",
                {
                  type: "button",
                  onClick: () => setTab(item.id),
                  className: `rounded-full px-4 py-2 text-sm font-semibold transition ${
                    tab === item.id
                      ? "bg-white text-slate-950 shadow-sm"
                      : "text-slate-700 hover:text-slate-950"
                  }`,
                  children: item.label,
                },
                item.id,
              ),
            ),
          }),
          tab === "invoices"
            ? invoices.length === 0
              ? jsxs("div", {
                  className: `${surfaceClass} mt-6 text-center`,
                  children: [
                    jsx(CreditCard, { className: "mx-auto mb-3 text-slate-300", size: 32 }),
                    jsx("p", { className: "text-sm text-slate-500", children: "No fee invoices found for your account." }),
                  ],
                })
              : jsx("div", {
                  className: "mt-6 space-y-4",
                  children: invoices.map((invoice) => {
                    const invoiceBalance = Number(invoice.balance ?? 0);
                    const invoiceStatus = normalizeStatus(invoice.status);
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
                                    jsx("p", {
                                      className: "text-lg font-semibold text-slate-950",
                                      children: invoice.description || invoice.invoice_number || `Invoice #${invoice.id}`,
                                    }),
                                    jsxs("span", {
                                      className: `inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-semibold ${invoiceBadgeClass(
                                        invoiceStatus,
                                      )}`,
                                      children: [statusIcon(invoiceStatus), String(invoice.status || "Pending").replace("_", " ")],
                                    }),
                                  ],
                                }),
                                jsxs("div", {
                                  className: "mt-2 flex flex-wrap gap-4 text-sm text-slate-500",
                                  children: [
                                    jsx("span", { children: invoice.invoice_number || `Invoice #${invoice.id}` }),
                                    invoice.term ? jsxs("span", { children: ["Term: ", invoice.term] }) : null,
                                    invoice.academic_year ? jsxs("span", { children: ["Year: ", invoice.academic_year] }) : null,
                                    invoice.due_date
                                      ? jsxs("span", {
                                          className: "inline-flex items-center gap-1",
                                          children: [jsx(Clock, { size: 12 }), "Due: ", formatDate(invoice.due_date)],
                                        })
                                      : null,
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
                                    jsx("p", { className: "text-lg font-semibold text-slate-950", children: formatCurrency(invoice.amount) }),
                                    jsx("p", {
                                      className: "mt-1 text-sm text-emerald-600",
                                      children: `Paid: ${formatCurrency(invoice.amount_paid)}`,
                                    }),
                                    invoiceBalance > 0
                                      ? jsx("p", {
                                          className: "mt-1 text-sm text-amber-600",
                                          children: `Due: ${formatCurrency(invoiceBalance)}`,
                                        })
                                      : null,
                                  ],
                                }),
                                invoiceBalance > 0
                                  ? jsx("button", {
                                      type: "button",
                                      onClick: () => openPaymentModal(invoice, "mpesa"),
                                      className:
                                        "rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800",
                                      children: "Pay now",
                                    })
                                  : null,
                              ],
                            }),
                          ],
                        }),
                      },
                      invoice.id,
                    );
                  }),
                })
            : payments.length > 0
              ? jsx("div", {
                  className: "mt-6 space-y-4",
                  children: payments.map((payment) =>
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
                                  children: payment.transaction_reference || "Payment reference pending",
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
                                  className: "text-lg font-semibold text-emerald-700",
                                  children: formatCurrency(payment.amount_paid),
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
                  className: `${surfaceClass} mt-6 text-center text-sm text-slate-500`,
                  children: "No payments recorded yet.",
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
                            children: "Pay Invoice",
                          }),
                          jsx("h2", {
                            className: "mt-2 text-xl font-semibold text-slate-950",
                            children: "Pay invoice",
                          }),
                          jsx("p", {
                            className: "mt-1 text-sm text-slate-500",
                            children: selectedInvoice
                              ? `${selectedInvoice.invoice_number || `Invoice #${selectedInvoice.id}`} • Outstanding ${formatCurrency(selectedInvoice.balance)}`
                              : "Select an invoice to continue.",
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
                        ? "Enter the Safaricom number that should receive the prompt. We keep checking the status until the transaction settles or times out."
                        : paymentMethod === "stripe"
                          ? "Stripe redirects you to a secure hosted checkout. After card payment succeeds, you return here and the balance refreshes."
                          : "Bank transfer gives you a unique reference to include in your narration or deposit slip. The invoice clears after reconciliation, not instantly.",
                  }),
                  jsxs("label", {
                    className: "block text-sm text-slate-700",
                    children: [
                      jsx("span", { className: "font-medium", children: "Amount (KES)" }),
                      jsx("input", {
                        type: "number",
                        min: "1",
                        max: selectedInvoice?.balance || undefined,
                        value: paymentAmount,
                        onChange: (event) => {
                          setPaymentAmount(event.target.value);
                          setPaymentError(null);
                        },
                        className: `mt-2 ${inputClass}`,
                      }),
                    ],
                  }),
                  selectedInvoice?.balance
                    ? jsx("div", {
                        className: "flex flex-wrap gap-2",
                        children: [
                          {
                            label: "Full Balance",
                            value: toAmountInput(selectedInvoice.balance),
                          },
                          {
                            label: "Half Payment",
                            value: toAmountInput(Number(selectedInvoice.balance) / 2),
                          },
                        ].map((item) =>
                          jsx(
                            "button",
                            {
                              type: "button",
                              onClick: () => {
                                setPaymentAmount(item.value);
                                setPaymentError(null);
                              },
                              className:
                                "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                              children: item.label,
                            },
                            item.label,
                          ),
                        ),
                      })
                    : null,
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
                          "Create a bank-transfer reference here, then include it in your bank narration or deposit slip. Your balance updates after reconciliation.",
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
                  paymentResult === "success" && paymentMethod !== "bank" && payments[0]
                    ? jsxs("div", {
                        className: "space-y-4 rounded-[24px] border border-emerald-200 bg-[linear-gradient(135deg,#ecfdf5,white)] p-5",
                        children: [
                          jsxs("div", {
                            className: "text-center",
                            children: [
                              jsx("div", {
                                className: "mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-xl text-emerald-600",
                                children: "✓",
                              }),
                              jsx("h3", {
                                className: "mt-3 text-xl font-semibold text-emerald-700",
                                children: "Payment Successful!",
                              }),
                              jsx("p", {
                                className: "mt-1 text-sm text-slate-500",
                                children: `${formatCurrency(Number(paymentAmount || selectedInvoice?.balance || 0))} has been paid for ${selectedInvoice?.invoice_number || `Invoice #${selectedInvoice?.id || ""}`}`,
                              }),
                            ],
                          }),
                          jsx("div", {
                            className: "rounded-[22px] border border-slate-200 bg-white/90 p-4",
                            children: [
                              {
                                label: "M-Pesa Reference",
                                value: payments[0].transaction_reference || "--",
                              },
                              {
                                label: "Method",
                                value: payments[0].payment_method || "--",
                              },
                              {
                                label: "Transaction Date",
                                value: formatDate(payments[0].payment_date),
                              },
                            ].map((item) =>
                              jsxs(
                                "div",
                                {
                                  className: "flex items-center justify-between gap-3 border-b border-slate-200 py-3 last:border-b-0",
                                  children: [
                                    jsx("span", { className: "text-sm text-slate-500", children: item.label }),
                                    jsx("span", { className: "text-sm font-semibold text-slate-900", children: item.value }),
                                  ],
                                },
                                item.label,
                              ),
                            ),
                          }),
                        ],
                      })
                    : null,
                  jsxs("div", {
                    className: "flex flex-col gap-2 sm:flex-row",
                    children: [
                      jsx("button", {
                        type: "button",
                        onClick:
                          paymentResult === "success" && paymentMethod !== "bank" && payments[0]?.receipt_url
                            ? () => {
                                if (typeof window !== "undefined") {
                                  window.open(payments[0].receipt_url, "_blank", "noopener,noreferrer");
                                }
                              }
                            : submitPayment,
                        disabled:
                          paymentResult === "success" && paymentMethod !== "bank"
                            ? !payments[0]?.receipt_url
                            : submitting || polling,
                        className:
                          "flex-1 rounded-full bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60",
                        children:
                          paymentResult === "success" && paymentMethod !== "bank"
                            ? "Download Receipt"
                            : paymentMethod === "stripe"
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
                        children: paymentResult === "success" ? "Done" : "Cancel",
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

export { FeesPage as default };
