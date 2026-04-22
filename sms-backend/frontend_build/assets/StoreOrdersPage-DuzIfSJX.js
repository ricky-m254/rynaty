import { r as React, j as e, b as api } from "./index-D7ltaYVC.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";
import { P as PlusIcon } from "./plus-CQ41G_RD.js";
import { C as CheckIcon } from "./check-BI53z6hp.js";
import { X as CloseIcon } from "./x-CEi3D4aT.js";
import { C as ChevronDownIcon } from "./chevron-down-BMVcUee6.js";
import { C as ChevronUpIcon } from "./chevron-up-CAnJkIyv.js";
import { R as RefreshIcon } from "./refresh-cw-DOVkzt4u.js";
import { P as PackageIcon } from "./package-KitsIxSS.js";
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

function createLineItem() {
  return {
    item: "",
    item_name: "",
    unit: "pcs",
    quantity_requested: 1,
    quoted_unit_price: "",
    notes: "",
  };
}

function calculateLineTotal(item) {
  const quantity = Number(item.quantity_approved ?? item.quantity_requested ?? 0);
  const approvedTotal = Number(item.approved_total ?? 0);
  const unitPrice = Number(item.quoted_unit_price ?? 0);
  if (Number.isNaN(quantity) || Number.isNaN(unitPrice)) return 0;
  if (!Number.isNaN(approvedTotal) && approvedTotal > 0) {
    return approvedTotal;
  }
  return quantity * unitPrice;
}

