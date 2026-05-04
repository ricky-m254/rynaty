import { r as React, b as api, j as e } from "./index-D7ltaYVC.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.08)",
};

const inputClassName =
  "w-full rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-400";

function coerceList(payload) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (Array.isArray(payload?.results)) {
    return payload.results;
  }
  return [];
}

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

const typeOptions = ["System", "Financial", "Academic", "Behavioral", "HR", "Event", "Emergency"];
const priorityOptions = ["Informational", "Important", "Urgent"];

const priorityTone = {
  Informational: {
    background: "rgba(59,130,246,0.10)",
    borderColor: "rgba(59,130,246,0.30)",
    color: "#93c5fd",
  },
  Important: {
    background: "rgba(245,158,11,0.10)",
    borderColor: "rgba(245,158,11,0.30)",
    color: "#fcd34d",
  },
  Urgent: {
    background: "rgba(239,68,68,0.10)",
    borderColor: "rgba(239,68,68,0.30)",
    color: "#fca5a5",
  },
};

function toneForPriority(priority) {
  return priorityTone[String(priority || "").trim()] || priorityTone.Informational;
}

function NotificationsPage() {
  const [loading, setLoading] = React.useState(true);
  const [notifications, setNotifications] = React.useState([]);
  const [preferences, setPreferences] = React.useState([]);
  const [recipients, setRecipients] = React.useState([]);
  const [isAdminMode, setIsAdminMode] = React.useState(false);
  const [unreadCount, setUnreadCount] = React.useState(0);
  const [recipientQuery, setRecipientQuery] = React.useState("");
  const [filters, setFilters] = React.useState({
    readState: "all",
    notificationType: "",
    recipientId: "",
    adminScope: false,
  });
  const [submitting, setSubmitting] = React.useState(false);
  const [readAllBusy, setReadAllBusy] = React.useState(false);
  const [notice, setNotice] = React.useState(null);
  const [draft, setDraft] = React.useState({
    title: "",
    message: "",
    notification_type: "System",
    priority: "Informational",
    action_url: "",
    recipient_ids: [],
  });

  const flashNotice = React.useCallback((message, ok = true) => {
    setNotice({ message, ok });
    window.setTimeout(() => setNotice(null), 4000);
  }, []);

  const loadRecipients = React.useCallback(
    async (query = "") => {
      try {
        const response = await api.get("communication/notifications/recipients/", {
          params: query ? { q: query } : undefined,
        });
        setRecipients(coerceList(response.data));
        setIsAdminMode(true);
      } catch {
        setRecipients([]);
        setIsAdminMode(false);
      }
    },
    [],
  );

  const loadUnreadCount = React.useCallback(async () => {
    try {
      const response = await api.get("communication/notifications/unread-count/");
      setUnreadCount(Number(response.data?.unread_count || 0));
    } catch {
      setUnreadCount(0);
    }
  }, []);

  const loadPreferences = React.useCallback(async () => {
    try {
      const response = await api.get("communication/notification-preferences/");
      setPreferences(coerceList(response.data));
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to load notification preferences.", false);
    }
  }, [flashNotice]);

  const loadNotifications = React.useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.notificationType) {
        params.notification_type = filters.notificationType;
      }
      if (filters.readState === "read") {
        params.is_read = true;
      } else if (filters.readState === "unread") {
        params.is_read = false;
      }
      if (isAdminMode && filters.adminScope) {
        params.scope = true;
        if (filters.recipientId) {
          params.recipient_id = filters.recipientId;
        }
      }
      const response = await api.get("communication/notifications/", { params });
      setNotifications(coerceList(response.data));
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to load notifications.", false);
    } finally {
      setLoading(false);
    }
  }, [filters.adminScope, filters.notificationType, filters.readState, filters.recipientId, flashNotice, isAdminMode]);

  React.useEffect(() => {
    Promise.all([loadUnreadCount(), loadPreferences(), loadRecipients("")]).finally(() => {
      loadNotifications();
    });
  }, [loadNotifications, loadPreferences, loadRecipients, loadUnreadCount]);

  React.useEffect(() => {
    const handle = window.setTimeout(() => {
      if (isAdminMode) {
        loadRecipients(recipientQuery);
      }
    }, 250);
    return () => window.clearTimeout(handle);
  }, [recipientQuery, loadRecipients, isAdminMode]);

  async function submitNotification(event) {
    event.preventDefault();
    if (!draft.title.trim() || !draft.message.trim()) {
      flashNotice("Title and message are required.", false);
      return;
    }
    setSubmitting(true);
    try {
      const body = {
        title: draft.title,
        message: draft.message,
        notification_type: draft.notification_type,
        priority: draft.priority,
        action_url: draft.action_url,
      };
      if (isAdminMode && draft.recipient_ids.length > 0) {
        body.recipient_ids = draft.recipient_ids;
      }
      const response = await api.post("communication/notifications/", body);
      const createdRows = coerceList(response.data);
      setDraft({
        title: "",
        message: "",
        notification_type: "System",
        priority: "Informational",
        action_url: "",
        recipient_ids: [],
      });
      flashNotice(`Created ${response.data?.created || createdRows.length || 1} notification(s).`);
      await Promise.all([loadNotifications(), loadUnreadCount()]);
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to create notification.", false);
    } finally {
      setSubmitting(false);
    }
  }

  async function markRead(notificationId) {
    try {
      await api.patch(`communication/notifications/${notificationId}/read/`, {});
      await Promise.all([loadNotifications(), loadUnreadCount()]);
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to mark notification as read.", false);
    }
  }

  async function deleteNotification(notificationId) {
    try {
      await api.delete(`communication/notifications/${notificationId}/`);
      flashNotice("Notification removed.");
      await Promise.all([loadNotifications(), loadUnreadCount()]);
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to delete notification.", false);
    }
  }

  async function readAll() {
    setReadAllBusy(true);
    try {
      const response = await api.post("communication/notifications/read-all/", {});
      flashNotice(`Marked ${response.data?.updated || 0} notifications as read.`);
      await Promise.all([loadNotifications(), loadUnreadCount()]);
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to mark all notifications as read.", false);
    } finally {
      setReadAllBusy(false);
    }
  }

  async function savePreference(row) {
    try {
      await api.patch("communication/notification-preferences/", {
        notification_type: row.notification_type,
        channel_in_app: !!row.channel_in_app,
        channel_email: !!row.channel_email,
        channel_sms: !!row.channel_sms,
        channel_push: !!row.channel_push,
        quiet_hours_start: row.quiet_hours_start || null,
        quiet_hours_end: row.quiet_hours_end || null,
      });
      flashNotice(`Preferences updated for ${row.notification_type}.`);
      await loadPreferences();
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to save preference.", false);
    }
  }

  function toggleRecipient(recipientId) {
    setDraft((current) => {
      const existing = new Set(current.recipient_ids);
      if (existing.has(recipientId)) {
        existing.delete(recipientId);
      } else {
        existing.add(recipientId);
      }
      return {
        ...current,
        recipient_ids: Array.from(existing),
      };
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
        badge: "NOTIFICATIONS",
        badgeColor: "amber",
        title: "Notification Center",
        subtitle: "Unread counts, bulk read actions, admin recipient lookup, scoped review, and delivery preferences.",
        icon: "N",
      }),
      e.jsxs("div", {
        className: "grid grid-cols-1 gap-6 xl:grid-cols-3",
        children: [
          e.jsxs("section", {
            className: "space-y-6 xl:col-span-2",
            children: [
              e.jsxs("div", {
                className: "rounded-3xl p-5",
                style: panelStyle,
                children: [
                  e.jsxs("div", {
                    className: "flex flex-wrap items-center justify-between gap-3",
                    children: [
                      e.jsxs("div", {
                        children: [
                          e.jsx("h2", {
                            className: "text-lg font-display font-bold text-white",
                            children: "Notification Activity",
                          }),
                          e.jsxs("p", {
                            className: "mt-1 text-sm text-slate-400",
                            children: [
                              "Unread count: ",
                              e.jsx("span", {
                                className: "font-semibold text-white",
                                children: unreadCount,
                              }),
                            ],
                          }),
                        ],
                      }),
                      e.jsx("button", {
                        type: "button",
                        onClick: readAll,
                        disabled: readAllBusy,
                        className:
                          "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-bold text-slate-950 transition disabled:opacity-60",
                        children: readAllBusy ? "Updating..." : "Mark Visible as Read",
                      }),
                    ],
                  }),
                  e.jsxs("div", {
                    className: "mt-5 grid grid-cols-1 gap-3 md:grid-cols-4",
                    children: [
                      e.jsxs("select", {
                        className: inputClassName,
                        value: filters.readState,
                        onChange: (event) =>
                          setFilters((current) => ({ ...current, readState: event.target.value })),
                        children: [
                          e.jsx("option", { value: "all", children: "All states" }),
                          e.jsx("option", { value: "unread", children: "Unread" }),
                          e.jsx("option", { value: "read", children: "Read" }),
                        ],
                      }),
                      e.jsxs("select", {
                        className: inputClassName,
                        value: filters.notificationType,
                        onChange: (event) =>
                          setFilters((current) => ({ ...current, notificationType: event.target.value })),
                        children: [
                          e.jsx("option", { value: "", children: "All types" }),
                          ...typeOptions.map((type) =>
                            e.jsx("option", { value: type, children: type }, type),
                          ),
                        ],
                      }),
                      isAdminMode &&
                        e.jsx("input", {
                          className: inputClassName,
                          placeholder: "Search recipients",
                          value: recipientQuery,
                          onChange: (event) => setRecipientQuery(event.target.value),
                        }),
                      isAdminMode &&
                        e.jsxs("select", {
                          className: inputClassName,
                          value: filters.recipientId,
                          onChange: (event) =>
                            setFilters((current) => ({ ...current, recipientId: event.target.value })),
                          children: [
                            e.jsx("option", { value: "", children: "All recipients" }),
                            ...recipients.map((row) =>
                              e.jsx(
                                "option",
                                { value: row.id, children: row.label || row.username || row.email || row.id },
                                row.id,
                              ),
                            ),
                          ],
                        }),
                    ],
                  }),
                  isAdminMode &&
                    e.jsxs("label", {
                      className: "mt-4 flex items-center gap-2 text-sm text-slate-300",
                      children: [
                        e.jsx("input", {
                          type: "checkbox",
                          checked: !!filters.adminScope,
                          onChange: (event) =>
                            setFilters((current) => ({ ...current, adminScope: event.target.checked })),
                        }),
                        e.jsx("span", {
                          children: "Use admin scope to inspect tenant-wide notifications",
                        }),
                      ],
                    }),
                  e.jsx("div", {
                    className: "mt-5 space-y-3",
                    children: loading
                      ? e.jsx("p", {
                          className: "text-sm text-slate-500",
                          children: "Loading notifications...",
                        })
                      : notifications.length > 0
                      ? notifications.map((row) => {
                          const tone = toneForPriority(row.priority);
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
                                              children: row.notification_type,
                                            }),
                                            e.jsx("span", {
                                              className: "rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold text-slate-200",
                                              children: row.is_read ? "Read" : "Unread",
                                            }),
                                          ],
                                        }),
                                        e.jsx("p", {
                                          className: "mt-2 text-sm text-slate-200",
                                          children: row.message,
                                        }),
                                        e.jsxs("p", {
                                          className: "mt-3 text-[11px] text-slate-300",
                                          children: [
                                            row.recipient_name || "Current user",
                                            " - ",
                                            formatDateTime(row.sent_at),
                                          ],
                                        }),
                                        row.action_url &&
                                          e.jsx("p", {
                                            className: "mt-1 text-[11px] text-sky-200",
                                            children: row.action_url,
                                          }),
                                      ],
                                    }),
                                    e.jsxs("div", {
                                      className: "flex flex-wrap gap-2",
                                      children: [
                                        !row.is_read &&
                                          e.jsx("button", {
                                            type: "button",
                                            onClick: () => markRead(row.id),
                                            className:
                                              "rounded-xl border border-emerald-300/30 bg-emerald-300/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-300/20",
                                            children: "Mark read",
                                          }),
                                        e.jsx("button", {
                                          type: "button",
                                          onClick: () => deleteNotification(row.id),
                                          className:
                                            "rounded-xl border border-rose-300/30 bg-rose-300/10 px-3 py-2 text-xs font-semibold text-rose-100 transition hover:bg-rose-300/20",
                                          children: "Delete",
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
                          children: "No notifications match the active filters.",
                        }),
                  }),
                ],
              }),
              e.jsxs("div", {
                className: "rounded-3xl p-5",
                style: panelStyle,
                children: [
                  e.jsx("h2", {
                    className: "text-lg font-display font-bold text-white",
                    children: "Notification Preferences",
                  }),
                  e.jsx("p", {
                    className: "mt-1 text-sm text-slate-400",
                    children:
                      "Each preference row uses the communication notification-preferences endpoint, including quiet-hours fields.",
                  }),
                  e.jsx("div", {
                    className: "mt-5 space-y-4",
                    children: preferences.map((row) =>
                      e.jsxs(
                        "div",
                        {
                          className: "rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4",
                          children: [
                            e.jsx("p", {
                              className: "text-sm font-bold text-white",
                              children: row.notification_type,
                            }),
                            e.jsxs("div", {
                              className: "mt-3 grid grid-cols-2 gap-3 md:grid-cols-4",
                              children: [
                                ["channel_in_app", "In-app"],
                                ["channel_email", "Email"],
                                ["channel_sms", "SMS"],
                                ["channel_push", "Push"],
                              ].map(([fieldName, label]) =>
                                e.jsxs(
                                  "label",
                                  {
                                    className: "flex items-center gap-2 text-sm text-slate-300",
                                    children: [
                                      e.jsx("input", {
                                        type: "checkbox",
                                        checked: !!row[fieldName],
                                        onChange: (event) =>
                                          setPreferences((current) =>
                                            current.map((candidate) =>
                                              candidate.id === row.id
                                                ? { ...candidate, [fieldName]: event.target.checked }
                                                : candidate,
                                            ),
                                          ),
                                      }),
                                      e.jsx("span", { children: label }),
                                    ],
                                  },
                                  fieldName,
                                ),
                              ),
                            }),
                            e.jsxs("div", {
                              className: "mt-4 grid grid-cols-1 gap-3 md:grid-cols-3",
                              children: [
                                e.jsxs("div", {
                                  children: [
                                    e.jsx("label", {
                                      className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                                      children: "Quiet start",
                                    }),
                                    e.jsx("input", {
                                      type: "time",
                                      className: inputClassName,
                                      value: row.quiet_hours_start || "",
                                      onChange: (event) =>
                                        setPreferences((current) =>
                                          current.map((candidate) =>
                                            candidate.id === row.id
                                              ? { ...candidate, quiet_hours_start: event.target.value }
                                              : candidate,
                                          ),
                                        ),
                                    }),
                                  ],
                                }),
                                e.jsxs("div", {
                                  children: [
                                    e.jsx("label", {
                                      className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                                      children: "Quiet end",
                                    }),
                                    e.jsx("input", {
                                      type: "time",
                                      className: inputClassName,
                                      value: row.quiet_hours_end || "",
                                      onChange: (event) =>
                                        setPreferences((current) =>
                                          current.map((candidate) =>
                                            candidate.id === row.id
                                              ? { ...candidate, quiet_hours_end: event.target.value }
                                              : candidate,
                                          ),
                                        ),
                                    }),
                                  ],
                                }),
                                e.jsx("button", {
                                  type: "button",
                                  onClick: () => savePreference(row),
                                  className:
                                    "self-end rounded-xl bg-sky-500 px-4 py-2 text-sm font-bold text-slate-950 transition",
                                  children: "Save Preference",
                                }),
                              ],
                            }),
                          ],
                        },
                        row.id,
                      ),
                    ),
                  }),
                ],
              }),
            ],
          }),
          e.jsxs("section", {
            className: "space-y-6",
            children: [
              e.jsxs("form", {
                onSubmit: submitNotification,
                className: "rounded-3xl p-5 space-y-4",
                style: panelStyle,
                children: [
                  e.jsx("h2", {
                    className: "text-lg font-display font-bold text-white",
                    children: "Create Notification",
                  }),
                  e.jsx("input", {
                    className: inputClassName,
                    placeholder: "Title",
                    value: draft.title,
                    onChange: (event) => setDraft((current) => ({ ...current, title: event.target.value })),
                  }),
                  e.jsx("textarea", {
                    rows: 4,
                    className: `${inputClassName} resize-none`,
                    placeholder: "Message",
                    value: draft.message,
                    onChange: (event) => setDraft((current) => ({ ...current, message: event.target.value })),
                  }),
                  e.jsxs("div", {
                    className: "grid grid-cols-2 gap-3",
                    children: [
                      e.jsxs("select", {
                        className: inputClassName,
                        value: draft.notification_type,
                        onChange: (event) =>
                          setDraft((current) => ({ ...current, notification_type: event.target.value })),
                        children: typeOptions.map((type) =>
                          e.jsx("option", { value: type, children: type }, type),
                        ),
                      }),
                      e.jsxs("select", {
                        className: inputClassName,
                        value: draft.priority,
                        onChange: (event) =>
                          setDraft((current) => ({ ...current, priority: event.target.value })),
                        children: priorityOptions.map((priority) =>
                          e.jsx("option", { value: priority, children: priority }, priority),
                        ),
                      }),
                    ],
                  }),
                  e.jsx("input", {
                    className: inputClassName,
                    placeholder: "Action URL (optional)",
                    value: draft.action_url,
                    onChange: (event) => setDraft((current) => ({ ...current, action_url: event.target.value })),
                  }),
                  isAdminMode &&
                    e.jsxs("div", {
                      className: "space-y-3",
                      children: [
                        e.jsx("p", {
                          className: "text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                          children: "Admin Recipient Lookup",
                        }),
                        e.jsx("input", {
                          className: inputClassName,
                          placeholder: "Search users by name, username, or email",
                          value: recipientQuery,
                          onChange: (event) => setRecipientQuery(event.target.value),
                        }),
                        e.jsx("div", {
                          className: "max-h-56 space-y-2 overflow-y-auto pr-1",
                          children: recipients.length > 0
                            ? recipients.map((row) =>
                                e.jsxs(
                                  "label",
                                  {
                                    className: "flex items-start gap-2 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-sm text-slate-300",
                                    children: [
                                      e.jsx("input", {
                                        type: "checkbox",
                                        checked: draft.recipient_ids.includes(row.id),
                                        onChange: () => toggleRecipient(row.id),
                                      }),
                                      e.jsxs("div", {
                                        className: "min-w-0",
                                        children: [
                                          e.jsx("p", {
                                            className: "font-semibold text-white",
                                            children: row.label || row.username || row.email || row.id,
                                          }),
                                          row.role_name &&
                                            e.jsx("p", {
                                              className: "mt-1 text-[11px] text-slate-500",
                                              children: row.role_name,
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
                                children: "No recipient matches found.",
                              }),
                        }),
                      ],
                    }),
                  e.jsx("button", {
                    type: "submit",
                    disabled: submitting,
                    className:
                      "w-full rounded-xl bg-emerald-500 px-4 py-2.5 text-sm font-bold text-slate-950 transition disabled:opacity-60",
                    children: submitting ? "Sending..." : "Create Notification",
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

export { NotificationsPage as default };
