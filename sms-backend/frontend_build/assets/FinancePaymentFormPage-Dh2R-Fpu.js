import { u as useNavigate, r as React, j as jsxRuntime, b as api } from "./index-D7ltaYVC.js";
import { n as normalizePaginated } from "./pagination-DjjjzeDo.js";
import { e as getErrorMessage, m as getFieldErrors } from "./forms-ZJa1TpnO.js";
import { B as BackButton } from "./BackButton-CZKTKPYV.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";

const MANUAL_METHODS = ["Cash", "Bank Transfer", "Card", "Mobile Money", "Cheque", "Other"];
const PAYMENT_METHODS = [...MANUAL_METHODS, "Stripe Checkout"];
const today = () => new Date().toISOString().slice(0, 10);
const panelClass = "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.45)]";
const fieldClass = "mt-2 w-full rounded-xl border border-white/[0.07] bg-slate-950 px-4 py-2 text-sm text-white outline-none focus:border-emerald-400";
const invalidFieldClass = "mt-2 w-full rounded-xl border border-rose-500/70 bg-slate-950 px-4 py-2 text-sm text-white outline-none focus:border-rose-400";
const formatMoney = (value) =>
  Number(value ?? 0).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const getPrimarySmsTarget = (student) => {
  if (!student) return "";
  const guardians = student.guardians ?? [];
  const guardian = guardians.find((item) => (item?.phone ?? "").trim());
  return (guardian?.phone ?? student.phone ?? "").trim();
};

const buildSmsCopy = (payment, student) => {
  if (!payment) return "";
  const studentName = payment.student_name || [student?.first_name, student?.last_name].filter(Boolean).join(" ").trim() || student?.admission_number || "student";
  const admission = payment.admission_number || student?.admission_number || "";
  const receiptNo = payment.receipt_no || payment.receipt_number || payment.id || "N/A";
  const transactionCode = payment.transaction_code || payment.reference_number || receiptNo;
  const amount = formatMoney(payment.amount);
  return `Payment received for ${studentName}${admission ? ` (${admission})` : ""}. Receipt ${receiptNo}. Ref ${transactionCode}. Amount KES ${amount}.`;
};

function Field({ label, error, children, hint }) {
  return jsxRuntime.jsxs("label", {
    className: "block text-sm",
    children: [
      label,
      children,
      error ? jsxRuntime.jsx("p", { className: "mt-1 text-xs text-rose-300", children: error }) : null,
      hint ? jsxRuntime.jsx("p", { className: "mt-1 text-[11px] text-slate-500", children: hint }) : null,
    ],
  });
}

function Flash({ tone = "success", message }) {
  if (!message) return null;
  const classes =
    tone === "error"
      ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
      : "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
  return jsxRuntime.jsx("div", {
    className: `col-span-12 rounded-2xl border p-4 text-sm ${classes}`,
    children: message,
  });
}

