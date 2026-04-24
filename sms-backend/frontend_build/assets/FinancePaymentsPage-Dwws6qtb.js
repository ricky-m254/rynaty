import {
  a as useAppStore,
  u as useNavigate,
  c as useLocation,
  r as React,
  j as jsxRuntime,
  b as api,
} from "./index-D7ltaYVC.js";
import { n as normalizePaginated } from "./pagination-DjjjzeDo.js";
import { C as ConfirmDialog } from "./ConfirmDialog-WF6S4jMq.js";
import { e as getErrorMessage } from "./forms-ZJa1TpnO.js";
import { d as downloadBlob } from "./download-EzDvBC7h.js";
import { P as PermissionGate } from "./PermissionGate-pg50vBbt.js";

const { jsx, jsxs } = jsxRuntime;

const PAGE_SIZE = 8;
const shellClass =
  "rounded-[32px] border border-slate-200/80 bg-[#f5f7fb] p-5 shadow-[0_28px_70px_rgba(15,23,42,0.08)] md:p-7 xl:p-8";
const surfaceClass =
  "rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-[0_22px_50px_rgba(15,23,42,0.06)]";
const insetClass = "rounded-[22px] border border-slate-200 bg-slate-50/85 p-4";
const inputClass =
  "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5";
const softButtonClass =
  "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900";

function go(path) {
  if (typeof window !== "undefined") {
    window.location.assign(path);
  }
}

