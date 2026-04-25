import { r, j as e } from "./index-D7ltaYVC.js";
import { p as d } from "./publicClient-BdJTy9AM.js";
import { n as v } from "./pagination-DjjjzeDo.js";
import { e as h } from "./forms-ZJa1TpnO.js";
import { P as D } from "./PageHero-Ct90nOAG.js";

const Y = {
  up: {
    shell: "border-emerald-400/30 bg-emerald-500/10",
    chip: "border border-emerald-400/30 bg-emerald-400/15 text-emerald-200",
    dot: "bg-emerald-300",
    title: "Database reachable",
    summary: "Public schema health probe is returning 200.",
  },
  down: {
    shell: "border-rose-400/30 bg-rose-500/10",
    chip: "border border-rose-400/30 bg-rose-400/15 text-rose-200",
    dot: "bg-rose-300",
    title: "Database unavailable",
    summary: "Public schema health probe is returning 503.",
  },
  unknown: {
    shell: "border-amber-400/30 bg-amber-500/10",
    chip: "border border-amber-400/30 bg-amber-400/15 text-amber-100",
    dot: "bg-amber-300",
    title: "Health signal unavailable",
    summary: "The monitoring page could not confirm the latest DB state.",
  },
  checking: {
    shell: "border-sky-400/30 bg-sky-500/10",
    chip: "border border-sky-400/30 bg-sky-400/15 text-sky-100",
    dot: "bg-sky-300",
    title: "Checking database health",
    summary: "Refreshing the public schema probe now.",
  },
};