function StudentContext({ student, enrollment, warning }) {
  const guardians = student?.guardians ?? [];
  const smsTarget = getPrimarySmsTarget(student);
  return jsxRuntime.jsxs("aside", {
    className: `col-span-12 ${panelClass} lg:col-span-5`,
    children: [
      jsxRuntime.jsx("h3", { className: "text-sm font-semibold text-slate-200", children: "Student context" }),
      jsxRuntime.jsxs("div", {
        className: "mt-3 grid gap-3 text-xs text-slate-300 md:grid-cols-2",
        children: [
          jsxRuntime.jsxs("div", {
            children: [
              jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-slate-400", children: "Name" }),
              jsxRuntime.jsx("p", { children: student ? `${student.first_name} ${student.last_name}` : "Select a student" }),
            ],
          }),
          jsxRuntime.jsxs("div", {
            children: [
              jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-slate-400", children: "Admission #" }),
              jsxRuntime.jsx("p", { children: student?.admission_number ?? "--" }),
            ],
          }),
          jsxRuntime.jsxs("div", {
            children: [
              jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-slate-400", children: "Class" }),
              jsxRuntime.jsx("p", { children: enrollment?.class_name ?? "--" }),
            ],
          }),
          jsxRuntime.jsxs("div", {
            children: [
              jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-slate-400", children: "Term" }),
              jsxRuntime.jsx("p", { children: enrollment?.term_name ?? "--" }),
            ],
          }),
          jsxRuntime.jsxs("div", {
            children: [
              jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-slate-400", children: "SMS target" }),
              jsxRuntime.jsx("p", { children: smsTarget || student?.phone || "--" }),
            ],
          }),
        ],
      }),
      warning ? jsxRuntime.jsx("p", { className: "mt-2 text-[11px] text-amber-200", children: warning }) : null,
      jsxRuntime.jsxs("div", {
        className: "mt-4",
        children: [
          jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-slate-400", children: "Parents / Guardians" }),
          jsxRuntime.jsx("div", {
            className: "mt-2 space-y-2",
            children:
              guardians.length > 0
                ? guardians.map((guardian) =>
                    jsxRuntime.jsxs(
                      "div",
                      {
                        className: "rounded-xl border border-white/[0.07] p-3 text-xs",
                        children: [
                          jsxRuntime.jsx("p", { className: "text-sm text-white", children: guardian.name }),
                          jsxRuntime.jsx("p", {
                            className: "text-[11px] text-slate-400",
                            children: guardian.relationship ?? "Guardian",
                          }),
                          jsxRuntime.jsxs("p", {
                            className: "text-[11px] text-slate-400",
                            children: [guardian.phone ?? "--", " | ", guardian.email ?? "--"],
                          }),
                        ],
                      },
                      guardian.id,
                    ),
                  )
                : jsxRuntime.jsx("p", {
                    className: "text-[11px] text-slate-400",
                    children: "No guardian records found.",
                  }),
          }),
        ],
      }),
    ],
  });
}

function StripeSummary({ session, onOpen, onReset }) {
  if (!session) return null;
  return jsxRuntime.jsxs("div", {
    className: "rounded-2xl border border-sky-500/30 bg-sky-500/10 p-4 text-sm text-sky-100",
    children: [
      jsxRuntime.jsx("p", { className: "font-semibold", children: "Stripe checkout is ready." }),
      jsxRuntime.jsxs("div", {
        className: "mt-3 grid gap-2 text-xs text-sky-100/80 sm:grid-cols-2",
        children: [
          jsxRuntime.jsxs("div", { children: ["Reference: ", jsxRuntime.jsx("strong", { children: session.reference })] }),
          jsxRuntime.jsxs("div", {
            children: ["Session: ", jsxRuntime.jsx("strong", { children: session.checkout_session_id })],
          }),
        ],
      }),
      jsxRuntime.jsxs("div", {
        className: "mt-4 flex flex-wrap gap-2",
        children: [
          jsxRuntime.jsx("button", {
            type: "button",
            className: "rounded-xl bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-300",
            onClick: onOpen,
            children: "Open checkout",
          }),
          jsxRuntime.jsx("button", {
            type: "button",
            className: "rounded-xl border border-white/[0.14] px-4 py-2 text-sm text-slate-100 transition hover:bg-white/[0.04]",
            onClick: onReset,
            children: "Create another link",
          }),
        ],
      }),
    ],
  });
}

