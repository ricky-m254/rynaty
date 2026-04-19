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

  const isStripeFlow = form.payment_method === "Stripe Checkout";

  const updateForm = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => ({ ...current, [key]: "" }));
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
    await api.post("/finance/payments/", {
      student: Number(form.student),
      amount: Number(form.amount),
      payment_date: form.payment_date,
      payment_method: form.payment_method,
      reference_number: form.reference_number,
      notes: form.notes,
    });
    navigate("/modules/finance/payments", { state: { flash: "Payment recorded." } });
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
        children: jsxRuntime.jsxs("form", {
          className: "space-y-4",
          onSubmit: handleSubmit,
          children: [
            jsxRuntime.jsx(Field, {
              label: "Student",
              error: fieldErrors.student,
              children: jsxRuntime.jsxs("select", {
                className: fieldErrors.student ? invalidFieldClass : fieldClass,
                value: form.student,
                "aria-invalid": !!fieldErrors.student,
                onChange: (event) => updateForm("student", event.target.value),
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
