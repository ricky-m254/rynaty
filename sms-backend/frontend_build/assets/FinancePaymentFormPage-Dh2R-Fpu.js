import { u as useNavigate, r as React, j as jsxRuntime, b as api } from "./index-D7ltaYVC.js";
import { n as normalizePaginated } from "./pagination-DjjjzeDo.js";
import { e as getErrorMessage, m as getFieldErrors } from "./forms-ZJa1TpnO.js";

const { jsx, jsxs } = jsxRuntime;

const MANUAL_METHODS = ["Cash", "Bank Transfer", "Card", "Mobile Money", "Cheque", "Other"];
const PAYMENT_METHODS = [...MANUAL_METHODS, "Stripe Checkout"];
const shellClass =
  "rounded-[32px] border border-slate-200/80 bg-[#f6f7fb] p-5 shadow-[0_30px_80px_rgba(15,23,42,0.08)] md:p-7 xl:p-8";
const surfaceClass =
  "rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-[0_22px_50px_rgba(15,23,42,0.06)]";
const insetClass = "rounded-[24px] border border-slate-200 bg-slate-50/80 p-4";
const fieldClass =
  "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5";
const invalidFieldClass =
  "mt-2 w-full rounded-2xl border border-rose-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-rose-400 focus:ring-4 focus:ring-rose-100";

const today = () => new Date().toISOString().slice(0, 10);