function StoreOrdersPage() {
  const [dashboard, setDashboard] = React.useState({
    pending_procurement_orders: 0,
    pending_lpo_orders: 0,
    pending_lso_orders: 0,
    approved_procurement_total: 0,
  });
  const [orders, setOrders] = React.useState([]);
  const [items, setItems] = React.useState([]);
  const [suppliers, setSuppliers] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [notice, setNotice] = React.useState(null);
  const [error, setError] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");
  const [procurementFilter, setProcurementFilter] = React.useState("");
  const [expandedOrders, setExpandedOrders] = React.useState(() => new Set());
  const [createOpen, setCreateOpen] = React.useState(false);
  const [reviewState, setReviewState] = React.useState({
    orderId: null,
    action: "APPROVE",
    notes: "",
  });
  const [form, setForm] = React.useState({
    title: "",
    description: "",
    notes: "",
    procurement_type: "LPO",
    send_to: "FINANCE",
    supplier: "",
    order_items: [createLineItem()],
  });

  const procurementTypeOptions = React.useMemo(
    () => [
      { value: "LPO", label: PROCUREMENT_LABELS.LPO },
      { value: "LSO", label: PROCUREMENT_LABELS.LSO },
    ],
    [],
  );

  const refreshData = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (procurementFilter) params.procurement_type = procurementFilter;

      const [dashboardResponse, ordersResponse, itemsResponse, suppliersResponse] = await Promise.all([
        api.get("/store/dashboard/").catch(() => ({ data: {} })),
        api.get("/store/orders/", { params }),
        api.get("/store/items/", { params: { is_active: "true" } }),
        api.get("/store/suppliers/", { params: { is_active: "true" } }),
      ]);

      setDashboard(dashboardResponse.data ?? {});
      const orderPayload = ordersResponse.data?.results ?? ordersResponse.data ?? [];
      setOrders(Array.isArray(orderPayload) ? orderPayload : []);
      const itemPayload = itemsResponse.data?.results ?? itemsResponse.data ?? [];
      setItems(Array.isArray(itemPayload) ? itemPayload : []);
      const supplierPayload = suppliersResponse.data?.results ?? suppliersResponse.data ?? [];
      setSuppliers(Array.isArray(supplierPayload) ? supplierPayload : []);
    } catch (err) {
      setError(extractError(err, "Failed to load store procurement data."));
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

  const updateLineItem = (index, key, value) => {
    setForm((current) => {
      const nextItems = current.order_items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [key]: value } : item,
      );
      return { ...current, order_items: nextItems };
    });
  };

  const addLineItem = () => {
    setForm((current) => ({ ...current, order_items: [...current.order_items, createLineItem()] }));
  };

  const removeLineItem = (index) => {
    setForm((current) => ({
      ...current,
      order_items: current.order_items.filter((_, itemIndex) => itemIndex !== index),
    }));
  };

  const submitOrder = async () => {
    const usableItems = form.order_items.filter((item) => item.item || item.item_name.trim());
    if (!form.title.trim() || !form.supplier || !usableItems.length) {
      setError("Choose a supplier, give the procurement a title, and add at least one line item.");
      return;
    }

    setSaving(true);
    setError("");
    setNotice(null);
    try {
      await api.post("/store/orders/", {
        title: form.title.trim(),
        description: form.description.trim(),
        notes: form.notes.trim(),
        procurement_type: form.procurement_type,
        office_owner: form.procurement_type === "LSO" ? "ADMIN" : "FINANCE",
        send_to: form.send_to,
        supplier: Number(form.supplier),
        order_items: usableItems.map((item) => ({
          item: item.item ? Number(item.item) : null,
          item_name: item.item_name.trim(),
          unit: item.unit.trim() || "pcs",
          quantity_requested: Number(item.quantity_requested || 1),
          quoted_unit_price:
            item.quoted_unit_price === "" || item.quoted_unit_price === null
              ? null
              : Number(item.quoted_unit_price),
          notes: item.notes.trim(),
        })),
      });
      setNotice({ type: "success", text: "Procurement request submitted." });
      setCreateOpen(false);
      setForm({
        title: "",
        description: "",
        notes: "",
        procurement_type: "LPO",
        send_to: "FINANCE",
        supplier: "",
        order_items: [createLineItem()],
      });
      await refreshData();
    } catch (err) {
      setError(extractError(err, "Unable to submit the procurement request."));
    } finally {
      setSaving(false);
    }
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
        reviewState.action === "FULFILL"
          ? "Order marked as received."
          : reviewState.action === "APPROVE"
            ? "Order approved."
            : "Order rejected.";
      setNotice({ type: "success", text: message });
      setReviewState({ orderId: null, action: "APPROVE", notes: "" });
      await refreshData();
    } catch (err) {
      setError(extractError(err, "Unable to update the procurement request."));
    } finally {
      setSaving(false);
    }
  };

  const setReviewAction = (orderId, action) => {
    setReviewState({ orderId, action, notes: "" });
  };

  const summaryCards = [
    {
      label: "Pending Requests",
      value: Number(dashboard.pending_procurement_orders ?? orders.filter((order) => order.status === "PENDING").length),
      accent: "#f59e0b",
    },
    {
      label: "Pending LPOs",
      value: Number(dashboard.pending_lpo_orders ?? orders.filter((order) => order.status === "PENDING" && order.procurement_type === "LPO").length),
      accent: "#8b5cf6",
    },
    {
      label: "Pending LSOs",
      value: Number(dashboard.pending_lso_orders ?? orders.filter((order) => order.status === "PENDING" && order.procurement_type === "LSO").length),
      accent: "#0ea5e9",
    },
    {
      label: "Approved Value",
      value: Number(dashboard.approved_procurement_total ?? 0),
      accent: "#10b981",
      money: true,
    },
  ];

  return jsxs("div", {
    className: "space-y-6",
    children: [
      jsx(PageHero, {
        badge: "STORE",
        badgeColor: "orange",
        title: "Procurement Requests",
        subtitle: "Create LPOs and LSOs, track supplier quotes, and manage receipt state from one screen.",
        icon: "📦",
      }),
      jsxs("div", {
        className: "grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4",
        children: summaryCards.map((card) =>
          jsxs(
            "div",
            {
              className: "rounded-2xl p-4",
              style: {
                background: "rgba(255,255,255,0.03)",
                border: `1px solid ${card.accent}25`,
              },
              children: [
                jsx("p", {
                  className: "text-xs font-semibold uppercase tracking-wider text-slate-400",
                  children: card.label,
                }),
                jsx("p", {
                  className: "mt-2 text-2xl font-bold text-white",
                  children: card.money ? formatMoney(card.value) : card.value,
                }),
              ],
            },
            card.label,
          ),
        ),
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
                  ...procurementTypeOptions.map((option) =>
                    jsx("option", { value: option.value, children: option.label }, option.value),
                  ),
                ],
              }),
              jsx("button", {
                onClick: refreshData,
                className: "flex items-center gap-2 rounded-xl border border-white/[0.07] px-3 py-2 text-sm text-slate-200 transition hover:text-white",
                children: [
                  jsx(RefreshIcon, { size: 14, className: loading ? "animate-spin" : "" }),
                  "Refresh",
                ],
              }),
            ],
          }),
          jsx("button", {
            onClick: () => setCreateOpen(true),
            className: "flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500",
            children: [jsx(PlusIcon, { size: 14 }), "New Request"],
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
                              jsx("h3", {
                                className: "text-lg font-semibold text-white",
                                children: order.title,
                              }),
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
                              jsx("p", {
                                className: "text-xl font-bold text-emerald-400",
                                children: formatMoney(total),
                              }),
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
                                          onClick: () => setReviewAction(order.id, "APPROVE"),
                                          className: "flex items-center gap-1 rounded-lg bg-emerald-500/20 px-3 py-1.5 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/30",
                                          children: [jsx(CheckIcon, { size: 12 }), "Approve"],
                                        }),
                                        jsx("button", {
                                          onClick: () => setReviewAction(order.id, "REJECT"),
                                          className: "flex items-center gap-1 rounded-lg bg-rose-500/20 px-3 py-1.5 text-xs font-semibold text-rose-300 transition hover:bg-rose-500/30",
                                          children: [jsx(CloseIcon, { size: 12 }), "Reject"],
                                        }),
                                      ],
                                    }),
                                  order.status === "APPROVED" &&
                                    jsx("button", {
                                      onClick: () => setReviewAction(order.id, "FULFILL"),
                                      className: "rounded-lg bg-sky-500/20 px-3 py-1.5 text-xs font-semibold text-sky-300 transition hover:bg-sky-500/30",
                                      children: "Mark Received",
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
                            order.received_notes &&
                              jsx("p", {
                                className: "mb-4 rounded-xl border border-sky-500/20 bg-sky-500/5 px-4 py-3 text-sm text-sky-200",
                                children: order.received_notes,
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
      createOpen &&
        jsx("div", {
          className: "fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4",
          children: jsxs("div", {
            className: "max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-white/[0.07] bg-[#0d1421] p-6",
            children: [
              jsxs("div", {
                className: "mb-4 flex items-start justify-between gap-3",
                children: [
                  jsxs("div", {
                    children: [
                      jsx("h2", { className: "text-lg font-semibold text-white", children: "New Procurement Request" }),
                      jsx("p", {
                        className: "text-sm text-slate-400",
                        children: "Choose the supplier, identify the procurement type, and snapshot the quote prices.",
                      }),
                    ],
                  }),
                  jsx("button", {
                    onClick: () => setCreateOpen(false),
                    className: "rounded-lg border border-white/[0.07] p-2 text-slate-400 transition hover:text-white",
                    children: jsx(CloseIcon, { size: 16 }),
                  }),
                ],
              }),
              jsxs("div", {
                className: "grid gap-4 md:grid-cols-2",
                children: [
                  jsxs("div", {
                    className: "md:col-span-2",
                    children: [
                      jsx("label", { className: "mb-1 block text-xs text-slate-400", children: "Title *" }),
                      jsx("input", {
                        value: form.title,
                        onChange: (event) => setForm((current) => ({ ...current, title: event.target.value })),
                        className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                        placeholder: "e.g. Term 2 stationery procurement",
                      }),
                    ],
                  }),
                  jsxs("div", {
                    children: [
                      jsx("label", { className: "mb-1 block text-xs text-slate-400", children: "Procurement Type" }),
                      jsx("select", {
                        value: form.procurement_type,
                        onChange: (event) =>
                          setForm((current) => ({
                            ...current,
                            procurement_type: event.target.value,
                            send_to: event.target.value === "LSO" ? "ADMIN" : "FINANCE",
                          })),
                        className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                        children: procurementTypeOptions.map((option) =>
                          jsx("option", { value: option.value, children: option.label }, option.value),
                        ),
                      }),
                    ],
                  }),
                  jsxs("div", {
                    children: [
                      jsx("label", { className: "mb-1 block text-xs text-slate-400", children: "Route To" }),
                      jsx("select", {
                        value: form.send_to,
                        onChange: (event) => setForm((current) => ({ ...current, send_to: event.target.value })),
                        className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                        children: [
                          jsx("option", { value: "FINANCE", children: "Finance Office" }),
                          jsx("option", { value: "ADMIN", children: "Administration" }),
                          jsx("option", { value: "BOTH", children: "Finance & Admin" }),
                        ],
                      }),
                    ],
                  }),
                  jsxs("div", {
                    children: [
                      jsx("label", { className: "mb-1 block text-xs text-slate-400", children: "Supplier *" }),
                      jsx("select", {
                        value: form.supplier,
                        onChange: (event) => setForm((current) => ({ ...current, supplier: event.target.value })),
                        className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                        children: [
                          jsx("option", { value: "", children: "Select supplier" }),
                          suppliers.map((supplier) =>
                            jsx(
                              "option",
                              {
                                value: supplier.id,
                                children: `${supplier.name}${supplier.product_types ? ` - ${supplier.product_types}` : ""}`,
                              },
                              supplier.id,
                            ),
                          ),
                        ],
                      }),
                    ],
                  }),
                  jsxs("div", {
                    className: "md:col-span-2",
                    children: [
                      jsx("label", { className: "mb-1 block text-xs text-slate-400", children: "Description" }),
                      jsx("textarea", {
                        rows: 2,
                        value: form.description,
                        onChange: (event) => setForm((current) => ({ ...current, description: event.target.value })),
                        className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                      }),
                    ],
                  }),
                  jsxs("div", {
                    className: "md:col-span-2",
                    children: [
                      jsx("label", { className: "mb-1 block text-xs text-slate-400", children: "Notes" }),
                      jsx("textarea", {
                        rows: 2,
                        value: form.notes,
                        onChange: (event) => setForm((current) => ({ ...current, notes: event.target.value })),
                        className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                      }),
                    ],
                  }),
                ],
              }),
              jsxs("div", {
                className: "mt-6",
                children: [
                  jsxs("div", {
                    className: "mb-3 flex items-center justify-between",
                    children: [
                      jsx("h3", { className: "text-sm font-semibold text-white", children: "Line Items" }),
                      jsx("button", {
                        onClick: addLineItem,
                        className: "flex items-center gap-2 rounded-lg border border-white/[0.07] px-3 py-2 text-xs font-semibold text-slate-200 transition hover:text-white",
                        children: [jsx(PlusIcon, { size: 12 }), "Add Item"],
                      }),
                    ],
                  }),
                  jsxs("div", {
                    className: "space-y-3",
                    children: form.order_items.map((lineItem, index) =>
                      jsxs(
                        "div",
                        {
                          className: "grid gap-2 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-3 lg:grid-cols-12",
                          children: [
                            jsx("div", {
                              className: "lg:col-span-4",
                              children: jsxs("select", {
                                value: lineItem.item,
                                onChange: (event) => {
                                  const selectedItem = items.find((item) => String(item.id) === event.target.value);
                                  updateLineItem(index, "item", event.target.value);
                                  if (selectedItem) {
                                    updateLineItem(index, "item_name", selectedItem.name || "");
                                    updateLineItem(index, "unit", selectedItem.unit || "pcs");
                                    updateLineItem(index, "quoted_unit_price", selectedItem.cost_price ?? "");
                                  }
                                },
                                className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                                children: [
                                  jsx("option", { value: "", children: "Select item" }),
                                  items.map((item) =>
                                    jsx(
                                      "option",
                                      {
                                        value: item.id,
                                        children: `${item.name}${item.cost_price ? ` (${formatMoney(item.cost_price)})` : ""}`,
                                      },
                                      item.id,
                                    ),
                                  ),
                                ],
                              }),
                            }),
                            jsx("div", {
                              className: "lg:col-span-2",
                              children: jsx("input", {
                                value: lineItem.item_name,
                                onChange: (event) => updateLineItem(index, "item_name", event.target.value),
                                placeholder: "Custom name",
                                className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                              }),
                            }),
                            jsx("div", {
                              className: "lg:col-span-2",
                              children: jsx("input", {
                                value: lineItem.quantity_requested,
                                onChange: (event) => updateLineItem(index, "quantity_requested", event.target.value),
                                type: "number",
                                min: "0",
                                step: "0.01",
                                placeholder: "Qty",
                                className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                              }),
                            }),
                            jsx("div", {
                              className: "lg:col-span-2",
                              children: jsx("input", {
                                value: lineItem.unit,
                                onChange: (event) => updateLineItem(index, "unit", event.target.value),
                                placeholder: "Unit",
                                className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                              }),
                            }),
                            jsx("div", {
                              className: "lg:col-span-2",
                              children: jsx("input", {
                                value: lineItem.quoted_unit_price,
                                onChange: (event) => updateLineItem(index, "quoted_unit_price", event.target.value),
                                type: "number",
                                min: "0",
                                step: "0.01",
                                placeholder: "Quote",
                                className: "w-full rounded-xl border border-white/[0.07] bg-slate-950 px-3 py-2 text-sm text-white outline-none",
                              }),
                            }),
                            jsx("div", {
                              className: "flex items-start justify-end lg:col-span-12",
                              children: jsx("button", {
                                onClick: () => removeLineItem(index),
                                className: "text-xs font-semibold text-rose-300 transition hover:text-rose-200",
                                children: "Remove",
                              }),
                            }),
                          ],
                        },
                        `${index}-${lineItem.item}-${lineItem.item_name}`,
                      ),
                    ),
                  }),
                ],
              }),
              jsxs("div", {
                className: "mt-6 flex items-center justify-end gap-3",
                children: [
                  jsx("button", {
                    onClick: () => setCreateOpen(false),
                    className: "rounded-xl px-4 py-2 text-sm text-slate-400 transition hover:text-white",
                    children: "Cancel",
                  }),
                  jsx("button", {
                    onClick: submitOrder,
                    disabled: saving,
                    className: "rounded-xl bg-emerald-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-60",
                    children: saving ? "Submitting..." : "Submit Procurement",
                  }),
                ],
              }),
            ],
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
                children:
                  reviewState.action === "FULFILL"
                    ? "Mark Order as Received"
                    : reviewState.action === "REJECT"
                      ? "Reject Procurement"
                      : "Approve Procurement",
              }),
              jsx("p", {
                className: "mt-1 text-sm text-slate-400",
                children: "Leave a short note so the trail clearly shows why this action was taken.",
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
                        : reviewState.action === "FULFILL"
                          ? "bg-sky-600 hover:bg-sky-500"
                          : "bg-emerald-600 hover:bg-emerald-500"
                    }`,
                    children: saving
                      ? "Saving..."
                      : reviewState.action === "FULFILL"
                        ? "Confirm Receipt"
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

export default StoreOrdersPage;
