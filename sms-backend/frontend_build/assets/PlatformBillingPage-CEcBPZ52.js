import { r as React, f as getApiBase, h as privateClient, j as jsxRuntime } from "./index-D7ltaYVC.js";
import { p as publicClient } from "./publicClient-BdJTy9AM.js";
import { n as normalizePaginated } from "./pagination-DjjjzeDo.js";
import { e as getErrorMessage } from "./forms-ZJa1TpnO.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";

const { jsx, jsxs, Fragment } = jsxRuntime;

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.07)",
};

const fieldClass =
  "w-full rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-400";

const defaultPlans = [
  {
    code: "STARTER",
    name: "Starter",
    description: "For small schools with up to 50 students. KES 300/student/year. Includes 100 free SMS credits.",
    monthly_price: "1250.00",
    annual_price: "15000.00",
    max_students: 50,
    max_storage_gb: 5,
    enabled_modules: ["CORE", "STUDENTS", "ACADEMICS", "FINANCE"],
    is_active: true,
  },
  {
    code: "GROWTH",
    name: "Growth",
    description: "For growing schools with 51-200 students. KES 280/student/year. Includes 500 free SMS credits.",
    monthly_price: "5000.00",
    annual_price: "60000.00",
    max_students: 200,
    max_storage_gb: 20,
    enabled_modules: [],
    is_active: true,
  },
  {
    code: "PRO",
    name: "Pro",
    description: "For established schools with 201-500 students. KES 260/student/year. Includes 2,000 free SMS credits.",
    monthly_price: "12500.00",
    annual_price: "150000.00",
    max_students: 500,
    max_storage_gb: 50,
    enabled_modules: [],
    is_active: true,
  },
  {
    code: "ENTERPRISE",
    name: "Enterprise",
    description: "For large schools with 500+ students. KES 240/student/year. Includes 5,000+ free SMS credits.",
    monthly_price: "12500.00",
    annual_price: "150000.00",
    max_students: 9999,
    max_storage_gb: 200,
    enabled_modules: [],
    is_active: true,
  },
  {
    code: "UNLIMITED",
    name: "Unlimited",
    description: "Unlimited students with high storage and white-label options.",
    monthly_price: "0.00",
    annual_price: "0.00",
    max_students: 999999,
    max_storage_gb: 500,
    enabled_modules: [],
    is_active: true,
  },
];

const pricingReference = {
  STARTER: { rate: 300, sms: 100, accent: "border-slate-600/60 bg-slate-950/60" },
  GROWTH: { rate: 280, sms: 500, accent: "border-sky-500/30 bg-sky-500/5" },
  PRO: { rate: 260, sms: 2000, accent: "border-violet-500/30 bg-violet-500/5" },
  PROFESSIONAL: { rate: 260, sms: 2000, accent: "border-violet-500/30 bg-violet-500/5" },
  ENTERPRISE: { rate: 240, sms: 5000, accent: "border-amber-500/30 bg-amber-500/5" },
  UNLIMITED: { rate: 220, sms: 10000, accent: "border-emerald-500/30 bg-emerald-500/5" },
};

const emptyPlanForm = {
  code: "",
  name: "",
  description: "",
  monthly_price: "",
  annual_price: "",
  max_students: "",
  max_storage_gb: "",
  is_active: true,
};

const emptySubscriptionForm = {
  tenant: "",
  plan: "",
  billing_cycle: "ANNUAL",
};

const emptyRecordPaymentForm = {
  amount: "",
  transaction_id: "",
  status: "PENDING",
  method: "M-Pesa",
  external_reference: "",
};

const emptyReviewForm = {
  reason: "",
};