function formatMoney(value) {
  return Number(value ?? 0).toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function getPrimarySmsTarget(student) {
  if (!student) return "";
  const guardians = student.guardians ?? [];
  const guardian = guardians.find((item) => (item?.phone ?? "").trim());
  return (guardian?.phone ?? student.phone ?? "").trim();
}

function buildSmsCopy(payment, student) {
  if (!payment) return "";
  const studentName =
    payment.student_name ||
    [student?.first_name, student?.last_name].filter(Boolean).join(" ").trim() ||
    student?.admission_number ||
    "student";
  const admission = payment.admission_number || student?.admission_number || "";
  const receiptNo = payment.receipt_no || payment.receipt_number || payment.id || "N/A";
  const transactionCode = payment.transaction_code || payment.reference_number || receiptNo;
  const amount = formatMoney(payment.amount);
  return `Payment received for ${studentName}${admission ? ` (${admission})` : ""}. Receipt ${receiptNo}. Ref ${transactionCode}. Amount KES ${amount}.`;
}

function methodDescription(method) {
  if (method === "Stripe Checkout") {
    return "Launch a hosted card checkout and wait for webhook confirmation before the ledger settles.";
  }
  if (method === "Bank Transfer") {
    return "Capture a bank-confirmed payment that has already been received by the school.";
  }
  if (method === "Mobile Money") {
    return "Record a verified mobile money payment received outside the parent or student portal.";
  }
  if (method === "Cheque") {
    return "Use this for cheque receipts that need a physical reference captured.";
  }
  return "Record an office-collected payment and generate a receipt immediately.";
}

function Flash({ tone = "success", message }) {
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

function Field({ label, error, hint, children }) {
  return jsxs("label", {
    className: "block text-sm text-slate-700",
    children: [
      jsx("span", { className: "font-medium", children: label }),
      children,
      error ? jsx("p", { className: "mt-1.5 text-xs text-rose-600", children: error }) : null,
      hint ? jsx("p", { className: "mt-1.5 text-xs text-slate-500", children: hint }) : null,
    ],
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

function MethodOption({ method, active, onSelect }) {
  return jsx("button", {
    type: "button",
    onClick: () => onSelect(method),
    className: `rounded-[22px] border p-4 text-left transition ${
      active
        ? "border-slate-900 bg-slate-900 text-white shadow-[0_18px_40px_rgba(15,23,42,0.18)]"
        : "border-slate-200 bg-white text-slate-900 hover:-translate-y-[1px] hover:border-slate-300 hover:shadow-[0_18px_40px_rgba(15,23,42,0.08)]"
    }`,
    children: jsxs("div", {
      children: [
        jsx("p", { className: "text-sm font-semibold", children: method }),
        jsx("p", {
          className: `mt-2 text-xs leading-5 ${active ? "text-slate-200" : "text-slate-500"}`,
          children: methodDescription(method),
        }),
      ],
    }),
  });
}

function StudentContext({ student, enrollment, warning }) {
  const guardians = student?.guardians ?? [];
  const smsTarget = getPrimarySmsTarget(student);

  return jsxs("aside", {
    className: `${surfaceClass} space-y-5`,
    children: [
      jsxs("div", {
        children: [
          jsx("p", {
            className: "text-[11px] font-semibold uppercase tracking-[0.26em] text-slate-400",
            children: "Student Context",
          }),
          jsx("h3", {
            className: "mt-2 text-lg font-semibold text-slate-900",
            children: student ? `${student.first_name} ${student.last_name}` : "Choose a student to continue",
          }),
          jsx("p", {
            className: "mt-1 text-sm text-slate-500",
            children: "This card stays visible while you capture the payment so class, guardian, and SMS details are always in view.",
          }),
        ],
      }),
      jsx("div", {
        className: "grid gap-3 sm:grid-cols-2",
        children: [
          { label: "Admission No.", value: student?.admission_number ?? "--" },
          { label: "Class", value: enrollment?.class_name ?? "--" },
          { label: "Term", value: enrollment?.term_name ?? "--" },
          { label: "SMS Target", value: smsTarget || student?.phone || "--" },
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
      warning ? jsx("p", { className: "text-xs text-amber-600", children: warning }) : null,
      jsxs("div", {
        children: [
          jsx("p", {
            className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
            children: "Guardians",
          }),
          jsx("div", {
            className: "mt-3 space-y-3",
            children:
              guardians.length > 0
                ? guardians.map((guardian) =>
                    jsxs(
                      "div",
                      {
                        className: insetClass,
                        children: [
                          jsx("p", { className: "text-sm font-semibold text-slate-900", children: guardian.name }),
                          jsx("p", {
                            className: "mt-1 text-xs uppercase tracking-[0.18em] text-slate-400",
                            children: guardian.relationship ?? "Guardian",
                          }),
                          jsx("p", {
                            className: "mt-2 text-sm text-slate-600",
                            children: guardian.phone || guardian.email ? `${guardian.phone ?? "--"} ${guardian.email ? `• ${guardian.email}` : ""}` : "No contact details on file",
                          }),
                        ],
                      },
                      guardian.id,
                    ),
                  )
                : jsx("div", {
                    className: insetClass,
                    children: jsx("p", {
                      className: "text-sm text-slate-500",
                      children: "No guardian records are attached to this student yet.",
                    }),
                  }),
          }),
        ],
      }),
    ],
  });
}

function StripeSummary({ session, onOpen, onReset }) {
  if (!session) return null;
  return jsxs("div", {
    className:
      "rounded-[24px] border border-sky-200 bg-[linear-gradient(135deg,#eff6ff,white)] p-5 text-slate-900 shadow-[0_18px_40px_rgba(59,130,246,0.12)]",
    children: [
      jsx("p", {
        className: "text-[11px] font-semibold uppercase tracking-[0.26em] text-sky-500",
        children: "Hosted Checkout Ready",
      }),
      jsx("h3", {
        className: "mt-2 text-lg font-semibold",
        children: "Stripe link created successfully.",
      }),
      jsx("p", {
        className: "mt-1 text-sm text-slate-600",
        children: "Open the hosted page to complete payment, then come back here for any follow-up or another link.",
      }),
      jsx("div", {
        className: "mt-4 grid gap-3 sm:grid-cols-2",
        children: [
          { label: "Reference", value: session.reference || "--" },
          { label: "Checkout Session", value: session.checkout_session_id || "--" },
        ].map((item) =>
          jsxs(
            "div",
            {
              className: "rounded-2xl border border-sky-100 bg-white/80 p-4",
              children: [
                jsx("p", { className: "text-[11px] uppercase tracking-[0.2em] text-slate-400", children: item.label }),
                jsx("p", { className: "mt-2 break-all text-sm font-semibold text-slate-900", children: item.value }),
              ],
            },
            item.label,
          ),
        ),
      }),
      jsxs("div", {
        className: "mt-4 flex flex-wrap gap-2",
        children: [
          jsx("button", {
            type: "button",
            className:
              "rounded-full bg-sky-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-600",
            onClick: onOpen,
            children: "Open checkout",
          }),
          jsx("button", {
            type: "button",
            className:
              "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
            onClick: onReset,
            children: "Create another link",
          }),
        ],
      }),
    ],
  });
}

function PaymentReceiptPanel({
  payment,
  student,
  smsCopyText,
  onOpenReceipt,
  onOpenReceiptJson,
  onCopySms,
  onReset,
}) {
  if (!payment) return null;
  const smsTarget = getPrimarySmsTarget(student);

  return jsxs("div", {
    className:
      "rounded-[28px] border border-emerald-200 bg-[linear-gradient(135deg,#ecfdf5,white)] p-5 shadow-[0_18px_45px_rgba(16,185,129,0.12)]",
    children: [
      jsx("p", {
        className: "text-[11px] font-semibold uppercase tracking-[0.28em] text-emerald-500",
        children: "Receipt Ready",
      }),
      jsx("h3", {
        className: "mt-2 text-xl font-semibold text-slate-900",
        children: payment.receipt_no ? `Receipt ${payment.receipt_no}` : "Payment recorded successfully",
      }),
      jsx("div", {
        className: "mt-4 grid gap-3 md:grid-cols-2",
        children: [
          { label: "Transaction", value: payment.transaction_code || payment.reference_number || "--" },
          { label: "Status", value: payment.status || "Saved" },
          { label: "Amount", value: `KES ${formatMoney(payment.amount)}` },
          { label: "SMS Target", value: smsTarget || "No guardian phone captured" },
        ].map((item) =>
          jsxs(
            "div",
            {
              className: "rounded-2xl border border-emerald-100 bg-white/80 p-4",
              children: [
                jsx("p", { className: "text-[11px] uppercase tracking-[0.2em] text-slate-400", children: item.label }),
                jsx("p", { className: "mt-2 text-sm font-semibold text-slate-900", children: item.value }),
              ],
            },
            item.label,
          ),
        ),
      }),
      jsxs("div", {
        className: "mt-4 rounded-[24px] border border-slate-200 bg-white p-4",
        children: [
          jsx("p", {
            className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
            children: "SMS Confirmation Copy",
          }),
          jsx("textarea", {
            className:
              "mt-3 h-28 w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 outline-none",
            readOnly: true,
            value: smsCopyText,
          }),
        ],
      }),
      jsxs("div", {
        className: "mt-4 flex flex-wrap gap-2",
        children: [
          jsx("button", {
            type: "button",
            className:
              "rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-600",
            onClick: onOpenReceipt,
            children: "Open receipt PDF",
          }),
          jsx("button", {
            type: "button",
            className:
              "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
            onClick: onOpenReceiptJson,
            children: "View receipt JSON",
          }),
          jsx("button", {
            type: "button",
            className:
              "rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 transition hover:border-amber-300 hover:bg-amber-100",
            onClick: onCopySms,
            children: "Copy SMS",
          }),
          jsx("button", {
            type: "button",
            className:
              "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
            onClick: onReset,
            children: "Record another",
          }),
        ],
      }),
    ],
  });
}

function FinancePaymentFormPage() {
  const navigate = useNavigate();
  const [students, setStudents] = React.useState([]);
  const [loadingStudents, setLoadingStudents] = React.useState(true);
  const [formError, setFormError] = React.useState(null);
  const [fieldErrors, setFieldErrors] = React.useState({});
  const [submitting, setSubmitting] = React.useState(false);
  const [student, setStudent] = React.useState(null);
  const [enrollment, setEnrollment] = React.useState(null);
  const [studentWarning, setStudentWarning] = React.useState(null);
  const [flash, setFlash] = React.useState(null);
  const [stripeSession, setStripeSession] = React.useState(null);
  const [admissionLookup, setAdmissionLookup] = React.useState("");
  const [admissionOpen, setAdmissionOpen] = React.useState(false);
  const [lastPayment, setLastPayment] = React.useState(null);
  const [form, setForm] = React.useState({
    student: "",
    amount: "",
    payment_date: today(),
    payment_method: "",
    reference_number: "",
    notes: "",
  });

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const response = await api.get("/finance/ref/students/");
        if (active) {
          setStudents(normalizePaginated(response.data).items);
        }
      } catch (error) {
        if (active) setFormError(getErrorMessage(error, "Unable to load student references."));
      } finally {
        if (active) setLoadingStudents(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  React.useEffect(() => {
    if (!form.student) {
      setStudent(null);
      setEnrollment(null);
      setStudentWarning(null);
      return;
    }

    let active = true;
    (async () => {
      try {
        const [studentResponse, enrollmentResponse] = await Promise.all([
          api.get(`/students/${form.student}/`),
          api.get("/finance/ref/enrollments/", { params: { student_id: form.student, active: true } }),
        ]);
        if (!active) return;
        setStudent(studentResponse.data);
        const enrollments = Array.isArray(enrollmentResponse.data)
          ? enrollmentResponse.data
          : enrollmentResponse.data.results ?? [];
        setEnrollment(enrollments[0] ?? null);
        setStudentWarning(null);
      } catch {
        if (!active) return;
        setStudent(null);
        setEnrollment(null);
        setStudentWarning("Student contact or class info is not available.");
      }
    })();

    return () => {
      active = false;
    };
  }, [form.student]);

  React.useEffect(() => {
    if (student) {
      setAdmissionLookup(`${student.admission_number} - ${student.first_name} ${student.last_name}`.trim());
      return;
    }
    if (!form.student) {
      setAdmissionLookup("");
    }
  }, [student, form.student]);

  const isStripeFlow = form.payment_method === "Stripe Checkout";
  const selectedStudentLabel = student
    ? `${student.first_name} ${student.last_name}`.trim() || student.admission_number
    : "";
  const admissionMatches = React.useMemo(() => {
    const query = admissionLookup.trim().toLowerCase();
    if (!query) return [];
    return students
      .filter((item) => {
        const haystack = [
          item.admission_number,
          item.first_name,
          item.last_name,
          `${item.first_name} ${item.last_name}`,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(query);
      })
      .slice(0, 6);
  }, [admissionLookup, students]);
  const smsCopyText = React.useMemo(() => buildSmsCopy(lastPayment, student), [lastPayment, student]);

  const updateForm = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => ({ ...current, [key]: "" }));
  };

  const selectStudent = (item) => {
    updateForm("student", String(item.id));
    setAdmissionLookup(`${item.admission_number} - ${item.first_name} ${item.last_name}`.trim());
    setAdmissionOpen(false);
    setLastPayment(null);
  };

  const validate = () => {
    const nextErrors = {};
    if (!form.student) nextErrors.student = "Select a student.";

    const amount = Number(form.amount);
    if (!form.amount || Number.isNaN(amount) || amount <= 0) {
      nextErrors.amount = "Enter a valid amount.";
    }

    if (!isStripeFlow) {
      if (!form.payment_date) nextErrors.payment_date = "Select a payment date.";
      if (form.payment_date > today()) nextErrors.payment_date = "Payment date cannot be in the future.";
    }

    if (!form.payment_method.trim()) {
      nextErrors.payment_method = "Select a payment method.";
    } else if (!PAYMENT_METHODS.includes(form.payment_method)) {
      nextErrors.payment_method = "Select a valid payment method.";
    }

    if (!isStripeFlow && !form.reference_number.trim()) {
      nextErrors.reference_number = "Enter a reference number.";
    }

    return nextErrors;
  };

  const handleManualPayment = async () => {
    const response = await api.post("/finance/payments/", {
      student: Number(form.student),
      amount: Number(form.amount),
      payment_date: form.payment_date,
      payment_method: form.payment_method,
      reference_number: form.reference_number,
      notes: form.notes,
    });
    setLastPayment(response.data);
    setStripeSession(null);
    setFlash({
      tone: "success",
      message: `Payment recorded. Receipt ${response.data.receipt_no || response.data.receipt_number || response.data.id} is ready.`,
    });
    setForm((current) => ({
      ...current,
      amount: "",
      payment_date: today(),
      reference_number: "",
      notes: "",
    }));
  };

  const handleStripeCheckout = async () => {
    const response = await api.post("/finance/stripe/checkout-session/", {
      student_id: Number(form.student),
      amount: Number(form.amount),
      notes: form.notes,
      reference: form.reference_number || undefined,
    });
    const session = response.data;
    setStripeSession(session);
    setFlash({ tone: "success", message: "Stripe checkout link created. Open it to complete payment." });
    if (session.checkout_url && typeof window !== "undefined") {
      window.open(session.checkout_url, "_blank", "noopener,noreferrer");
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError(null);
    setFlash(null);
    setLastPayment(null);
    const nextErrors = validate();
    if (Object.keys(nextErrors).length > 0) {
      setFieldErrors(nextErrors);
      setFormError("Please correct the highlighted fields.");
      return;
    }

    setSubmitting(true);
    try {
      if (isStripeFlow) {
        await handleStripeCheckout();
      } else {
        await handleManualPayment();
      }
    } catch (error) {
      const mappedErrors = getFieldErrors(error, [
        "student",
        "amount",
        "payment_date",
        "payment_method",
        "reference_number",
      ]);
      if (Object.keys(mappedErrors).length > 0) {
        setFieldErrors(mappedErrors);
      }
      setFormError(
        getErrorMessage(error, isStripeFlow ? "Unable to create Stripe checkout." : "Unable to record payment."),
      );
    } finally {
      setSubmitting(false);
    }
  };

  const openStripeCheckout = () => {
    if (stripeSession?.checkout_url && typeof window !== "undefined") {
      window.open(stripeSession.checkout_url, "_blank", "noopener,noreferrer");
    }
  };

  const resetStripeSession = () => {
    setStripeSession(null);
    setFlash(null);
  };

  const openReceipt = (kind) => {
    if (!lastPayment || typeof window === "undefined") return;
    const url = kind === "json" ? lastPayment.receipt_json_url : lastPayment.receipt_pdf_url;
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  };

  const copySmsMessage = async () => {
    if (!smsCopyText) return;
    if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
      setFlash({ tone: "error", message: "Clipboard access is not available in this browser." });
      return;
    }
    try {
      await navigator.clipboard.writeText(smsCopyText);
      setFlash({ tone: "success", message: "SMS message copied to clipboard." });
    } catch {
      setFlash({ tone: "error", message: "Unable to copy the SMS message." });
    }
  };

  const resetPaymentForm = () => {
    setLastPayment(null);
    setFlash(null);
    setFieldErrors({});
    setForm((current) => ({
      ...current,
      amount: "",
      payment_date: today(),
      reference_number: "",
      notes: "",
    }));
  };

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
                    children: "Record school payments with a cleaner bursar workspace",
                  }),
                  jsx("p", {
                    className: "mt-3 max-w-2xl text-sm leading-6 text-slate-600",
                    children:
                      "Capture manual receipts, launch Stripe for assisted card payments, and keep student context visible while you work.",
                  }),
                ],
              }),
              jsxs("div", {
                className: "flex flex-wrap gap-2",
                children: [
                  jsx(ActionChip, {
                    active: false,
                    onClick: () => navigate("/modules/finance/payments"),
                    children: "Payments",
                  }),
                  jsx(ActionChip, { active: true, onClick: () => {}, children: "Record Payment" }),
                  jsx(ActionChip, {
                    active: false,
                    onClick: () => navigate("/modules/finance/reconciliation"),
                    children: "Reconciliation",
                  }),
                ],
              }),
            ],
          }),
          jsxs("div", {
            className: "mt-6 space-y-4",
            children: [
              loadingStudents
                ? jsx("div", {
                    className: `${surfaceClass} text-sm text-slate-600`,
                    children: "Loading student references...",
                  })
                : null,
              jsx(Flash, { tone: flash?.tone, message: flash?.message }),
              jsx(Flash, { tone: "error", message: formError }),
            ],
          }),
          jsxs("div", {
            className: "mt-6 grid gap-6 xl:grid-cols-[1.18fr,0.82fr]",
            children: [
              jsxs("section", {
                className: `${surfaceClass} space-y-5`,
                children: [
                  jsxs("div", {
                    children: [
                      jsx("p", {
                        className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                        children: "Capture Mode",
                      }),
                      jsx("h2", {
                        className: "mt-2 text-xl font-semibold text-slate-950",
                        children: isStripeFlow ? "Launch hosted checkout" : "Save a manual receipt",
                      }),
                      jsx("p", {
                        className: "mt-1 text-sm text-slate-600",
                        children: isStripeFlow
                          ? "Use this when the payer should complete card payment on Stripe’s hosted page."
                          : "This path saves the payment immediately and makes the receipt available right away.",
                      }),
                    ],
                  }),
                  jsxs("form", {
                    className: "space-y-5",
                    onSubmit: handleSubmit,
                    children: [
                      jsx(Field, {
                        label: "Admission search",
                        error: fieldErrors.student,
                        hint: "Start with admission number or student name, then select the matching learner.",
                        children: jsxs("div", {
                          className: "relative",
                          children: [
                            jsx("input", {
                              className: fieldErrors.student ? invalidFieldClass : fieldClass,
                              value: admissionLookup,
                              "aria-invalid": !!fieldErrors.student,
                              autoComplete: "off",
                              placeholder: "Type admission number or student name...",
                              onFocus: () => setAdmissionOpen(true),
                              onBlur: () => setTimeout(() => setAdmissionOpen(false), 150),
                              onChange: (event) => {
                                setAdmissionLookup(event.target.value);
                                setAdmissionOpen(true);
                              },
                            }),
                            admissionOpen && admissionMatches.length > 0
                              ? jsx("ul", {
                                  className:
                                    "absolute z-30 mt-2 w-full overflow-hidden rounded-[22px] border border-slate-200 bg-white shadow-[0_24px_50px_rgba(15,23,42,0.12)]",
                                  children: admissionMatches.map((item) =>
                                    jsx(
                                      "li",
                                      {
                                        children: jsxs("button", {
                                          type: "button",
                                          className:
                                            "flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm transition hover:bg-slate-50",
                                          onMouseDown: () => selectStudent(item),
                                          children: [
                                            jsxs("span", {
                                              className: "font-medium text-slate-900",
                                              children: [item.first_name, " ", item.last_name],
                                            }),
                                            jsx("span", {
                                              className:
                                                "rounded-full bg-slate-100 px-2.5 py-1 font-mono text-[11px] text-slate-500",
                                              children: item.admission_number,
                                            }),
                                          ],
                                        }),
                                      },
                                      item.id,
                                    ),
                                  ),
                                })
                              : null,
                            admissionOpen && admissionLookup.trim().length > 1 && admissionMatches.length === 0
                              ? jsx("div", {
                                  className:
                                    "absolute z-30 mt-2 w-full rounded-[22px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-[0_24px_50px_rgba(15,23,42,0.12)]",
                                  children: `No students match "${admissionLookup}"`,
                                })
                              : null,
                          ],
                        }),
                      }),
                      selectedStudentLabel
                        ? jsxs("div", {
                            className:
                              "inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700",
                            children: ["Selected: ", selectedStudentLabel, " • ", student?.admission_number ?? "--"],
                          })
                        : null,
                      jsx(Field, {
                        label: "Student list fallback",
                        error: fieldErrors.student,
                        hint: "If search is slow or ambiguous, choose from the full student list here.",
                        children: jsxs("select", {
                          className: fieldErrors.student ? invalidFieldClass : fieldClass,
                          value: form.student,
                          "aria-invalid": !!fieldErrors.student,
                          onChange: (event) => {
                            const nextStudent = students.find((item) => String(item.id) === event.target.value);
                            updateForm("student", event.target.value);
                            setAdmissionLookup(
                              nextStudent
                                ? `${nextStudent.admission_number} - ${nextStudent.first_name} ${nextStudent.last_name}`
                                : "",
                            );
                            setAdmissionOpen(false);
                            setLastPayment(null);
                          },
                          children: [
                            jsx("option", { value: "", children: "Select student" }),
                            students.map((item) =>
                              jsxs(
                                "option",
                                {
                                  value: item.id,
                                  children: [item.admission_number, " - ", item.first_name, " ", item.last_name],
                                },
                                item.id,
                              ),
                            ),
                          ],
                        }),
                      }),
                      jsx("div", {
                        className: "grid gap-5 lg:grid-cols-[0.9fr,1.1fr]",
                        children: [
                          jsx(Field, {
                            label: "Amount (KES)",
                            error: fieldErrors.amount,
                            children: jsx("input", {
                              type: "number",
                              min: "0.01",
                              step: "0.01",
                              className: fieldErrors.amount ? invalidFieldClass : fieldClass,
                              value: form.amount,
                              "aria-invalid": !!fieldErrors.amount,
                              onChange: (event) => updateForm("amount", event.target.value),
                              placeholder: "500.00",
                            }),
                          }),
                          !isStripeFlow
                            ? jsx(Field, {
                                label: "Payment date",
                                error: fieldErrors.payment_date,
                                children: jsx("input", {
                                  type: "date",
                                  className: fieldErrors.payment_date ? invalidFieldClass : fieldClass,
                                  value: form.payment_date,
                                  "aria-invalid": !!fieldErrors.payment_date,
                                  onChange: (event) => updateForm("payment_date", event.target.value),
                                }),
                              })
                            : jsx("div", {
                                className: `${insetClass} flex items-center`,
                                children: jsxs("div", {
                                  children: [
                                    jsx("p", {
                                      className: "text-[11px] uppercase tracking-[0.22em] text-slate-400",
                                      children: "Settlement Rule",
                                    }),
                                    jsx("p", {
                                      className: "mt-2 text-sm font-semibold text-slate-900",
                                      children: "Ledger updates after Stripe confirms payment.",
                                    }),
                                    jsx("p", {
                                      className: "mt-1 text-xs text-slate-500",
                                      children: "This mode does not save a manual receipt immediately.",
                                    }),
                                  ],
                                }),
                              }),
                        ],
                      }),
                      jsxs("div", {
                        children: [
                          jsx("p", {
                            className: "text-sm font-medium text-slate-700",
                            children: "Payment method",
                          }),
                          jsx("div", {
                            className: "mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3",
                            children: PAYMENT_METHODS.map((method) =>
                              jsx(MethodOption, {
                                method,
                                active: form.payment_method === method,
                                onSelect: (nextMethod) => {
                                  updateForm("payment_method", nextMethod);
                                  setLastPayment(null);
                                  if (nextMethod !== "Stripe Checkout") {
                                    setStripeSession(null);
                                  }
                                },
                              }, method),
                            ),
                          }),
                          fieldErrors.payment_method
                            ? jsx("p", { className: "mt-2 text-xs text-rose-600", children: fieldErrors.payment_method })
                            : null,
                        ],
                      }),
                      jsx(Field, {
                        label: isStripeFlow ? "Internal reference (optional)" : "Reference number",
                        error: fieldErrors.reference_number,
                        hint: isStripeFlow
                          ? "Leave blank to let the platform generate a clean Stripe launch reference."
                          : "Use teller, bank, cheque, or office receipt reference exactly as it appears in your source record.",
                        children: jsx("input", {
                          className: fieldErrors.reference_number ? invalidFieldClass : fieldClass,
                          value: form.reference_number,
                          "aria-invalid": !!fieldErrors.reference_number,
                          onChange: (event) => updateForm("reference_number", event.target.value),
                          placeholder: isStripeFlow ? "STR-FASTTRACK-001" : "RCT-1001",
                        }),
                      }),
                      jsx(Field, {
                        label: "Notes",
                        hint: "Optional internal detail for finance staff, reconciliation, or support follow-up.",
                        children: jsx("textarea", {
                          className: fieldClass,
                          value: form.notes,
                          onChange: (event) => updateForm("notes", event.target.value),
                          rows: 4,
                          placeholder: "Example: paid at bursar desk, verified against bank slip, parent requested emailed receipt.",
                        }),
                      }),
                      isStripeFlow
                        ? jsx(StripeSummary, {
                            session: stripeSession,
                            onOpen: openStripeCheckout,
                            onReset: resetStripeSession,
                          })
                        : null,
                      jsxs("div", {
                        className: "flex flex-wrap gap-3",
                        children: [
                          jsx("button", {
                            className:
                              "rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60",
                            type: "submit",
                            disabled: submitting,
                            children: submitting
                              ? isStripeFlow
                                ? "Creating checkout..."
                                : "Saving payment..."
                              : isStripeFlow
                                ? "Create Stripe checkout"
                                : "Record payment",
                          }),
                          jsx("button", {
                            className:
                              "rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                            type: "button",
                            onClick: () => navigate("/modules/finance/payments"),
                            children: "Back to payments",
                          }),
                        ],
                      }),
                    ],
                  }),
                  lastPayment
                    ? jsx(PaymentReceiptPanel, {
                        payment: lastPayment,
                        student,
                        smsCopyText,
                        onOpenReceipt: () => openReceipt("pdf"),
                        onOpenReceiptJson: () => openReceipt("json"),
                        onCopySms: copySmsMessage,
                        onReset: resetPaymentForm,
                      })
                    : null,
                ],
              }),
              jsxs("div", {
                className: "space-y-6",
                children: [
                  jsx(StudentContext, {
                    student,
                    enrollment,
                    warning: studentWarning,
                  }),
                  jsxs("section", {
                    className: surfaceClass,
                    children: [
                      jsx("p", {
                        className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                        children: "Operator Notes",
                      }),
                      jsx("h3", {
                        className: "mt-2 text-lg font-semibold text-slate-900",
                        children: "Use the right path for the right payment",
                      }),
                      jsx("div", {
                        className: "mt-4 space-y-3",
                        children: [
                          {
                            title: "Manual receipt",
                            body: "Use for cash, card, cheque, mobile money, or already-confirmed bank transfers received by the school office.",
                          },
                          {
                            title: "Stripe checkout",
                            body: "Use when the payer is still going to complete payment. The receipt appears after Stripe confirms the session.",
                          },
                          {
                            title: "Receipt and SMS",
                            body: "After a manual save, the receipt links and SMS copy stay aligned so the office can share the correct confirmation text.",
                          },
                        ].map((item) =>
                          jsxs(
                            "div",
                            {
                              className: insetClass,
                              children: [
                                jsx("p", { className: "text-sm font-semibold text-slate-900", children: item.title }),
                                jsx("p", { className: "mt-2 text-sm leading-6 text-slate-600", children: item.body }),
                              ],
                            },
                            item.title,
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
      }),
    ],
  });
}

export { FinancePaymentFormPage as default };
