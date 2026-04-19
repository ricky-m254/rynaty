import { r as React, j as jsxRuntime, b as api } from "./index-D7ltaYVC.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";
import { D as DollarSign } from "./dollar-sign-BsYV7G3i.js";
import { C as CircleCheckBig } from "./circle-check-big-gKc9ia_Q.js";
import { C as CircleAlert } from "./circle-alert-QkR7CaoT.js";
import { F as FileText } from "./file-text-BMGjGS-3.js";
import { C as CreditCard } from "./credit-card-pJ6qZy3c.js";
import { c as createLucideIcon } from "./createLucideIcon-BLtbVmUp.js";
import { T as Trash2 } from "./trash-2-Bs1RXa9v.js";
import { R as RefreshCw } from "./refresh-cw-DOVkzt4u.js";
import { P as Plus } from "./plus-CQ41G_RD.js";
import { S as Save } from "./save-DVPXWNqk.js";

const Percent = createLucideIcon("Percent", [
  ["line", { x1: "19", x2: "5", y1: "5", y2: "19", key: "1x9vlm" }],
  ["circle", { cx: "6.5", cy: "6.5", r: "2.5", key: "4mh3h7" }],
  ["circle", { cx: "17.5", cy: "17.5", r: "2.5", key: "1mdrzq" }],
]);

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.07)",
  boxShadow: "0 24px 80px rgba(15, 23, 42, 0.35)",
};
const inputClass =
  "w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-emerald-500/50";
const selectClass =
  "w-full rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500/50";
const labelClass = "mb-1 block text-xs font-medium uppercase tracking-wide text-white/50";

const PAYMENT_METHODS = ["Cash", "MPesa", "Bank Transfer", "Cheque", "Card", "Stripe", "Standing Order", "Online", "Other"];
const CURRENCIES = ["KES", "USD", "EUR", "GBP", "UGX", "TZS", "ETB", "GHS", "NGN", "ZAR"];
const DEFAULT_FINANCE = {
  currency: "KES",
  tax_percentage: "0.00",
  receipt_prefix: "RCT-",
  invoice_prefix: "INV-",
  late_fee_grace_days: 0,
  late_fee_type: "FLAT",
  late_fee_value: "0.00",
  late_fee_max: null,
  accepted_payment_methods: ["Cash", "MPesa", "Bank Transfer"],
  late_fee_rules: [],
};
const DEFAULT_LATE_RULE = { grace_days: 0, fee_type: "FLAT", value: "0.00", max_fee: null };
const DEFAULT_MPESA = {
  enabled: true,
  consumer_key: "",
  consumer_secret: "",
  shortcode: "",
  passkey: "",
  environment: "sandbox",
};
const DEFAULT_STRIPE = {
  enabled: true,
  publishable_key: "",
  secret_key: "",
  webhook_secret: "",
};

function Section({ title, icon, accent = "text-emerald-400", status, children }) {
  return jsxRuntime.jsxs("div", {
    className: "rounded-xl p-5 space-y-4",
    style: panelStyle,
    children: [
      jsxRuntime.jsxs("div", {
        className: "flex items-center gap-2",
        children: [
          jsxRuntime.jsx(icon, { className: `h-4 w-4 ${accent}` }),
          jsxRuntime.jsx("h3", {
            className: "text-sm font-semibold uppercase tracking-wide text-white/80",
            children: title,
          }),
          status ? jsxRuntime.jsx("div", { className: "ml-auto", children: status }) : null,
        ],
      }),
      children,
    ],
  });
}

function Field({ label, hint, children }) {
  return jsxRuntime.jsxs("div", {
    children: [
      jsxRuntime.jsx("label", { className: labelClass, children: label }),
      children,
      hint ? jsxRuntime.jsx("p", { className: "mt-1 text-[11px] text-white/35", children: hint }) : null,
    ],
  });
}

function InlineNotice({ notice }) {
  if (!notice) return null;
  return jsxRuntime.jsxs("div", {
    className: `flex items-center gap-2 rounded-lg px-4 py-3 text-sm ${
      notice.ok
        ? "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
        : "border border-red-500/20 bg-red-500/10 text-red-400"
    }`,
    children: [
      notice.ok
        ? jsxRuntime.jsx(CircleCheckBig, { className: "h-4 w-4" })
        : jsxRuntime.jsx(CircleAlert, { className: "h-4 w-4" }),
      notice.msg,
    ],
  });
}