function PaymentReceiptPanel({ payment, student, onOpenReceipt, onOpenReceiptJson, onCopySms, onReset }) {
  if (!payment) return null;
  const smsTarget = getPrimarySmsTarget(student);
  const smsStatus = smsTarget ? `Queued to ${smsTarget}` : "No SMS target on file";
  return jsxRuntime.jsxs("div", {
    className: "mt-6 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5 text-sm text-emerald-100",
    children: [
      jsxRuntime.jsx("p", {
        className: "text-[11px] uppercase tracking-[0.3em] text-emerald-200",
        children: "Receipt ready",
      }),
      jsxRuntime.jsx("h3", {
        className: "mt-2 text-lg font-semibold text-white",
        children: payment.receipt_no ? `Receipt ${payment.receipt_no}` : "Payment recorded",
      }),
      jsxRuntime.jsxs("div", {
        className: "mt-4 grid gap-3 md:grid-cols-2",
        children: [
          jsxRuntime.jsxs("div", {
            children: [
              jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-emerald-200/80", children: "Transaction" }),
              jsxRuntime.jsx("p", { children: payment.transaction_code || payment.reference_number || "--" }),
            ],
          }),
          jsxRuntime.jsxs("div", {
            children: [
              jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-emerald-200/80", children: "Status" }),
              jsxRuntime.jsx("p", { children: payment.status || "--" }),
            ],
          }),
          jsxRuntime.jsxs("div", {
            children: [
              jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-emerald-200/80", children: "Amount" }),
              jsxRuntime.jsx("p", { children: `KES ${formatMoney(payment.amount)}` }),
            ],
          }),
          jsxRuntime.jsxs("div", {
            children: [
              jsxRuntime.jsx("p", { className: "text-[11px] uppercase text-emerald-200/80", children: "SMS" }),
              jsxRuntime.jsx("p", { children: smsStatus }),
            ],
          }),
        ],
      }),
      jsxRuntime.jsxs("div", {
        className: "mt-5 flex flex-wrap gap-2",
        children: [
          jsxRuntime.jsx("button", {
            type: "button",
            className: "rounded-xl bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300",
            onClick: onOpenReceipt,
            children: "Receipt",
          }),
          jsxRuntime.jsx("button", {
            type: "button",
            className: "rounded-xl border border-white/[0.14] px-4 py-2 text-sm text-slate-100 transition hover:bg-white/[0.04]",
            onClick: onOpenReceiptJson,
            children: "Receipt JSON",
          }),
          jsxRuntime.jsx("button", {
            type: "button",
            className: "rounded-xl border border-amber-500/40 px-4 py-2 text-sm text-amber-100 transition hover:bg-amber-500/10",
            onClick: onCopySms,
            children: "SMS",
          }),
          jsxRuntime.jsx("button", {
            type: "button",
            className: "rounded-xl border border-white/[0.14] px-4 py-2 text-sm text-slate-100 transition hover:bg-white/[0.04]",
            onClick: onReset,
            children: "Record another",
          }),
        ],
      }),
      jsxRuntime.jsx("p", {
        className: "mt-3 text-xs text-emerald-100/75",
        children: `Receipt and SMS payload are aligned to ${payment.receipt_no || payment.receipt_number || "the saved payment"}.`,
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
  const selectedStudentLabel = student ? `${student.first_name} ${student.last_name}`.trim() || student.admission_number : "";
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
      const mappedErrors = getFieldErrors(error, ["student", "amount", "payment_date", "payment_method", "reference_number"]);
      if (Object.keys(mappedErrors).length > 0) {
        setFieldErrors(mappedErrors);
      }
      setFormError(getErrorMessage(error, isStripeFlow ? "Unable to create Stripe checkout." : "Unable to record payment."));
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

  return jsxRuntime.jsxs("div", {
    className: "grid grid-cols-12 gap-6",
    children: [
      jsxRuntime.jsx(PageHero, {
        badge: "FINANCE",
        badgeColor: "emerald",
        title: "Record Payment",
        subtitle: "Capture manual receipts or launch a hosted Stripe checkout from the same workspace.",
        icon: "💰",
      }),
      jsxRuntime.jsx("div", {
        className: "col-span-12",
        children: jsxRuntime.jsx(BackButton, { to: "/modules/finance/payments", label: "Back to Payments" }),
      }),
      loadingStudents
        ? jsxRuntime.jsx("div", {
            className: `col-span-12 ${panelClass}`,
            children: jsxRuntime.jsx("p", { className: "text-sm text-slate-300", children: "Loading students..." }),
          })
        : null,
      jsxRuntime.jsx(Flash, { tone: flash?.tone, message: flash?.message }),
      jsxRuntime.jsx(Flash, { tone: "error", message: formError }),
      jsxRuntime.jsx("section", {
        className: `col-span-12 ${panelClass} lg:col-span-7`,
        children: [
          jsxRuntime.jsxs("form", {
            className: "space-y-4",
            onSubmit: handleSubmit,
            children: [
              jsxRuntime.jsx(Field, {
                label: "Admission No.",
                error: fieldErrors.student,
                hint: "Search an admission number or name, then choose the matching student.",
                children: jsxRuntime.jsxs("div", {
                  className: "relative",
                  children: [
                    jsxRuntime.jsx("input", {
                      className: fieldErrors.student ? invalidFieldClass : fieldClass,
                      value: admissionLookup,
                      "aria-invalid": !!fieldErrors.student,
                      autoComplete: "off",
                      placeholder: "Type admission number or name...",
                      onFocus: () => setAdmissionOpen(true),
                      onBlur: () => setTimeout(() => setAdmissionOpen(false), 150),
                      onChange: (event) => {
                        setAdmissionLookup(event.target.value);
                        setAdmissionOpen(true);
                      },
                    }),
                    admissionOpen && admissionMatches.length > 0
                      ? jsxRuntime.jsx("ul", {
                          className:
                            "absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-white/[0.09] bg-[#0d1421] shadow-xl",
                          children: admissionMatches.map((item) =>
                            jsxRuntime.jsx(
                              "li",
                              {
                                children: jsxRuntime.jsxs("button", {
                                  type: "button",
                                  className:
                                    "flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-sm hover:bg-slate-800 transition",
                                  onMouseDown: () => selectStudent(item),
                                  children: [
                                    jsxRuntime.jsxs("span", {
                                      className: "text-white",
                                      children: [item.first_name, " ", item.last_name],
                                    }),
                                    jsxRuntime.jsx("span", {
                                      className: "font-mono text-xs text-slate-400",
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
                      ? jsxRuntime.jsx("div", {
                          className:
                            "absolute z-30 mt-1 w-full rounded-xl border border-white/[0.09] bg-[#0d1421] px-4 py-3 text-sm text-slate-500",
                          children: `No students match "${admissionLookup}"`,
                        })
                      : null,
                  ],
                }),
              }),
              selectedStudentLabel
                ? jsxRuntime.jsxs("p", {
                    className: "text-xs text-emerald-400",
                    children: ["Selected student: ", selectedStudentLabel, " (", student?.admission_number ?? "--", ")"],
                  })
                : null,
              jsxRuntime.jsx(Field, {
                label: "Student",
                error: fieldErrors.student,
                children: jsxRuntime.jsxs("select", {
                  className: fieldErrors.student ? invalidFieldClass : fieldClass,
                  value: form.student,
                  "aria-invalid": !!fieldErrors.student,
                  onChange: (event) => {
                    const nextStudent = students.find((item) => String(item.id) === event.target.value);
                    updateForm("student", event.target.value);
                    setAdmissionLookup(
                      nextStudent ? `${nextStudent.admission_number} - ${nextStudent.first_name} ${nextStudent.last_name}` : "",
                    );
                    setAdmissionOpen(false);
                    setLastPayment(null);
                  },
                  children: [
                    jsxRuntime.jsx("option", { value: "", children: "Select student" }),
                    students.map((item) =>
                      jsxRuntime.jsxs(
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
              jsxRuntime.jsx(Field, {
                label: "Amount",
                error: fieldErrors.amount,
                children: jsxRuntime.jsx("input", {
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
              jsxRuntime.jsx(Field, {
                label: "Payment Method",
                error: fieldErrors.payment_method,
                hint: isStripeFlow
                  ? "This launches a hosted Stripe card checkout and records the payment after the webhook confirms success."
                  : "Manual methods record the payment immediately in the ledger.",
                children: jsxRuntime.jsxs("select", {
                  className: fieldErrors.payment_method ? invalidFieldClass : fieldClass,
                  value: form.payment_method,
                  "aria-invalid": !!fieldErrors.payment_method,
                  onChange: (event) => {
                    const nextMethod = event.target.value;
                    updateForm("payment_method", nextMethod);
                    setLastPayment(null);
                    if (nextMethod !== "Stripe Checkout") {
                      setStripeSession(null);
                    }
                  },
                  children: [
                    jsxRuntime.jsx("option", { value: "", children: "Select method" }),
                    PAYMENT_METHODS.map((method) => jsxRuntime.jsx("option", { value: method, children: method }, method)),
                  ],
                }),
              }),
              !isStripeFlow
                ? jsxRuntime.jsx(Field, {
                    label: "Payment Date",
                    error: fieldErrors.payment_date,
                    children: jsxRuntime.jsx("input", {
                      type: "date",
                      className: fieldErrors.payment_date ? invalidFieldClass : fieldClass,
                      value: form.payment_date,
                      "aria-invalid": !!fieldErrors.payment_date,
                      onChange: (event) => updateForm("payment_date", event.target.value),
                    }),
                  })
                : null,
              jsxRuntime.jsx(Field, {
                label: isStripeFlow ? "Internal Reference (Optional)" : "Reference Number",
                error: fieldErrors.reference_number,
                hint: isStripeFlow ? "Leave blank to auto-generate a Stripe launch reference." : "",
                children: jsxRuntime.jsx("input", {
                  className: fieldErrors.reference_number ? invalidFieldClass : fieldClass,
                  value: form.reference_number,
                  "aria-invalid": !!fieldErrors.reference_number,
                  onChange: (event) => updateForm("reference_number", event.target.value),
                  placeholder: isStripeFlow ? "STR-FASTTRACK-001" : "RCPT-1001",
                }),
              }),
              jsxRuntime.jsx(Field, {
                label: "Notes",
                children: jsxRuntime.jsx("textarea", {
                  className: fieldClass,
                  value: form.notes,
                  onChange: (event) => updateForm("notes", event.target.value),
                  rows: 3,
                }),
              }),
              isStripeFlow
                ? jsxRuntime.jsx(StripeSummary, {
                    session: stripeSession,
                    onOpen: openStripeCheckout,
                    onReset: resetStripeSession,
                  })
                : null,
              jsxRuntime.jsxs("div", {
                className: "flex flex-wrap gap-2",
                children: [
                  jsxRuntime.jsx("button", {
                    className:
                      "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 disabled:cursor-not-allowed disabled:opacity-70",
                    type: "submit",
                    disabled: submitting,
                    children: submitting
                      ? isStripeFlow
                        ? "Creating checkout..."
                        : "Saving..."
                      : isStripeFlow
                      ? "Create Stripe checkout"
                      : "Record payment",
                  }),
                  jsxRuntime.jsx("button", {
                    className: "rounded-xl border border-white/[0.09] px-4 py-2 text-sm text-slate-200",
                    type: "button",
                    onClick: () => navigate("/modules/finance/payments"),
                    children: "Cancel",
                  }),
                ],
              }),
            ],
          }),
          lastPayment
            ? jsxRuntime.jsx(PaymentReceiptPanel, {
                payment: lastPayment,
                student,
                onOpenReceipt: () => openReceipt("pdf"),
                onOpenReceiptJson: () => openReceipt("json"),
                onCopySms: copySmsMessage,
                onReset: resetPaymentForm,
              })
            : null,
        ],
      }),
      jsxRuntime.jsx(StudentContext, {
        student,
        enrollment,
        warning: studentWarning,
      }),
    ],
  });
}

export { FinancePaymentFormPage as default };
