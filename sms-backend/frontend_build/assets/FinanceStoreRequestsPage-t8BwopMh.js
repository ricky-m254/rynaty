import { r as React, j as e, b as api } from "./index-D7ltaYVC.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";
import { P as PackageIcon } from "./package-KitsIxSS.js";
import { C as CheckIcon } from "./check-BI53z6hp.js";
import { X as CloseIcon } from "./x-CEi3D4aT.js";
import { C as ChevronDownIcon } from "./chevron-down-BMVcUee6.js";
import { C as ChevronUpIcon } from "./chevron-up-CAnJkIyv.js";
import { R as RefreshIcon } from "./refresh-cw-DOVkzt4u.js";
import "./createLucideIcon-BLtbVmUp.js";

const jsx = e.jsx;
const jsxs = e.jsxs;

const STATUS_COLORS = {
  PENDING: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  APPROVED: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  REJECTED: "bg-rose-500/20 text-rose-300 border-rose-500/30",
  FULFILLED: "bg-sky-500/20 text-sky-300 border-sky-500/30",
};

const PROCUREMENT_LABELS = {
  LPO: "Local Purchase Order",
  LSO: "Local Supply Order",
};

const OFFICE_LABELS = {
  FINANCE: "Finance Office",
  ADMIN: "Administration",
};