function formatMoney(value) {
  return `Ksh ${Number(value ?? 0).toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function shortDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${date.toLocaleDateString("en-KE", { month: "short", day: "numeric" })}, ${date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function allocationState(payment) {
  if (!payment?.is_active) {
    return { key: "reversed", label: "Reversed" };
  }
  const unallocated = Number(payment.unallocated_amount ?? 0);
  const allocated = Number(payment.allocated_amount ?? 0);
  if (unallocated <= 0 && allocated > 0) {
    return { key: "allocated", label: "Allocated" };
  }
  if (allocated > 0) {
    return { key: "partial", label: "Partial" };
  }
  return { key: "unallocated", label: "Unallocated" };
}

function toneClass(value) {
  return (
    {
      reversed: "border-rose-200 bg-rose-50 text-rose-700",
      allocated: "border-emerald-200 bg-emerald-50 text-emerald-700",
      partial: "border-amber-200 bg-amber-50 text-amber-700",
      unallocated: "border-slate-200 bg-slate-100 text-slate-700",
      APPROVED: "border-emerald-200 bg-emerald-50 text-emerald-700",
      REJECTED: "border-rose-200 bg-rose-50 text-rose-700",
      PENDING: "border-amber-200 bg-amber-50 text-amber-700",
      active: "border-emerald-200 bg-emerald-50 text-emerald-700",
    }[String(value || "")] ?? "border-slate-200 bg-slate-100 text-slate-700"
  );
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

function buildCsv(rows) {
  return rows
    .map((row) => row.map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");
}

function paymentBadge(method) {
  const normalized = String(method || "").toLowerCase();
  if (normalized.includes("mpesa")) return { icon: "M", tone: "text-emerald-700 bg-emerald-50" };
  if (normalized.includes("cash")) return { icon: "$", tone: "text-slate-700 bg-slate-100" };
  if (normalized.includes("bank")) return { icon: "B", tone: "text-sky-700 bg-sky-50" };
  if (normalized.includes("stripe") || normalized.includes("card")) return { icon: "C", tone: "text-violet-700 bg-violet-50" };
  return { icon: "P", tone: "text-slate-700 bg-slate-100" };
}

function FinancePaymentsPage() {
  const role = useAppStore((state) => state.role);
  const canReviewReversals = role === "ADMIN" || role === "TENANT_SUPER_ADMIN";
  const navigate = useNavigate();
  const location = useLocation();

  const [payments, setPayments] = React.useState([]);
  const [students, setStudents] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState(null);
  const [flash, setFlash] = React.useState(null);
  const [page, setPage] = React.useState(1);
  const [totalCount, setTotalCount] = React.useState(0);
  const [isServerPaginated, setIsServerPaginated] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const [studentFilter, setStudentFilter] = React.useState("all");
  const [methodFilter, setMethodFilter] = React.useState("all");
  const [allocationFilter, setAllocationFilter] = React.useState("all");
  const [dateFrom, setDateFrom] = React.useState("");
  const [dateTo, setDateTo] = React.useState("");
  const [expandedPaymentId, setExpandedPaymentId] = React.useState(null);
  const [contextLoadingId, setContextLoadingId] = React.useState(null);
  const [studentProfiles, setStudentProfiles] = React.useState({});
  const [enrollments, setEnrollments] = React.useState({});
  const [contextWarnings, setContextWarnings] = React.useState({});
  const [deleteTarget, setDeleteTarget] = React.useState(null);
  const [deleteProcessing, setDeleteProcessing] = React.useState(false);
  const [deleteError, setDeleteError] = React.useState(null);
  const [reversalTarget, setReversalTarget] = React.useState(null);
  const [reversalReason, setReversalReason] = React.useState("");
  const [reversalSubmitting, setReversalSubmitting] = React.useState(false);
  const [reversalModalError, setReversalModalError] = React.useState(null);
  const [reversals, setReversals] = React.useState([]);
  const [reversalsLoading, setReversalsLoading] = React.useState(false);
  const [reversalQueueError, setReversalQueueError] = React.useState(null);
  const [reversalQueueFlash, setReversalQueueFlash] = React.useState(null);
  const [reversalSearch, setReversalSearch] = React.useState("");
  const [reversalStatus, setReversalStatus] = React.useState("");
  const [reversalActionId, setReversalActionId] = React.useState(null);

  const invalidDateRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);

  React.useEffect(() => {
    const state = location.state;
    if (state?.flash) {
      setFlash(state.flash);
      navigate(location.pathname, { replace: true });
    }
  }, [location.state, location.pathname, navigate]);

  const loadPayments = React.useCallback(async () => {
    if (invalidDateRange) {
      setLoadError("Invalid payment date range: From date cannot be after To date.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const [paymentResponse, studentResponse] = await Promise.all([
        api.get("/finance/payments/", {
          params: {
            page,
            search: search.trim() || undefined,
            student: studentFilter !== "all" ? studentFilter : undefined,
            payment_method: methodFilter !== "all" ? methodFilter : undefined,
            allocation_status: allocationFilter !== "all" ? allocationFilter : undefined,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
          },
        }),
        api.get("/finance/ref/students/"),
      ]);
      const normalizedPayments = normalizePaginated(paymentResponse.data);
      setPayments(normalizedPayments.items);
      setTotalCount(normalizedPayments.totalCount);
      setIsServerPaginated(normalizedPayments.isPaginated);
      setStudents(normalizePaginated(studentResponse.data).items);
    } catch (error) {
      const statusCode = error?.response?.status;
      setLoadError(
        statusCode === 401
          ? "Session expired. Please sign in again."
          : statusCode === 403
            ? "Access denied. Ensure this account has finance access."
            : statusCode === 404
              ? "Finance payment endpoints were not found for this tenant."
              : getErrorMessage(error, "Unable to load payment collections."),
      );
    } finally {
      setLoading(false);
    }
  }, [allocationFilter, dateFrom, dateTo, invalidDateRange, methodFilter, page, search, studentFilter]);

  const loadReversals = React.useCallback(async () => {
    setReversalsLoading(true);
    setReversalQueueError(null);
    try {
      const response = await api.get("/finance/payment-reversals/", {
        params: {
          search: reversalSearch.trim() || undefined,
          status: reversalStatus || undefined,
        },
      });
      setReversals(normalizePaginated(response.data).items);
    } catch (error) {
      setReversalQueueError(getErrorMessage(error, "Unable to load payment reversal requests."));
    } finally {
      setReversalsLoading(false);
    }
  }, [reversalSearch, reversalStatus]);

  React.useEffect(() => {
    loadPayments();
  }, [loadPayments]);

  React.useEffect(() => {
    loadReversals();
  }, [loadReversals]);

  const studentLookup = React.useMemo(
    () =>
      students.reduce((accumulator, item) => {
        accumulator[item.id] = `${item.first_name} ${item.last_name}`.trim() || item.admission_number || String(item.id);
        return accumulator;
      }, {}),
    [students],
  );

  const filteredPayments = React.useMemo(() => {
    const term = search.trim().toLowerCase();
    return payments.filter((payment) => {
      if (studentFilter !== "all" && String(payment.student) !== studentFilter) return false;
      if (methodFilter !== "all" && payment.payment_method !== methodFilter) return false;
      if (allocationFilter !== "all" && allocationState(payment).key !== allocationFilter) return false;
      if (dateFrom && payment.payment_date && payment.payment_date < dateFrom) return false;
      if (dateTo && payment.payment_date && payment.payment_date > dateTo) return false;
      if (!term) return true;

      const studentLabel = (studentLookup[payment.student] || "").toLowerCase();
      return [
        payment.receipt_no || payment.receipt_number || "",
        payment.transaction_code || "",
        payment.reference_number || "",
        payment.vote_head_summary || "",
        payment.payment_method || "",
        String(payment.student || ""),
        studentLabel,
      ]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [allocationFilter, dateFrom, dateTo, methodFilter, payments, search, studentFilter, studentLookup]);

  const visiblePayments = React.useMemo(() => {
    if (isServerPaginated) return filteredPayments;
    const start = (page - 1) * PAGE_SIZE;
    return filteredPayments.slice(start, start + PAGE_SIZE);
  }, [filteredPayments, isServerPaginated, page]);

  const totalPages = Math.max(1, Math.ceil((isServerPaginated ? totalCount : filteredPayments.length) / PAGE_SIZE));
  const methodOptions = React.useMemo(
    () => Array.from(new Set(payments.map((item) => item.payment_method).filter(Boolean))).sort(),
    [payments],
  );
  const activePayments = filteredPayments.filter((item) => item.is_active);
  const totalCollected = activePayments.reduce((sum, item) => sum + Number(item.amount ?? 0), 0);
  const unallocatedTotal = activePayments.reduce((sum, item) => sum + Number(item.unallocated_amount ?? 0), 0);
  const pendingReversals = reversals.filter((item) => item.status === "PENDING").length;

  const exportPaymentsCsv = () => {
    const csv = buildCsv([
      ["receipt", "transaction", "student", "method", "amount", "allocation", "payment_date", "reference"],
      ...filteredPayments.map((payment) => [
        payment.receipt_no || payment.receipt_number || `RCT-${payment.id}`,
        payment.transaction_code || payment.reference_number || "",
        studentLookup[payment.student] || payment.student,
        payment.payment_method || "",
        payment.amount || "",
        allocationState(payment).label,
        payment.payment_date || "",
        payment.reference_number || "",
      ]),
    ]);
    downloadBlob(new Blob([csv], { type: "text/csv;charset=utf-8;" }), "finance_payments.csv");
  };

  const toggleContext = async (payment) => {
    if (expandedPaymentId === payment.id) {
      setExpandedPaymentId(null);
      return;
    }

    setExpandedPaymentId(payment.id);
    const studentId = payment.student;
    if (studentProfiles[studentId] || contextWarnings[studentId]) {
      return;
    }

    setContextLoadingId(payment.id);
    try {
      const [studentResponse, enrollmentResponse] = await Promise.all([
        api.get(`/students/${studentId}/`),
        api.get("/finance/ref/enrollments/", { params: { student_id: studentId, active: true } }),
      ]);
      const enrollmentItems = Array.isArray(enrollmentResponse.data)
        ? enrollmentResponse.data
        : enrollmentResponse.data?.results ?? [];
      setStudentProfiles((current) => ({ ...current, [studentId]: studentResponse.data }));
      setEnrollments((current) => ({ ...current, [studentId]: enrollmentItems[0] ?? null }));
    } catch {
      setContextWarnings((current) => ({
        ...current,
        [studentId]: "Student contact or class details could not be loaded.",
      }));
    } finally {
      setContextLoadingId(null);
    }
  };

  const handleDeletePayment = async () => {
    if (!deleteTarget) return;
    setDeleteProcessing(true);
    setDeleteError(null);
    try {
      await api.delete(`/finance/payments/${deleteTarget.id}/`);
      setFlash({
        tone: "success",
        message: `Deleted payment ${deleteTarget.receipt_no || deleteTarget.reference_number || deleteTarget.id}.`,
      });
      setDeleteTarget(null);
      await loadPayments();
    } catch (error) {
      setDeleteError(getErrorMessage(error, "Unable to delete payment."));
    } finally {
      setDeleteProcessing(false);
    }
  };

  const downloadReceiptPdf = async (payment) => {
    try {
      const response = await api.get(`/api/finance/payments/${payment.id}/receipt/pdf/`, {
        responseType: "blob",
      });
      downloadBlob(response.data, `receipt_${payment.receipt_no || payment.receipt_number || payment.id}.pdf`);
    } catch (error) {
      setLoadError(getErrorMessage(error, "Unable to download the receipt PDF."));
    }
  };

  const openReversalModal = (payment) => {
    if (!payment.is_active) {
      setFlash({ tone: "error", message: "This payment is already reversed." });
      return;
    }
    setReversalTarget(payment);
    setReversalReason("");
    setReversalModalError(null);
  };

  const submitReversalRequest = async () => {
    if (!reversalTarget || reversalSubmitting) return;
    if (!reversalReason.trim()) {
      setReversalModalError("Reversal reason is required.");
      return;
    }
    setReversalSubmitting(true);
    setReversalModalError(null);
    try {
      await api.post("/finance/payment-reversals/", {
        payment: reversalTarget.id,
        reason: reversalReason.trim(),
      });
      setFlash({
        tone: "success",
        message: `Reversal request submitted for ${reversalTarget.receipt_no || reversalTarget.reference_number}.`,
      });
      setReversalTarget(null);
      setReversalReason("");
      await loadReversals();
    } catch (error) {
      setReversalModalError(
        getErrorMessage(error, `Failed to submit reversal request for ${reversalTarget.receipt_no || reversalTarget.reference_number}.`),
      );
    } finally {
      setReversalSubmitting(false);
    }
  };

  const reviewReversal = async (requestId, action) => {
    if (reversalActionId !== null) return;
    setReversalActionId(requestId);
    setReversalQueueFlash(null);
    setReversalQueueError(null);
    try {
      await api.post(`/finance/payment-reversals/${requestId}/${action}/`, {});
      setReversalQueueFlash(`Reversal ${action}d successfully.`);
      await Promise.all([loadReversals(), loadPayments()]);
    } catch (error) {
      setReversalQueueError(getErrorMessage(error, `Unable to ${action} reversal request.`));
    } finally {
      setReversalActionId(null);
    }
  };

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
                    children: "Review collections, open receipts, inspect student context, and keep maker-checker reversals visible.",
                  }),
                ],
              }),
              jsx(PortalSwitch, { active: "bursar" }),
            ],
          }),
          jsx("div", { className: "mt-6", children: jsx(FinanceTabs, { active: "payments" }) }),
          jsxs("div", {
            className: "mt-6 space-y-4",
            children: [
              jsx(Notice, { tone: flash?.tone, message: flash?.message }),
              jsx(Notice, { tone: "error", message: loadError }),
            ],
          }),
          jsx("div", {
            className: "mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4",
            children: [
              jsx(MetricCard, {
                label: "Total Collected",
                value: formatMoney(totalCollected),
                detail: `${activePayments.length} active transactions in this view.`,
                tone: "text-emerald-600",
              }),
              jsx(MetricCard, {
                label: "Recorded Receipts",
                value: String(filteredPayments.length),
                detail: "Current result set after search and filters.",
              }),
              jsx(MetricCard, {
                label: "Outstanding Allocation",
                value: formatMoney(unallocatedTotal),
                detail: "Still waiting to be fully allocated across invoices or vote heads.",
                tone: "text-amber-600",
              }),
              jsx(MetricCard, {
                label: "Pending Reversals",
                value: String(pendingReversals),
                detail: "Maker-checker requests still awaiting review.",
                tone: pendingReversals > 0 ? "text-rose-600" : "text-slate-950",
              }),
            ],
          }),
          jsxs("section", {
            className: `${surfaceClass} mt-6`,
            children: [
              jsxs("div", {
                className: "flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between",
                children: [
                  jsxs("div", {
                    children: [
                      jsx("h2", { className: "text-xl font-semibold text-slate-950", children: "Recent Payments" }),
                      jsx("p", {
                        className: "mt-1 text-sm text-slate-500",
                        children: "Latest payment transactions with cleaner placement for status, amount, reference, and bursar actions.",
                      }),
                    ],
                  }),
                  jsxs("div", {
                    className: "flex flex-wrap gap-2",
                    children: [
                      jsx("button", {
                        type: "button",
                        className: softButtonClass,
                        onClick: exportPaymentsCsv,
                        children: "Export CSV",
                      }),
                      jsx(PermissionGate, {
                        permission: "finance.payment.create",
                        children: jsx("button", {
                          type: "button",
                          className:
                            "rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800",
                          onClick: () => navigate("/modules/finance/payments/new"),
                          children: "Record payment",
                        }),
                      }),
                    ],
                  }),
                ],
              }),
              jsx("div", {
                className: "mt-5 grid gap-3 xl:grid-cols-6",
                children: [
                  jsx("input", {
                    className: "xl:col-span-2 " + inputClass,
                    placeholder: "Search receipt, transaction, vote head, or student",
                    value: search,
                    onChange: (event) => {
                      setSearch(event.target.value);
                      setPage(1);
                    },
                  }),
                  jsxs("select", {
                    className: inputClass,
                    value: studentFilter,
                    onChange: (event) => {
                      setStudentFilter(event.target.value);
                      setPage(1);
                    },
                    children: [
                      jsx("option", { value: "all", children: "All students" }),
                      students.map((item) =>
                        jsxs("option", { value: String(item.id), children: [item.first_name, " ", item.last_name] }, item.id),
                      ),
                    ],
                  }),
                  jsxs("select", {
                    className: inputClass,
                    value: methodFilter,
                    onChange: (event) => {
                      setMethodFilter(event.target.value);
                      setPage(1);
                    },
                    children: [
                      jsx("option", { value: "all", children: "All methods" }),
                      methodOptions.map((method) => jsx("option", { value: method, children: method }, method)),
                    ],
                  }),
                  jsxs("select", {
                    className: inputClass,
                    value: allocationFilter,
                    onChange: (event) => {
                      setAllocationFilter(event.target.value);
                      setPage(1);
                    },
                    children: [
                      jsx("option", { value: "all", children: "All allocation states" }),
                      jsx("option", { value: "allocated", children: "Allocated" }),
                      jsx("option", { value: "partial", children: "Partial" }),
                      jsx("option", { value: "unallocated", children: "Unallocated" }),
                      jsx("option", { value: "reversed", children: "Reversed" }),
                    ],
                  }),
                  jsx("input", {
                    type: "date",
                    className: inputClass,
                    value: dateFrom,
                    onChange: (event) => {
                      setDateFrom(event.target.value);
                      setPage(1);
                    },
                  }),
                  jsx("input", {
                    type: "date",
                    className: inputClass,
                    value: dateTo,
                    onChange: (event) => {
                      setDateTo(event.target.value);
                      setPage(1);
                    },
                  }),
                ],
              }),
              invalidDateRange
                ? jsx("p", {
                    className: "mt-3 text-sm text-rose-600",
                    children: "Date range is invalid. Adjust the dates before continuing.",
                  })
                : null,
              jsx("div", {
                className: "mt-5 overflow-hidden rounded-[24px] border border-slate-200",
                children:
                  loading
                    ? jsx("div", {
                        className: "px-6 py-12 text-center text-sm text-slate-500",
                        children: "Loading payments...",
                      })
                    : visiblePayments.length === 0
                      ? jsx("div", {
                          className: "px-6 py-12 text-center text-sm text-slate-500",
                          children: "No payments match the current filters.",
                        })
                      : visiblePayments.map((payment, index) => {
                          const allocation = allocationState(payment);
                          const studentId = payment.student;
                          const studentProfile = studentProfiles[studentId];
                          const enrollment = enrollments[studentId];
                          const guardians = studentProfile?.guardians ?? [];
                          const expanded = expandedPaymentId === payment.id;
                          const badge = paymentBadge(payment.payment_method);
                          return jsxs(
                            "div",
                            {
                              className: index === 0 ? "" : "border-t border-slate-200",
                              children: [
                                jsxs("div", {
                                  className: "flex flex-col gap-4 px-6 py-5 lg:flex-row lg:items-start lg:justify-between",
                                  children: [
                                    jsxs("div", {
                                      className: "flex min-w-0 gap-4",
                                      children: [
                                        jsx("div", {
                                          className: `flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl text-sm font-semibold ${badge.tone}`,
                                          children: badge.icon,
                                        }),
                                        jsxs("div", {
                                          className: "min-w-0",
                                          children: [
                                            jsx("p", {
                                              className: "text-lg font-semibold text-slate-950",
                                              children: studentLookup[payment.student] || payment.student,
                                            }),
                                            jsx("p", {
                                              className: "mt-1 text-sm text-slate-500",
                                              children: payment.receipt_no || payment.receipt_number || `RCT-${payment.id}`,
                                            }),
                                            jsx("p", {
                                              className: "mt-1 text-sm text-slate-500",
                                              children: shortDateTime(payment.created_at || payment.payment_date),
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
                                              className: "text-[1.75rem] font-semibold leading-none text-emerald-600",
                                              children: formatMoney(payment.amount),
                                            }),
                                            jsx("p", {
                                              className: "mt-1 text-sm text-slate-600",
                                              children: payment.payment_method || "--",
                                            }),
                                            jsx("p", {
                                              className: "mt-1 text-xs text-slate-500",
                                              children: payment.transaction_code || payment.reference_number || "--",
                                            }),
                                          ],
                                        }),
                                        jsxs("div", {
                                          className: "flex flex-wrap items-center justify-start gap-2 lg:justify-end",
                                          children: [
                                            jsx("span", {
                                              className: `inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${toneClass(allocation.key)}`,
                                              children: allocation.label,
                                            }),
                                            jsx("span", {
                                              className: `inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${
                                                payment.is_active ? toneClass("active") : toneClass("reversed")
                                              }`,
                                              children: payment.is_active ? "Completed" : "Reversed",
                                            }),
                                          ],
                                        }),
                                      ],
                                    }),
                                  ],
                                }),
                                jsxs("div", {
                                  className: "flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/70 px-6 py-3",
                                  children: [
                                    jsxs("div", {
                                      className: "flex flex-wrap gap-2",
                                      children: [
                                        jsx("button", {
                                          type: "button",
                                          className: softButtonClass,
                                          onClick: () => toggleContext(payment),
                                          children: expanded ? "Hide context" : "Context",
                                        }),
                                        jsx("button", {
                                          type: "button",
                                          className: softButtonClass,
                                          onClick: () => downloadReceiptPdf(payment),
                                          children: "Receipt PDF",
                                        }),
                                        jsx("button", {
                                          type: "button",
                                          className:
                                            "rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 transition hover:border-amber-300 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50",
                                          onClick: () => openReversalModal(payment),
                                          disabled: !payment.is_active,
                                          children: "Request reversal",
                                        }),
                                      ],
                                    }),
                                    jsx(PermissionGate, {
                                      permission: "finance.payment.delete",
                                      children: jsx("button", {
                                        type: "button",
                                        className:
                                          "rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:border-rose-300 hover:bg-rose-100",
                                        onClick: () => setDeleteTarget(payment),
                                        children: "Delete",
                                      }),
                                    }),
                                  ],
                                }),
                                expanded
                                  ? jsx("div", {
                                      className: "border-t border-slate-200 bg-white px-6 py-5",
                                      children: contextLoadingId === payment.id && !studentProfile
                                        ? jsx("p", { className: "text-sm text-slate-500", children: "Loading student context..." })
                                        : jsx("div", {
                                            className: "grid gap-4 xl:grid-cols-2",
                                            children: [
                                              jsx("div", {
                                                className: "grid gap-3 sm:grid-cols-2",
                                                children: [
                                                  { label: "Class", value: enrollment?.class_name ?? "--" },
                                                  { label: "Term", value: enrollment?.term_name ?? "--" },
                                                  { label: "Reference", value: payment.reference_number || "--" },
                                                  { label: "Notes", value: payment.notes || "No notes saved" },
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
                                              jsxs("div", {
                                                className: "space-y-3",
                                                children: [
                                                  jsx("p", {
                                                    className: "text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400",
                                                    children: "Parents / Guardians",
                                                  }),
                                                  guardians.length > 0
                                                    ? guardians.map((guardian) =>
                                                        jsxs(
                                                          "div",
                                                          {
                                                            className: insetClass,
                                                            children: [
                                                              jsx("p", {
                                                                className: "text-sm font-semibold text-slate-900",
                                                                children: guardian.name,
                                                              }),
                                                              jsx("p", {
                                                                className: "mt-1 text-[11px] uppercase tracking-[0.18em] text-slate-400",
                                                                children: guardian.relationship || "Guardian",
                                                              }),
                                                              jsx("p", {
                                                                className: "mt-2 text-sm text-slate-600",
                                                                children:
                                                                  guardian.phone || guardian.email
                                                                    ? `${guardian.phone ?? "--"}${guardian.email ? ` • ${guardian.email}` : ""}`
                                                                    : "No contact details captured",
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
                                                          children:
                                                            contextWarnings[studentId] ||
                                                            "No guardian records were found for this student.",
                                                        }),
                                                      }),
                                                ],
                                              }),
                                            ],
                                          }),
                                    })
                                  : null,
                              ],
                            },
                            payment.id,
                          );
                        }),
              }),
              jsxs("div", {
                className: "mt-4 flex items-center justify-between text-sm text-slate-500",
                children: [
                  jsxs("span", { children: ["Page ", page, " of ", totalPages] }),
                  jsxs("div", {
                    className: "flex gap-2",
                    children: [
                      jsx("button", {
                        type: "button",
                        className: softButtonClass,
                        disabled: page === 1,
                        onClick: () => setPage((current) => Math.max(1, current - 1)),
                        children: "Previous",
                      }),
                      jsx("button", {
                        type: "button",
                        className: softButtonClass,
                        disabled: page === totalPages,
                        onClick: () => setPage((current) => Math.min(totalPages, current + 1)),
                        children: "Next",
                      }),
                    ],
                  }),
                ],
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
                      jsx("h2", {
                        className: "text-xl font-semibold text-slate-950",
                        children: "Payment Reversal Queue",
                      }),
                      jsx("p", {
                        className: "mt-1 text-sm text-slate-500",
                        children: "Review office-initiated reversal requests with status chips and maker-checker controls.",
                      }),
                    ],
                  }),
                  jsx("div", {
                    className: "grid gap-3 sm:grid-cols-2",
                    children: [
                      jsx("input", {
                        className: inputClass,
                        placeholder: "Search receipt, reference, or reason",
                        value: reversalSearch,
                        onChange: (event) => setReversalSearch(event.target.value),
                      }),
                      jsxs("select", {
                        className: inputClass,
                        value: reversalStatus,
                        onChange: (event) => setReversalStatus(event.target.value),
                        children: [
                          jsx("option", { value: "", children: "All statuses" }),
                          jsx("option", { value: "PENDING", children: "Pending" }),
                          jsx("option", { value: "APPROVED", children: "Approved" }),
                          jsx("option", { value: "REJECTED", children: "Rejected" }),
                        ],
                      }),
                    ],
                  }),
                ],
              }),
              jsx("div", {
                className: "mt-4 space-y-3",
                children: [
                  jsx(Notice, { tone: "error", message: reversalQueueError }),
                  jsx(Notice, { tone: "success", message: reversalQueueFlash }),
                ],
              }),
              jsx("div", {
                className: "mt-4 space-y-3",
                children:
                  reversalsLoading
                    ? jsx("div", {
                        className: `${insetClass} text-sm text-slate-500`,
                        children: "Loading reversal requests...",
                      })
                    : reversals.length === 0
                      ? jsx("div", {
                          className: `${insetClass} text-sm text-slate-500`,
                          children: "No reversal requests found.",
                        })
                      : reversals.map((item) =>
                          jsxs(
                            "div",
                            {
                              className: "rounded-[24px] border border-slate-200 bg-white p-4",
                              children: [
                                jsxs("div", {
                                  className: "flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between",
                                  children: [
                                    jsxs("div", {
                                      children: [
                                        jsx("p", {
                                          className: "text-base font-semibold text-slate-950",
                                          children: item.payment_reference || `PAY-${item.payment}`,
                                        }),
                                        jsx("p", {
                                          className: "mt-1 text-sm text-slate-500",
                                          children: item.payment_receipt || "--",
                                        }),
                                        jsx("p", {
                                          className: "mt-2 text-sm text-slate-600",
                                          children: item.reason,
                                        }),
                                      ],
                                    }),
                                    jsxs("div", {
                                      className: "flex flex-col gap-2 lg:items-end",
                                      children: [
                                        jsx("span", {
                                          className: `inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${toneClass(item.status)}`,
                                          children: item.status,
                                        }),
                                        jsx("p", {
                                          className: "text-xs text-slate-500",
                                          children: `Requested ${formatDateTime(item.requested_at)}`,
                                        }),
                                        jsx("p", {
                                          className: "text-xs text-slate-500",
                                          children: `Reviewed by ${item.reviewed_by_name || "--"}`,
                                        }),
                                      ],
                                    }),
                                  ],
                                }),
                                jsx("div", {
                                  className: "mt-4 flex flex-wrap gap-2",
                                  children:
                                    canReviewReversals && item.status === "PENDING"
                                      ? [
                                          jsx("button", {
                                            type: "button",
                                            className:
                                              "rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:border-emerald-300 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50",
                                            onClick: () => reviewReversal(item.id, "approve"),
                                            disabled: reversalActionId !== null,
                                            children: "Approve",
                                          }, `approve-${item.id}`),
                                          jsx("button", {
                                            type: "button",
                                            className:
                                              "rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:border-rose-300 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50",
                                            onClick: () => reviewReversal(item.id, "reject"),
                                            disabled: reversalActionId !== null,
                                            children: "Reject",
                                          }, `reject-${item.id}`),
                                        ]
                                      : jsx("span", { className: "text-xs text-slate-400", children: "No action available" }),
                                }),
                              ],
                            },
                            item.id,
                          ),
                        ),
              }),
            ],
          }),
        ],
      }),
      jsx(ConfirmDialog, {
        open: !!deleteTarget,
        title: "Delete payment",
        description: jsxs(React.Fragment, {
          children: [
            "This will remove payment ",
            jsx("strong", { children: deleteTarget?.receipt_no || deleteTarget?.reference_number }),
            ". Continue?",
          ],
        }),
        confirmLabel: "Confirm delete",
        isProcessing: deleteProcessing,
        error: deleteError,
        onConfirm: handleDeletePayment,
        onCancel: () => setDeleteTarget(null),
      }),
      reversalTarget
        ? jsx("div", {
            className: "fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 px-4",
            children: jsx("div", {
              className:
                "w-full max-w-xl rounded-[30px] border border-slate-200 bg-white p-6 shadow-[0_30px_80px_rgba(15,23,42,0.25)]",
              children: jsxs("div", {
                className: "space-y-5",
                children: [
                  jsxs("div", {
                    className: "flex items-start justify-between gap-4",
                    children: [
                      jsxs("div", {
                        children: [
                          jsx("p", {
                            className: "text-[11px] font-semibold uppercase tracking-[0.26em] text-slate-400",
                            children: "Reversal Request",
                          }),
                          jsx("h3", {
                            className: "mt-2 text-xl font-semibold text-slate-950",
                            children: "Request payment reversal",
                          }),
                          jsx("p", {
                            className: "mt-1 text-sm text-slate-600",
                            children: `Submit a maker-checker reversal request for ${reversalTarget.receipt_no || reversalTarget.reference_number}.`,
                          }),
                        ],
                      }),
                      jsx("button", {
                        type: "button",
                        className: "text-2xl leading-none text-slate-400 transition hover:text-slate-700",
                        onClick: () => setReversalTarget(null),
                        children: "×",
                      }),
                    ],
                  }),
                  jsx("textarea", {
                    className:
                      "h-36 w-full rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5",
                    placeholder: "State the reason for the reversal and any supporting office context.",
                    value: reversalReason,
                    onChange: (event) => {
                      setReversalReason(event.target.value);
                      setReversalModalError(null);
                    },
                  }),
                  reversalModalError
                    ? jsx("div", {
                        className: "rounded-[22px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700",
                        children: reversalModalError,
                      })
                    : null,
                  jsxs("div", {
                    className: "flex flex-wrap gap-3",
                    children: [
                      jsx("button", {
                        type: "button",
                        className:
                          "rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60",
                        onClick: submitReversalRequest,
                        disabled: reversalSubmitting,
                        children: reversalSubmitting ? "Submitting..." : "Submit request",
                      }),
                      jsx("button", {
                        type: "button",
                        className:
                          "rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-900",
                        onClick: () => setReversalTarget(null),
                        children: "Cancel",
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

export { FinancePaymentsPage as default };