function StatusChip({ tone, children }) {
  const tones = {
    good: "border border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
    warn: "border border-amber-500/30 bg-amber-500/15 text-amber-300",
    neutral: "border border-white/10 bg-white/10 text-slate-300",
  };
  return jsxRuntime.jsx("span", {
    className: `rounded-full px-2 py-0.5 text-[11px] font-medium ${tones[tone] || tones.neutral}`,
    children,
  });
}

function resolveIntegration(settings, grouped, key) {
  const fromFlat = settings?.[key];
  if (fromFlat && typeof fromFlat === "object") return fromFlat;

  const categories = Object.values(grouped || {});
  for (const category of categories) {
    const row = category?.[key];
    if (row?.value && typeof row.value === "object") return row.value;
  }
  return {};
}

function SettingsFinancePage() {
  const [finance, setFinance] = React.useState(DEFAULT_FINANCE);
  const [lateRule, setLateRule] = React.useState(DEFAULT_LATE_RULE);
  const [mpesa, setMpesa] = React.useState(DEFAULT_MPESA);
  const [stripe, setStripe] = React.useState(DEFAULT_STRIPE);
  const [loading, setLoading] = React.useState(true);
  const [savingFinance, setSavingFinance] = React.useState(false);
  const [savingMpesa, setSavingMpesa] = React.useState(false);
  const [savingStripe, setSavingStripe] = React.useState(false);
  const [addingRule, setAddingRule] = React.useState(false);
  const [notice, setNotice] = React.useState(null);
  const [mpesaReachability, setMpesaReachability] = React.useState(null);
  const [stripeReachability, setStripeReachability] = React.useState(null);
  const [testingMpesa, setTestingMpesa] = React.useState(false);
  const [testingStripe, setTestingStripe] = React.useState(false);
  const [hasMpesaConfig, setHasMpesaConfig] = React.useState(false);
  const [hasStripeConfig, setHasStripeConfig] = React.useState(false);

  const showNotice = React.useCallback((msg, ok = true) => {
    setNotice({ msg, ok });
    window.clearTimeout(showNotice._timer);
    showNotice._timer = window.setTimeout(() => setNotice(null), 3500);
  }, []);

  const loadFinanceSettings = React.useCallback(async () => {
    const response = await api.get("/settings/finance/");
    setFinance({ ...DEFAULT_FINANCE, ...response.data });
  }, []);

  const testMpesaConnection = React.useCallback(async (payload = mpesa, silent = false) => {
    setTestingMpesa(true);
    if (!silent) setMpesaReachability(null);
    try {
      const response = await api.post("/finance/mpesa/test-connection/", {
        consumer_key: payload.consumer_key || "",
        consumer_secret: payload.consumer_secret || "",
        shortcode: payload.shortcode || "",
        passkey: payload.passkey || "",
        environment: payload.environment || "sandbox",
      });
      setMpesaReachability({ ok: true, msg: response.data?.message || "Connection successful." });
      return true;
    } catch (error) {
      setMpesaReachability({
        ok: false,
        msg: error?.response?.data?.error || "Connection failed. Check your credentials.",
      });
      return false;
    } finally {
      setTestingMpesa(false);
    }
  }, [mpesa]);

  const testStripeConnection = React.useCallback(async (payload = stripe, silent = false) => {
    setTestingStripe(true);
    if (!silent) setStripeReachability(null);
    try {
      const response = await api.post("/finance/stripe/test-connection/", {
        secret_key: payload.secret_key || "",
      });
      setStripeReachability({
        ok: true,
        msg: response.data?.message || "Connection successful.",
      });
      return true;
    } catch (error) {
      setStripeReachability({
        ok: false,
        msg: error?.response?.data?.error || "Connection failed. Check your credentials.",
      });
      return false;
    } finally {
      setTestingStripe(false);
    }
  }, [stripe]);

  const loadIntegrations = React.useCallback(async () => {
    const response = await api.get("/settings/");
    const settings = response.data?.settings || {};
    const grouped = response.data?.grouped || {};

    const mpesaConfig = { ...DEFAULT_MPESA, ...resolveIntegration(settings, grouped, "integrations.mpesa") };
    const stripeConfig = { ...DEFAULT_STRIPE, ...resolveIntegration(settings, grouped, "integrations.stripe") };

    setMpesa(mpesaConfig);
    setStripe(stripeConfig);

    const mpesaConfigured = !!(
      mpesaConfig.consumer_key ||
      mpesaConfig.consumer_secret ||
      mpesaConfig.shortcode ||
      mpesaConfig.passkey
    );
    const stripeConfigured = !!(
      stripeConfig.publishable_key ||
      stripeConfig.secret_key ||
      stripeConfig.webhook_secret
    );

    setHasMpesaConfig(mpesaConfigured);
    setHasStripeConfig(stripeConfigured);

    if (mpesaConfigured && mpesaConfig.enabled !== false) {
      testMpesaConnection(mpesaConfig, true);
    } else {
      setMpesaReachability(null);
    }

    if (stripeConfigured && stripeConfig.enabled !== false && stripeConfig.secret_key) {
      testStripeConnection(stripeConfig, true);
    } else {
      setStripeReachability(null);
    }
  }, [testMpesaConnection, testStripeConnection]);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        await Promise.all([loadFinanceSettings(), loadIntegrations()]);
      } catch {
        if (active) showNotice("Failed to load finance settings.", false);
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [loadFinanceSettings, loadIntegrations, showNotice]);

  const saveFinance = async () => {
    setSavingFinance(true);
    try {
      await api.patch("/settings/finance/", {
        currency: finance.currency,
        tax_percentage: finance.tax_percentage,
        receipt_prefix: finance.receipt_prefix,
        invoice_prefix: finance.invoice_prefix,
        late_fee_grace_days: finance.late_fee_grace_days,
        late_fee_type: finance.late_fee_type,
        late_fee_value: finance.late_fee_value,
        late_fee_max: finance.late_fee_max || null,
        accepted_payment_methods: finance.accepted_payment_methods,
      });
      showNotice("Finance settings saved.");
    } catch {
      showNotice("Unable to save finance settings.", false);
    } finally {
      setSavingFinance(false);
    }
  };

  const addLateFeeRule = async () => {
    setAddingRule(true);
    try {
      const response = await api.post("/finance/late-fee-rules/", {
        grace_days: lateRule.grace_days,
        fee_type: lateRule.fee_type,
        value: lateRule.value,
        max_fee: lateRule.max_fee || null,
        is_active: true,
      });
      setFinance((current) => ({
        ...current,
        late_fee_rules: [...current.late_fee_rules, response.data],
      }));
      setLateRule(DEFAULT_LATE_RULE);
      showNotice("Late fee rule added.");
    } catch {
      showNotice("Unable to add late fee rule.", false);
    } finally {
      setAddingRule(false);
    }
  };

  const deleteLateFeeRule = async (ruleId) => {
    try {
      await api.delete(`/finance/late-fee-rules/${ruleId}/`);
      setFinance((current) => ({
        ...current,
        late_fee_rules: current.late_fee_rules.filter((rule) => rule.id !== ruleId),
      }));
      showNotice("Late fee rule deleted.");
    } catch {
      showNotice("Unable to delete late fee rule.", false);
    }
  };

  const saveMpesa = async () => {
    setSavingMpesa(true);
    try {
      await api.post("/settings/", {
        key: "integrations.mpesa",
        value: { ...mpesa },
        category: "integrations",
      });
      setHasMpesaConfig(true);
      showNotice("M-Pesa credentials saved.");
      if (mpesa.enabled !== false) {
        await testMpesaConnection(mpesa, true);
      }
    } catch {
      showNotice("Unable to save M-Pesa credentials.", false);
    } finally {
      setSavingMpesa(false);
    }
  };

  const saveStripe = async () => {
    setSavingStripe(true);
    try {
      await api.post("/settings/", {
        key: "integrations.stripe",
        value: { ...stripe },
        category: "integrations",
      });
      setHasStripeConfig(true);
      showNotice("Stripe credentials saved.");
      if (stripe.enabled !== false && stripe.secret_key) {
        await testStripeConnection(stripe, true);
      }
    } catch {
      showNotice("Unable to save Stripe credentials.", false);
    } finally {
      setSavingStripe(false);
    }
  };

  const toggleMethod = (method) => {
    setFinance((current) => ({
      ...current,
      accepted_payment_methods: current.accepted_payment_methods.includes(method)
        ? current.accepted_payment_methods.filter((item) => item !== method)
        : [...current.accepted_payment_methods, method],
    }));
  };

  const integrationStatus = (configured, reachability, testing, enabled = true) => {
    if (!configured) return jsxRuntime.jsx(StatusChip, { tone: "neutral", children: "Not configured" });
    if (enabled === false) return jsxRuntime.jsx(StatusChip, { tone: "warn", children: "Disabled" });
    if (testing) return jsxRuntime.jsx(StatusChip, { tone: "neutral", children: "Checking..." });
    if (reachability?.ok) return jsxRuntime.jsx(StatusChip, { tone: "good", children: "Reachable" });
    if (reachability && !reachability.ok) return jsxRuntime.jsx(StatusChip, { tone: "warn", children: "Needs attention" });
    return jsxRuntime.jsx(StatusChip, { tone: "good", children: "Configured" });
  };

  if (loading) {
    return jsxRuntime.jsx("div", {
      className: "flex h-64 items-center justify-center",
      children: jsxRuntime.jsx("div", {
        className: "h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent",
      }),
    });
  }

  return jsxRuntime.jsxs("div", {
    className: "space-y-6",
    children: [
      jsxRuntime.jsx(PageHero, {
        title: "Finance Configuration",
        subtitle: "Manage billing defaults, accepted payment methods, and live gateway credentials from one place.",
        icon: jsxRuntime.jsx(DollarSign, { className: "h-6 w-6 text-emerald-400" }),
      }),
      jsxRuntime.jsx(InlineNotice, { notice }),
      jsxRuntime.jsxs("div", {
        className: "grid grid-cols-1 gap-6 lg:grid-cols-2",
        children: [
          jsxRuntime.jsxs(Section, {
            title: "Currency & Invoicing",
            icon: FileText,
            accent: "text-emerald-400",
            children: [
              jsxRuntime.jsx(Field, {
                label: "Currency",
                children: jsxRuntime.jsx("select", {
                  className: selectClass,
                  value: finance.currency,
                  onChange: (event) => setFinance((current) => ({ ...current, currency: event.target.value })),
                  children: CURRENCIES.map((currency) =>
                    jsxRuntime.jsx("option", { value: currency, children: currency }, currency),
                  ),
                }),
              }),
              jsxRuntime.jsx(Field, {
                label: "Tax / VAT percentage (%)",
                children: jsxRuntime.jsx("input", {
                  className: inputClass,
                  type: "number",
                  step: "0.01",
                  min: "0",
                  max: "100",
                  value: finance.tax_percentage,
                  onChange: (event) => setFinance((current) => ({ ...current, tax_percentage: event.target.value })),
                }),
              }),
              jsxRuntime.jsxs("div", {
                className: "grid grid-cols-2 gap-3",
                children: [
                  jsxRuntime.jsx(Field, {
                    label: "Receipt prefix",
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      value: finance.receipt_prefix,
                      onChange: (event) => setFinance((current) => ({ ...current, receipt_prefix: event.target.value })),
                      placeholder: "RCT-",
                    }),
                  }),
                  jsxRuntime.jsx(Field, {
                    label: "Invoice prefix",
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      value: finance.invoice_prefix,
                      onChange: (event) => setFinance((current) => ({ ...current, invoice_prefix: event.target.value })),
                      placeholder: "INV-",
                    }),
                  }),
                ],
              }),
              jsxRuntime.jsxs("div", {
                className: "rounded-lg bg-white/3 p-3 text-xs text-white/30",
                children: [
                  jsxRuntime.jsxs("div", {
                    children: ["Receipt example: ", jsxRuntime.jsxs("span", { className: "text-white/60", children: [finance.receipt_prefix, "00001"] })],
                  }),
                  jsxRuntime.jsxs("div", {
                    children: ["Invoice example: ", jsxRuntime.jsxs("span", { className: "text-white/60", children: [finance.invoice_prefix, "00001"] })],
                  }),
                ],
              }),
            ],
          }),
          jsxRuntime.jsxs(Section, {
            title: "Accepted Payment Methods",
            icon: CreditCard,
            accent: "text-sky-400",
            children: [
              jsxRuntime.jsx("p", {
                className: "text-xs text-white/40",
                children: "Enable the collection methods your school currently supports across receipts, payment forms, and portal workflows.",
              }),
              jsxRuntime.jsx("div", {
                className: "grid grid-cols-2 gap-2",
                children: PAYMENT_METHODS.map((method) => {
                  const active = finance.accepted_payment_methods.includes(method);
                  return jsxRuntime.jsxs(
                    "button",
                    {
                      type: "button",
                      onClick: () => toggleMethod(method),
                      className: `flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition ${
                        active
                          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                          : "border-white/10 bg-white/3 text-white/40 hover:text-white/70"
                      }`,
                      children: [
                        jsxRuntime.jsx("span", {
                          className: `h-2 w-2 rounded-full ${active ? "bg-emerald-400" : "bg-white/20"}`,
                        }),
                        method,
                      ],
                    },
                    method,
                  );
                }),
              }),
            ],
          }),
          jsxRuntime.jsxs(Section, {
            title: "Default Late Fee Policy",
            icon: Percent,
            accent: "text-amber-400",
            children: [
              jsxRuntime.jsx(Field, {
                label: "Grace period (days after due date)",
                children: jsxRuntime.jsx("input", {
                  className: inputClass,
                  type: "number",
                  min: "0",
                  value: finance.late_fee_grace_days,
                  onChange: (event) =>
                    setFinance((current) => ({
                      ...current,
                      late_fee_grace_days: parseInt(event.target.value, 10) || 0,
                    })),
                }),
              }),
              jsxRuntime.jsxs("div", {
                className: "grid grid-cols-2 gap-3",
                children: [
                  jsxRuntime.jsx(Field, {
                    label: "Fee type",
                    children: jsxRuntime.jsxs("select", {
                      className: selectClass,
                      value: finance.late_fee_type,
                      onChange: (event) => setFinance((current) => ({ ...current, late_fee_type: event.target.value })),
                      children: [
                        jsxRuntime.jsx("option", { value: "FLAT", children: "Flat amount" }),
                        jsxRuntime.jsx("option", { value: "PERCENT", children: "Percentage" }),
                      ],
                    }),
                  }),
                  jsxRuntime.jsx(Field, {
                    label: finance.late_fee_type === "PERCENT" ? "Percentage (%)" : `Amount (${finance.currency})`,
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      type: "number",
                      step: "0.01",
                      min: "0",
                      value: finance.late_fee_value,
                      onChange: (event) => setFinance((current) => ({ ...current, late_fee_value: event.target.value })),
                    }),
                  }),
                ],
              }),
              jsxRuntime.jsx(Field, {
                label: `Maximum late fee (${finance.currency})`,
                hint: "Leave blank for no cap.",
                children: jsxRuntime.jsx("input", {
                  className: inputClass,
                  type: "number",
                  step: "0.01",
                  min: "0",
                  value: finance.late_fee_max ?? "",
                  onChange: (event) =>
                    setFinance((current) => ({ ...current, late_fee_max: event.target.value || null })),
                }),
              }),
            ],
          }),
          jsxRuntime.jsxs(Section, {
            title: "Tiered Late Fee Rules",
            icon: Percent,
            accent: "text-violet-400",
            children: [
              jsxRuntime.jsx("p", {
                className: "text-xs text-white/40",
                children: "Optional escalations that stack on top of the default policy for longer overdue balances.",
              }),
              finance.late_fee_rules.length > 0
                ? jsxRuntime.jsx("div", {
                    className: "space-y-2",
                    children: finance.late_fee_rules.map((rule) =>
                      jsxRuntime.jsxs(
                        "div",
                        {
                          className: "flex items-center gap-3 rounded-lg border border-white/7 bg-white/3 px-3 py-2",
                          children: [
                            jsxRuntime.jsxs("div", {
                              className: "flex-1 text-sm",
                              children: [
                                jsxRuntime.jsx("span", { className: "text-white/70", children: "After " }),
                                jsxRuntime.jsxs("span", { className: "font-medium text-amber-400", children: [rule.grace_days, "d"] }),
                                jsxRuntime.jsx("span", { className: "mx-1.5 text-white/50", children: "->" }),
                                jsxRuntime.jsx("span", {
                                  className: "font-medium text-emerald-400",
                                  children:
                                    rule.fee_type === "PERCENT" ? `${rule.value}%` : `${finance.currency} ${rule.value}`,
                                }),
                                rule.max_fee
                                  ? jsxRuntime.jsxs("span", {
                                      className: "ml-1 text-white/30",
                                      children: ["(max ", finance.currency, " ", rule.max_fee, ")"],
                                    })
                                  : null,
                              ],
                            }),
                            rule.id
                              ? jsxRuntime.jsx("button", {
                                  type: "button",
                                  className: "p-1 text-white/20 transition hover:text-red-400",
                                  onClick: () => deleteLateFeeRule(rule.id),
                                  children: jsxRuntime.jsx(Trash2, { className: "h-3.5 w-3.5" }),
                                })
                              : null,
                          ],
                        },
                        rule.id,
                      ),
                    ),
                  })
                : jsxRuntime.jsx("div", { className: "py-2 text-xs text-white/25", children: "No tiered rules yet." }),
              jsxRuntime.jsxs("div", {
                className: "space-y-3 border-t border-white/7 pt-3",
                children: [
                  jsxRuntime.jsx("div", { className: "text-xs font-medium text-white/40", children: "Add rule" }),
                  jsxRuntime.jsxs("div", {
                    className: "grid grid-cols-2 gap-2",
                    children: [
                      jsxRuntime.jsx(Field, {
                        label: "Grace days",
                        children: jsxRuntime.jsx("input", {
                          className: inputClass,
                          type: "number",
                          min: "0",
                          value: lateRule.grace_days,
                          onChange: (event) =>
                            setLateRule((current) => ({
                              ...current,
                              grace_days: parseInt(event.target.value, 10) || 0,
                            })),
                        }),
                      }),
                      jsxRuntime.jsx(Field, {
                        label: "Type",
                        children: jsxRuntime.jsxs("select", {
                          className: selectClass,
                          value: lateRule.fee_type,
                          onChange: (event) => setLateRule((current) => ({ ...current, fee_type: event.target.value })),
                          children: [
                            jsxRuntime.jsx("option", { value: "FLAT", children: "Flat" }),
                            jsxRuntime.jsx("option", { value: "PERCENT", children: "Percent" }),
                          ],
                        }),
                      }),
                      jsxRuntime.jsx(Field, {
                        label: "Value",
                        children: jsxRuntime.jsx("input", {
                          className: inputClass,
                          type: "number",
                          step: "0.01",
                          min: "0",
                          value: lateRule.value,
                          onChange: (event) => setLateRule((current) => ({ ...current, value: event.target.value })),
                        }),
                      }),
                      jsxRuntime.jsx(Field, {
                        label: "Max (optional)",
                        children: jsxRuntime.jsx("input", {
                          className: inputClass,
                          type: "number",
                          step: "0.01",
                          min: "0",
                          value: lateRule.max_fee ?? "",
                          onChange: (event) => setLateRule((current) => ({ ...current, max_fee: event.target.value || null })),
                        }),
                      }),
                    ],
                  }),
                  jsxRuntime.jsxs("button", {
                    type: "button",
                    onClick: addLateFeeRule,
                    disabled: addingRule,
                    className:
                      "flex items-center gap-2 rounded-lg border border-violet-500/20 bg-violet-500/10 px-3 py-1.5 text-xs text-violet-400 transition hover:bg-violet-500/20 disabled:opacity-40",
                    children: [
                      addingRule
                        ? jsxRuntime.jsx(RefreshCw, { className: "h-3 w-3 animate-spin" })
                        : jsxRuntime.jsx(Plus, { className: "h-3 w-3" }),
                      addingRule ? "Adding..." : "Add Rule",
                    ],
                  }),
                ],
              }),
            ],
          }),
          jsxRuntime.jsxs(Section, {
            title: "M-Pesa Integration",
            icon: CreditCard,
            accent: "text-emerald-400",
            status: integrationStatus(hasMpesaConfig, mpesaReachability, testingMpesa, mpesa.enabled),
            children: [
              jsxRuntime.jsx("p", {
                className: "text-xs text-white/40",
                children: "Safaricom Daraja STK push credentials. Test connection only performs the OAuth handshake.",
              }),
              jsxRuntime.jsxs("label", {
                className: "flex items-center gap-2 text-sm text-slate-200",
                children: [
                  jsxRuntime.jsx("input", {
                    type: "checkbox",
                    checked: mpesa.enabled !== false,
                    onChange: (event) => setMpesa((current) => ({ ...current, enabled: event.target.checked })),
                  }),
                  "Enable M-Pesa for this tenant",
                ],
              }),
              jsxRuntime.jsxs("div", {
                className: "grid grid-cols-2 gap-3",
                children: [
                  jsxRuntime.jsx(Field, {
                    label: "Consumer Key",
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      type: "password",
                      value: mpesa.consumer_key,
                      onChange: (event) => setMpesa((current) => ({ ...current, consumer_key: event.target.value })),
                      placeholder: "Your Daraja consumer key",
                    }),
                  }),
                  jsxRuntime.jsx(Field, {
                    label: "Consumer Secret",
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      type: "password",
                      value: mpesa.consumer_secret,
                      onChange: (event) => setMpesa((current) => ({ ...current, consumer_secret: event.target.value })),
                      placeholder: "Your Daraja consumer secret",
                    }),
                  }),
                  jsxRuntime.jsx(Field, {
                    label: "Shortcode (Paybill / Till)",
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      value: mpesa.shortcode,
                      onChange: (event) => setMpesa((current) => ({ ...current, shortcode: event.target.value })),
                      placeholder: "e.g. 174379",
                    }),
                  }),
                  jsxRuntime.jsx(Field, {
                    label: "Passkey",
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      type: "password",
                      value: mpesa.passkey,
                      onChange: (event) => setMpesa((current) => ({ ...current, passkey: event.target.value })),
                      placeholder: "Your Daraja passkey",
                    }),
                  }),
                  jsxRuntime.jsx(Field, {
                    label: "Environment",
                    children: jsxRuntime.jsxs("select", {
                      className: selectClass,
                      value: mpesa.environment,
                      onChange: (event) => setMpesa((current) => ({ ...current, environment: event.target.value })),
                      children: [
                        jsxRuntime.jsx("option", { value: "sandbox", children: "Sandbox (testing)" }),
                        jsxRuntime.jsx("option", { value: "production", children: "Production (live)" }),
                      ],
                    }),
                  }),
                ],
              }),
              mpesaReachability
                ? jsxRuntime.jsx(InlineNotice, {
                    notice: { msg: mpesaReachability.msg, ok: mpesaReachability.ok },
                  })
                : null,
              jsxRuntime.jsxs("div", {
                className: "flex gap-3",
                children: [
                  jsxRuntime.jsxs("button", {
                    type: "button",
                    onClick: () => testMpesaConnection(),
                    disabled: testingMpesa,
                    className:
                      "flex items-center gap-2 rounded-lg border border-sky-500/20 bg-sky-500/10 px-4 py-2 text-sm text-sky-400 transition hover:bg-sky-500/20 disabled:opacity-50",
                    children: [
                      jsxRuntime.jsx(RefreshCw, { className: `h-4 w-4 ${testingMpesa ? "animate-spin" : ""}` }),
                      testingMpesa ? "Testing..." : "Test Connection",
                    ],
                  }),
                  jsxRuntime.jsxs("button", {
                    type: "button",
                    onClick: saveMpesa,
                    disabled: savingMpesa,
                    className:
                      "flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-400 transition hover:bg-emerald-500/20 disabled:opacity-50",
                    children: [
                      jsxRuntime.jsx(Save, { className: "h-4 w-4" }),
                      savingMpesa ? "Saving..." : "Save Credentials",
                    ],
                  }),
                ],
              }),
            ],
          }),
          jsxRuntime.jsxs(Section, {
            title: "Stripe Integration",
            icon: CreditCard,
            accent: "text-sky-400",
            status: integrationStatus(hasStripeConfig, stripeReachability, testingStripe, stripe.enabled),
            children: [
              jsxRuntime.jsx("p", {
                className: "text-xs text-white/40",
                children: "Hosted card checkout fast-track. Use your Stripe secret key for session creation and webhook secret for `/api/finance/gateway/webhooks/stripe/`.",
              }),
              jsxRuntime.jsxs("label", {
                className: "flex items-center gap-2 text-sm text-slate-200",
                children: [
                  jsxRuntime.jsx("input", {
                    type: "checkbox",
                    checked: stripe.enabled !== false,
                    onChange: (event) => setStripe((current) => ({ ...current, enabled: event.target.checked })),
                  }),
                  "Enable Stripe for this tenant",
                ],
              }),
              jsxRuntime.jsxs("div", {
                className: "grid grid-cols-1 gap-3",
                children: [
                  jsxRuntime.jsx(Field, {
                    label: "Publishable Key",
                    hint: "Optional for the current hosted checkout MVP, but useful for future embedded flows.",
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      type: "password",
                      value: stripe.publishable_key,
                      onChange: (event) => setStripe((current) => ({ ...current, publishable_key: event.target.value })),
                      placeholder: "pk_test_...",
                    }),
                  }),
                  jsxRuntime.jsx(Field, {
                    label: "Secret Key",
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      type: "password",
                      value: stripe.secret_key,
                      onChange: (event) => setStripe((current) => ({ ...current, secret_key: event.target.value })),
                      placeholder: "sk_test_...",
                    }),
                  }),
                  jsxRuntime.jsx(Field, {
                    label: "Webhook Secret",
                    hint: "Configure this in Stripe after pointing the webhook endpoint to the finance gateway route.",
                    children: jsxRuntime.jsx("input", {
                      className: inputClass,
                      type: "password",
                      value: stripe.webhook_secret,
                      onChange: (event) => setStripe((current) => ({ ...current, webhook_secret: event.target.value })),
                      placeholder: "whsec_...",
                    }),
                  }),
                ],
              }),
              jsxRuntime.jsxs("div", {
                className: "rounded-lg border border-white/10 bg-white/3 p-3 text-[11px] text-white/45",
                children: [
                  jsxRuntime.jsx("div", { children: "Webhook endpoint" }),
                  jsxRuntime.jsx("code", {
                    className: "mt-1 block rounded bg-slate-950/80 px-2 py-1 text-sky-300",
                    children: "/api/finance/gateway/webhooks/stripe/",
                  }),
                ],
              }),
              stripeReachability
                ? jsxRuntime.jsx(InlineNotice, {
                    notice: { msg: stripeReachability.msg, ok: stripeReachability.ok },
                  })
                : null,
              jsxRuntime.jsxs("div", {
                className: "flex gap-3",
                children: [
                  jsxRuntime.jsxs("button", {
                    type: "button",
                    onClick: () => testStripeConnection(),
                    disabled: testingStripe || !stripe.secret_key,
                    className:
                      "flex items-center gap-2 rounded-lg border border-sky-500/20 bg-sky-500/10 px-4 py-2 text-sm text-sky-400 transition hover:bg-sky-500/20 disabled:opacity-50",
                    children: [
                      jsxRuntime.jsx(RefreshCw, { className: `h-4 w-4 ${testingStripe ? "animate-spin" : ""}` }),
                      testingStripe ? "Testing..." : "Test Connection",
                    ],
                  }),
                  jsxRuntime.jsxs("button", {
                    type: "button",
                    onClick: saveStripe,
                    disabled: savingStripe,
                    className:
                      "flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-400 transition hover:bg-emerald-500/20 disabled:opacity-50",
                    children: [
                      jsxRuntime.jsx(Save, { className: "h-4 w-4" }),
                      savingStripe ? "Saving..." : "Save Credentials",
                    ],
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
      jsxRuntime.jsx("div", {
        className: "flex justify-end",
        children: jsxRuntime.jsxs("button", {
          type: "button",
          onClick: saveFinance,
          disabled: savingFinance,
          className:
            "flex items-center gap-2 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:opacity-50",
          children: [
            jsxRuntime.jsx(Save, { className: "h-4 w-4" }),
            savingFinance ? "Saving..." : "Save Finance Settings",
          ],
        }),
      }),
    ],
  });
}

export { SettingsFinancePage as default };