function formatMoney(value) {
  const amount = Number(value ?? 0);
  if (Number.isNaN(amount)) return "Ksh 0.00";
  return `Ksh ${amount.toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("en-KE", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return String(value);
  }
}

function extractError(error, fallback) {
  return (
    error?.response?.data?.error ||
    error?.response?.data?.detail ||
    error?.message ||
    fallback
  );
}

function calculateLineTotal(item) {
  const approvedTotal = Number(item.approved_total ?? 0);
  if (!Number.isNaN(approvedTotal) && approvedTotal > 0) {
    return approvedTotal;
  }
  const quantity = Number(item.quantity_approved ?? item.quantity_requested ?? 0);
  const unitPrice = Number(item.quoted_unit_price ?? 0);
  if (Number.isNaN(quantity) || Number.isNaN(unitPrice)) return 0;
  return quantity * unitPrice;
}

function StoreRequestsPage() {
  const [orders, setOrders] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [notice, setNotice] = React.useState(null);
  const [error, setError] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");
  const [procurementFilter, setProcurementFilter] = React.useState("");
  const [expandedOrders, setExpandedOrders] = React.useState(() => new Set());
  const [reviewState, setReviewState] = React.useState({
    orderId: null,
    action: "APPROVE",
    notes: "",
  });

  const refreshData = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = { page_size: 200 };
      if (statusFilter) params.status = statusFilter;
      if (procurementFilter) params.procurement_type = procurementFilter;
      const response = await api.get("/store/orders/", { params });
      const payload = response.data?.results ?? response.data ?? [];
      setOrders(Array.isArray(payload) ? payload : []);
    } catch (err) {
      setError(extractError(err, "Failed to load procurement requests."));
    } finally {
      setLoading(false);
    }
  }, [procurementFilter, statusFilter]);

  React.useEffect(() => {
    refreshData();
  }, [refreshData]);

  const toggleExpanded = (orderId) => {
    setExpandedOrders((current) => {
      const next = new Set(current);
      if (next.has(orderId)) next.delete(orderId);
      else next.add(orderId);
      return next;
    });
  };

  const submitReview = async () => {
    if (!reviewState.orderId) return;
    setSaving(true);
    setError("");
    setNotice(null);
    try {
      await api.patch(`/store/orders/${reviewState.orderId}/review/`, {
        action: reviewState.action,
        notes: reviewState.notes,
      });
      const message =
        reviewState.action === "REJECT"
          ? "Procurement request rejected."
          : "Procurement request approved.";
      setNotice({ type: "success", text: message });
      setReviewState({ orderId: null, action: "APPROVE", notes: "" });
      await refreshData();
    } catch (err) {
      setError(extractError(err, "Unable to update the procurement request."));
    } finally {
      setSaving(false);
    }
  };

  const generateExpense = async (orderId) => {
    setSaving(true);
    setError("");
    setNotice(null);
    try {
      const response = await api.post(`/store/orders/${orderId}/generate-expense/`);
      const expenseId = response.data?.expense_id;
      const alreadyGenerated = response.data?.already_generated;
      setNotice({
        type: "success",
        text: alreadyGenerated
          ? `Expense #${expenseId} was already linked to this procurement.`
          : `Expense #${expenseId} created from the approved procurement total.`,
      });
      await refreshData();
    } catch (err) {
      setError(extractError(err, "Unable to generate the procurement expense."));
    } finally {
      setSaving(false);
    }
  };

  const totalApprovedValue = orders.reduce((sum, order) => sum + Number(order.approved_total ?? 0), 0);

  return jsxs("div", {
    className: "space-y-6",
    children: [
      jsx(PageHero, {
        badge: "FINANCE",
        badgeColor: "emerald",
        title: "Procurement Review",
        subtitle: "Review LPOs and LSOs, lock in approved totals, and generate expenses from the stored snapshots.",
        icon: "💰",
      }),
      jsxs("div", {
        className: "grid grid-cols-1 gap-3 sm:grid-cols-3",
        children: [
          jsxs(
            "div",
            {
              className: "rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4",
              children: [
                jsx("p", {
                  className: "text-xs font-semibold uppercase tracking-wider text-slate-400",
                  children: "Requests Loaded",
                }),
                jsx("p", { className: "mt-2 text-2xl font-bold text-white", children: orders.length }),
              ],
            },
          ),
          jsxs(
            "div",
            {
              className: "rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4",
              children: [
                jsx("p", {
                  className: "text-xs font-semibold uppercase tracking-wider text-slate-400",
                  children: "Approved Value",
                }),
                jsx("p", { className: "mt-2 text-2xl font-bold text-emerald-400", children: formatMoney(totalApprovedValue) }),
              ],
            },
          ),
          jsxs(
            "div",
            {
              className: "rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4",
              children: [
                jsx("p", {
                  className: "text-xs font-semibold uppercase tracking-wider text-slate-400",
                  children: "Pending Review",
                }),
                jsx("p", {
                  className: "mt-2 text-2xl font-bold text-amber-300",
                  children: orders.filter((order) => order.status === "PENDING").length,
                }),
              ],
            },
          ),
        ],
      }),
      (error || notice) &&
        jsxs("div", {
          className: "space-y-2",
          children: [
            error &&
              jsx("div", {
                className: "rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200",
                children: error,
              }),
            notice &&
              jsx("div", {
                className: `rounded-xl border px-4 py-3 text-sm ${
                  notice.type === "success"
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                    : "border-sky-500/40 bg-sky-500/10 text-sky-200"
                }`,
                children: notice.text,
              }),
          ],
        }),
      jsxs("div", {
        className: "flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4",
        children: [
          jsxs("div", {
            className: "flex flex-wrap items-center gap-3",
            children: [
              jsx("select", {
                value: statusFilter,
                onChange: (event) => setStatusFilter(event.target.value),
                className: "rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                children: [
                  jsx("option", { value: "", children: "All Statuses" }),
                  jsx("option", { value: "PENDING", children: "Pending" }),
                  jsx("option", { value: "APPROVED", children: "Approved" }),
                  jsx("option", { value: "REJECTED", children: "Rejected" }),
                  jsx("option", { value: "FULFILLED", children: "Fulfilled" }),
                ],
              }),
              jsx("select", {
                value: procurementFilter,
                onChange: (event) => setProcurementFilter(event.target.value),
                className: "rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                children: [
                  jsx("option", { value: "", children: "All Procurement Types" }),
                  jsx("option", { value: "LPO", children: PROCUREMENT_LABELS.LPO }),
                  jsx("option", { value: "LSO", children: PROCUREMENT_LABELS.LSO }),
                ],
              }),
              jsx("button", {
                onClick: refreshData,
                className: "flex items-center gap-2 rounded-xl border border-white/[0.07] px-3 py-2 text-sm text-slate-200 transition hover:text-white",
                children: [jsx(RefreshIcon, { size: 14, className: loading ? "animate-spin" : "" }), "Refresh"],
              }),
            ],
          }),
        ],
      }),
      jsxs("div", {
        className: "grid gap-4",
        children: loading
          ? jsx("div", {
              className: "rounded-2xl border border-white/[0.07] bg-white/[0.02] p-10 text-center text-slate-400",
              children: "Loading procurement requests...",
            })
          : orders.length
            ? orders.map((order) => {
                const expanded = expandedOrders.has(order.id);
                const total = Number(order.approved_total ?? 0) || order.items.reduce((sum, item) => sum + calculateLineTotal(item), 0);
                return jsxs(
                  "div",
                  {
                    className: "overflow-hidden rounded-2xl border border-white/[0.07] bg-white/[0.02]",
                    children: [
                      jsxs("div", {
                        className: "flex flex-wrap items-start justify-between gap-4 p-5",
                        children: [
                          jsxs("div", {
                            className: "space-y-2",
                            children: [
                              jsxs("div", {
                                className: "flex flex-wrap items-center gap-2",
                                children: [
                                  jsx("span", {
                                    className: "rounded border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-bold text-emerald-300",
                                    children: order.document_number || order.request_code || `REQ-${order.id}`,
                                  }),
                                  jsx("span", {
                                    className: `rounded border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                                      STATUS_COLORS[order.status] || "bg-slate-500/20 text-slate-300 border-slate-500/30"
                                    }`,
                                    children: order.status,
                                  }),
                                  jsx("span", {
                                    className: "rounded border border-violet-500/20 bg-violet-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-violet-300",
                                    children: PROCUREMENT_LABELS[order.procurement_type] || order.procurement_type,
                                  }),
                                  jsx("span", {
                                    className: "rounded border border-cyan-500/20 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-cyan-300",
                                    children: OFFICE_LABELS[order.office_owner] || order.office_owner,
                                  }),
                                ],
                              }),
                              jsx("h3", { className: "text-lg font-semibold text-white", children: order.title }),
                              jsx("p", {
                                className: "text-sm text-slate-400",
                                children: order.description || "No description provided.",
                              }),
                              jsxs("div", {
                                className: "flex flex-wrap gap-3 text-xs text-slate-500",
                                children: [
                                  jsxs("span", {
                                    children: ["Supplier: ", jsx("span", { className: "text-slate-300", children: order.supplier_name || "—" })],
                                  }),
                                  jsxs("span", {
                                    children: ["Requested by: ", jsx("span", { className: "text-slate-300", children: order.requested_by_name || "—" })],
                                  }),
                                  jsxs("span", {
                                    children: ["Created: ", jsx("span", { className: "text-slate-300", children: formatDate(order.created_at) })],
                                  }),
                                ],
                              }),
                            ],
                          }),
                          jsxs("div", {
                            className: "flex flex-col items-end gap-2",
                            children: [
                              jsx("p", { className: "text-xl font-bold text-emerald-400", children: formatMoney(total) }),
                              jsx("p", {
                                className: "text-xs text-slate-500",
                                children: order.receiving_state_label || order.receiving_state || "Pending receipt",
                              }),
                              jsxs("div", {
                                className: "flex flex-wrap justify-end gap-2",
                                children: [
                                  order.status === "PENDING" &&
                                    jsxs(React.Fragment, {
                                      children: [
                                        jsx("button", {
                                          onClick: () => setReviewState({ orderId: order.id, action: "APPROVE", notes: "" }),
                                          className: "flex items-center gap-1 rounded-lg bg-emerald-500/20 px-3 py-1.5 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/30",
                                          children: [jsx(CheckIcon, { size: 12 }), "Approve"],
                                        }),
                                        jsx("button", {
                                          onClick: () => setReviewState({ orderId: order.id, action: "REJECT", notes: "" }),
                                          className: "flex items-center gap-1 rounded-lg bg-rose-500/20 px-3 py-1.5 text-xs font-semibold text-rose-300 transition hover:bg-rose-500/30",
                                          children: [jsx(CloseIcon, { size: 12 }), "Reject"],
                                        }),
                                      ],
                                    }),
                                  (order.status === "APPROVED" || order.status === "FULFILLED") &&
                                    jsx("button", {
                                      onClick: () => generateExpense(order.id),
                                      className: "rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-violet-500 disabled:opacity-60",
                                      disabled: saving,
                                      children: "Generate Expense",
                                    }),
                                  jsx("button", {
                                    onClick: () => toggleExpanded(order.id),
                                    className: "rounded-lg border border-white/[0.07] px-3 py-1.5 text-xs font-semibold text-slate-300 transition hover:text-white",
                                    children: expanded ? "Collapse" : "Details",
                                  }),
                                ],
                              }),
                            ],
                          }),
                        ],
                      }),
                      expanded &&
                        jsxs("div", {
                          className: "border-t border-white/[0.06] px-5 pb-5 pt-4",
                          children: [
                            order.reviewed_by_name &&
                              jsx("p", {
                                className: "mb-4 rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3 text-sm text-slate-300",
                                children: `Reviewed by ${order.reviewed_by_name}${order.reviewed_at ? ` on ${formatDate(order.reviewed_at)}` : ""}`,
                              }),
                            order.generated_expense_id &&
                              jsx("p", {
                                className: "mb-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-200",
                                children: `Expense linked: #${order.generated_expense_id}`,
                              }),
                            jsxs("div", {
                              className: "overflow-x-auto rounded-xl border border-white/[0.06] bg-slate-950/40",
                              children: [
                                jsx("table", {
                                  className: "w-full text-sm",
                                  children: jsxs("thead", {
                                    children: [
                                      jsx("tr", {
                                        className: "border-b border-white/[0.07] text-xs uppercase tracking-wider text-slate-500",
                                        children: [
                                          jsx("th", { className: "px-4 py-2 text-left", children: "Item" }),
                                          jsx("th", { className: "px-4 py-2 text-right", children: "Requested" }),
                                          jsx("th", { className: "px-4 py-2 text-right", children: "Approved" }),
                                          jsx("th", { className: "px-4 py-2 text-right", children: "Quoted" }),
                                          jsx("th", { className: "px-4 py-2 text-right", children: "Approved Total" }),
                                        ],
                                      }),
                                    ],
                                  }),
                                }),
                                jsx("table", {
                                  className: "w-full text-sm",
                                  children: jsx("tbody", {
                                    className: "divide-y divide-white/[0.04]",
                                    children: (order.items || []).map((item) =>
                                      jsxs(
                                        "tr",
                                        {
                                          className: "text-slate-300",
                                          children: [
                                            jsx("td", {
                                              className: "px-4 py-3",
                                              children: item.item_name_display || item.item_name || "Item",
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-3 text-right text-slate-400",
                                              children: `${item.quantity_requested} ${item.unit || "pcs"}`,
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-3 text-right text-slate-300",
                                              children:
                                                item.quantity_approved !== null && item.quantity_approved !== undefined
                                                  ? `${item.quantity_approved} ${item.unit || "pcs"}`
                                                  : "—",
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-3 text-right text-slate-400",
                                              children: formatMoney(item.quoted_unit_price),
                                            }),
                                            jsx("td", {
                                              className: "px-4 py-3 text-right font-medium text-emerald-300",
                                              children: formatMoney(item.approved_total || calculateLineTotal(item)),
                                            }),
                                          ],
                                        },
                                        item.id,
                                      ),
                                    ),
                                  }),
                                }),
                              ],
                            }),
                            order.approval_trail?.length
                              ? jsxs("div", {
                                  className: "mt-4 space-y-2",
                                  children: [
                                    jsx("p", {
                                      className: "text-xs font-semibold uppercase tracking-wider text-slate-500",
                                      children: "Approval Trail",
                                    }),
                                    order.approval_trail.map((entry, index) =>
                                      jsxs(
                                        "div",
                                        {
                                          className: "rounded-xl border border-white/[0.06] bg-white/[0.03] px-4 py-3 text-xs text-slate-400",
                                          children: [
                                            jsxs("div", {
                                              className: "flex flex-wrap items-center justify-between gap-2",
                                              children: [
                                                jsx("span", {
                                                  className: "font-semibold text-slate-200",
                                                  children: `${entry.action} · ${entry.status}`,
                                                }),
                                                jsx("span", { children: formatDate(entry.timestamp) }),
                                              ],
                                            }),
                                            jsxs("p", {
                                              className: "mt-1",
                                              children: ["By ", jsx("span", { className: "text-slate-200", children: entry.actor || "System" })],
                                            }),
                                            entry.notes &&
                                              jsx("p", {
                                                className: "mt-1 text-slate-500",
                                                children: entry.notes,
                                              }),
                                          ],
                                        },
                                        `${entry.timestamp || index}-${index}`,
                                      ),
                                    ),
                                  ],
                                })
                              : null,
                          ],
                        }),
                    ],
                  },
                  order.id,
                );
              })
            : jsx("div", {
                className: "rounded-2xl border border-white/[0.07] bg-white/[0.02] p-10 text-center text-slate-500",
                children: "No procurement requests found.",
              }),
      }),
      reviewState.orderId !== null &&
        jsx("div", {
          className: "fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4",
          children: jsxs("div", {
            className: "w-full max-w-md rounded-2xl border border-white/[0.07] bg-[#0d1421] p-6",
            children: [
              jsx("h3", {
                className: "text-lg font-semibold text-white",
                children: reviewState.action === "REJECT" ? "Reject Procurement" : "Approve Procurement",
              }),
              jsx("p", {
                className: "mt-1 text-sm text-slate-400",
                children: "Add a short note so the approval trail stays easy to audit later.",
              }),
              jsxs("div", {
                className: "mt-4",
                children: [
                  jsx("label", { className: "mb-1 block text-xs text-slate-400", children: "Notes" }),
                  jsx("textarea", {
                    rows: 3,
                    value: reviewState.notes,
                    onChange: (event) =>
                      setReviewState((current) => ({ ...current, notes: event.target.value })),
                    className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                  }),
                ],
              }),
              jsxs("div", {
                className: "mt-5 flex justify-end gap-3",
                children: [
                  jsx("button", {
                    onClick: () => setReviewState({ orderId: null, action: "APPROVE", notes: "" }),
                    className: "rounded-xl px-4 py-2 text-sm text-slate-400 transition hover:text-white",
                    children: "Cancel",
                  }),
                  jsx("button", {
                    onClick: submitReview,
                    disabled: saving,
                    className: `rounded-xl px-4 py-2 text-sm font-semibold text-white transition disabled:opacity-60 ${
                      reviewState.action === "REJECT"
                        ? "bg-rose-600 hover:bg-rose-500"
                        : "bg-emerald-600 hover:bg-emerald-500"
                    }`,
                    children: saving
                      ? "Saving..."
                      : reviewState.action === "REJECT"
                        ? "Confirm Reject"
                        : "Confirm Approve",
                  }),
                ],
              }),
            ],
          }),
        }),
    ],
  });
}

export default StoreRequestsPage;
