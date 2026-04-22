import { r as a, j as e, b as l } from "./index-D7ltaYVC.js";
import { P as u } from "./PageHero-Ct90nOAG.js";
import { B as h } from "./book-open-DkSh7gF5.js";
import { U as x } from "./users-9FLXP15V.js";
import { P as v } from "./plus-CQ41G_RD.js";
import { T as y } from "./trash-2-Bs1RXa9v.js";
import { F as b } from "./file-text-BMGjGS-3.js";
import { V as N } from "./video-BNuKx11H.js";
import { L as R } from "./link-2-CrhZeLSd.js";
import { E as C } from "./external-link-CIX8um0u.js";
import { R as A } from "./refresh-cw-DOVkzt4u.js";

const c = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.07)",
};
const p = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.09)",
};
const m = {
  document: { label: "Document", icon: b, color: "#0ea5e9", bg: "rgba(14,165,233,0.1)" },
  video: { label: "Video", icon: N, color: "#a855f7", bg: "rgba(168,85,247,0.1)" },
  link: { label: "Link", icon: R, color: "#10b981", bg: "rgba(16,185,129,0.1)" },
  slide: { label: "Slides", icon: h, color: "#f59e0b", bg: "rgba(245,158,11,0.1)" },
};

function k(t) {
  if (!t) return "—";
  try {
    return new Date(t).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return String(t);
  }
}

function w(t) {
  if (!t) return false;
  try {
    const s = new Date(t);
    const n = new Date();
    s.setHours(0, 0, 0, 0);
    n.setHours(0, 0, 0, 0);
    return s < n;
  } catch {
    return false;
  }
}

