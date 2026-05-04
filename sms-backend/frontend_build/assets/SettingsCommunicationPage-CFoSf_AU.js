import { r as React, b as api, j as e } from "./index-D7ltaYVC.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.08)",
};

const inputClassName =
  "w-full rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-400";

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

function QueueMetric({ label, value }) {
  return e.jsxs(
    "div",
    {
      className: "rounded-xl border border-white/[0.06] bg-black/20 p-3",
      children: [
        e.jsx("p", {
          className: "text-[10px] uppercase tracking-[0.18em] text-slate-500",
          children: label,
        }),
        e.jsx("p", {
          className: "mt-1 text-lg font-bold text-white tabular-nums",
          children: value,
        }),
      ],
    },
  );
}

function GatewayStatusBadge({ configured }) {
  return e.jsx("span", {
    className: "rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-[0.14em]",
    style: configured
      ? {
          background: "rgba(16,185,129,0.12)",
          border: "1px solid rgba(16,185,129,0.25)",
          color: "#34d399",
        }
      : {
          background: "rgba(239,68,68,0.12)",
          border: "1px solid rgba(239,68,68,0.25)",
          color: "#fca5a5",
        },
    children: configured ? "Configured" : "Not configured",
  });
}

function SettingsCommunicationPage() {
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [testingChannel, setTestingChannel] = React.useState("");
  const [notice, setNotice] = React.useState(null);
  const [payload, setPayload] = React.useState(null);
  const [form, setForm] = React.useState({
    profile: {
      school_name: "",
      phone: "",
      email_address: "",
    },
    email: {
      sender_email: "",
      smtp_host: "",
      smtp_port: 587,
      smtp_user: "",
      smtp_password: "",
      smtp_use_tls: true,
    },
    sms: {
      provider: "",
      username: "",
      sender_id: "",
      api_key: "",
    },
    whatsapp: {
      phone_id: "",
      api_key: "",
    },
    push: {
      setting_key: "integrations.push",
      provider: "fcm",
      enabled: false,
      project_id: "",
      sender_id: "",
      server_key: "",
    },
  });

  const flashNotice = React.useCallback((message, ok = true) => {
    setNotice({ message, ok });
    window.setTimeout(() => setNotice(null), 4000);
  }, []);

  const syncFormFromPayload = React.useCallback((nextPayload) => {
    setPayload(nextPayload);
    setForm({
      profile: {
        school_name: nextPayload?.profile?.school_name || "",
        phone: nextPayload?.profile?.phone || "",
        email_address: nextPayload?.profile?.email_address || "",
      },
      email: {
        sender_email: nextPayload?.email?.settings?.sender_email || "",
        smtp_host: nextPayload?.email?.settings?.smtp_host || "",
        smtp_port: nextPayload?.email?.settings?.smtp_port || 587,
        smtp_user: nextPayload?.email?.settings?.smtp_user || "",
        smtp_password: "",
        smtp_use_tls: nextPayload?.email?.settings?.smtp_use_tls !== false,
      },
      sms: {
        provider: nextPayload?.sms?.settings?.provider || "",
        username: nextPayload?.sms?.settings?.username || "",
        sender_id: nextPayload?.sms?.settings?.sender_id || "",
        api_key: "",
      },
      whatsapp: {
        phone_id: nextPayload?.whatsapp?.settings?.phone_id || "",
        api_key: "",
      },
      push: {
        setting_key: nextPayload?.push?.settings?.setting_key || "integrations.push",
        provider: nextPayload?.push?.settings?.provider || "fcm",
        enabled: !!nextPayload?.push?.settings?.enabled,
        project_id: nextPayload?.push?.settings?.project_id || "",
        sender_id: nextPayload?.push?.settings?.sender_id || "",
        server_key: "",
      },
    });
  }, []);

  const loadSettings = React.useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("communication/settings/gateways/");
      syncFormFromPayload(response.data || {});
    } catch (error) {
      flashNotice(error?.response?.data?.detail || "Failed to load communication settings.", false);
    } finally {
      setLoading(false);
    }
  }, [flashNotice, syncFormFromPayload]);

  React.useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  function updateBlock(block, field, value) {
    setForm((current) => ({
      ...current,
      [block]: {
        ...current[block],
        [field]: value,
      },
    }));
  }

  async function saveSettings() {
    setSaving(true);
    try {
      const body = {
        profile: {
          school_name: form.profile.school_name,
          phone: form.profile.phone,
          email_address: form.profile.email_address,
        },
        email: {
          sender_email: form.email.sender_email,
          smtp_host: form.email.smtp_host,
          smtp_port: Number(form.email.smtp_port) || 587,
          smtp_user: form.email.smtp_user,
          smtp_use_tls: !!form.email.smtp_use_tls,
        },
        sms: {
          provider: form.sms.provider,
          username: form.sms.username,
          sender_id: form.sms.sender_id,
        },
        whatsapp: {
          phone_id: form.whatsapp.phone_id,
        },
        push: {
          setting_key: form.push.setting_key,
          provider: form.push.provider || "fcm",
          enabled: !!form.push.enabled,
          project_id: form.push.project_id,
          sender_id: form.push.sender_id,
        },
      };
      if (form.email.smtp_password) {
        body.email.smtp_password = form.email.smtp_password;
      }
      if (form.sms.api_key) {
        body.sms.api_key = form.sms.api_key;
      }
      if (form.whatsapp.api_key) {
        body.whatsapp.api_key = form.whatsapp.api_key;
      }
      if (form.push.server_key) {
        body.push.server_key = form.push.server_key;
      }
      const response = await api.patch("communication/settings/gateways/", body);
      syncFormFromPayload(response.data || {});
      flashNotice("Communication settings saved.");
    } catch (error) {
      const payloadMessage = error?.response?.data;
      const firstMessage =
        typeof payloadMessage === "string"
          ? payloadMessage
          : Object.values(payloadMessage || {})[0] || "Failed to save communication settings.";
      flashNotice(Array.isArray(firstMessage) ? firstMessage[0] : firstMessage, false);
    } finally {
      setSaving(false);
    }
  }

  async function testGateway(channel) {
    setTestingChannel(channel);
    try {
      const response = await api.post("communication/settings/gateways/test/", {
        channel,
      });
      flashNotice(response?.data?.message || `${channel} test succeeded.`);
      await loadSettings();
    } catch (error) {
      flashNotice(error?.response?.data?.error || `${channel} test failed.`, false);
    } finally {
      setTestingChannel("");
    }
  }

  if (loading || !payload) {
    return e.jsx("div", {
      className: "py-20 text-center text-slate-500",
      children: "Loading communication settings...",
    });
  }

  const gatewayCards = [
    { key: "email", label: "Email", accent: "#38bdf8", testChannel: "EMAIL" },
    { key: "sms", label: "SMS", accent: "#10b981", testChannel: "SMS" },
    { key: "whatsapp", label: "WhatsApp", accent: "#f59e0b", testChannel: "WHATSAPP" },
    { key: "push", label: "Push", accent: "#a78bfa", testChannel: "PUSH" },
  ];

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
        badge: "SETTINGS",
        badgeColor: "sky",
        title: "Communication Gateway Settings",
        subtitle: "Email, SMS, WhatsApp, and push now run on communication-owned settings and test endpoints.",
        icon: "CFG",
      }),
      e.jsxs("div", {
        className: "rounded-3xl p-5",
        style: panelStyle,
        children: [
          e.jsx("h2", {
            className: "text-lg font-display font-bold text-white",
            children: "School Contact Profile",
          }),
          e.jsx("p", {
            className: "mt-1 text-sm text-slate-400",
            children:
              "These values feed test routing and default sender context for communication channels.",
          }),
          e.jsxs("div", {
            className: "mt-5 grid grid-cols-1 gap-4 md:grid-cols-3",
            children: [
              e.jsxs("div", {
                children: [
                  e.jsx("label", {
                    className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                    children: "School Name",
                  }),
                  e.jsx("input", {
                    className: inputClassName,
                    value: form.profile.school_name,
                    onChange: (event) => updateBlock("profile", "school_name", event.target.value),
                  }),
                ],
              }),
              e.jsxs("div", {
                children: [
                  e.jsx("label", {
                    className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                    children: "Phone",
                  }),
                  e.jsx("input", {
                    className: inputClassName,
                    value: form.profile.phone,
                    onChange: (event) => updateBlock("profile", "phone", event.target.value),
                  }),
                ],
              }),
              e.jsxs("div", {
                children: [
                  e.jsx("label", {
                    className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                    children: "Email Address",
                  }),
                  e.jsx("input", {
                    className: inputClassName,
                    value: form.profile.email_address,
                    onChange: (event) => updateBlock("profile", "email_address", event.target.value),
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
      e.jsx("div", {
        className: "grid grid-cols-1 gap-6 xl:grid-cols-2",
        children: gatewayCards.map((card) => {
          const channel = payload[card.key] || {};
          const settings = channel.settings || {};
          const queue = channel.queue || {};
          const recentFailures = channel.recent_failures || [];
          const recentSuccesses = channel.recent_successes || [];
          return e.jsxs(
            "section",
            {
              className: "rounded-3xl p-5 space-y-5",
              style: panelStyle,
              children: [
                e.jsxs("div", {
                  className: "flex flex-wrap items-start justify-between gap-3",
                  children: [
                    e.jsxs("div", {
                      children: [
                        e.jsxs("div", {
                          className: "flex items-center gap-2",
                          children: [
                            e.jsx("h2", {
                              className: "text-lg font-display font-bold text-white",
                              children: card.label,
                            }),
                            e.jsx(GatewayStatusBadge, { configured: !!channel.configured }),
                          ],
                        }),
                        e.jsxs("p", {
                          className: "mt-1 text-sm text-slate-400",
                          children: [
                            "Provider: ",
                            e.jsx("span", {
                              className: "font-semibold text-slate-200",
                              children: channel.provider || "-",
                            }),
                          ],
                        }),
                        settings.server_key?.configured &&
                          e.jsx("p", {
                            className: "mt-1 text-xs text-slate-500",
                            children: `Secret: ${settings.server_key.preview || settings.server_key.masked_label}`,
                          }),
                        settings.api_key?.configured &&
                          e.jsx("p", {
                            className: "mt-1 text-xs text-slate-500",
                            children: `Secret: ${settings.api_key.preview || settings.api_key.masked_label}`,
                          }),
                        settings.smtp_password?.configured &&
                          e.jsx("p", {
                            className: "mt-1 text-xs text-slate-500",
                            children: `Secret: ${settings.smtp_password.preview || settings.smtp_password.masked_label}`,
                          }),
                      ],
                    }),
                    e.jsx("button", {
                      type: "button",
                      onClick: () => testGateway(card.testChannel),
                      disabled: testingChannel === card.testChannel,
                      className:
                        "rounded-xl px-4 py-2 text-sm font-bold text-slate-950 transition disabled:opacity-60",
                      style: { background: card.accent },
                      children: testingChannel === card.testChannel ? "Testing..." : `Test ${card.label}`,
                    }),
                  ],
                }),
                e.jsxs("div", {
                  className: "grid grid-cols-2 gap-3 md:grid-cols-4",
                  children: [
                    e.jsx(QueueMetric, { label: "Queued", value: queue.queued_total || 0 }),
                    e.jsx(QueueMetric, { label: "Ready", value: queue.ready || 0 }),
                    e.jsx(QueueMetric, { label: "Retrying", value: queue.retrying || 0 }),
                    e.jsx(QueueMetric, { label: "Failed", value: queue.failed || 0 }),
                  ],
                }),
                e.jsxs("div", {
                  className: "grid grid-cols-1 gap-4 md:grid-cols-2",
                  children: [
                    e.jsxs("div", {
                      className: "rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 text-sm text-slate-300",
                      children: [
                        e.jsx("p", {
                          className: "text-xs font-semibold uppercase tracking-[0.16em] text-slate-500",
                          children: "Live Health",
                        }),
                        e.jsxs("div", {
                          className: "mt-3 space-y-2",
                          children: [
                            e.jsxs("p", {
                              children: [
                                "Configured via settings: ",
                                e.jsx("span", {
                                  className: "font-semibold text-white",
                                  children: channel.settings_configured ? "Yes" : "No",
                                }),
                              ],
                            }),
                            e.jsxs("p", {
                              children: [
                                "Last success: ",
                                e.jsx("span", {
                                  className: "font-semibold text-white",
                                  children: formatDateTime(channel.last_success_at),
                                }),
                              ],
                            }),
                            e.jsxs("p", {
                              children: [
                                "Last failure: ",
                                e.jsx("span", {
                                  className: "font-semibold text-white",
                                  children: formatDateTime(channel.last_failure_at),
                                }),
                              ],
                            }),
                            channel.balance &&
                              e.jsxs("p", {
                                children: [
                                  "Balance: ",
                                  e.jsx("span", {
                                    className: "font-semibold text-white",
                                    children: channel.balance.balance || JSON.stringify(channel.balance),
                                  }),
                                ],
                              }),
                            typeof channel.active_devices === "number" &&
                              e.jsxs("p", {
                                children: [
                                  "Active devices: ",
                                  e.jsx("span", {
                                    className: "font-semibold text-white",
                                    children: channel.active_devices,
                                  }),
                                ],
                              }),
                          ],
                        }),
                      ],
                    }),
                    e.jsxs("div", {
                      className: "rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 text-sm text-slate-300",
                      children: [
                        e.jsx("p", {
                          className: "text-xs font-semibold uppercase tracking-[0.16em] text-slate-500",
                          children: "Recent Queue Outcomes",
                        }),
                        recentFailures.length === 0 && recentSuccesses.length === 0
                          ? e.jsx("p", {
                              className: "mt-3 text-slate-500",
                              children: "No recent queue samples recorded.",
                            })
                          : e.jsxs("div", {
                              className: "mt-3 space-y-3",
                              children: [
                                recentFailures.length > 0 &&
                                  e.jsxs("div", {
                                    children: [
                                      e.jsx("p", {
                                        className: "text-xs font-bold uppercase tracking-[0.14em] text-rose-300",
                                        children: "Recent failures",
                                      }),
                                      e.jsx("div", {
                                        className: "mt-2 space-y-2",
                                        children: recentFailures.map((row, index) =>
                                          e.jsxs(
                                            "div",
                                            {
                                              className: "rounded-xl border border-rose-400/20 bg-rose-400/10 p-3",
                                              children: [
                                                e.jsx("p", {
                                                  className: "text-xs font-semibold text-white",
                                                  children: row.recipient || row.title || row.provider_id || row.source_type || "Failure",
                                                }),
                                                e.jsx("p", {
                                                  className: "mt-1 text-[11px] text-rose-100",
                                                  children: row.last_error || row.failure_reason || row.status || "Failed",
                                                }),
                                              ],
                                            },
                                            `${card.key}-failure-${index}`,
                                          ),
                                        ),
                                      }),
                                    ],
                                  }),
                                recentSuccesses.length > 0 &&
                                  e.jsxs("div", {
                                    children: [
                                      e.jsx("p", {
                                        className: "text-xs font-bold uppercase tracking-[0.14em] text-emerald-300",
                                        children: "Recent successes",
                                      }),
                                      e.jsx("div", {
                                        className: "mt-2 space-y-2",
                                        children: recentSuccesses.map((row, index) =>
                                          e.jsxs(
                                            "div",
                                            {
                                              className: "rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-3",
                                              children: [
                                                e.jsx("p", {
                                                  className: "text-xs font-semibold text-white",
                                                  children: row.recipient || row.subject || row.title || row.provider_id || "Delivered",
                                                }),
                                                e.jsx("p", {
                                                  className: "mt-1 text-[11px] text-emerald-100",
                                                  children: row.status || formatDateTime(row.sent_at || row.delivered_at),
                                                }),
                                              ],
                                            },
                                            `${card.key}-success-${index}`,
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
                card.key === "email" &&
                  e.jsxs("div", {
                    className: "grid grid-cols-1 gap-4 md:grid-cols-2",
                    children: [
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "Sender Email",
                          }),
                          e.jsx("input", {
                            className: inputClassName,
                            value: form.email.sender_email,
                            onChange: (event) => updateBlock("email", "sender_email", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "SMTP Host",
                          }),
                          e.jsx("input", {
                            className: inputClassName,
                            value: form.email.smtp_host,
                            onChange: (event) => updateBlock("email", "smtp_host", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "SMTP Port",
                          }),
                          e.jsx("input", {
                            type: "number",
                            className: inputClassName,
                            value: form.email.smtp_port,
                            onChange: (event) => updateBlock("email", "smtp_port", Number(event.target.value) || 587),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "SMTP User",
                          }),
                          e.jsx("input", {
                            className: inputClassName,
                            value: form.email.smtp_user,
                            onChange: (event) => updateBlock("email", "smtp_user", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "New SMTP Password",
                          }),
                          e.jsx("input", {
                            type: "password",
                            className: inputClassName,
                            value: form.email.smtp_password,
                            placeholder: payload.email?.settings?.smtp_password?.configured ? "Leave blank to keep current secret" : "",
                            onChange: (event) => updateBlock("email", "smtp_password", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("label", {
                        className: "flex items-center gap-2 text-sm text-slate-300",
                        children: [
                          e.jsx("input", {
                            type: "checkbox",
                            checked: !!form.email.smtp_use_tls,
                            onChange: (event) => updateBlock("email", "smtp_use_tls", event.target.checked),
                          }),
                          e.jsx("span", { children: "Use TLS" }),
                        ],
                      }),
                    ],
                  }),
                card.key === "sms" &&
                  e.jsxs("div", {
                    className: "grid grid-cols-1 gap-4 md:grid-cols-2",
                    children: [
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "Provider",
                          }),
                          e.jsxs("select", {
                            className: inputClassName,
                            value: form.sms.provider,
                            onChange: (event) => updateBlock("sms", "provider", event.target.value),
                            children: [
                              e.jsx("option", { value: "", children: "Select provider" }),
                              e.jsx("option", { value: "africastalking", children: "Africa's Talking" }),
                              e.jsx("option", { value: "twilio", children: "Twilio" }),
                              e.jsx("option", { value: "infobip", children: "Infobip" }),
                              e.jsx("option", { value: "vonage", children: "Vonage" }),
                            ],
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "Username",
                          }),
                          e.jsx("input", {
                            className: inputClassName,
                            value: form.sms.username,
                            onChange: (event) => updateBlock("sms", "username", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "Sender ID",
                          }),
                          e.jsx("input", {
                            className: inputClassName,
                            value: form.sms.sender_id,
                            onChange: (event) => updateBlock("sms", "sender_id", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "New API Key",
                          }),
                          e.jsx("input", {
                            type: "password",
                            className: inputClassName,
                            value: form.sms.api_key,
                            placeholder: payload.sms?.settings?.api_key?.configured ? "Leave blank to keep current secret" : "",
                            onChange: (event) => updateBlock("sms", "api_key", event.target.value),
                          }),
                        ],
                      }),
                    ],
                  }),
                card.key === "whatsapp" &&
                  e.jsxs("div", {
                    className: "grid grid-cols-1 gap-4 md:grid-cols-2",
                    children: [
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "Phone Number ID",
                          }),
                          e.jsx("input", {
                            className: inputClassName,
                            value: form.whatsapp.phone_id,
                            onChange: (event) => updateBlock("whatsapp", "phone_id", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "New Access Token",
                          }),
                          e.jsx("input", {
                            type: "password",
                            className: inputClassName,
                            value: form.whatsapp.api_key,
                            placeholder: payload.whatsapp?.settings?.api_key?.configured ? "Leave blank to keep current secret" : "",
                            onChange: (event) => updateBlock("whatsapp", "api_key", event.target.value),
                          }),
                        ],
                      }),
                    ],
                  }),
                card.key === "push" &&
                  e.jsxs("div", {
                    className: "grid grid-cols-1 gap-4 md:grid-cols-2",
                    children: [
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "Setting Key",
                          }),
                          e.jsxs("select", {
                            className: inputClassName,
                            value: form.push.setting_key,
                            onChange: (event) => updateBlock("push", "setting_key", event.target.value),
                            children: [
                              e.jsx("option", { value: "integrations.push", children: "integrations.push" }),
                              e.jsx("option", { value: "integrations.fcm", children: "integrations.fcm" }),
                            ],
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "Provider",
                          }),
                          e.jsxs("select", {
                            className: inputClassName,
                            value: form.push.provider,
                            onChange: (event) => updateBlock("push", "provider", event.target.value),
                            children: [e.jsx("option", { value: "fcm", children: "FCM" })],
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "Project ID",
                          }),
                          e.jsx("input", {
                            className: inputClassName,
                            value: form.push.project_id,
                            onChange: (event) => updateBlock("push", "project_id", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "Sender ID",
                          }),
                          e.jsx("input", {
                            className: inputClassName,
                            value: form.push.sender_id,
                            onChange: (event) => updateBlock("push", "sender_id", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "md:col-span-2",
                        children: [
                          e.jsx("label", {
                            className: "mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400",
                            children: "New Server Key",
                          }),
                          e.jsx("input", {
                            type: "password",
                            className: inputClassName,
                            value: form.push.server_key,
                            placeholder: payload.push?.settings?.server_key?.configured ? "Leave blank to keep current secret" : "",
                            onChange: (event) => updateBlock("push", "server_key", event.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("label", {
                        className: "flex items-center gap-2 text-sm text-slate-300",
                        children: [
                          e.jsx("input", {
                            type: "checkbox",
                            checked: !!form.push.enabled,
                            onChange: (event) => updateBlock("push", "enabled", event.target.checked),
                          }),
                          e.jsx("span", { children: "Enable push gateway" }),
                        ],
                      }),
                    ],
                  }),
              ],
            },
            card.key,
          );
        }),
      }),
      e.jsx("div", {
        className: "flex justify-end",
        children: e.jsx("button", {
          type: "button",
          onClick: saveSettings,
          disabled: saving,
          className:
            "rounded-2xl bg-emerald-500 px-8 py-3 text-sm font-bold text-slate-950 transition disabled:opacity-60",
          children: saving ? "Saving..." : "Save Communication Settings",
        }),
      }),
    ],
  });
}

export { SettingsCommunicationPage as default };