function K(a) {
  if (!a) return "Not checked yet";
  return new Intl.DateTimeFormat(void 0, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(a);
}

function Q(a) {
  const c = a?.response?.status;
  const t = a?.response?.data;
  if (c === 503) {
    return {
      state: "down",
      detail: t?.detail || "Database unavailable",
      checkedAt: new Date(),
    };
  }
  return {
    state: "unknown",
    detail: h(a, "Unable to refresh database health."),
    checkedAt: new Date(),
  };
}

function Z({ health, checking, onRefresh }) {
  const a = Y[health.state] || Y.unknown;
  return e.jsxs("section", {
    className: `col-span-12 overflow-hidden rounded-3xl border shadow-[0_20px_60px_rgba(2,6,23,0.28)] ${a.shell}`,
    children: [
      e.jsxs("div", {
        className:
          "flex flex-col gap-5 border-b border-white/[0.08] px-6 py-5 lg:flex-row lg:items-start lg:justify-between",
        children: [
          e.jsxs("div", {
            className: "space-y-3",
            children: [
              e.jsxs("div", {
                className: `inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${a.chip}`,
                children: [
                  e.jsx("span", {
                    className: `h-2 w-2 rounded-full ${a.dot} ${checking ? "animate-pulse" : ""}`,
                  }),
                  "DB Health",
                ],
              }),
              e.jsx("h2", {
                className: "text-xl font-display font-semibold text-white",
                children: a.title,
              }),
              e.jsx("p", {
                className: "max-w-3xl text-sm leading-6 text-slate-200",
                children:
                  "This probe uses the same lightweight /api/health/ endpoint the platform login surface can read before authentication. It sits in normal page flow, so it never covers the platform chrome.",
              }),
            ],
          }),
          e.jsxs("div", {
            className: "flex flex-col gap-2 lg:items-end",
            children: [
              e.jsx("button", {
                type: "button",
                onClick: onRefresh,
                disabled: checking,
                className:
                  "rounded-xl border border-white/[0.12] bg-slate-950/55 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-white/25 hover:bg-slate-900/70 disabled:cursor-not-allowed disabled:opacity-70",
                children: checking ? "Refreshing..." : "Refresh DB health",
              }),
              e.jsxs("p", {
                className: "text-xs text-slate-300",
                children: ["Last checked ", K(health.checkedAt)],
              }),
            ],
          }),
        ],
      }),
      e.jsxs("div", {
        className: "grid gap-4 px-6 py-5 md:grid-cols-4",
        children: [
          e.jsxs("div", {
            className: "rounded-2xl bg-slate-950/35 px-4 py-4",
            children: [
              e.jsx("p", {
                className: "text-[11px] uppercase tracking-[0.18em] text-slate-400",
                children: "Current state",
              }),
              e.jsx("p", {
                className: "mt-2 text-lg font-semibold text-white",
                children: a.summary,
              }),
            ],
          }),
          e.jsxs("div", {
            className: "rounded-2xl bg-slate-950/35 px-4 py-4",
            children: [
              e.jsx("p", {
                className: "text-[11px] uppercase tracking-[0.18em] text-slate-400",
                children: "Endpoint",
              }),
              e.jsx("p", {
                className: "mt-2 font-mono text-xs text-slate-100",
                children: "/api/health/",
              }),
            ],
          }),
          e.jsxs("div", {
            className: "rounded-2xl bg-slate-950/35 px-4 py-4",
            children: [
              e.jsx("p", {
                className: "text-[11px] uppercase tracking-[0.18em] text-slate-400",
                children: "Schema impact",
              }),
              e.jsx("p", {
                className: "mt-2 text-sm leading-6 text-slate-100",
                children:
                  health.state === "up"
                    ? "Platform auth, monitoring, and global admin actions can reach the public schema."
                    : "Expect platform auth and platform-side API surfaces to fail until the public schema recovers.",
              }),
            ],
          }),
          e.jsxs("div", {
            className: "rounded-2xl bg-slate-950/35 px-4 py-4",
            children: [
              e.jsx("p", {
                className: "text-[11px] uppercase tracking-[0.18em] text-slate-400",
                children: "Probe detail",
              }),
              e.jsx("p", {
                className: "mt-2 text-sm leading-6 text-slate-100",
                children: health.detail,
              }),
            ],
          }),
        ],
      }),
    ],
  });
}

function W() {
  const [S, _] = r.useState([]);
  const [C, A] = r.useState([]);
  const [j, R] = r.useState([]);
  const [x, M] = r.useState(null);
  const [i, P] = r.useState(null);
  const [E, N] = r.useState(true);
  const [b, n] = r.useState(null);
  const [f, o] = r.useState(null);
  const [k, q] = r.useState({
    state: "checking",
    detail: "Running public schema health probe.",
    checkedAt: null,
  });
  const [F, G] = r.useState(false);
  const [a, p] = r.useState({ metric_key: "", tenant: "", value: "", payload: "{}" });
  const [l, c] = r.useState({ title: "", metric_key: "", tenant: "", severity: "WARNING", details: "" });

  const B = r.useCallback(async () => {
    G(true);
    try {
      const t = await d.get("/health/");
      q({
        state: t?.data?.db === "up" ? "up" : "unknown",
        detail:
          t?.data?.db === "up"
            ? "Public schema database is reachable."
            : "Health check returned an unexpected response.",
        checkedAt: new Date(),
      });
    } catch (t) {
      q(Q(t));
    } finally {
      G(false);
    }
  }, []);

  const u = r.useCallback(async () => {
    N(true);
    n(null);
    const [t, s, m, g, y, H] = await Promise.allSettled([
      d.get("/platform/monitoring/snapshots/"),
      d.get("/platform/monitoring/alerts/"),
      d.get("/platform/tenants/"),
      d.get("/platform/monitoring/snapshots/overview/"),
      d.get("/platform/monitoring/alerts/summary/"),
      d.get("/health/"),
    ]);

    if (t.status === "fulfilled") _(v(t.value.data).items);
    if (s.status === "fulfilled") A(v(s.value.data).items);
    if (m.status === "fulfilled") R(v(m.value.data).items);
    if (g.status === "fulfilled") M(g.value.data);
    if (y.status === "fulfilled") P(y.value.data);

    if (H.status === "fulfilled") {
      q({
        state: H.value?.data?.db === "up" ? "up" : "unknown",
        detail:
          H.value?.data?.db === "up"
            ? "Public schema database is reachable."
            : "Health check returned an unexpected response.",
        checkedAt: new Date(),
      });
    } else {
      q(Q(H.reason));
    }

    const J = [t, s, m, g, y].find((T) => T.status === "rejected");
    if (J) n(h(J.reason, "Unable to load monitoring data."));
    N(false);
  }, []);

  r.useEffect(() => {
    u();
  }, [u]);

  const I = async (t) => {
    t.preventDefault();
    n(null);
    o(null);
    try {
      await d.post("/platform/monitoring/snapshots/", {
        metric_key: a.metric_key.trim(),
        tenant: a.tenant ? Number(a.tenant) : null,
        value: a.value ? Number(a.value) : null,
        payload: a.payload ? JSON.parse(a.payload) : {},
      });
      p({ metric_key: "", tenant: "", value: "", payload: "{}" });
      o("Snapshot created.");
      await u();
    } catch (s) {
      n(h(s, "Unable to create monitoring snapshot."));
    }
  };

  const O = async (t) => {
    t.preventDefault();
    n(null);
    o(null);
    try {
      await d.post("/platform/monitoring/alerts/", {
        title: l.title.trim(),
        metric_key: l.metric_key.trim(),
        tenant: l.tenant ? Number(l.tenant) : null,
        severity: l.severity,
        details: l.details.trim(),
      });
      c({ title: "", metric_key: "", tenant: "", severity: "WARNING", details: "" });
      o("Alert created.");
      await u();
    } catch (s) {
      n(h(s, "Unable to create monitoring alert."));
    }
  };

  const w = async (t, s) => {
    n(null);
    o(null);
    try {
      await d.post(`/platform/monitoring/alerts/${t}/${s}/`, {});
      o(`Alert ${s}d.`);
      await u();
    } catch (m) {
      n(h(m, `Unable to ${s} alert.`));
    }
  };

  return e.jsxs("div", {
    className: "grid grid-cols-12 gap-6",
    children: [
      e.jsx(D, {
        badge: "MODULE",
        badgeColor: "emerald",
        title: "Monitoring",
        subtitle: "Monitoring management, public schema health, and operational overview.",
        icon: "📋",
      }),
      e.jsx(Z, { health: k, checking: F, onRefresh: B }),
      k.state === "down"
        ? e.jsx("div", {
            className:
              "col-span-12 rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-4 text-sm text-rose-200",
            children:
              "Public schema DB health is degraded. Platform login, monitoring actions, and other global admin flows are expected to return 503 until the database probe recovers.",
          })
        : null,
      x
        ? e.jsxs("section", {
            className: "col-span-12 grid gap-4 md:grid-cols-3",
            children: [
              e.jsxs("div", {
                className: "rounded-2xl glass-panel p-4 text-sm",
                children: ["Open alerts: ", x.open_alerts],
              }),
              e.jsxs("div", {
                className: "rounded-2xl glass-panel p-4 text-sm",
                children: ["Critical open alerts: ", x.critical_alerts],
              }),
              e.jsxs("div", {
                className: "rounded-2xl glass-panel p-4 text-sm",
                children: ["Metric keys tracked: ", x.snapshot_metric_keys.length],
              }),
            ],
          })
        : null,
      i
        ? e.jsxs("section", {
            className: "col-span-12 grid gap-4 md:grid-cols-5",
            children: [
              e.jsxs("div", {
                className: "rounded-2xl glass-panel p-4 text-sm",
                children: ["Open: ", i.open],
              }),
              e.jsxs("div", {
                className: "rounded-2xl glass-panel p-4 text-sm",
                children: ["Acknowledged: ", i.acknowledged],
              }),
              e.jsxs("div", {
                className: "rounded-2xl glass-panel p-4 text-sm",
                children: ["Resolved: ", i.resolved],
              }),
              e.jsxs("div", {
                className: "rounded-2xl glass-panel p-4 text-sm",
                children: ["Critical open: ", i.critical_open],
              }),
              e.jsxs("div", {
                className: "rounded-2xl glass-panel p-4 text-sm",
                children: ["MTTR 30d (hrs): ", i.mttr_hours_30d],
              }),
            ],
          })
        : null,
      b
        ? e.jsx("div", {
            className: "col-span-12 rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200",
            children: b,
          })
        : null,
      f
        ? e.jsx("div", {
            className: "col-span-12 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-sm text-emerald-200",
            children: f,
          })
        : null,
      e.jsxs("section", {
        className: "col-span-12 rounded-2xl glass-panel p-6 lg:col-span-6",
        children: [
          e.jsx("h2", { className: "text-lg font-semibold", children: "Create Snapshot" }),
          e.jsxs("form", {
            className: "mt-4 grid gap-3",
            onSubmit: I,
            children: [
              e.jsx("input", {
                className: "rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                placeholder: "Metric key",
                value: a.metric_key,
                onChange: (t) => p((s) => ({ ...s, metric_key: t.target.value })),
                required: true,
              }),
              e.jsxs("select", {
                className: "rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                value: a.tenant,
                onChange: (t) => p((s) => ({ ...s, tenant: t.target.value })),
                children: [
                  e.jsx("option", { value: "", children: "Platform-wide" }),
                  j.map((t) => e.jsx("option", { value: t.id, children: t.name }, t.id)),
                ],
              }),
              e.jsx("input", {
                className: "rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                placeholder: "Value (optional)",
                value: a.value,
                onChange: (t) => p((s) => ({ ...s, value: t.target.value })),
              }),
              e.jsx("textarea", {
                className: "rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                rows: 3,
                placeholder: 'Payload JSON e.g. {"p95": 120}',
                value: a.payload,
                onChange: (t) => p((s) => ({ ...s, payload: t.target.value })),
              }),
              e.jsx("button", {
                type: "submit",
                className: "rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900",
                children: "Create Snapshot",
              }),
            ],
          }),
        ],
      }),
      e.jsxs("section", {
        className: "col-span-12 rounded-2xl glass-panel p-6 lg:col-span-6",
        children: [
          e.jsx("h2", { className: "text-lg font-semibold", children: "Create Alert" }),
          e.jsxs("form", {
            className: "mt-4 grid gap-3",
            onSubmit: O,
            children: [
              e.jsx("input", {
                className: "rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                placeholder: "Alert title",
                value: l.title,
                onChange: (t) => c((s) => ({ ...s, title: t.target.value })),
                required: true,
              }),
              e.jsx("input", {
                className: "rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                placeholder: "Metric key",
                value: l.metric_key,
                onChange: (t) => c((s) => ({ ...s, metric_key: t.target.value })),
              }),
              e.jsxs("select", {
                className: "rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                value: l.tenant,
                onChange: (t) => c((s) => ({ ...s, tenant: t.target.value })),
                children: [
                  e.jsx("option", { value: "", children: "Platform-wide" }),
                  j.map((t) => e.jsx("option", { value: t.id, children: t.name }, t.id)),
                ],
              }),
              e.jsx("select", {
                className: "rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                value: l.severity,
                onChange: (t) => c((s) => ({ ...s, severity: t.target.value })),
                children: ["INFO", "WARNING", "CRITICAL"].map((t) =>
                  e.jsx("option", { value: t, children: t }, t),
                ),
              }),
              e.jsx("textarea", {
                className: "rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                rows: 3,
                placeholder: "Details",
                value: l.details,
                onChange: (t) => c((s) => ({ ...s, details: t.target.value })),
              }),
              e.jsx("button", {
                type: "submit",
                className: "rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900",
                children: "Create Alert",
              }),
            ],
          }),
        ],
      }),
      e.jsxs("section", {
        className: "col-span-12 rounded-2xl glass-panel p-6",
        children: [
          e.jsx("h2", { className: "text-lg font-semibold", children: "Recent Alerts" }),
          e.jsx("div", {
            className: "mt-4 overflow-x-auto rounded-xl border border-white/[0.07]",
            children: e.jsxs("table", {
              className: "min-w-[920px] w-full text-left text-sm",
              children: [
                e.jsx("thead", {
                  className: "bg-white/[0.03] text-xs uppercase tracking-wide text-slate-400",
                  children: e.jsxs("tr", {
                    children: [
                      e.jsx("th", { className: "px-3 py-2", children: "Title" }),
                      e.jsx("th", { className: "px-3 py-2", children: "Metric" }),
                      e.jsx("th", { className: "px-3 py-2", children: "Severity" }),
                      e.jsx("th", { className: "px-3 py-2", children: "Status" }),
                      e.jsx("th", { className: "px-3 py-2", children: "Tenant" }),
                      e.jsx("th", { className: "px-3 py-2", children: "Actions" }),
                    ],
                  }),
                }),
                e.jsxs("tbody", {
                  className: "divide-y divide-slate-800",
                  children: [
                    E
                      ? e.jsx("tr", {
                          children: e.jsx("td", {
                            className: "px-3 py-3 text-slate-400",
                            colSpan: 6,
                            children: "Loading...",
                          }),
                        })
                      : null,
                    C.map((t) =>
                      e.jsxs(
                        "tr",
                        {
                          className: "bg-slate-950/50",
                          children: [
                            e.jsx("td", { className: "px-3 py-2", children: t.title }),
                            e.jsx("td", { className: "px-3 py-2", children: t.metric_key || "--" }),
                            e.jsx("td", { className: "px-3 py-2", children: t.severity }),
                            e.jsx("td", { className: "px-3 py-2", children: t.status }),
                            e.jsx("td", { className: "px-3 py-2", children: t.tenant_name ?? "Platform" }),
                            e.jsxs("td", {
                              className: "space-x-2 px-3 py-2",
                              children: [
                                e.jsx("button", {
                                  className: "rounded border border-white/[0.09] px-2 py-1 text-xs",
                                  onClick: () => {
                                    w(t.id, "acknowledge");
                                  },
                                  children: "Acknowledge",
                                }),
                                e.jsx("button", {
                                  className: "rounded border border-white/[0.09] px-2 py-1 text-xs",
                                  onClick: () => {
                                    w(t.id, "resolve");
                                  },
                                  children: "Resolve",
                                }),
                              ],
                            }),
                          ],
                        },
                        t.id,
                      ),
                    ),
                  ],
                }),
              ],
            }),
          }),
        ],
      }),
      e.jsxs("section", {
        className: "col-span-12 rounded-2xl glass-panel p-6",
        children: [
          e.jsx("h2", { className: "text-lg font-semibold", children: "Recent Snapshots" }),
          e.jsx("div", {
            className: "mt-4 overflow-x-auto rounded-xl border border-white/[0.07]",
            children: e.jsxs("table", {
              className: "min-w-[760px] w-full text-left text-sm",
              children: [
                e.jsx("thead", {
                  className: "bg-white/[0.03] text-xs uppercase tracking-wide text-slate-400",
                  children: e.jsxs("tr", {
                    children: [
                      e.jsx("th", { className: "px-3 py-2", children: "Metric" }),
                      e.jsx("th", { className: "px-3 py-2", children: "Value" }),
                      e.jsx("th", { className: "px-3 py-2", children: "Tenant" }),
                      e.jsx("th", { className: "px-3 py-2", children: "Captured" }),
                    ],
                  }),
                }),
                e.jsx("tbody", {
                  className: "divide-y divide-slate-800",
                  children: S.slice(0, 20).map((t) =>
                    e.jsxs(
                      "tr",
                      {
                        className: "bg-slate-950/50",
                        children: [
                          e.jsx("td", { className: "px-3 py-2", children: t.metric_key }),
                          e.jsx("td", { className: "px-3 py-2", children: t.value ?? "--" }),
                          e.jsx("td", { className: "px-3 py-2", children: t.tenant ?? "Platform" }),
                          e.jsx("td", { className: "px-3 py-2", children: t.captured_at }),
                        ],
                      },
                      t.id,
                    ),
                  ),
                }),
              ],
            }),
          }),
        ],
      }),
    ],
  });
}

export { W as default };