function j() {
  const [t, s] = a.useState(true);
  const [n, i] = a.useState("");
  const [o, d] = a.useState("");
  const [r, f] = a.useState({
    summary: {
      teacher_custody_count: 0,
      available_for_student_issue: 0,
      active_student_loans: 0,
      overdue_student_loans: 0,
    },
    held_books: [],
    active_student_loans: [],
    recent_student_returns: [],
    eligible_students: [],
    teacher_member: null,
  });
  const [g, q] = a.useState({ courses: [], materials: [] });
  const [_, T] = a.useState(false);
  const [P, L] = a.useState(false);
  const [B, F] = a.useState(false);
  const [D, I] = a.useState({
    copy: "",
    student_id: "",
    due_date: "",
    notes: "",
  });
  const [E, S] = a.useState({
    course: "",
    title: "",
    type: "document",
    url: "",
    description: "",
  });

  const O = async () => {
    s(true);
    i("");
    try {
      const [M, U] = await Promise.all([
        l.get("/teacher-portal/resources/library/"),
        l.get("/teacher-portal/resources/"),
      ]);
      const G = M.data ?? {};
      const H = U.data ?? {};
      f({
        summary: G.summary ?? {
          teacher_custody_count: 0,
          available_for_student_issue: 0,
          active_student_loans: 0,
          overdue_student_loans: 0,
        },
        held_books: Array.isArray(G.held_books) ? G.held_books : [],
        active_student_loans: Array.isArray(G.active_student_loans) ? G.active_student_loans : [],
        recent_student_returns: Array.isArray(G.recent_student_returns) ? G.recent_student_returns : [],
        eligible_students: Array.isArray(G.eligible_students) ? G.eligible_students : [],
        teacher_member: G.teacher_member ?? null,
      });
      q({
        courses: Array.isArray(H.courses) ? H.courses : [],
        materials: Array.isArray(H.materials) ? H.materials : [],
      });
      if (!D.copy && Array.isArray(G.held_books) && G.held_books.length > 0) {
        I((K) => ({ ...K, copy: String(G.held_books[0].copy_id ?? "") }));
      }
      if (!D.student_id && Array.isArray(G.eligible_students) && G.eligible_students.length > 0) {
        I((K) => ({ ...K, student_id: String(G.eligible_students[0].id ?? "") }));
      }
      if (!E.course && Array.isArray(H.courses) && H.courses.length > 0) {
        S((K) => ({ ...K, course: String(H.courses[0].id ?? "") }));
      }
    } catch (M) {
      i(M?.response?.data?.error || "Unable to load teacher resources right now.");
    } finally {
      s(false);
    }
  };

  a.useEffect(() => {
    O();
  }, []);

  const X = async () => {
    if (!D.copy || !D.student_id) {
      d("Select a classroom book and student first.");
      return;
    }
    T(true);
    i("");
    d("");
    try {
      const M = {
        copy: Number(D.copy),
        student_id: Number(D.student_id),
        notes: D.notes,
      };
      if (D.due_date) M.due_date = D.due_date;
      const U = await l.post("/teacher-portal/resources/library/issue/", M);
      d(U.data?.message || "Classroom book issued.");
      I({ copy: "", student_id: D.student_id, due_date: "", notes: "" });
      await O();
    } catch (M) {
      i(M?.response?.data?.error || "Unable to issue the classroom book.");
    } finally {
      T(false);
    }
  };

  const J = async (M) => {
    L(true);
    i("");
    d("");
    try {
      const U = await l.post("/teacher-portal/resources/library/return/", { loan: M });
      d(U.data?.message || "Student return recorded.");
      await O();
    } catch (U) {
      i(U?.response?.data?.error || "Unable to record the return.");
    } finally {
      L(false);
    }
  };

  const Q = async () => {
    if (!E.course || !E.title.trim()) {
      d("Choose a course and title for the teaching material.");
      return;
    }
    F(true);
    i("");
    d("");
    try {
      const M = await l.post("/teacher-portal/resources/", {
        course: Number(E.course),
        title: E.title.trim(),
        type: E.type,
        url: E.url.trim(),
        description: E.description.trim(),
      });
      q((U) => ({ ...U, materials: [M.data, ...U.materials] }));
      S((U) => ({
        ...U,
        title: "",
        url: "",
        description: "",
      }));
      d("Teaching material saved.");
    } catch (M) {
      i(M?.response?.data?.error || "Unable to save the teaching material.");
    } finally {
      F(false);
    }
  };

  const V = async (M) => {
    i("");
    d("");
    try {
      await l.delete(`/teacher-portal/resources/${M}/`);
      q((U) => ({ ...U, materials: U.materials.filter((G) => G.id !== M) }));
      d("Teaching material deleted.");
    } catch (U) {
      i(U?.response?.data?.error || "Unable to delete the teaching material.");
    }
  };

  const W = [
    {
      label: "In My Custody",
      value: r.summary.teacher_custody_count,
      color: "#8b5cf6",
      bg: "rgba(139,92,246,0.1)",
      icon: h,
    },
    {
      label: "Ready To Issue",
      value: r.summary.available_for_student_issue,
      color: "#10b981",
      bg: "rgba(16,185,129,0.1)",
      icon: v,
    },
    {
      label: "With Students",
      value: r.summary.active_student_loans,
      color: "#0ea5e9",
      bg: "rgba(14,165,233,0.1)",
      icon: x,
    },
    {
      label: "Student Overdue",
      value: r.summary.overdue_student_loans,
      color: "#f97316",
      bg: "rgba(249,115,22,0.1)",
      icon: A,
    },
  ];

  return e.jsxs("div", {
    className: "space-y-6",
    children: [
      e.jsx(u, {
        badge: "TEACHER",
        badgeColor: "purple",
        title: "Classroom Library & Resources",
        subtitle: "Issue classroom books already assigned to you, track student handoffs, and keep teaching materials in one place.",
        icon: "📚",
      }),
      e.jsx("div", {
        className: "grid grid-cols-2 sm:grid-cols-4 gap-3",
        children: W.map((M) =>
          e.jsxs(
            "div",
            {
              className: "rounded-2xl p-4",
              style: { background: M.bg, border: `1px solid ${M.color}25` },
              children: [
                e.jsxs("div", {
                  className: "flex items-center justify-between mb-1",
                  children: [
                    e.jsx(M.icon, { size: 14, style: { color: M.color } }),
                    e.jsx("span", { className: "text-xs text-slate-500", children: M.label }),
                  ],
                }),
                e.jsx("p", { className: "text-xl font-bold text-white", children: M.value }),
              ],
            },
            M.label,
          ),
        ),
      }),
      n &&
        e.jsx("div", {
          className: "rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200",
          children: n,
        }),
      o &&
        e.jsx("div", {
          className: "rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200",
          children: o,
        }),
      e.jsxs("div", {
        className: "rounded-2xl p-5 space-y-5",
        style: c,
        children: [
          e.jsxs("div", {
            className: "flex items-start justify-between gap-3",
            children: [
              e.jsxs("div", {
                children: [
                  e.jsx("p", { className: "text-sm font-bold text-white", children: "Classroom Library" }),
                  e.jsx("p", {
                    className: "text-xs text-slate-400 mt-1",
                    children:
                      "Only books already checked out to you can be issued to students. Library return still closes the full custody chain when a copy comes back to the desk.",
                  }),
                ],
              }),
              e.jsxs("button", {
                onClick: O,
                className: "shrink-0 flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold text-slate-200 transition hover:text-white",
                style: p,
                disabled: t,
                children: [e.jsx(A, { size: 13, className: t ? "animate-spin" : "" }), "Refresh"],
              }),
            ],
          }),
          e.jsxs("div", {
            className: "grid grid-cols-1 lg:grid-cols-[1.1fr,0.9fr] gap-5",
            children: [
              e.jsxs("div", {
                className: "rounded-2xl p-5 space-y-4",
                style: p,
                children: [
                  e.jsx("p", { className: "text-sm font-bold text-white", children: "Issue A Classroom Book" }),
                  e.jsxs("div", {
                    className: "grid gap-3 sm:grid-cols-2",
                    children: [
                      e.jsxs("select", {
                        value: D.copy,
                        onChange: (M) => I((U) => ({ ...U, copy: M.target.value })),
                        className: "rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                        children: [
                          e.jsx("option", { value: "", children: "Select held copy" }),
                          r.held_books.map((M) =>
                            e.jsx(
                              "option",
                              {
                                value: M.copy_id,
                                children: `${M.copy_accession_number} — ${M.resource_title}`,
                              },
                              M.copy_id,
                            ),
                          ),
                        ],
                      }),
                      e.jsxs("select", {
                        value: D.student_id,
                        onChange: (M) => I((U) => ({ ...U, student_id: M.target.value })),
                        className: "rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                        children: [
                          e.jsx("option", { value: "", children: "Select assigned student" }),
                          r.eligible_students.map((M) =>
                            e.jsx(
                              "option",
                              {
                                value: M.id,
                                children: `${M.full_name} — ${M.class_name || M.admission_number}`,
                              },
                              M.id,
                            ),
                          ),
                        ],
                      }),
                      e.jsx("input", {
                        type: "date",
                        value: D.due_date,
                        onChange: (M) => I((U) => ({ ...U, due_date: M.target.value })),
                        className: "rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                      }),
                      e.jsx("input", {
                        value: D.notes,
                        onChange: (M) => I((U) => ({ ...U, notes: M.target.value })),
                        placeholder: "Notes (optional)",
                        className: "rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                      }),
                    ],
                  }),
                  e.jsxs("button", {
                    onClick: X,
                    disabled: _ || !r.held_books.length || !r.eligible_students.length,
                    className: "rounded-xl bg-violet-600 px-5 py-2 text-sm font-semibold text-white transition disabled:opacity-40 hover:bg-violet-500",
                    children: [e.jsx(v, { size: 13, className: "inline mr-1.5" }), _ ? "Issuing…" : "Issue To Student"],
                  }),
                ],
              }),
              e.jsxs("div", {
                className: "rounded-2xl p-5 space-y-3",
                style: p,
                children: [
                  e.jsx("p", { className: "text-sm font-bold text-white", children: "Held Books" }),
                  !r.held_books.length && !t
                    ? e.jsx("p", {
                        className: "text-sm text-slate-500",
                        children: "No books are currently sitting in your classroom custody.",
                      })
                    : r.held_books.map((M) =>
                        e.jsxs(
                          "div",
                          {
                            className: "rounded-xl px-4 py-3",
                            style: { background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" },
                            children: [
                              e.jsxs("div", {
                                className: "flex items-start justify-between gap-3",
                                children: [
                                  e.jsxs("div", {
                                    children: [
                                      e.jsx("p", { className: "text-sm font-semibold text-white", children: M.resource_title }),
                                      e.jsx("p", {
                                        className: "text-xs text-slate-500 mt-1",
                                        children: `${M.copy_accession_number} • Due ${k(M.teacher_due_date)}`,
                                      }),
                                    ],
                                  }),
                                  e.jsx("button", {
                                    onClick: () => I((U) => ({ ...U, copy: String(M.copy_id) })),
                                    className: "rounded-lg px-3 py-1.5 text-[11px] font-semibold text-violet-300 transition hover:text-white",
                                    style: { background: "rgba(139,92,246,0.12)", border: "1px solid rgba(139,92,246,0.2)" },
                                    children: "Use",
                                  }),
                                ],
                              }),
                            ],
                          },
                          M.copy_id,
                        ),
                      ),
                ],
              }),
            ],
          }),
          e.jsxs("div", {
            className: "grid grid-cols-1 lg:grid-cols-[1.1fr,0.9fr] gap-5",
            children: [
              e.jsxs("div", {
                className: "rounded-2xl p-5 space-y-3",
                style: p,
                children: [
                  e.jsx("p", { className: "text-sm font-bold text-white", children: "Books With Students" }),
                  !r.active_student_loans.length && !t
                    ? e.jsx("p", {
                        className: "text-sm text-slate-500",
                        children: "No active student handoffs are open right now.",
                      })
                    : r.active_student_loans.map((M) =>
                        e.jsxs(
                          "div",
                          {
                            className: "rounded-xl px-4 py-3",
                            style: { background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" },
                            children: [
                              e.jsxs("div", {
                                className: "flex items-start justify-between gap-3",
                                children: [
                                  e.jsxs("div", {
                                    children: [
                                      e.jsx("p", { className: "text-sm font-semibold text-white", children: M.resource_title }),
                                      e.jsx("p", {
                                        className: "text-xs text-slate-400 mt-1",
                                        children: `${M.student_name} • ${M.copy_accession_number}`,
                                      }),
                                      e.jsx("p", {
                                        className: `text-[11px] mt-1 ${w(M.due_date) ? "text-rose-300" : "text-slate-500"}`,
                                        children: `Due ${k(M.due_date)}`,
                                      }),
                                    ],
                                  }),
                                  e.jsx("button", {
                                    onClick: () => J(M.id),
                                    disabled: P,
                                    className: "rounded-lg px-3 py-1.5 text-[11px] font-semibold text-emerald-300 transition hover:text-white disabled:opacity-40",
                                    style: { background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.2)" },
                                    children: P ? "Saving…" : "Mark Returned",
                                  }),
                                ],
                              }),
                            ],
                          },
                          M.id,
                        ),
                      ),
                ],
              }),
              e.jsxs("div", {
                className: "rounded-2xl p-5 space-y-3",
                style: p,
                children: [
                  e.jsx("p", { className: "text-sm font-bold text-white", children: "Recent Student Returns" }),
                  !r.recent_student_returns.length && !t
                    ? e.jsx("p", {
                        className: "text-sm text-slate-500",
                        children: "Recent return history will appear here.",
                      })
                    : r.recent_student_returns.map((M) =>
                        e.jsxs(
                          "div",
                          {
                            className: "rounded-xl px-4 py-3",
                            style: { background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" },
                            children: [
                              e.jsx("p", { className: "text-sm font-semibold text-white", children: M.resource_title }),
                              e.jsx("p", {
                                className: "text-xs text-slate-400 mt-1",
                                children: `${M.student_name} • Returned to ${M.return_destination || "Teacher"}`,
                              }),
                              e.jsx("p", {
                                className: "text-[11px] text-slate-500 mt-1",
                                children: k(M.return_date),
                              }),
                            ],
                          },
                          M.id,
                        ),
                      ),
                ],
              }),
            ],
          }),
        ],
      }),
      e.jsxs("div", {
        className: "rounded-2xl p-5 space-y-5",
        style: c,
        children: [
          e.jsxs("div", {
            className: "flex items-start justify-between gap-3",
            children: [
              e.jsxs("div", {
                children: [
                  e.jsx("p", { className: "text-sm font-bold text-white", children: "Teaching Materials" }),
                  e.jsx("p", {
                    className: "text-xs text-slate-400 mt-1",
                    children: "Keep your digital teaching resources on the same screen as your classroom book workflow.",
                  }),
                ],
              }),
              e.jsxs("button", {
                onClick: () => S((M) => ({ ...M, course: g.courses[0]?.id ? String(g.courses[0].id) : M.course })) || I,
                className: "hidden",
                children: [],
              }),
            ],
          }),
          e.jsxs("div", {
            className: "flex items-center justify-between gap-3",
            children: [
              e.jsxs("div", {
                className: "text-xs text-slate-500",
                children: [
                  "Courses: ",
                  e.jsx("span", { className: "text-slate-300 font-semibold", children: g.courses.length }),
                  " • Materials: ",
                  e.jsx("span", { className: "text-slate-300 font-semibold", children: g.materials.length }),
                ],
              }),
              e.jsxs("button", {
                onClick: () => S((M) => ({ ...M, course: g.courses[0]?.id ? String(g.courses[0].id) : M.course })) || B ? null : null,
                className: "hidden",
                children: [],
              }),
            ],
          }),
          e.jsxs("div", {
            className: "rounded-2xl p-5 space-y-4",
            style: p,
            children: [
              e.jsx("p", { className: "text-sm font-bold text-white", children: "Add Teaching Material" }),
              e.jsxs("div", {
                className: "grid gap-3 sm:grid-cols-2",
                children: [
                  e.jsxs("select", {
                    value: E.course,
                    onChange: (M) => S((U) => ({ ...U, course: M.target.value })),
                    className: "rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                    children: [
                      e.jsx("option", { value: "", children: "Select course" }),
                      g.courses.map((M) =>
                        e.jsx(
                          "option",
                          {
                            value: M.id,
                            children: `${M.title}${M.class_name ? ` — ${M.class_name}` : ""}`,
                          },
                          M.id,
                        ),
                      ),
                    ],
                  }),
                  e.jsxs("select", {
                    value: E.type,
                    onChange: (M) => S((U) => ({ ...U, type: M.target.value })),
                    className: "rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                    children: Object.entries(m).map(([M, U]) =>
                      e.jsx("option", { value: M, children: U.label }, M),
                    ),
                  }),
                  e.jsx("input", {
                    value: E.title,
                    onChange: (M) => S((U) => ({ ...U, title: M.target.value })),
                    placeholder: "Material title",
                    className: "sm:col-span-2 rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                  }),
                  e.jsx("input", {
                    value: E.url,
                    onChange: (M) => S((U) => ({ ...U, url: M.target.value })),
                    placeholder: "URL or file link",
                    className: "sm:col-span-2 rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                  }),
                  e.jsx("textarea", {
                    value: E.description,
                    onChange: (M) => S((U) => ({ ...U, description: M.target.value })),
                    placeholder: "Description (optional)",
                    rows: 2,
                    className:
                      "sm:col-span-2 rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none resize-none",
                  }),
                ],
              }),
              e.jsxs("button", {
                onClick: Q,
                disabled: B || !g.courses.length,
                className: "rounded-xl bg-violet-600 px-5 py-2 text-sm font-semibold text-white transition disabled:opacity-40 hover:bg-violet-500",
                children: [e.jsx(v, { size: 13, className: "inline mr-1.5" }), B ? "Saving…" : "Save Material"],
              }),
            ],
          }),
          !g.materials.length && !t
            ? e.jsx("p", {
                className: "text-center text-slate-500 py-10",
                children: "No teaching materials have been added yet.",
              })
            : e.jsx("div", {
                className: "grid grid-cols-1 sm:grid-cols-2 gap-4",
                children: g.materials.map((M) => {
                  const U = m[M.type] || m.document;
                  const G = U.icon;
                  return e.jsxs(
                    "div",
                    {
                      className: "rounded-2xl p-5 group hover:scale-[1.01] transition-all",
                      style: c,
                      children: [
                        e.jsxs("div", {
                          className: "flex items-start justify-between gap-3 mb-3",
                          children: [
                            e.jsxs("div", {
                              className: "flex items-center gap-3",
                              children: [
                                e.jsx("div", {
                                  className: "w-9 h-9 rounded-xl flex items-center justify-center shrink-0",
                                  style: { background: U.bg },
                                  children: e.jsx(G, { size: 16, style: { color: U.color } }),
                                }),
                                e.jsxs("div", {
                                  children: [
                                    e.jsx("p", { className: "font-semibold text-white text-sm", children: M.title }),
                                    e.jsxs("div", {
                                      className: "flex items-center gap-2 mt-0.5 flex-wrap",
                                      children: [
                                        e.jsx("span", {
                                          className: "rounded-full px-2 py-0.5 text-[10px] font-bold",
                                          style: { background: U.bg, color: U.color },
                                          children: U.label,
                                        }),
                                        e.jsx("span", {
                                          className: "rounded-full px-2 py-0.5 text-[10px] font-semibold text-slate-400",
                                          style: { background: "rgba(255,255,255,0.05)" },
                                          children: M.subject,
                                        }),
                                      ],
                                    }),
                                  ],
                                }),
                              ],
                            }),
                            e.jsx("button", {
                              onClick: () => V(M.id),
                              className:
                                "opacity-0 group-hover:opacity-100 transition rounded-lg p-1.5 text-slate-600 hover:text-rose-400",
                              style: { background: "rgba(255,255,255,0.04)" },
                              children: e.jsx(y, { size: 13 }),
                            }),
                          ],
                        }),
                        M.description &&
                          e.jsx("p", { className: "text-xs text-slate-400 mb-3", children: M.description }),
                        e.jsxs("div", {
                          className: "flex items-center justify-between gap-3",
                          children: [
                            e.jsx("p", { className: "text-[10px] text-slate-600", children: k(M.created_at) }),
                            M.url &&
                              e.jsxs("a", {
                                href: M.url,
                                target: "_blank",
                                rel: "noreferrer",
                                className: "flex items-center gap-1 text-[11px] font-semibold transition",
                                style: { color: U.color },
                                children: ["Open ", e.jsx(C, { size: 10 })],
                              }),
                          ],
                        }),
                      ],
                    },
                    M.id,
                  );
                }),
              }),
        ],
      }),
    ],
  });
}

export { j as default };
