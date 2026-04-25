import { u as y, a as s, r as l, j as e } from "./index-D7ltaYVC.js";
import { p as x } from "./publicClient-BdJTy9AM.js";
import { e as v } from "./forms-ZJa1TpnO.js";
import { P } from "./PageHero-Ct90nOAG.js";

const K = {
  up: {
    shell: "border-emerald-400/25 bg-emerald-500/10",
    chip: "border border-emerald-400/30 bg-emerald-400/15 text-emerald-200",
    dot: "bg-emerald-300",
    title: "Platform database online",
  },
  down: {
    shell: "border-rose-400/25 bg-rose-500/10",
    chip: "border border-rose-400/30 bg-rose-400/15 text-rose-200",
    dot: "bg-rose-300",
    title: "Platform database unavailable",
  },
  unknown: {
    shell: "border-amber-400/25 bg-amber-500/10",
    chip: "border border-amber-400/30 bg-amber-400/15 text-amber-100",
    dot: "bg-amber-300",
    title: "Platform health needs attention",
  },
  checking: {
    shell: "border-sky-400/25 bg-sky-500/10",
    chip: "border border-sky-400/30 bg-sky-400/15 text-sky-100",
    dot: "bg-sky-300",
    title: "Checking platform database",
  },
};

function Q(t) {
  if (!t) return "Not checked yet";
  return new Intl.DateTimeFormat(void 0, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(t);
}

function J(t) {
  const a = t?.response?.status;
  const r = t?.response?.data;
  if (a === 503) {
    return {
      state: "down",
      detail: r?.detail || "Database unavailable",
      checkedAt: new Date(),
    };
  }
  return {
    state: "unknown",
    detail: v(t, "Unable to verify platform database health."),
    checkedAt: new Date(),
  };
}

function X({ health, checking, onRefresh }) {
  const t = K[health.state] || K.unknown;
  return e.jsxs("section", {
    className: `rounded-3xl border px-5 py-4 shadow-[0_20px_60px_rgba(2,6,23,0.32)] backdrop-blur ${t.shell}`,
    children: [
      e.jsxs("div", {
        className: "flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between",
        children: [
          e.jsxs("div", {
            className: "space-y-3",
            children: [
              e.jsxs("div", {
                className: `inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] ${t.chip}`,
                children: [
                  e.jsx("span", {
                    className: `h-2 w-2 rounded-full ${t.dot} ${checking ? "animate-pulse" : ""}`,
                  }),
                  "DB Health",
                ],
              }),
              e.jsx("h2", {
                className: "text-lg font-display font-semibold text-white",
                children: t.title,
              }),
              e.jsx("p", {
                className: "max-w-3xl text-sm leading-6 text-slate-200",
                children:
                  health.state === "up"
                    ? "Global Super Admin login is backed by the public schema. The latest probe confirms the database is reachable."
                    : "Global Super Admin login depends on the public schema database. If this check stays unhealthy, platform authentication and monitoring calls will fail with 503 responses.",
              }),
            ],
          }),
          e.jsxs("div", {
            className: "flex flex-col gap-2 sm:items-end",
            children: [
              e.jsx("button", {
                type: "button",
                onClick: onRefresh,
                disabled: checking,
                className:
                  "rounded-xl border border-white/[0.12] bg-slate-950/50 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-white/25 hover:bg-slate-900/70 disabled:cursor-not-allowed disabled:opacity-70",
                children: checking ? "Checking..." : "Refresh health",
              }),
              e.jsxs("p", {
                className: "text-xs text-slate-300",
                children: ["Last checked ", Q(health.checkedAt)],
              }),
            ],
          }),
        ],
      }),
      e.jsxs("div", {
        className: "mt-4 grid gap-3 border-t border-white/[0.08] pt-4 text-sm text-slate-200 md:grid-cols-3",
        children: [
          e.jsxs("div", {
            className: "rounded-2xl bg-slate-950/35 px-4 py-3",
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
            className: "rounded-2xl bg-slate-950/35 px-4 py-3",
            children: [
              e.jsx("p", {
                className: "text-[11px] uppercase tracking-[0.18em] text-slate-400",
                children: "Database",
              }),
              e.jsx("p", {
                className: "mt-2 text-sm font-semibold text-slate-100",
                children:
                  health.state === "up"
                    ? "Reachable"
                    : health.state === "down"
                      ? "Unavailable"
                      : health.state === "checking"
                        ? "Checking..."
                        : "Unknown",
              }),
            ],
          }),
          e.jsxs("div", {
            className: "rounded-2xl bg-slate-950/35 px-4 py-3",
            children: [
              e.jsx("p", {
                className: "text-[11px] uppercase tracking-[0.18em] text-slate-400",
                children: "Operator note",
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

function R() {
  const r = y();
  const u = s((t) => t.setTokens);
  const p = s((t) => t.setAuthMode);
  const h = s((t) => t.setTenant);
  const f = s((t) => t.setUsername);
  const g = s((t) => t.setRole);
  const b = s((t) => t.setPermissions);
  const [o, w] = l.useState("");
  const [n, j] = l.useState("");
  const [i, m] = l.useState(null);
  const [c, d] = l.useState(false);
  const [k, q] = l.useState({
    state: "checking",
    detail: "Checking public schema database connectivity.",
    checkedAt: null,
  });
  const [B, L] = l.useState(false);

  const N = l.useCallback(async () => {
    L(true);
    try {
      const t = await x.get("/health/");
      q({
        state: t?.data?.db === "up" ? "up" : "unknown",
        detail:
          t?.data?.db === "up"
            ? "Public schema database is reachable."
            : "Health check returned an unexpected response.",
        checkedAt: new Date(),
      });
    } catch (t) {
      q(J(t));
    } finally {
      L(false);
    }
  }, []);

  l.useEffect(() => {
    N();
    const t = window.setInterval(N, 6e4);
    return () => window.clearInterval(t);
  }, [N]);

  const U = async (t) => {
    t.preventDefault();
    m(null);
    d(true);
    try {
      const a = await x.post("/platform/auth/login/", {
        username: o.trim(),
        password: n,
      });
      u(a.data.access, a.data.refresh);
      p("platform");
      h(null);
      f(o.trim());
      g(a.data.role ?? "GLOBAL_SUPER_ADMIN");
      b(["PLATFORM_ADMIN"]);
      r("/platform");
      void x.get("/platform/analytics/overview/").catch(() => {});
    } catch (a) {
      m(v(a, "Platform login failed or user is not a platform admin."));
    } finally {
      d(false);
    }
  };

  return e.jsxs("div", {
    className: "min-h-screen bg-slate-950 text-white",
    children: [
      e.jsx(P, {
        badge: "PLATFORM",
        badgeColor: "rose",
        title: "Platform Login",
        subtitle: "Manage platform login for this school",
        icon: "🛡️",
      }),
      e.jsxs("div", {
        className: "mx-auto max-w-5xl px-4 pb-10 pt-6 sm:px-6 sm:pb-16",
        children: [
          e.jsx(X, { health: k, checking: B, onRefresh: N }),
          e.jsxs("div", {
            className:
              "mt-6 flex min-h-[calc(100vh-18rem)] flex-col items-center gap-10 md:flex-row",
            children: [
              e.jsxs("div", {
                className: "flex-1 space-y-6",
                children: [
                  e.jsx("p", {
                    className: "text-xs uppercase tracking-[0.4em] text-slate-400",
                    children: "SMS Platform",
                  }),
                  e.jsx("h1", {
                    className: "text-4xl font-display font-semibold leading-tight md:text-5xl",
                    children: "Super Admin control center",
                  }),
                  e.jsx("p", {
                    className: "text-base text-slate-300",
                    children:
                      "Platform-level access for tenant provisioning, support, monitoring, analytics, and operational recovery.",
                  }),
                  e.jsx("div", {
                    className:
                      "rounded-3xl border border-white/[0.08] bg-white/[0.03] p-5 text-sm leading-6 text-slate-300",
                    children:
                      k.state === "down"
                        ? "Database health is currently degraded. Login may still be attempted, but platform auth requests are expected to fail until the public schema is reachable again."
                        : "This banner stays inside the page flow instead of pinning over the header, so operators can always see the full login surface and any system message together.",
                  }),
                ],
              }),
              e.jsxs("div", {
                className:
                  "w-full max-w-md rounded-3xl border border-white/[0.07] bg-[#0d1421]/70 p-6 shadow-2xl sm:p-8",
                children: [
                  e.jsx("h2", {
                    className: "text-xl font-display font-semibold",
                    children: "Platform sign in",
                  }),
                  e.jsx("p", {
                    className: "mt-2 text-sm text-slate-400",
                    children: "Public schema login for Global Super Admin users.",
                  }),
                  e.jsxs("form", {
                    className: "mt-6 space-y-4",
                    onSubmit: U,
                    children: [
                      e.jsxs("label", {
                        className: "block text-sm",
                        children: [
                          "Username",
                          e.jsx("input", {
                            className:
                              "mt-2 w-full rounded-xl border border-white/[0.07] bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-emerald-400",
                            placeholder: "platform-admin",
                            value: o,
                            onChange: (t) => w(t.target.value),
                          }),
                        ],
                      }),
                      e.jsxs("label", {
                        className: "block text-sm",
                        children: [
                          "Password",
                          e.jsx("input", {
                            type: "password",
                            className:
                              "mt-2 w-full rounded-xl border border-white/[0.07] bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-emerald-400",
                            value: n,
                            onChange: (t) => j(t.target.value),
                          }),
                        ],
                      }),
                      i
                        ? e.jsx("p", {
                            className: "text-sm text-rose-400",
                            children: i,
                          })
                        : null,
                      e.jsx("button", {
                        className:
                          "w-full rounded-xl bg-emerald-500 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-70",
                        type: "submit",
                        disabled: c,
                        children: c ? "Signing in..." : "Sign in",
                      }),
                    ],
                  }),
                  e.jsxs("p", {
                    className: "mt-4 text-center text-xs text-slate-400",
                    children: [
                      "School user? ",
                      e.jsx("button", {
                        type: "button",
                        className: "text-emerald-300 hover:text-emerald-200",
                        onClick: () => r("/login"),
                        children: "Use tenant login",
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

export { R as default };