const formatMoney = (value) =>
  `KES ${Number(value ?? 0).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const formatDate = (value) => {
  if (!value) return "--";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString();
};

const formatDateTime = (value) => {
  if (!value) return "--";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
};

const safeJson = (value) => {
  if (value == null) return "No metadata captured.";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch (error) {
    return String(value);
  }
};

const subscriptionTone = (status) =>
  (
    {
      ACTIVE: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
      TRIAL: "border-sky-500/30 bg-sky-500/10 text-sky-200",
      SUSPENDED: "border-amber-500/30 bg-amber-500/10 text-amber-200",
      CANCELLED: "border-rose-500/30 bg-rose-500/10 text-rose-200",
    }[String(status || "").toUpperCase()] ?? "border-slate-500/30 bg-slate-500/10 text-slate-300"
  );

const invoiceTone = (status) =>
  (
    {
      PAID: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
      PENDING: "border-amber-500/30 bg-amber-500/10 text-amber-200",
      OVERDUE: "border-rose-500/30 bg-rose-500/10 text-rose-200",
      CANCELLED: "border-slate-500/30 bg-slate-500/10 text-slate-300",
    }[String(status || "").toUpperCase()] ?? "border-slate-500/30 bg-slate-500/10 text-slate-300"
  );

const paymentTone = (status) =>
  (
    {
      PAID: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
      PENDING: "border-amber-500/30 bg-amber-500/10 text-amber-200",
      FAILED: "border-rose-500/30 bg-rose-500/10 text-rose-200",
    }[String(status || "").toUpperCase()] ?? "border-slate-500/30 bg-slate-500/10 text-slate-300"
  );

const integrationTone = (status) =>
  (
    {
      connected: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
      error: "border-rose-500/30 bg-rose-500/10 text-rose-200",
      disconnected: "border-slate-500/30 bg-slate-500/10 text-slate-300",
      pending: "border-amber-500/30 bg-amber-500/10 text-amber-200",
    }[String(status || "").toLowerCase()] ?? "border-slate-500/30 bg-slate-500/10 text-slate-300"
  );

function Flash({ tone = "success", message }) {
  if (!message) return null;
  const classes =
    tone === "error"
      ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
      : "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
  return jsx("div", {
    className: `col-span-12 rounded-2xl border px-4 py-3 text-sm ${classes}`,
    children: message,
  });
}

function StatCard({ label, value, detail, tone = "text-white" }) {
  return jsxs("div", {
    className: "rounded-2xl p-4",
    style: panelStyle,
    children: [
      jsx("p", { className: "text-[11px] uppercase tracking-wide text-slate-500", children: label }),
      jsx("p", { className: `mt-2 text-2xl font-semibold ${tone}`, children: value }),
      jsx("p", { className: "mt-1 text-xs text-slate-500", children: detail }),
    ],
  });
}

function OverlayCard({ title, subtitle, onClose, children }) {
  return jsx("div", {
    className: "fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4",
    children: jsxs("div", {
      className: "w-full max-w-2xl rounded-3xl p-6",
      style: {
        background: "#0f172a",
        border: "1px solid rgba(148,163,184,0.22)",
        boxShadow: "0 32px 80px rgba(15,23,42,0.55)",
      },
      children: [
        jsxs("div", {
          className: "flex items-start justify-between gap-4",
          children: [
            jsxs("div", {
              children: [
                jsx("h2", { className: "text-lg font-semibold text-white", children: title }),
                subtitle ? jsx("p", { className: "mt-1 text-sm text-slate-400", children: subtitle }) : null,
              ],
            }),
            jsx("button", {
              type: "button",
              onClick: onClose,
              className: "rounded-xl border border-white/[0.09] px-3 py-1 text-sm text-slate-300 transition hover:bg-white/[0.04]",
              children: "Close",
            }),
          ],
        }),
        jsx("div", { className: "mt-5", children }),
      ],
    }),
  });
}

function PlatformBillingPage() {
  const [plans, setPlans] = React.useState([]);
  const [tenants, setTenants] = React.useState([]);
  const [integrations, setIntegrations] = React.useState([]);
  const [subscriptions, setSubscriptions] = React.useState([]);
  const [invoices, setInvoices] = React.useState([]);
  const [payments, setPayments] = React.useState([]);
  const [paybillSetting, setPaybillSetting] = React.useState(null);
  const [paybill, setPaybill] = React.useState("522522");
  const [loadingCatalog, setLoadingCatalog] = React.useState(true);
  const [loadingRecords, setLoadingRecords] = React.useState(true);
  const [flash, setFlash] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [invoiceFilters, setInvoiceFilters] = React.useState({ tenant: "", status: "" });
  const [subscriptionFilters, setSubscriptionFilters] = React.useState({ tenant: "", plan: "", status: "" });
  const [paymentFilters, setPaymentFilters] = React.useState({ tenant: "", status: "", method: "" });
  const [subscriptionForm, setSubscriptionForm] = React.useState(emptySubscriptionForm);
  const [planEditor, setPlanEditor] = React.useState(null);
  const [planForm, setPlanForm] = React.useState(emptyPlanForm);
  const [planFormError, setPlanFormError] = React.useState(null);
  const [savingPlan, setSavingPlan] = React.useState(false);
  const [deletingPlanId, setDeletingPlanId] = React.useState(null);
  const [creatingSubscription, setCreatingSubscription] = React.useState(false);
  const [savingPaybill, setSavingPaybill] = React.useState(false);
  const [recordPaymentTarget, setRecordPaymentTarget] = React.useState(null);
  const [recordPaymentForm, setRecordPaymentForm] = React.useState(emptyRecordPaymentForm);
  const [recordPaymentError, setRecordPaymentError] = React.useState(null);
  const [recordingPayment, setRecordingPayment] = React.useState(false);
  const [reviewModal, setReviewModal] = React.useState(null);
  const [reviewForm, setReviewForm] = React.useState(emptyReviewForm);
  const [reviewError, setReviewError] = React.useState(null);
  const [reviewingPayment, setReviewingPayment] = React.useState(false);
  const [expandedPaymentId, setExpandedPaymentId] = React.useState(null);

  const loadCatalog = React.useCallback(async () => {
    setLoadingCatalog(true);
    setError(null);
    try {
      const apiBase = getApiBase().replace(/\/$/, "");
      const [planResult, tenantResult, settingsResult, integrationResult] = await Promise.allSettled([
        privateClient.get(`${apiBase}/api/platform/plans/`),
        publicClient.get("/platform/tenants/"),
        publicClient.get("/platform/settings/"),
        publicClient.get("/platform/integrations/"),
      ]);

      if (planResult.status === "fulfilled") {
        const nextPlans = normalizePaginated(planResult.value.data).items;
        setPlans(nextPlans);
      } else {
        setError(getErrorMessage(planResult.reason, "Unable to load platform subscription plans."));
      }

      if (tenantResult.status === "fulfilled") {
        setTenants(normalizePaginated(tenantResult.value.data).items);
      } else {
        setError((current) => current ?? getErrorMessage(tenantResult.reason, "Unable to load platform tenants."));
      }

      if (settingsResult.status === "fulfilled") {
        const nextSetting = normalizePaginated(settingsResult.value.data).items.find((item) => item.key === "MPESA_PAYBILL") ?? null;
        setPaybillSetting(nextSetting);
        if (nextSetting?.value?.number) {
          setPaybill(String(nextSetting.value.number));
        }
      }

      if (integrationResult.status === "fulfilled") {
        setIntegrations(normalizePaginated(integrationResult.value.data).items);
      } else {
        setError((current) => current ?? getErrorMessage(integrationResult.reason, "Unable to load gateway readiness."));
      }
    } finally {
      setLoadingCatalog(false);
    }
  }, []);

  const loadRecords = React.useCallback(async () => {
    setLoadingRecords(true);
    setError(null);
    try {
      const [invoiceResult, subscriptionResult, paymentResult] = await Promise.allSettled([
        publicClient.get("/platform/subscription-invoices/", {
          params: {
            tenant_id: invoiceFilters.tenant || undefined,
            status: invoiceFilters.status || undefined,
          },
        }),
        publicClient.get("/platform/subscriptions/", {
          params: {
            tenant_id: subscriptionFilters.tenant || undefined,
            plan_id: subscriptionFilters.plan || undefined,
            status: subscriptionFilters.status || undefined,
          },
        }),
        publicClient.get("/platform/subscription-payments/", {
          params: {
            tenant_id: paymentFilters.tenant || undefined,
            status: paymentFilters.status || undefined,
            method: paymentFilters.method || undefined,
          },
        }),
      ]);

      if (invoiceResult.status === "fulfilled") {
        setInvoices(normalizePaginated(invoiceResult.value.data).items);
      } else {
        setError(getErrorMessage(invoiceResult.reason, "Unable to load billing invoices."));
      }

      if (subscriptionResult.status === "fulfilled") {
        setSubscriptions(normalizePaginated(subscriptionResult.value.data).items);
      } else {
        setError((current) => current ?? getErrorMessage(subscriptionResult.reason, "Unable to load subscriptions."));
      }

      if (paymentResult.status === "fulfilled") {
        setPayments(normalizePaginated(paymentResult.value.data).items);
      } else {
        setError((current) => current ?? getErrorMessage(paymentResult.reason, "Unable to load tenant payments."));
      }
    } finally {
      setLoadingRecords(false);
    }
  }, [invoiceFilters.tenant, invoiceFilters.status, paymentFilters.method, paymentFilters.status, paymentFilters.tenant, subscriptionFilters.plan, subscriptionFilters.status, subscriptionFilters.tenant]);

  React.useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  React.useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  const activeCurrentSubscriptions = subscriptions.filter((row) => row.is_current);
  const overdueInvoices = invoices.filter((row) => String(row.status || "").toUpperCase() === "OVERDUE");
  const pendingPayments = payments.filter((row) => String(row.status || "").toUpperCase() === "PENDING");
  const failedPayments = payments.filter((row) => String(row.status || "").toUpperCase() === "FAILED");
  const paidPayments = payments.filter((row) => String(row.status || "").toUpperCase() === "PAID");
  const invoiceTotals = invoices.reduce(
    (accumulator, row) => {
      accumulator.total += Number(row.total_amount || 0);
      if (String(row.status || "").toUpperCase() === "PAID") {
        accumulator.paidCount += 1;
      }
      return accumulator;
    },
    { total: 0, paidCount: 0 },
  );
  const paymentTotals = payments.reduce(
    (accumulator, row) => {
      const amount = Number(row.amount || 0);
      const status = String(row.status || "").toUpperCase();
      accumulator.total += amount;
      if (status === "PAID") {
        accumulator.settled += amount;
      } else if (status === "PENDING") {
        accumulator.pending += amount;
      } else if (status === "FAILED") {
        accumulator.failed += amount;
      }
      return accumulator;
    },
    { total: 0, settled: 0, pending: 0, failed: 0 },
  );
  const billingIntegrations = React.useMemo(
    () =>
      integrations
        .filter((item) => ["mpesa", "stripe"].includes(String(item.code || "").toLowerCase()))
        .sort((left, right) => String(left.name || "").localeCompare(String(right.name || ""))),
    [integrations],
  );
  const tenantAlerts = React.useMemo(() => {
    const paymentMap = new Map();
    payments.forEach((row) => {
      const items = paymentMap.get(row.tenant_name) ?? [];
      items.push(row);
      paymentMap.set(row.tenant_name, items);
    });

    return activeCurrentSubscriptions
      .map((subscription) => {
        const tenantName = subscription.tenant_name;
        const tenantInvoices = invoices.filter((row) => row.tenant_name === tenantName);
        const tenantPayments = paymentMap.get(tenantName) ?? [];
        const tenantOverdueCount = tenantInvoices.filter((row) => String(row.status || "").toUpperCase() === "OVERDUE").length;
        const tenantPendingPayments = tenantPayments.filter((row) => String(row.status || "").toUpperCase() === "PENDING").length;
        const reasons = [];

        if (tenantOverdueCount > 0) {
          reasons.push(`${tenantOverdueCount} overdue invoice(s)`);
        }
        if (tenantPendingPayments > 0) {
          reasons.push(`${tenantPendingPayments} payment(s) awaiting review`);
        }
        if (String(subscription.status || "").toUpperCase() === "SUSPENDED") {
          reasons.push("subscription currently suspended");
        }
        if (reasons.length === 0 && subscription.next_billing_date) {
          reasons.push(`next billing ${formatDate(subscription.next_billing_date)}`);
        }

        return {
          id: subscription.id,
          tenantName,
          planName: subscription.plan_detail?.name ?? subscription.plan,
          status: subscription.status,
          reasons,
        };
      })
      .filter((item) => item.reasons.length > 0)
      .sort((left, right) => right.reasons.length - left.reasons.length)
      .slice(0, 6);
  }, [activeCurrentSubscriptions, invoices, payments]);

  const selectedPlan = plans.find((row) => String(row.id) === String(subscriptionForm.plan)) ?? null;
  const recordPaymentGuidance = React.useMemo(() => {
    const method = String(recordPaymentForm.method || "").trim().toLowerCase();
    if (method.includes("stripe")) {
      return "Use Pending when the checkout proof is captured but Stripe settlement still needs webhook or operator confirmation. Use Paid only after the hosted payment is already settled.";
    }
    if (method.includes("bank")) {
      return "Record the bank or deposit reference exactly as issued by the bank so operators can match tenant proof to the invoice without ambiguity.";
    }
    return "Use Pending when the tenant has submitted proof but the payment still needs platform approval. Use Paid only when settlement is already confirmed and access should reactivate immediately.";
  }, [recordPaymentForm.method]);

  const resetPlanEditor = () => {
    setPlanEditor(null);
    setPlanForm(emptyPlanForm);
    setPlanFormError(null);
  };

  const openPlanEditor = (mode, plan) => {
    if (mode === "edit" && plan) {
      setPlanForm({
        code: plan.code,
        name: plan.name,
        description: plan.description ?? "",
        monthly_price: plan.monthly_price,
        annual_price: plan.annual_price,
        max_students: String(plan.max_students),
        max_storage_gb: String(plan.max_storage_gb),
        is_active: !!plan.is_active,
      });
      setPlanEditor({ mode, id: plan.id });
      setPlanFormError(null);
      return;
    }

    setPlanEditor({ mode: "create", id: null });
    setPlanForm(emptyPlanForm);
    setPlanFormError(null);
  };

  const savePlan = async (event) => {
    event.preventDefault();
    setSavingPlan(true);
    setPlanFormError(null);

    const payload = {
      code: planForm.code.toUpperCase(),
      name: planForm.name,
      description: planForm.description,
      monthly_price: planForm.monthly_price,
      annual_price: planForm.annual_price,
      max_students: Number(planForm.max_students),
      max_storage_gb: Number(planForm.max_storage_gb),
      is_active: planForm.is_active,
    };

    try {
      if (planEditor?.mode === "edit" && planEditor.id) {
        await publicClient.patch(`/platform/plans/${planEditor.id}/`, payload);
        setFlash({ tone: "success", message: "Billing plan updated successfully." });
      } else {
        await publicClient.post("/platform/plans/", payload);
        setFlash({ tone: "success", message: "Billing plan created successfully." });
      }
      resetPlanEditor();
      await loadCatalog();
    } catch (requestError) {
      setPlanFormError(getErrorMessage(requestError, "Unable to save platform billing plan."));
    } finally {
      setSavingPlan(false);
    }
  };

  const deletePlan = async (planId) => {
    setDeletingPlanId(planId);
    try {
      await publicClient.delete(`/platform/plans/${planId}/`);
      setFlash({ tone: "success", message: "Plan deleted." });
      await loadCatalog();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to delete platform plan."));
    } finally {
      setDeletingPlanId(null);
    }
  };

  const seedPlans = async () => {
    setLoadingCatalog(true);
    setError(null);
    try {
      for (const plan of defaultPlans) {
        await publicClient.post("/platform/plans/", { ...plan, is_active: true });
      }
      setFlash({ tone: "success", message: "Default billing plans seeded successfully." });
      await loadCatalog();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to seed default billing plans."));
      setLoadingCatalog(false);
    }
  };

  const savePaybill = async () => {
    const nextPaybill = paybill.trim();
    if (!nextPaybill) {
      setError("Enter a valid M-Pesa paybill number.");
      return;
    }

    setSavingPaybill(true);
    setError(null);
    try {
      if (paybillSetting?.id) {
        await publicClient.patch(`/platform/settings/${paybillSetting.id}/`, { value: { number: nextPaybill } });
      } else {
        const response = await publicClient.post("/platform/settings/", {
          key: "MPESA_PAYBILL",
          value: { number: nextPaybill },
          description: "M-Pesa Paybill number displayed on billing page and invoices.",
        });
        setPaybillSetting(response.data);
      }
      setFlash({ tone: "success", message: `Paybill number saved as ${nextPaybill}.` });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to save M-Pesa paybill."));
    } finally {
      setSavingPaybill(false);
    }
  };

  const createSubscription = async (event) => {
    event.preventDefault();
    if (!subscriptionForm.tenant || !subscriptionForm.plan) {
      setError("Select both a tenant and a billing plan.");
      return;
    }

    setCreatingSubscription(true);
    setError(null);
    try {
      await publicClient.post("/platform/subscriptions/", {
        tenant: Number(subscriptionForm.tenant),
        plan: Number(subscriptionForm.plan),
        billing_cycle: subscriptionForm.billing_cycle,
      });
      setSubscriptionForm(emptySubscriptionForm);
      setFlash({ tone: "success", message: "Subscription created successfully." });
      await loadRecords();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to create tenant subscription."));
    } finally {
      setCreatingSubscription(false);
    }
  };

  const openRecordPayment = (invoice) => {
    setRecordPaymentTarget(invoice);
    setRecordPaymentForm({
      amount: String(invoice.total_amount || ""),
      transaction_id: invoice.invoice_number || "",
      status: "PENDING",
      method: "M-Pesa",
      external_reference: invoice.external_reference || "",
    });
    setRecordPaymentError(null);
  };

  const closeRecordPayment = () => {
    if (recordingPayment) return;
    setRecordPaymentTarget(null);
    setRecordPaymentForm(emptyRecordPaymentForm);
    setRecordPaymentError(null);
  };

  const submitRecordPayment = async (event) => {
    event.preventDefault();
    if (!recordPaymentTarget) return;
    const numericAmount = Number(recordPaymentForm.amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setRecordPaymentError("Enter a valid payment amount.");
      return;
    }
    if (!recordPaymentForm.transaction_id.trim()) {
      setRecordPaymentError("Transaction code is required.");
      return;
    }

    setRecordingPayment(true);
    setRecordPaymentError(null);
    try {
      await publicClient.post("/platform/subscription-payments/", {
        invoice: recordPaymentTarget.id,
        amount: numericAmount,
        method: recordPaymentForm.method.trim() || "M-Pesa",
        status: recordPaymentForm.status === "PAID" ? "PAID" : "PENDING",
        transaction_id: recordPaymentForm.transaction_id.trim(),
        external_reference: recordPaymentForm.external_reference.trim(),
        metadata: {
          source: "platform_billing_workspace",
          recorded_via: "platform_admin_ui",
        },
      });
      setFlash({ tone: "success", message: `Payment captured for invoice ${recordPaymentTarget.invoice_number}.` });
      closeRecordPayment();
      await loadRecords();
    } catch (requestError) {
      setRecordPaymentError(getErrorMessage(requestError, "Unable to record tenant payment."));
    } finally {
      setRecordingPayment(false);
    }
  };

  const openReviewModal = (mode, payment) => {
    setReviewModal({ mode, payment });
    setReviewForm(emptyReviewForm);
    setReviewError(null);
  };

  const closeReviewModal = () => {
    if (reviewingPayment) return;
    setReviewModal(null);
    setReviewForm(emptyReviewForm);
    setReviewError(null);
  };

  const submitReview = async (event) => {
    event.preventDefault();
    if (!reviewModal?.payment) return;
    const { mode, payment } = reviewModal;

    setReviewingPayment(true);
    setReviewError(null);
    try {
      if (mode === "approve") {
        await publicClient.post(`/platform/subscription-payments/${payment.id}/approve/`, {});
        setFlash({ tone: "success", message: `Payment approved for ${payment.invoice_number}.` });
      } else if (mode === "reject") {
        await publicClient.post(`/platform/subscription-payments/${payment.id}/reject/`, {
          reason: reviewForm.reason.trim(),
        });
        setFlash({ tone: "success", message: `Payment rejected for ${payment.invoice_number}.` });
      } else {
        await publicClient.post(`/platform/subscription-payments/${payment.id}/retry-verification/`, {
          reason: reviewForm.reason.trim(),
        });
        setFlash({ tone: "success", message: `Verification retried for ${payment.invoice_number}.` });
      }
      closeReviewModal();
      await loadRecords();
    } catch (requestError) {
      setReviewError(getErrorMessage(requestError, `Unable to ${mode} tenant payment.`));
    } finally {
      setReviewingPayment(false);
    }
  };

  return jsxs("div", {
    className: "grid grid-cols-12 gap-6",
    children: [
      jsx(PageHero, {
        badge: "PLATFORM",
        badgeColor: "emerald",
        title: "Subscription & Billing",
        subtitle: "Operate plans, invoices, subscription access, and tenant-payment review from one platform workspace.",
        icon: "KES",
      }),
      jsx(Flash, { tone: flash?.tone, message: flash?.message }),
      jsx(Flash, { tone: "error", message: typeof error === "string" ? error : null }),
      jsx("section", {
        className: "col-span-12 grid gap-3 lg:grid-cols-5",
        children: [
          {
            label: "Current subscriptions",
            value: String(activeCurrentSubscriptions.length),
            detail: "Tenant subscriptions currently in force",
            tone: "text-emerald-200",
          },
          {
            label: "Overdue invoices",
            value: String(overdueInvoices.length),
            detail: "Need collection or suspension follow-up",
            tone: overdueInvoices.length > 0 ? "text-amber-200" : "text-emerald-200",
          },
          {
            label: "Pending payments",
            value: String(pendingPayments.length),
            detail: "Awaiting platform review or callback confirmation",
            tone: pendingPayments.length > 0 ? "text-amber-200" : "text-emerald-200",
          },
          {
            label: "Settled payments",
            value: String(paidPayments.length),
            detail: `${formatMoney(paymentTotals.settled)} total settled`,
            tone: "text-sky-200",
          },
          {
            label: "Platform paybill",
            value: paybill || "--",
            detail: "Displayed on invoices and used for tenant collections",
            tone: "text-white",
          },
        ].map((item) =>
          jsx(
            StatCard,
            {
              label: item.label,
              value: item.value,
              detail: item.detail,
              tone: item.tone,
            },
            item.label,
          ),
        ),
      }),
      jsx("section", {
        className: "col-span-12 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]",
        children: [
          jsxs("div", {
            className: "rounded-2xl p-5",
            style: panelStyle,
            children: [
              jsx("p", {
                className: "text-[11px] uppercase tracking-wide text-slate-500",
                children: "Billing posture",
              }),
              jsx("h2", {
                className: "mt-2 text-lg font-semibold text-white",
                children: "Tenants needing billing attention",
              }),
              jsx("div", {
                className: "mt-4 space-y-3",
                children:
                  tenantAlerts.length > 0
                    ? tenantAlerts.map((item) =>
                        jsxs(
                          "div",
                          {
                            className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4",
                            children: [
                              jsxs("div", {
                                className: "flex flex-wrap items-center justify-between gap-2",
                                children: [
                                  jsxs("div", {
                                    children: [
                                      jsx("p", { className: "text-sm font-semibold text-white", children: item.tenantName }),
                                      jsx("p", { className: "text-xs text-slate-500", children: item.planName }),
                                    ],
                                  }),
                                  jsx("span", {
                                    className: `inline-flex rounded-full border px-2 py-0.5 text-[11px] ${subscriptionTone(item.status)}`,
                                    children: item.status,
                                  }),
                                ],
                              }),
                              jsx("ul", {
                                className: "mt-3 space-y-1 text-xs text-slate-300",
                                children: item.reasons.map((reason) =>
                                  jsx("li", { children: `- ${reason}` }, reason),
                                ),
                              }),
                            ],
                          },
                          item.id,
                        ),
                      )
                    : jsx("p", {
                        className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4 text-sm text-slate-400",
                        children: "No urgent tenant billing issues in the current subscription set.",
                      }),
              }),
            ],
          }),
          jsxs("div", {
            className: "rounded-2xl p-5",
            style: panelStyle,
            children: [
              jsx("p", {
                className: "text-[11px] uppercase tracking-wide text-slate-500",
                children: "Collection settings",
              }),
              jsx("h2", {
                className: "mt-2 text-lg font-semibold text-white",
                children: "M-Pesa paybill and operator guidance",
              }),
              jsxs("div", {
                className: "mt-4 space-y-3",
                children: [
                  jsxs("label", {
                    className: "block text-sm",
                    children: [
                      jsx("span", { className: "mb-1 block text-xs text-slate-400", children: "Paybill number" }),
                      jsx("input", {
                        className: fieldClass,
                        value: paybill,
                        onChange: (event) => setPaybill(event.target.value),
                        placeholder: "e.g. 522522",
                        maxLength: 10,
                      }),
                    ],
                  }),
                  jsx("p", {
                    className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 px-4 py-3 text-xs text-slate-400",
                    children:
                      "Keep this aligned with the callback-ready paybill in production. Tenant invoices, payment instructions, and operator review all depend on this single platform setting.",
                  }),
                  jsx("button", {
                    type: "button",
                    onClick: savePaybill,
                    disabled: savingPaybill,
                    className:
                      "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-emerald-400 disabled:opacity-70",
                    children: savingPaybill ? "Saving..." : "Save paybill",
                  }),
                  jsxs("div", {
                    className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4",
                    children: [
                      jsx("p", {
                        className: "text-[11px] uppercase tracking-wide text-slate-500",
                        children: "Gateway readiness",
                      }),
                      jsx("div", {
                        className: "mt-3 grid gap-3 sm:grid-cols-2",
                        children:
                          billingIntegrations.length > 0
                            ? billingIntegrations.map((integration) =>
                                jsxs(
                                  "div",
                                  {
                                    className: "rounded-2xl border border-white/[0.07] bg-black/20 p-3",
                                    children: [
                                      jsxs("div", {
                                        className: "flex items-center justify-between gap-2",
                                        children: [
                                          jsx("p", { className: "text-sm font-semibold text-white", children: integration.name }),
                                          jsx("span", {
                                            className: `inline-flex rounded-full border px-2 py-0.5 text-[11px] ${integrationTone(integration.status)}`,
                                            children: String(integration.status || "unknown").toUpperCase(),
                                          }),
                                        ],
                                      }),
                                      jsx("p", {
                                        className: "mt-2 text-xs text-slate-400",
                                        children: integration.description || "No integration notes available.",
                                      }),
                                      jsx("p", {
                                        className: "mt-2 text-[11px] text-slate-500",
                                        children: integration.updated_at ? `Last updated ${formatDateTime(integration.updated_at)}` : "No platform setting recorded yet.",
                                      }),
                                    ],
                                  },
                                  integration.code,
                                ),
                              )
                            : jsx("p", {
                                className: "text-sm text-slate-400",
                                children: "Gateway status will appear here after platform integrations are configured.",
                              }),
                      }),
                    ],
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
      jsxs("section", {
        className: "col-span-12 rounded-2xl p-6",
        style: panelStyle,
        children: [
          jsxs("div", {
            className: "flex flex-wrap items-start justify-between gap-3",
            children: [
              jsxs("div", {
                children: [
                  jsx("h2", { className: "text-lg font-semibold text-white", children: "Subscription plans" }),
                  jsx("p", {
                    className: "mt-1 text-sm text-slate-400",
                    children: "Edit commercial plans, student caps, storage limits, and operator-facing pricing reference.",
                  }),
                ],
              }),
              jsxs("div", {
                className: "flex flex-wrap gap-2",
                children: [
                  jsx("button", {
                    type: "button",
                    onClick: loadCatalog,
                    disabled: loadingCatalog,
                    className: "rounded-xl border border-white/[0.09] px-4 py-2 text-sm text-slate-200 transition hover:bg-white/[0.04]",
                    children: loadingCatalog ? "Loading..." : "Reload",
                  }),
                  jsx("button", {
                    type: "button",
                    onClick: seedPlans,
                    className: "rounded-xl border border-white/[0.09] px-4 py-2 text-sm text-slate-200 transition hover:bg-white/[0.04]",
                    children: "Seed defaults",
                  }),
                  jsx("button", {
                    type: "button",
                    onClick: () => openPlanEditor("create"),
                    className: "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-emerald-400",
                    children: "Add plan",
                  }),
                ],
              }),
            ],
          }),
          jsx("div", {
            className: "mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4",
            children:
              loadingCatalog
                ? Array.from({ length: 4 }).map((_, index) =>
                    jsx("div", {
                      className: "h-48 animate-pulse rounded-2xl border border-white/[0.05] bg-slate-950/60",
                    }, index),
                  )
                : plans.map((plan) => {
                    const reference = pricingReference[plan.code] ?? { rate: 300, sms: 100, accent: "border-white/[0.07] bg-slate-950/60" };
                    return jsxs(
                      "article",
                      {
                        className: `rounded-2xl border p-4 ${reference.accent}`,
                        children: [
                          jsxs("div", {
                            className: "flex items-start justify-between gap-3",
                            children: [
                              jsxs("div", {
                                children: [
                                  jsx("p", { className: "text-[10px] uppercase tracking-[0.28em] text-slate-500", children: plan.code }),
                                  jsx("h3", { className: "mt-2 text-lg font-semibold text-white", children: plan.name }),
                                ],
                              }),
                              jsx("span", {
                                className: "rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-200",
                                children: plan.is_active ? "ACTIVE" : "INACTIVE",
                              }),
                            ],
                          }),
                          jsx("p", {
                            className: "mt-3 text-sm text-slate-400",
                            children: plan.description || "No description provided.",
                          }),
                          jsxs("div", {
                            className: "mt-4 grid gap-2 text-xs text-slate-300",
                            children: [
                              jsxs("div", { className: "flex justify-between", children: [jsx("span", { children: "Annual" }), jsx("span", { className: "text-emerald-300", children: formatMoney(plan.annual_price) })] }),
                              jsxs("div", { className: "flex justify-between", children: [jsx("span", { children: "Monthly" }), jsx("span", { children: formatMoney(plan.monthly_price) })] }),
                              jsxs("div", { className: "flex justify-between", children: [jsx("span", { children: "Students" }), jsx("span", { children: plan.max_students >= 9999 ? "500+" : plan.max_students })] }),
                              jsxs("div", { className: "flex justify-between", children: [jsx("span", { children: "Storage" }), jsx("span", { children: `${plan.max_storage_gb} GB` })] }),
                              jsxs("div", { className: "flex justify-between", children: [jsx("span", { children: "Rate" }), jsx("span", { children: `KES ${reference.rate}/student/yr` })] }),
                              jsxs("div", { className: "flex justify-between", children: [jsx("span", { children: "Free SMS" }), jsx("span", { children: reference.sms.toLocaleString() })] }),
                            ],
                          }),
                          jsxs("div", {
                            className: "mt-4 flex gap-2",
                            children: [
                              jsx("button", {
                                type: "button",
                                onClick: () => openPlanEditor("edit", plan),
                                className: "flex-1 rounded-xl border border-white/[0.09] px-3 py-2 text-xs text-slate-200 transition hover:bg-white/[0.04]",
                                children: "Edit",
                              }),
                              jsx("button", {
                                type: "button",
                                onClick: () => deletePlan(plan.id),
                                disabled: deletingPlanId === plan.id,
                                className: "rounded-xl border border-rose-500/30 px-3 py-2 text-xs text-rose-300 transition hover:bg-rose-500/10 disabled:opacity-60",
                                children: deletingPlanId === plan.id ? "Deleting..." : "Delete",
                              }),
                            ],
                          }),
                        ],
                      },
                      plan.id,
                    );
                  }),
          }),
        ],
      }),
      jsxs("section", {
        className: "col-span-12 grid gap-4 xl:grid-cols-[0.95fr,1.05fr]",
        children: [
          jsxs("div", {
            className: "rounded-2xl p-6",
            style: panelStyle,
            children: [
              jsx("h2", { className: "text-lg font-semibold text-white", children: "Assign subscription" }),
              jsx("p", {
                className: "mt-1 text-sm text-slate-400",
                children: "Activate or change a tenant plan without leaving the billing workspace.",
              }),
              jsxs("form", {
                className: "mt-4 grid gap-3",
                onSubmit: createSubscription,
                children: [
                  jsxs("label", {
                    className: "block text-sm",
                    children: [
                      jsx("span", { className: "mb-1 block text-xs text-slate-400", children: "Tenant" }),
                      jsxs("select", {
                        className: fieldClass,
                        value: subscriptionForm.tenant,
                        onChange: (event) => setSubscriptionForm((current) => ({ ...current, tenant: event.target.value })),
                        required: true,
                        children: [
                          jsx("option", { value: "", children: "Select tenant" }),
                          tenants.map((tenant) =>
                            jsx("option", { value: tenant.id, children: tenant.name }, tenant.id),
                          ),
                        ],
                      }),
                    ],
                  }),
                  jsxs("label", {
                    className: "block text-sm",
                    children: [
                      jsx("span", { className: "mb-1 block text-xs text-slate-400", children: "Plan" }),
                      jsxs("select", {
                        className: fieldClass,
                        value: subscriptionForm.plan,
                        onChange: (event) => setSubscriptionForm((current) => ({ ...current, plan: event.target.value })),
                        required: true,
                        children: [
                          jsx("option", { value: "", children: "Select plan" }),
                          plans.map((plan) =>
                            jsx(
                              "option",
                              {
                                value: plan.id,
                                children: `${plan.name} - ${formatMoney(plan.annual_price)}/yr`,
                              },
                              plan.id,
                            ),
                          ),
                        ],
                      }),
                    ],
                  }),
                  jsxs("label", {
                    className: "block text-sm",
                    children: [
                      jsx("span", { className: "mb-1 block text-xs text-slate-400", children: "Billing cycle" }),
                      jsxs("select", {
                        className: fieldClass,
                        value: subscriptionForm.billing_cycle,
                        onChange: (event) => setSubscriptionForm((current) => ({ ...current, billing_cycle: event.target.value })),
                        children: [
                          jsx("option", { value: "ANNUAL", children: "Annual (recommended)" }),
                          jsx("option", { value: "MONTHLY", children: "Monthly" }),
                        ],
                      }),
                    ],
                  }),
                  selectedPlan
                    ? jsx("div", {
                        className: "rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-xs text-slate-300",
                        children: jsxs("div", {
                          className: "grid gap-2 sm:grid-cols-2",
                          children: [
                            jsxs("div", { children: [jsx("p", { className: "text-slate-500", children: "Annual fee" }), jsx("p", { className: "mt-1 font-semibold text-emerald-300", children: formatMoney(selectedPlan.annual_price) })] }),
                            jsxs("div", { children: [jsx("p", { className: "text-slate-500", children: "Monthly fee" }), jsx("p", { className: "mt-1 font-semibold text-white", children: formatMoney(selectedPlan.monthly_price) })] }),
                            jsxs("div", { children: [jsx("p", { className: "text-slate-500", children: "Student cap" }), jsx("p", { className: "mt-1 font-semibold text-white", children: selectedPlan.max_students >= 9999 ? "500+" : selectedPlan.max_students })] }),
                            jsxs("div", { children: [jsx("p", { className: "text-slate-500", children: "Storage" }), jsx("p", { className: "mt-1 font-semibold text-white", children: `${selectedPlan.max_storage_gb} GB` })] }),
                          ],
                        }),
                      })
                    : null,
                  jsx("button", {
                    type: "submit",
                    disabled: creatingSubscription,
                    className:
                      "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-emerald-400 disabled:opacity-70",
                    children: creatingSubscription ? "Creating..." : "Create subscription",
                  }),
                ],
              }),
            ],
          }),
          jsxs("div", {
            className: "rounded-2xl p-6",
            style: panelStyle,
            children: [
              jsxs("div", {
                className: "flex flex-wrap items-center gap-2",
                children: [
                  jsx("h2", { className: "text-lg font-semibold text-white", children: "Active subscriptions" }),
                  jsx("span", { className: "rounded-full border border-white/[0.08] px-2 py-0.5 text-[11px] text-slate-400", children: `${subscriptions.length} rows` }),
                ],
              }),
              jsx("div", {
                className: "mt-4 grid gap-2 sm:grid-cols-3",
                children: [
                  {
                    value: subscriptionFilters.tenant,
                    onChange: (event) => setSubscriptionFilters((current) => ({ ...current, tenant: event.target.value })),
                    options: [jsx("option", { value: "", children: "All tenants" }, "all"), ...tenants.map((tenant) => jsx("option", { value: tenant.id, children: tenant.name }, tenant.id))],
                  },
                  {
                    value: subscriptionFilters.plan,
                    onChange: (event) => setSubscriptionFilters((current) => ({ ...current, plan: event.target.value })),
                    options: [jsx("option", { value: "", children: "All plans" }, "all"), ...plans.map((plan) => jsx("option", { value: plan.id, children: plan.name }, plan.id))],
                  },
                  {
                    value: subscriptionFilters.status,
                    onChange: (event) => setSubscriptionFilters((current) => ({ ...current, status: event.target.value })),
                    options: [
                      jsx("option", { value: "", children: "All statuses" }, "all"),
                      ...["TRIAL", "ACTIVE", "SUSPENDED", "CANCELLED"].map((status) =>
                        jsx("option", { value: status, children: status }, status),
                      ),
                    ],
                  },
                ].map((config, index) =>
                  jsx(
                    "select",
                    {
                      className: fieldClass,
                      value: config.value,
                      onChange: config.onChange,
                      children: config.options,
                    },
                    index,
                  ),
                ),
              }),
              jsx("div", {
                className: "mt-4 overflow-x-auto rounded-2xl border border-white/[0.07]",
                children: jsxs("table", {
                  className: "min-w-[920px] w-full text-left text-sm",
                  children: [
                    jsx("thead", {
                      className: "bg-white/[0.03] text-xs uppercase tracking-wide text-slate-400",
                      children: jsxs("tr", {
                        children: [
                          jsx("th", { className: "px-3 py-2", children: "Tenant" }),
                          jsx("th", { className: "px-3 py-2", children: "Plan" }),
                          jsx("th", { className: "px-3 py-2", children: "Cycle" }),
                          jsx("th", { className: "px-3 py-2", children: "Status" }),
                          jsx("th", { className: "px-3 py-2", children: "Starts" }),
                          jsx("th", { className: "px-3 py-2", children: "Next Billing" }),
                          jsx("th", { className: "px-3 py-2", children: "Ends" }),
                        ],
                      }),
                    }),
                    jsx("tbody", {
                      className: "divide-y divide-slate-800",
                      children:
                        loadingRecords
                          ? jsx("tr", {
                              children: jsx("td", {
                                className: "px-3 py-4 text-slate-400",
                                colSpan: 7,
                                children: "Loading subscriptions...",
                              }),
                            })
                          : subscriptions.length > 0
                            ? subscriptions.map((row) =>
                                jsxs(
                                  "tr",
                                  {
                                    className: "bg-slate-950/50",
                                    children: [
                                      jsx("td", { className: "px-3 py-2 font-medium text-white", children: row.tenant_name }),
                                      jsx("td", { className: "px-3 py-2", children: row.plan_detail?.name ?? row.plan }),
                                      jsx("td", { className: "px-3 py-2", children: row.billing_cycle }),
                                      jsx("td", {
                                        className: "px-3 py-2",
                                        children: jsx("span", {
                                          className: `inline-flex rounded-full border px-2 py-0.5 text-[11px] ${subscriptionTone(row.status)}`,
                                          children: row.status,
                                        }),
                                      }),
                                      jsx("td", { className: "px-3 py-2 text-slate-400", children: formatDate(row.starts_on) }),
                                      jsx("td", { className: "px-3 py-2 text-slate-400", children: formatDate(row.next_billing_date) }),
                                      jsx("td", { className: "px-3 py-2 text-slate-400", children: formatDate(row.ends_on) }),
                                    ],
                                  },
                                  row.id,
                                ),
                              )
                            : jsx("tr", {
                                children: jsx("td", {
                                  className: "px-3 py-4 text-slate-400",
                                  colSpan: 7,
                                  children: "No subscriptions match the current filters.",
                                }),
                              }),
                    }),
                  ],
                }),
              }),
            ],
          }),
        ],
      }),
      jsxs("section", {
        className: "col-span-12 rounded-2xl p-6",
        style: panelStyle,
        children: [
          jsxs("div", {
            className: "flex flex-wrap items-start justify-between gap-3",
            children: [
              jsxs("div", {
                children: [
                  jsx("h2", { className: "text-lg font-semibold text-white", children: "Invoice management" }),
                  jsx("p", {
                    className: "mt-1 text-sm text-slate-400",
                    children: `Invoices: ${invoices.length} | Paid: ${invoiceTotals.paidCount} | Total billed: ${formatMoney(invoiceTotals.total)}`,
                  }),
                ],
              }),
              jsx("button", {
                type: "button",
                onClick: loadRecords,
                className: "rounded-xl border border-white/[0.09] px-4 py-2 text-sm text-slate-200 transition hover:bg-white/[0.04]",
                children: "Refresh",
              }),
            ],
          }),
          jsx("div", {
            className: "mt-4 grid gap-2 sm:grid-cols-2",
            children: [
              {
                value: invoiceFilters.tenant,
                onChange: (event) => setInvoiceFilters((current) => ({ ...current, tenant: event.target.value })),
                options: [jsx("option", { value: "", children: "All tenants" }, "all"), ...tenants.map((tenant) => jsx("option", { value: tenant.id, children: tenant.name }, tenant.id))],
              },
              {
                value: invoiceFilters.status,
                onChange: (event) => setInvoiceFilters((current) => ({ ...current, status: event.target.value })),
                options: [
                  jsx("option", { value: "", children: "All invoice statuses" }, "all"),
                  ...["PENDING", "PAID", "OVERDUE", "CANCELLED"].map((status) =>
                    jsx("option", { value: status, children: status }, status),
                  ),
                ],
              },
            ].map((config, index) =>
              jsx(
                "select",
                {
                  className: fieldClass,
                  value: config.value,
                  onChange: config.onChange,
                  children: config.options,
                },
                index,
              ),
            ),
          }),
          jsx("div", {
            className: "mt-4 overflow-x-auto rounded-2xl border border-white/[0.07]",
            children: jsxs("table", {
              className: "min-w-[1080px] w-full text-left text-sm",
              children: [
                jsx("thead", {
                  className: "bg-white/[0.03] text-xs uppercase tracking-wide text-slate-400",
                  children: jsxs("tr", {
                    children: [
                      jsx("th", { className: "px-3 py-2", children: "Invoice" }),
                      jsx("th", { className: "px-3 py-2", children: "Tenant" }),
                      jsx("th", { className: "px-3 py-2", children: "Cycle" }),
                      jsx("th", { className: "px-3 py-2", children: "Status" }),
                      jsx("th", { className: "px-3 py-2", children: "Period" }),
                      jsx("th", { className: "px-3 py-2", children: "Amount" }),
                      jsx("th", { className: "px-3 py-2", children: "Due Date" }),
                      jsx("th", { className: "px-3 py-2", children: "Actions" }),
                    ],
                  }),
                }),
                jsx("tbody", {
                  className: "divide-y divide-slate-800",
                  children:
                    loadingRecords
                      ? jsx("tr", {
                          children: jsx("td", {
                            className: "px-3 py-4 text-slate-400",
                            colSpan: 8,
                            children: "Loading invoices...",
                          }),
                        })
                      : invoices.length > 0
                        ? invoices.map((row) =>
                            jsxs(
                              "tr",
                              {
                                className: "bg-slate-950/50",
                                children: [
                                  jsx("td", { className: "px-3 py-2 font-medium text-white", children: row.invoice_number }),
                                  jsx("td", { className: "px-3 py-2", children: row.tenant_name }),
                                  jsx("td", { className: "px-3 py-2", children: row.billing_cycle }),
                                  jsx("td", {
                                    className: "px-3 py-2",
                                    children: jsx("span", {
                                      className: `inline-flex rounded-full border px-2 py-0.5 text-[11px] ${invoiceTone(row.status)}`,
                                      children: row.status,
                                    }),
                                  }),
                                  jsx("td", {
                                    className: "px-3 py-2 text-xs text-slate-400",
                                    children: `${formatDate(row.period_start)} - ${formatDate(row.period_end)}`,
                                  }),
                                  jsx("td", { className: "px-3 py-2", children: formatMoney(row.total_amount) }),
                                  jsx("td", { className: "px-3 py-2 text-slate-400", children: formatDate(row.due_date) }),
                                  jsx("td", {
                                    className: "px-3 py-2",
                                    children: jsx("button", {
                                      type: "button",
                                      onClick: () => openRecordPayment(row),
                                      disabled: String(row.status || "").toUpperCase() === "PAID",
                                      className:
                                        "rounded-xl border border-white/[0.09] px-3 py-1 text-xs text-slate-200 transition hover:bg-white/[0.04] disabled:opacity-50",
                                      children: "Record payment",
                                    }),
                                  }),
                                ],
                              },
                              row.id,
                            ),
                          )
                        : jsx("tr", {
                            children: jsx("td", {
                              className: "px-3 py-4 text-slate-400",
                              colSpan: 8,
                              children: "No invoices match the current filters.",
                            }),
                          }),
                }),
              ],
            }),
          }),
        ],
      }),
      jsxs("section", {
        className: "col-span-12 rounded-2xl p-6",
        style: panelStyle,
        children: [
          jsxs("div", {
            className: "flex flex-wrap items-start justify-between gap-3",
            children: [
              jsxs("div", {
                children: [
                  jsx("h2", { className: "text-lg font-semibold text-white", children: "Tenant payments" }),
                  jsx("p", {
                    className: "mt-1 text-sm text-slate-400",
                    children: `Payments: ${payments.length} | Pending: ${pendingPayments.length} | Failed: ${failedPayments.length} | Settled: ${formatMoney(paymentTotals.settled)}`,
                  }),
                ],
              }),
              jsx("button", {
                type: "button",
                onClick: loadRecords,
                className: "rounded-xl border border-white/[0.09] px-4 py-2 text-sm text-slate-200 transition hover:bg-white/[0.04]",
                children: "Refresh",
              }),
            ],
          }),
          jsx("div", {
            className: "mt-4 grid gap-2 md:grid-cols-3",
            children: [
              {
                value: paymentFilters.tenant,
                onChange: (event) => setPaymentFilters((current) => ({ ...current, tenant: event.target.value })),
                options: [jsx("option", { value: "", children: "All tenants" }, "all"), ...tenants.map((tenant) => jsx("option", { value: tenant.id, children: tenant.name }, tenant.id))],
              },
              {
                value: paymentFilters.status,
                onChange: (event) => setPaymentFilters((current) => ({ ...current, status: event.target.value })),
                options: [
                  jsx("option", { value: "", children: "All payment statuses" }, "all"),
                  ...["PENDING", "PAID", "FAILED"].map((status) => jsx("option", { value: status, children: status }, status)),
                ],
              },
              {
                value: paymentFilters.method,
                onChange: (event) => setPaymentFilters((current) => ({ ...current, method: event.target.value })),
                options: [
                  jsx("option", { value: "", children: "All methods" }, "all"),
                  ...["M-Pesa", "Bank Transfer", "Stripe Checkout", "Card", "Manual"].map((method) => jsx("option", { value: method, children: method }, method)),
                ],
              },
            ].map((config, index) =>
              jsx(
                "select",
                {
                  className: fieldClass,
                  value: config.value,
                  onChange: config.onChange,
                  children: config.options,
                },
                index,
              ),
            ),
          }),
          jsx("div", {
            className: "mt-4 overflow-x-auto rounded-2xl border border-white/[0.07]",
            children: jsxs("table", {
              className: "min-w-[1240px] w-full text-left text-sm",
              children: [
                jsx("thead", {
                  className: "bg-white/[0.03] text-xs uppercase tracking-wide text-slate-400",
                  children: jsxs("tr", {
                    children: [
                      jsx("th", { className: "px-3 py-2", children: "Tenant" }),
                      jsx("th", { className: "px-3 py-2", children: "Invoice" }),
                      jsx("th", { className: "px-3 py-2", children: "Amount" }),
                      jsx("th", { className: "px-3 py-2", children: "Method" }),
                      jsx("th", { className: "px-3 py-2", children: "Transaction" }),
                      jsx("th", { className: "px-3 py-2", children: "Payment" }),
                      jsx("th", { className: "px-3 py-2", children: "Invoice State" }),
                      jsx("th", { className: "px-3 py-2", children: "Recorded" }),
                      jsx("th", { className: "px-3 py-2", children: "Actions" }),
                    ],
                  }),
                }),
                jsx("tbody", {
                  className: "divide-y divide-slate-800",
                  children:
                    loadingRecords
                      ? jsx("tr", {
                          children: jsx("td", {
                            className: "px-3 py-4 text-slate-400",
                            colSpan: 9,
                            children: "Loading tenant payments...",
                          }),
                        })
                      : payments.length > 0
                        ? payments.map((row) =>
                            jsxs(
                              Fragment,
                              {
                                children: [
                                  jsxs("tr", {
                                    className: "bg-slate-950/50",
                                    children: [
                                      jsx("td", { className: "px-3 py-2 font-medium text-white", children: row.tenant_name }),
                                      jsx("td", { className: "px-3 py-2 text-slate-300", children: row.invoice_number }),
                                      jsx("td", { className: "px-3 py-2", children: formatMoney(row.amount) }),
                                      jsx("td", { className: "px-3 py-2", children: row.method || "M-Pesa" }),
                                      jsx("td", { className: "px-3 py-2 font-mono text-xs text-slate-300", children: row.transaction_code || "--" }),
                                      jsx("td", {
                                        className: "px-3 py-2",
                                        children: jsx("span", {
                                          className: `inline-flex rounded-full border px-2 py-0.5 text-[11px] ${paymentTone(row.status)}`,
                                          children: row.status,
                                        }),
                                      }),
                                      jsx("td", {
                                        className: "px-3 py-2",
                                        children: jsx("span", {
                                          className: `inline-flex rounded-full border px-2 py-0.5 text-[11px] ${invoiceTone(row.invoice_status)}`,
                                          children: row.invoice_status || "--",
                                        }),
                                      }),
                                      jsx("td", { className: "px-3 py-2 text-slate-400", children: formatDateTime(row.paid_at || row.created_at) }),
                                      jsx("td", {
                                        className: "px-3 py-2",
                                        children: jsxs("div", {
                                          className: "flex flex-wrap gap-2",
                                          children: [
                                            jsx("button", {
                                              type: "button",
                                              onClick: () => setExpandedPaymentId(expandedPaymentId === row.id ? null : row.id),
                                              className: "rounded-xl border border-white/[0.09] px-2 py-1 text-xs text-slate-200 transition hover:bg-white/[0.04]",
                                              children: expandedPaymentId === row.id ? "Hide detail" : "Detail",
                                            }),
                                            jsx("button", {
                                              type: "button",
                                              onClick: () => openReviewModal("approve", row),
                                              disabled: String(row.status || "").toUpperCase() === "PAID",
                                              className: "rounded-xl border border-emerald-500/30 px-2 py-1 text-xs text-emerald-300 transition hover:bg-emerald-500/10 disabled:opacity-50",
                                              children: "Approve",
                                            }),
                                            jsx("button", {
                                              type: "button",
                                              onClick: () => openReviewModal("reject", row),
                                              disabled: String(row.status || "").toUpperCase() === "PAID",
                                              className: "rounded-xl border border-rose-500/30 px-2 py-1 text-xs text-rose-300 transition hover:bg-rose-500/10 disabled:opacity-50",
                                              children: "Reject",
                                            }),
                                            jsx("button", {
                                              type: "button",
                                              onClick: () => openReviewModal("retry", row),
                                              disabled: String(row.status || "").toUpperCase() === "PAID",
                                              className: "rounded-xl border border-amber-500/30 px-2 py-1 text-xs text-amber-300 transition hover:bg-amber-500/10 disabled:opacity-50",
                                              children: "Retry verification",
                                            }),
                                          ],
                                        }),
                                      }),
                                    ],
                                  }),
                                  expandedPaymentId === row.id
                                    ? jsx("tr", {
                                        className: "bg-slate-950/30",
                                        children: jsx("td", {
                                          className: "px-3 py-4",
                                          colSpan: 9,
                                          children: jsxs("div", {
                                            className: "space-y-3 rounded-2xl border border-white/[0.07] bg-slate-950/70 p-4",
                                            children: [
                                              jsx("div", {
                                                className: "grid gap-3 text-xs text-slate-300 md:grid-cols-4",
                                                children: [
                                                  { label: "Invoice", value: row.invoice_number },
                                                  { label: "Tenant", value: row.tenant_name },
                                                  { label: "Transaction", value: row.transaction_code || "--" },
                                                  { label: "Recorded", value: formatDateTime(row.created_at) },
                                                ].map((item) =>
                                                  jsxs(
                                                    "div",
                                                    {
                                                      children: [
                                                        jsx("p", { className: "uppercase text-slate-500", children: item.label }),
                                                        jsx("p", { className: "mt-1 break-all text-slate-200", children: item.value }),
                                                      ],
                                                    },
                                                    item.label,
                                                  ),
                                                ),
                                              }),
                                              jsx("pre", {
                                                className: "overflow-x-auto rounded-xl border border-white/[0.07] bg-black/20 p-3 text-[11px] text-slate-300",
                                                children: safeJson(row.metadata),
                                              }),
                                            ],
                                          }),
                                        }),
                                      })
                                    : null,
                                ],
                              },
                              row.id,
                            ),
                          )
                        : jsx("tr", {
                            children: jsx("td", {
                              className: "px-3 py-4 text-slate-400",
                              colSpan: 9,
                              children: "No tenant payments match the current filters.",
                            }),
                          }),
                }),
              ],
            }),
          }),
        ],
      }),
      planEditor
        ? jsx(OverlayCard, {
            title: planEditor.mode === "create" ? "Create platform plan" : "Edit platform plan",
            subtitle: "Keep pricing, storage, and student caps aligned with the billing contract.",
            onClose: resetPlanEditor,
            children: jsxs("form", {
              className: "space-y-3",
              onSubmit: savePlan,
              children: [
                jsxs("div", {
                  className: "grid gap-3 md:grid-cols-2",
                  children: [
                    jsx("input", {
                      className: fieldClass,
                      value: planForm.code,
                      onChange: (event) => setPlanForm((current) => ({ ...current, code: event.target.value })),
                      placeholder: "Plan code",
                      required: true,
                    }),
                    jsx("input", {
                      className: fieldClass,
                      value: planForm.name,
                      onChange: (event) => setPlanForm((current) => ({ ...current, name: event.target.value })),
                      placeholder: "Plan name",
                      required: true,
                    }),
                  ],
                }),
                jsx("textarea", {
                  className: `${fieldClass} min-h-[96px]`,
                  value: planForm.description,
                  onChange: (event) => setPlanForm((current) => ({ ...current, description: event.target.value })),
                  placeholder: "Short commercial description",
                }),
                jsxs("div", {
                  className: "grid gap-3 md:grid-cols-2",
                  children: [
                    jsx("input", {
                      className: fieldClass,
                      type: "number",
                      step: "0.01",
                      value: planForm.monthly_price,
                      onChange: (event) => setPlanForm((current) => ({ ...current, monthly_price: event.target.value })),
                      placeholder: "Monthly price",
                      required: true,
                    }),
                    jsx("input", {
                      className: fieldClass,
                      type: "number",
                      step: "0.01",
                      value: planForm.annual_price,
                      onChange: (event) => setPlanForm((current) => ({ ...current, annual_price: event.target.value })),
                      placeholder: "Annual price",
                      required: true,
                    }),
                  ],
                }),
                jsxs("div", {
                  className: "grid gap-3 md:grid-cols-2",
                  children: [
                    jsx("input", {
                      className: fieldClass,
                      type: "number",
                      value: planForm.max_students,
                      onChange: (event) => setPlanForm((current) => ({ ...current, max_students: event.target.value })),
                      placeholder: "Max students",
                      required: true,
                    }),
                    jsx("input", {
                      className: fieldClass,
                      type: "number",
                      value: planForm.max_storage_gb,
                      onChange: (event) => setPlanForm((current) => ({ ...current, max_storage_gb: event.target.value })),
                      placeholder: "Storage in GB",
                      required: true,
                    }),
                  ],
                }),
                planFormError ? jsx("p", { className: "text-sm text-rose-300", children: planFormError }) : null,
                jsx("button", {
                  type: "submit",
                  disabled: savingPlan,
                  className:
                    "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-emerald-400 disabled:opacity-70",
                  children: savingPlan ? "Saving..." : planEditor.mode === "create" ? "Create plan" : "Save changes",
                }),
              ],
            }),
          })
        : null,
      recordPaymentTarget
        ? jsx(OverlayCard, {
            title: "Record tenant payment",
            subtitle: `${recordPaymentTarget.invoice_number} for ${recordPaymentTarget.tenant_name}`,
            onClose: closeRecordPayment,
            children: jsxs("form", {
              className: "space-y-3",
              onSubmit: submitRecordPayment,
              children: [
                jsxs("div", {
                  className: "grid gap-3 md:grid-cols-2",
                  children: [
                    jsx("input", {
                      className: fieldClass,
                      type: "number",
                      step: "0.01",
                      value: recordPaymentForm.amount,
                      onChange: (event) => setRecordPaymentForm((current) => ({ ...current, amount: event.target.value })),
                      placeholder: "Amount",
                      required: true,
                    }),
                    jsx("input", {
                      className: fieldClass,
                      value: recordPaymentForm.transaction_id,
                      onChange: (event) => setRecordPaymentForm((current) => ({ ...current, transaction_id: event.target.value })),
                      placeholder: "Transaction code",
                      required: true,
                    }),
                  ],
                }),
                jsxs("div", {
                  className: "grid gap-3 md:grid-cols-2",
                  children: [
                    jsxs("select", {
                      className: fieldClass,
                      value: recordPaymentForm.status,
                      onChange: (event) => setRecordPaymentForm((current) => ({ ...current, status: event.target.value })),
                      children: [
                        jsx("option", { value: "PENDING", children: "Pending review" }),
                        jsx("option", { value: "PAID", children: "Paid immediately" }),
                      ],
                    }),
                    jsxs("select", {
                      className: fieldClass,
                      value: recordPaymentForm.method,
                      onChange: (event) => setRecordPaymentForm((current) => ({ ...current, method: event.target.value })),
                      children: [
                        jsx("option", { value: "M-Pesa", children: "M-Pesa" }),
                        jsx("option", { value: "Bank Transfer", children: "Bank Transfer" }),
                        jsx("option", { value: "Stripe Checkout", children: "Stripe Checkout" }),
                        jsx("option", { value: "Card", children: "Card" }),
                        jsx("option", { value: "Manual", children: "Manual" }),
                      ],
                    }),
                  ],
                }),
                jsx("input", {
                  className: fieldClass,
                  value: recordPaymentForm.external_reference,
                  onChange: (event) => setRecordPaymentForm((current) => ({ ...current, external_reference: event.target.value })),
                  placeholder: "External reference (optional)",
                }),
                recordPaymentError ? jsx("p", { className: "text-sm text-rose-300", children: recordPaymentError }) : null,
                jsx("div", {
                  className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 px-4 py-3 text-xs text-slate-400",
                  children: recordPaymentGuidance,
                }),
                jsx("button", {
                  type: "submit",
                  disabled: recordingPayment,
                  className:
                    "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-emerald-400 disabled:opacity-70",
                  children: recordingPayment ? "Saving..." : "Save payment",
                }),
              ],
            }),
          })
        : null,
      reviewModal
        ? jsx(OverlayCard, {
            title:
              reviewModal.mode === "approve"
                ? "Approve tenant payment"
                : reviewModal.mode === "reject"
                  ? "Reject tenant payment"
                  : "Retry tenant verification",
            subtitle: `${reviewModal.payment.invoice_number} for ${reviewModal.payment.tenant_name}`,
            onClose: closeReviewModal,
            children: jsxs("form", {
              className: "space-y-3",
              onSubmit: submitReview,
              children: [
                jsx("div", {
                  className: "rounded-2xl border border-white/[0.07] bg-slate-950/70 px-4 py-3 text-sm text-slate-300",
                  children:
                    reviewModal.mode === "approve"
                      ? "Approving will settle the payment, mark the invoice paid, and reactivate tenant access when applicable."
                      : reviewModal.mode === "reject"
                        ? "Rejecting marks this payment as failed and returns the invoice to pending or overdue state."
                        : "Retry verification keeps the payment in a pending state and records another operator verification attempt.",
                }),
                reviewModal.mode !== "approve"
                  ? jsx("textarea", {
                      className: `${fieldClass} min-h-[96px]`,
                      value: reviewForm.reason,
                      onChange: (event) => setReviewForm({ reason: event.target.value }),
                      placeholder: reviewModal.mode === "reject" ? "Reason for rejection" : "Reason for retrying verification",
                    })
                  : jsx("textarea", {
                      className: `${fieldClass} min-h-[96px]`,
                      value: reviewForm.reason,
                      onChange: (event) => setReviewForm({ reason: event.target.value }),
                      placeholder: "Optional approval note",
                    }),
                reviewError ? jsx("p", { className: "text-sm text-rose-300", children: reviewError }) : null,
                jsx("button", {
                  type: "submit",
                  disabled: reviewingPayment,
                  className:
                    reviewModal.mode === "approve"
                      ? "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-emerald-400 disabled:opacity-70"
                      : reviewModal.mode === "reject"
                        ? "rounded-xl bg-rose-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-400 disabled:opacity-70"
                        : "rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-amber-400 disabled:opacity-70",
                  children:
                    reviewingPayment
                      ? "Working..."
                      : reviewModal.mode === "approve"
                        ? "Approve payment"
                        : reviewModal.mode === "reject"
                          ? "Reject payment"
                          : "Retry verification",
                }),
              ],
            }),
          })
        : null,
    ],
  });
}

export { PlatformBillingPage as default };
