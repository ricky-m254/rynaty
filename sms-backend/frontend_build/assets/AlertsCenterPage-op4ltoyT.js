import { r as React, b as api, j as e } from "./index-D7ltaYVC.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.08)",
};

const inputClassName =
  "w-full rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-400";

const severityTone = {
  INFO: {
    background: "rgba(59,130,246,0.12)",
    borderColor: "rgba(59,130,246,0.30)",
    color: "#93c5fd",
  },
  WARNING: {
    background: "rgba(245,158,11,0.12)",
    borderColor: "rgba(245,158,11,0.30)",
    color: "#fcd34d",
  },
  CRITICAL: {
    background: "rgba(239,68,68,0.12)",
    borderColor: "rgba(239,68,68,0.30)",
    color: "#fca5a5",
  },
};

const priorityTone = {
  Low: {
    background: "rgba(100,116,139,0.10)",
    borderColor: "rgba(100,116,139,0.20)",
    color: "#94a3b8",
  },
  Normal: {
    background: "rgba(59,130,246,0.12)",
    borderColor: "rgba(59,130,246,0.30)",
    color: "#93c5fd",
  },
  Important: {
    background: "rgba(245,158,11,0.12)",
    borderColor: "rgba(245,158,11,0.30)",
    color: "#fcd34d",
  },
  Urgent: {
    background: "rgba(239,68,68,0.12)",
    borderColor: "rgba(239,68,68,0.30)",
    color: "#fca5a5",
  },
  Critical: {
    background: "rgba(127,29,29,0.35)",
    borderColor: "rgba(239,68,68,0.40)",
    color: "#fecaca",
  },
};

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  try {
    return new Date(value).toLocaleString("en-KE", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

function coerceList(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (Array.isArray(payload?.results)) {
    return payload.results;
  }
  return [];
}

function toneForSeverity(severity) {
  return severityTone[String(severity || "").toUpperCase()] || severityTone.INFO;
}

function toneForPriority(priority) {
  return priorityTone[String(priority || "").trim()] || priorityTone.Normal;
}

function SummaryCard({ label, value, accent }) {
  return e.jsxs(
    "div",
    {
      className: "rounded-2xl p-4",
      style: {
        background: `${accent}14`,
        border: `1px solid ${accent}30`,
      },
      children: [
        e.jsx("p", {
          className: "text-[11px] uppercase tracking-[0.18em] text-slate-400",
          children: label,
        }),
        e.jsx("p", {
          className: "mt-2 text-3xl font-display font-bold text-white tabular-nums",
          children: value,
        }),
      ],
    },
  );
}

function AlertsCenterPage() {
  const [loading, setLoading] = React.useState(true);
  const [refreshing, setRefreshing] = React.useState(false);
  const [savingAnnouncement, setSavingAnnouncement] = React.useState(false);
  const [savingRule, setSavingRule] = React.useState(false);
  const [evaluating, setEvaluating] = React.useState(false);
  const [notice, setNotice] = React.useState(null);
  const [feed, setFeed] = React.useState({
    summary: {},
    announcements: [],
    alerts: [],
    reminders: [],
  });
  const [alertSummary, setAlertSummary] = React.useState({
    open: 0,
    acknowledged: 0,
    resolved: 0,
    critical_open: 0,
    by_severity: {},
    recent: [],
  });
  const [events, setEvents] = React.useState([]);
  const [rules, setRules] = React.useState([]);
  const [announcementForm, setAnnouncementForm] = React.useState({
    title: "",
    body: "",
    priority: "Normal",
    audience_type: "All",
    is_pinned: false,
  });
  const [ruleForm, setRuleForm] = React.useState({
    id: null,
    name: "",
    rule_type: "QUEUE_READY_BACKLOG",
    severity: "WARNING",
    channel: "EMAIL",
    threshold: 1,
    is_active: true,
  });

  const flashNotice = React.useCallback((message, ok = true) => {
    setNotice({ message, ok });
    window.setTimeout(() => setNotice(null), 4000);
  }, []);

  const loadPage = React.useCallback(async (mode = "loading") => {
    if (mode === "loading") {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    try {
      const [feedResponse, summaryResponse, eventsResponse, rulesResponse] = await Promise.all([
        api.get("communication/alerts/feed/"),
        api.get("communication/alerts/events/summary/"),
        api.get("communication/alerts/events/", { params: { status: "OPEN" } }),
        api.get("communication/alerts/rules/"),
      ]);
      setFeed(feedResponse.data || { summary: {}, announcements: [], alerts: [], reminders: [] });
      setAlertSummary(summaryResponse.data || {});
      setEvents(coerceList(eventsResponse.data));
      setRules(coerceList(rulesResponse.data));
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to load alerts center.", false);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [flashNotice]);

  React.useEffect(() => {
    loadPage("loading");
  }, [loadPage]);

  async function createAnnouncement(event) {
    event.preventDefault();
    if (!announcementForm.title.trim() || !announcementForm.body.trim()) {
      flashNotice("Announcement title and message are required.", false);
      return;
    }
    setSavingAnnouncement(true);
    try {
      await api.post("communication/announcements/", announcementForm);
      setAnnouncementForm({
        title: "",
        body: "",
        priority: "Normal",
        audience_type: "All",
        is_pinned: false,
      });
      flashNotice("Announcement published.");
      await loadPage("refresh");
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to publish announcement.", false);
    } finally {
      setSavingAnnouncement(false);
    }
  }

  async function submitRule(event) {
    event.preventDefault();
    if (!ruleForm.name.trim()) {
      flashNotice("Rule name is required.", false);
      return;
    }
    setSavingRule(true);
    try {
      const payload = {
        name: ruleForm.name,
        rule_type: ruleForm.rule_type,
        severity: ruleForm.severity,
        channel: ruleForm.channel,
        threshold: Number(ruleForm.threshold) || 1,
        is_active: !!ruleForm.is_active,
      };
      if (ruleForm.id) {
        await api.patch(`communication/alerts/rules/${ruleForm.id}/`, payload);
      } else {
        await api.post("communication/alerts/rules/", payload);
      }
      setRuleForm({
        id: null,
        name: "",
        rule_type: "QUEUE_READY_BACKLOG",
        severity: "WARNING",
        channel: "EMAIL",
        threshold: 1,
        is_active: true,
      });
      flashNotice(ruleForm.id ? "Rule updated." : "Rule created.");
      await loadPage("refresh");
    } catch (error) {
      const errorPayload = error?.response?.data;
      const firstMessage =
        typeof errorPayload === "string"
          ? errorPayload
          : Object.values(errorPayload || {})[0] || "Failed to save alert rule.";
      flashNotice(Array.isArray(firstMessage) ? firstMessage[0] : firstMessage, false);
    } finally {
      setSavingRule(false);
    }
  }

  async function archiveRule(ruleId) {
    try {
      await api.delete(`communication/alerts/rules/${ruleId}/`);
      flashNotice("Rule archived.");
      await loadPage("refresh");
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to archive rule.", false);
    }
  }

  async function runEvaluation(ruleIds = []) {
    setEvaluating(true);
    try {
      const response = await api.post("communication/alerts/rules/evaluate/", {
        rule_ids: ruleIds,
      });
      const data = response.data || {};
      flashNotice(
        `Evaluation complete: ${data.rules_evaluated || 0} rules, ${data.triggered || 0} triggered, ${data.opened || 0} opened.`,
      );
      await loadPage("refresh");
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Rule evaluation failed.", false);
    } finally {
      setEvaluating(false);
    }
  }

  async function updateEventStatus(eventId, actionName) {
    try {
      await api.post(`communication/alerts/events/${eventId}/${actionName}/`, {});
      flashNotice(actionName === "acknowledge" ? "Alert acknowledged." : "Alert resolved.");
      await loadPage("refresh");
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to update alert.", false);
    }
  }

  if (loading) {
    return e.jsx("div", {
      className: "py-20 text-center text-slate-500",
      children: "Loading alerts center...",
    });
  }

  return e.jsxs("div", {
    className: "space-y-6",
    children: [
      notice &&
        e.jsx("div", {
          className: "rounded-2xl px-4 py-3 text-sm font-semibold",
          style: notice.ok
            ? {
                background: "rgba(16,185,129,0.15)",
                border: "1px solid rgba(16,185,129,0.30)",
                color: "#34d399",
              }
            : {
                background: "rgba(239,68,68,0.15)",
                border: "1px solid rgba(239,68,68,0.30)",
                color: "#fca5a5",
              },
          children: notice.message,
        }),
      e.jsx(PageHero, {
        badge: "ALERTS",
        badgeColor: "amber",
        title: "Alerts and Reminders Center",
        subtitle: "Live alert feed, stored alert events, rule management, and announcements.",
        icon: "!",
      }),
      e.jsxs("div", {
        className: "grid grid-cols-1 gap-4 md:grid-cols-4",
        children: [
          e.jsx(SummaryCard, {
            label: "Feed Total",
            value: feed.summary?.total || 0,
            accent: "#10b981",
          }),
          e.jsx(SummaryCard, {
            label: "Open Alerts",
            value: alertSummary.open || 0,
            accent: "#f59e0b",
          }),
          e.jsx(SummaryCard, {
            label: "Critical Open",
            value: alertSummary.critical_open || 0,
            accent: "#ef4444",
          }),
          e.jsx(SummaryCard, {
            label: "Acknowledged",
            value: alertSummary.acknowledged || 0,
            accent: "#38bdf8",
          }),
        ],
      }),
      e.jsxs("div", {
        className: "flex flex-wrap items-center gap-3",
        children: [
          e.jsx("button", {
            type: "button",
            onClick: () => loadPage("refresh"),
            className:
              "rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-white/[0.06]",
            children: refreshing ? "Refreshing..." : "Refresh",
          }),
          e.jsx("button", {
            type: "button",
            onClick: () => runEvaluation([]),
            disabled: evaluating,
            className:
              "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-bold text-slate-950 transition disabled:opacity-60",
            children: evaluating ? "Evaluating..." : "Evaluate Rules",
          }),
        ],
      }),
      e.jsxs("div", {
        className: "grid grid-cols-1 gap-6 xl:grid-cols-3",
        children: [
          e.jsxs("section", {
            className: "space-y-4 xl:col-span-2",
            children: [
              e.jsxs("div", {
                className: "rounded-3xl p-5",
                style: panelStyle,
                children: [
                  e.jsx("h2", {
                    className: "text-lg font-display font-bold text-white",
                    children: "Backend Alerts Feed",
                  }),
                  e.jsx("p", {
                    className: "mt-1 text-sm text-slate-400",
                    children:
                      "Announcements, stored system alerts, and operational reminders now come directly from communication backend APIs.",
                  }),
                  e.jsxs("div", {
                    className: "mt-5 grid grid-cols-1 gap-4 lg:grid-cols-3",
                    children: [
                      e.jsxs("div", {
                        className: "space-y-3",
                        children: [
                          e.jsx("h3", {
                            className: "text-sm font-bold text-amber-300",
                            children: "Announcements",
                          }),
                          feed.announcements?.length
                            ? feed.announcements.map((row) => {
                                const tone = toneForPriority(row.priority);
                                return e.jsxs(
                                  "div",
                                  {
                                    className: "rounded-2xl border p-4",
                                    style: tone,
                                    children: [
                                      e.jsxs("div", {
                                        className: "flex items-center gap-2",
                                        children: [
                                          e.jsx("p", {
                                            className: "text-sm font-bold text-white",
                                            children: row.title,
                                          }),
                                          row.is_pinned &&
                                            e.jsx("span", {
                                              className: "rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold text-white",
                                              children: "Pinned",
                                            }),
                                        ],
                                      }),
                                      e.jsx("p", {
                                        className: "mt-2 text-xs text-slate-200",
                                        children: row.message,
                                      }),
                                      e.jsxs("p", {
                                        className: "mt-3 text-[10px] uppercase tracking-[0.16em] text-slate-300",
                                        children: [row.priority, " - ", row.audience_type],
                                      }),
                                    ],
                                  },
                                  row.id,
                                );
                              })
                            : e.jsx("p", {
                                className: "text-sm text-slate-500",
                                children: "No active announcements.",
                              }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-3",
                        children: [
                          e.jsx("h3", {
                            className: "text-sm font-bold text-rose-300",
                            children: "System Alerts",
                          }),
                          feed.alerts?.length
                            ? feed.alerts.map((row) => {
                                const tone = toneForSeverity(row.severity);
                                return e.jsxs(
                                  "div",
                                  {
                                    className: "rounded-2xl border p-4",
                                    style: tone,
                                    children: [
                                      e.jsx("p", {
                                        className: "text-sm font-bold text-white",
                                        children: row.title,
                                      }),
                                      e.jsx("p", {
                                        className: "mt-2 text-xs text-slate-200",
                                        children: row.message,
                                      }),
                                      e.jsxs("p", {
                                        className: "mt-3 text-[10px] uppercase tracking-[0.16em] text-slate-300",
                                        children: [row.severity, " - ", row.channel || "ALL"],
                                      }),
                                    ],
                                  },
                                  row.id,
                                );
                              })
                            : e.jsx("p", {
                                className: "text-sm text-slate-500",
                                children: "No open system alerts.",
                              }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-3",
                        children: [
                          e.jsx("h3", {
                            className: "text-sm font-bold text-sky-300",
                            children: "Operational Reminders",
                          }),
                          feed.reminders?.length
                            ? feed.reminders.map((row) =>
                                e.jsxs(
                                  "div",
                                  {
                                    className: "rounded-2xl border border-sky-500/20 bg-sky-500/10 p-4",
                                    children: [
                                      e.jsx("p", {
                                        className: "text-sm font-bold text-white",
                                        children: row.title,
                                      }),
                                      e.jsx("p", {
                                        className: "mt-2 text-xs text-slate-200",
                                        children: row.message,
                                      }),
                                      row.action_path &&
                                        e.jsx("p", {
                                          className: "mt-3 text-[10px] uppercase tracking-[0.16em] text-sky-200",
                                          children: row.action_path,
                                        }),
                                    ],
                                  },
                                  row.id,
                                ),
                              )
                            : e.jsx("p", {
                                className: "text-sm text-slate-500",
                                children: "No current reminders.",
                              }),
                        ],
                      }),
                    ],
                  }),
                ],
              }),
              e.jsxs("div", {
                className: "rounded-3xl p-5",
                style: panelStyle,
                children: [
                  e.jsx("h2", {
                    className: "text-lg font-display font-bold text-white",
                    children: "Stored Alert Events",
                  }),
                  e.jsx("p", {
                    className: "mt-1 text-sm text-slate-400",
                    children:
                      "Operators can acknowledge or resolve alert events without leaving the communication module.",
                  }),
                  e.jsx("div", {
                    className: "mt-4 space-y-3",
                    children:
                      events.length > 0
                        ? events.map((row) => {
                            const tone = toneForSeverity(row.severity);
                            return e.jsxs(
                              "div",
                              {
                                className: "rounded-2xl border p-4",
                                style: tone,
                                children: [
                                  e.jsxs("div", {
                                    className: "flex flex-wrap items-start justify-between gap-3",
                                    children: [
                                      e.jsxs("div", {
                                        className: "min-w-0 flex-1",
                                        children: [
                                          e.jsxs("div", {
                                            className: "flex flex-wrap items-center gap-2",
                                            children: [
                                              e.jsx("p", {
                                                className: "text-sm font-bold text-white",
                                                children: row.title,
                                              }),
                                              e.jsx("span", {
                                                className: "rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold text-white",
                                                children: row.status,
                                              }),
                                              row.channel &&
                                                e.jsx("span", {
                                                  className: "rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold text-slate-200",
                                                  children: row.channel,
                                                }),
                                            ],
                                          }),
                                          e.jsx("p", {
                                            className: "mt-2 text-xs text-slate-200",
                                            children: row.details,
                                          }),
                                          e.jsxs("p", {
                                            className: "mt-3 text-[10px] uppercase tracking-[0.16em] text-slate-300",
                                            children: [
                                              row.rule_name || "Rule",
                                              " - ",
                                              formatDateTime(row.last_triggered_at),
                                            ],
                                          }),
                                        ],
                                      }),
                                      e.jsxs("div", {
                                        className: "flex flex-wrap gap-2",
                                        children: [
                                          row.status === "OPEN" &&
                                            e.jsx("button", {
                                              type: "button",
                                              onClick: () => updateEventStatus(row.id, "acknowledge"),
                                              className:
                                                "rounded-xl border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs font-semibold text-amber-100 transition hover:bg-amber-300/20",
                                              children: "Acknowledge",
                                            }),
                                          row.status !== "RESOLVED" &&
                                            e.jsx("button", {
                                              type: "button",
                                              onClick: () => updateEventStatus(row.id, "resolve"),
                                              className:
                                                "rounded-xl border border-emerald-300/30 bg-emerald-300/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-300/20",
                                              children: "Resolve",
                                            }),
                                        ],
                                      }),
                                    ],
                                  }),
                                ],
                              },
                              row.id,
                            );
                          })
                        : e.jsx("p", {
                            className: "text-sm text-slate-500",
                            children: "No open stored alert events.",
                          }),
                  }),
                ],
              }),
            ],
          }),
          e.jsxs("section", {
            className: "space-y-6",
            children: [
              e.jsxs("form", {
                onSubmit: createAnnouncement,
                className: "rounded-3xl p-5 space-y-4",
                style: panelStyle,
                children: [
                  e.jsx("h2", {
                    className: "text-lg font-display font-bold text-white",
                    children: "Publish Announcement",
                  }),
                  e.jsx("input", {
                    className: inputClassName,
                    placeholder: "Announcement title",
                    value: announcementForm.title,
                    onChange: (event) =>
                      setAnnouncementForm((current) => ({ ...current, title: event.target.value })),
                  }),
                  e.jsx("textarea", {
                    rows: 4,
                    className: `${inputClassName} resize-none`,
                    placeholder: "Message for parents, staff, or students",
                    value: announcementForm.body,
                    onChange: (event) =>
                      setAnnouncementForm((current) => ({ ...current, body: event.target.value })),
                  }),
                  e.jsxs("div", {
                    className: "grid grid-cols-2 gap-3",
                    children: [
                      e.jsxs("select", {
                        className: inputClassName,
                        value: announcementForm.priority,
                        onChange: (event) =>
                          setAnnouncementForm((current) => ({ ...current, priority: event.target.value })),
                        children: [
                          e.jsx("option", { value: "Normal", children: "Normal" }),
                          e.jsx("option", { value: "Important", children: "Important" }),
                          e.jsx("option", { value: "Urgent", children: "Urgent" }),
                        ],
                      }),
                      e.jsxs("select", {
                        className: inputClassName,
                        value: announcementForm.audience_type,
                        onChange: (event) =>
                          setAnnouncementForm((current) => ({ ...current, audience_type: event.target.value })),
                        children: [
                          e.jsx("option", { value: "All", children: "All" }),
                          e.jsx("option", { value: "Parents", children: "Parents" }),
                          e.jsx("option", { value: "Staff", children: "Staff" }),
                          e.jsx("option", { value: "Students", children: "Students" }),
                          e.jsx("option", { value: "Custom", children: "Custom" }),
                        ],
                      }),
                    ],
                  }),
                  e.jsxs("label", {
                    className: "flex items-center gap-2 text-sm text-slate-300",
                    children: [
                      e.jsx("input", {
                        type: "checkbox",
                        checked: announcementForm.is_pinned,
                        onChange: (event) =>
                          setAnnouncementForm((current) => ({ ...current, is_pinned: event.target.checked })),
                      }),
                      e.jsx("span", { children: "Pin this announcement" }),
                    ],
                  }),
                  e.jsx("button", {
                    type: "submit",
                    disabled: savingAnnouncement,
                    className:
                      "w-full rounded-xl bg-emerald-500 px-4 py-2.5 text-sm font-bold text-slate-950 transition disabled:opacity-60",
                    children: savingAnnouncement ? "Publishing..." : "Publish Announcement",
                  }),
                ],
              }),
              e.jsxs("form", {
                onSubmit: submitRule,
                className: "rounded-3xl p-5 space-y-4",
                style: panelStyle,
                children: [
                  e.jsxs("div", {
                    className: "flex items-center justify-between gap-3",
                    children: [
                      e.jsx("h2", {
                        className: "text-lg font-display font-bold text-white",
                        children: ruleForm.id ? "Edit Alert Rule" : "Create Alert Rule",
                      }),
                      ruleForm.id &&
                        e.jsx("button", {
                          type: "button",
                          onClick: () =>
                            setRuleForm({
                              id: null,
                              name: "",
                              rule_type: "QUEUE_READY_BACKLOG",
                              severity: "WARNING",
                              channel: "EMAIL",
                              threshold: 1,
                              is_active: true,
                            }),
                          className: "text-xs font-semibold text-slate-400 hover:text-white",
                          children: "Reset",
                        }),
                    ],
                  }),
                  e.jsx("input", {
                    className: inputClassName,
                    placeholder: "Rule name",
                    value: ruleForm.name,
                    onChange: (event) => setRuleForm((current) => ({ ...current, name: event.target.value })),
                  }),
                  e.jsxs("select", {
                    className: inputClassName,
                    value: ruleForm.rule_type,
                    onChange: (event) => setRuleForm((current) => ({ ...current, rule_type: event.target.value })),
                    children: [
                      e.jsx("option", { value: "QUEUE_READY_BACKLOG", children: "Queue ready backlog" }),
                      e.jsx("option", { value: "QUEUE_FAILED_ITEMS", children: "Queue failed items" }),
                      e.jsx("option", { value: "QUEUE_RETRYING_BACKLOG", children: "Queue retrying backlog" }),
                      e.jsx("option", { value: "GATEWAY_UNCONFIGURED", children: "Gateway unconfigured" }),
                    ],
                  }),
                  e.jsxs("div", {
                    className: "grid grid-cols-2 gap-3",
                    children: [
                      e.jsxs("select", {
                        className: inputClassName,
                        value: ruleForm.severity,
                        onChange: (event) => setRuleForm((current) => ({ ...current, severity: event.target.value })),
                        children: [
                          e.jsx("option", { value: "INFO", children: "Info" }),
                          e.jsx("option", { value: "WARNING", children: "Warning" }),
                          e.jsx("option", { value: "CRITICAL", children: "Critical" }),
                        ],
                      }),
                      e.jsxs("select", {
                        className: inputClassName,
                        value: ruleForm.channel,
                        onChange: (event) => setRuleForm((current) => ({ ...current, channel: event.target.value })),
                        children: [
                          e.jsx("option", { value: "", children: "All channels" }),
                          e.jsx("option", { value: "EMAIL", children: "Email" }),
                          e.jsx("option", { value: "SMS", children: "SMS" }),
                          e.jsx("option", { value: "WHATSAPP", children: "WhatsApp" }),
                          e.jsx("option", { value: "PUSH", children: "Push" }),
                        ],
                      }),
                    ],
                  }),
                  e.jsx("input", {
                    type: "number",
                    min: 1,
                    className: inputClassName,
                    value: ruleForm.threshold,
                    onChange: (event) =>
                      setRuleForm((current) => ({
                        ...current,
                        threshold: Number(event.target.value) || 1,
                      })),
                  }),
                  e.jsxs("label", {
                    className: "flex items-center gap-2 text-sm text-slate-300",
                    children: [
                      e.jsx("input", {
                        type: "checkbox",
                        checked: !!ruleForm.is_active,
                        onChange: (event) => setRuleForm((current) => ({ ...current, is_active: event.target.checked })),
                      }),
                      e.jsx("span", { children: "Rule is active" }),
                    ],
                  }),
                  e.jsx("button", {
                    type: "submit",
                    disabled: savingRule,
                    className:
                      "w-full rounded-xl bg-sky-500 px-4 py-2.5 text-sm font-bold text-slate-950 transition disabled:opacity-60",
                    children: savingRule ? "Saving..." : ruleForm.id ? "Update Rule" : "Create Rule",
                  }),
                ],
              }),
              e.jsxs("div", {
                className: "rounded-3xl p-5",
                style: panelStyle,
                children: [
                  e.jsx("h2", {
                    className: "text-lg font-display font-bold text-white",
                    children: "Rule Registry",
                  }),
                  e.jsx("div", {
                    className: "mt-4 space-y-3",
                    children:
                      rules.length > 0
                        ? rules.map((row) =>
                            e.jsxs(
                              "div",
                              {
                                className: "rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4",
                                children: [
                                  e.jsxs("div", {
                                    className: "flex items-start justify-between gap-3",
                                    children: [
                                      e.jsxs("div", {
                                        className: "min-w-0 flex-1",
                                        children: [
                                          e.jsx("p", {
                                            className: "text-sm font-bold text-white",
                                            children: row.name,
                                          }),
                                          e.jsxs("p", {
                                            className: "mt-1 text-xs text-slate-400",
                                            children: [
                                              row.rule_type,
                                              " - ",
                                              row.channel || "ALL",
                                              " - threshold ",
                                              row.threshold,
                                            ],
                                          }),
                                        ],
                                      }),
                                      e.jsx("span", {
                                        className: "rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold text-slate-200",
                                        children: row.severity,
                                      }),
                                    ],
                                  }),
                                  e.jsxs("div", {
                                    className: "mt-4 flex flex-wrap gap-2",
                                    children: [
                                      e.jsx("button", {
                                        type: "button",
                                        onClick: () =>
                                          setRuleForm({
                                            id: row.id,
                                            name: row.name || "",
                                            rule_type: row.rule_type || "QUEUE_READY_BACKLOG",
                                            severity: row.severity || "WARNING",
                                            channel: row.channel || "",
                                            threshold: row.threshold || 1,
                                            is_active: row.is_active !== false,
                                          }),
                                        className:
                                          "rounded-xl border border-sky-400/30 bg-sky-400/10 px-3 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-400/20",
                                        children: "Edit",
                                      }),
                                      e.jsx("button", {
                                        type: "button",
                                        onClick: () => runEvaluation([row.id]),
                                        className:
                                          "rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-400/20",
                                        children: "Evaluate",
                                      }),
                                      e.jsx("button", {
                                        type: "button",
                                        onClick: () => archiveRule(row.id),
                                        className:
                                          "rounded-xl border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs font-semibold text-rose-200 transition hover:bg-rose-400/20",
                                        children: "Archive",
                                      }),
                                    ],
                                  }),
                                ],
                              },
                              row.id,
                            ),
                          )
                        : e.jsx("p", {
                            className: "text-sm text-slate-500",
                            children: "No alert rules configured.",
                          }),
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

export { AlertsCenterPage as default };
