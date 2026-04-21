import { r as React, j as e, b as api } from "./index-D7ltaYVC.js";

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.07)",
};

const inputClass =
  "w-full rounded-xl bg-white/[0.06] border border-white/[0.1] px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500/60";

const primaryButton =
  "rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-sm font-semibold px-4 py-2 transition disabled:opacity-40 disabled:cursor-not-allowed";

const secondaryButton =
  "rounded-xl border border-white/[0.1] hover:bg-white/[0.05] text-slate-300 text-sm px-4 py-2 transition disabled:opacity-40 disabled:cursor-not-allowed";

const dangerButton =
  "rounded-xl border border-red-500/40 hover:bg-red-500/10 text-red-400 text-sm px-3 py-1.5 transition disabled:opacity-40";

const EMPTY_FORM = {
  name: "",
  host: "",
  ip_version: "ipv4",
  port: 8443,
  use_https: false,
  username: "admin",
  password: "admin123",
  device_model: "",
  sync_days_back: 7,
  is_active: true,
  notes: "",
};

function normalizeRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
}

function formatTimestamp(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

function parseSyncResult(value) {
  if (!value) return null;
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function readError(err, fallback) {
  const data = err?.response?.data;
  if (typeof data === "string" && data) return data;
  if (typeof data?.detail === "string" && data.detail) return data.detail;
  if (typeof data?.error === "string" && data.error) return data.error;
  if (typeof data?.message === "string" && data.message) return data.message;
  try {
    return JSON.stringify(data) || fallback;
  } catch {
    return fallback;
  }
}

function SmartPSSPage() {
  const fileInputRef = React.useRef(null);
  const [sources, setSources] = React.useState([]);
  const [logs, setLogs] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [showForm, setShowForm] = React.useState(false);
  const [editingSource, setEditingSource] = React.useState(null);
  const [form, setForm] = React.useState({ ...EMPTY_FORM });
  const [saving, setSaving] = React.useState(false);
  const [formError, setFormError] = React.useState("");
  const [testResults, setTestResults] = React.useState({});
  const [testingId, setTestingId] = React.useState(null);
  const [syncResults, setSyncResults] = React.useState({});
  const [syncingId, setSyncingId] = React.useState(null);
  const [importResult, setImportResult] = React.useState(null);
  const [importing, setImporting] = React.useState(false);
  const [selectedSourceId, setSelectedSourceId] = React.useState("");

  const loadData = React.useCallback(async () => {
    setLoading(true);
    try {
      const [sourceResponse, logResponse] = await Promise.all([
        api.get("/clockin/smartpss/sources/"),
        api.get("/clockin/smartpss/logs/"),
      ]);
      setSources(normalizeRows(sourceResponse.data));
      setLogs(normalizeRows(logResponse.data));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  const openCreateForm = () => {
    setEditingSource(null);
    setForm({ ...EMPTY_FORM });
    setFormError("");
    setShowForm(true);
  };

  const openEditForm = (source) => {
    setEditingSource(source);
    setForm({
      name: source.name || "",
      host: source.host || "",
      ip_version: source.ip_version || "ipv4",
      port: source.port || 8443,
      use_https: !!source.use_https,
      username: source.username || "admin",
      password: "",
      device_model: source.device_model || "",
      sync_days_back: source.sync_days_back || 7,
      is_active: source.is_active !== false,
      notes: source.notes || "",
    });
    setFormError("");
    setShowForm(true);
  };

  const saveSource = async () => {
    if (!form.name.trim()) {
      setFormError("Name is required.");
      return;
    }
    if (!form.host.trim()) {
      setFormError("Host / IP address is required.");
      return;
    }

    setSaving(true);
    setFormError("");
    try {
      const payload = { ...form };
      if (!payload.password) delete payload.password;
      if (editingSource) {
        await api.patch(`/clockin/smartpss/sources/${editingSource.id}/`, payload);
      } else {
        await api.post("/clockin/smartpss/sources/", payload);
      }
      setShowForm(false);
      await loadData();
    } catch (err) {
      setFormError(readError(err, "Save failed."));
    } finally {
      setSaving(false);
    }
  };

  const deleteSource = async (source) => {
    if (!confirm(`Delete SmartPSS source "${source.name}"?`)) return;
    await api.delete(`/clockin/smartpss/sources/${source.id}/`);
    await loadData();
  };

  const testConnection = async (source) => {
    setTestingId(source.id);
    setTestResults((current) => ({
      ...current,
      [source.id]: { ok: false, message: "Testing..." },
    }));
    try {
      const response = await api.post(`/clockin/smartpss/sources/${source.id}/test/`);
      setTestResults((current) => ({ ...current, [source.id]: response.data }));
    } catch (err) {
      setTestResults((current) => ({
        ...current,
        [source.id]: {
          ok: false,
          message: readError(err, "Network error"),
        },
      }));
    } finally {
      setTestingId(null);
    }
  };

  const pullSync = async (source) => {
    setSyncingId(source.id);
    setSyncResults((current) => ({ ...current, [source.id]: null }));
    try {
      const response = await api.post(`/clockin/smartpss/sources/${source.id}/sync/`);
      setSyncResults((current) => ({ ...current, [source.id]: response.data }));
      await loadData();
    } catch (err) {
      const data = err?.response?.data;
      setSyncResults((current) => ({
        ...current,
        [source.id]: {
          error: data?.error || data?.detail || "Sync failed.",
          tip: data?.tip,
        },
      }));
    } finally {
      setSyncingId(null);
    }
  };

  const importCsv = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;

    setImporting(true);
    setImportResult(null);
    try {
      const payload = new FormData();
      payload.append("file", file);
      if (selectedSourceId) payload.append("source_id", selectedSourceId);
      const response = await api.post("/clockin/smartpss/import-csv/", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setImportResult(response.data);
      await loadData();
    } catch (err) {
      const data = err?.response?.data;
      setImportResult({
        error: data?.error || "Upload failed.",
        tip: data?.tip,
      });
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return e.jsxs("div", {
    style: { background: "#070b12", minHeight: "100vh", color: "#e2e8f0", fontFamily: "Inter, sans-serif" },
    className: "p-4 sm:p-6",
    children: [
      e.jsxs("div", {
        className: "mb-6 flex flex-wrap items-center justify-between gap-4",
        children: [
          e.jsxs("div", {
            children: [
              e.jsx("h1", {
                style: { color: "#10b981", fontSize: "1.5rem", fontWeight: 700 },
                children: "SmartPSS Lite Integration",
              }),
              e.jsx("p", {
                style: { color: "#94a3b8", fontSize: "0.85rem", marginTop: "4px" },
                children: "Pull attendance data from Dahua SmartPSS Lite via API sync or CSV import.",
              }),
            ],
          }),
          e.jsx("button", {
            className: primaryButton,
            onClick: openCreateForm,
            children: "+ Add SmartPSS Source",
          }),
        ],
      }),
      e.jsxs("div", {
        style: {
          ...panelStyle,
          borderRadius: "16px",
          padding: "16px 20px",
          marginBottom: "24px",
          borderLeft: "3px solid #10b981",
        },
        children: [
          e.jsx("p", {
            style: { fontWeight: 600, marginBottom: "8px", color: "#10b981", fontSize: "0.9rem" },
            children: "How SmartPSS Lite Sync Works",
          }),
          e.jsxs("div", {
            style: {
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "12px",
              fontSize: "0.8rem",
              color: "#94a3b8",
            },
            children: [
              e.jsxs("div", {
                children: [
                  e.jsx("p", {
                    style: { color: "#e2e8f0", fontWeight: 600, marginBottom: "4px" },
                    children: "API Pull Mode",
                  }),
                  e.jsx("p", {
                    children:
                      "Best when your school has a static IP and port forwarding to the SmartPSS Lite PC.",
                  }),
                ],
              }),
              e.jsxs("div", {
                children: [
                  e.jsx("p", {
                    style: { color: "#e2e8f0", fontWeight: 600, marginBottom: "4px" },
                    children: "CSV Import Mode",
                  }),
                  e.jsx("p", {
                    children:
                      "Works everywhere. Export attendance CSV from SmartPSS Lite and upload it here.",
                  }),
                ],
              }),
              e.jsxs("div", {
                children: [
                  e.jsx("p", {
                    style: { color: "#e2e8f0", fontWeight: 600, marginBottom: "4px" },
                    children: "IPv6 Support",
                  }),
                  e.jsx("p", {
                    children:
                      "Choose IPv4 or IPv6 when saving a source. IPv6 hosts are bracketed automatically in API URLs.",
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
      showForm &&
        e.jsxs("div", {
          style: { ...panelStyle, borderRadius: "16px", padding: "24px", marginBottom: "24px" },
          children: [
            e.jsx("h2", {
              style: { fontWeight: 600, marginBottom: "16px", fontSize: "1rem" },
              children: editingSource ? `Edit: ${editingSource.name}` : "Add SmartPSS Lite Source",
            }),
            e.jsxs("div", {
              style: {
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: "14px",
              },
              children: [
                e.jsxs("div", {
                  children: [
                    e.jsx("label", {
                      style: { display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" },
                      children: "Name *",
                    }),
                    e.jsx("input", {
                      className: inputClass,
                      placeholder: "Main Office SmartPSS",
                      value: form.name,
                      onChange: (event) =>
                        setForm((current) => ({ ...current, name: event.target.value })),
                    }),
                  ],
                }),
                e.jsxs("div", {
                  children: [
                    e.jsx("label", {
                      style: { display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" },
                      children: "Host / IP Address *",
                    }),
                    e.jsx("input", {
                      className: inputClass,
                      placeholder: form.ip_version === "ipv6" ? "2001:db8::200" : "192.168.1.200",
                      value: form.host,
                      onChange: (event) =>
                        setForm((current) => ({ ...current, host: event.target.value })),
                    }),
                  ],
                }),
                e.jsxs("div", {
                  children: [
                    e.jsx("label", {
                      style: { display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" },
                      children: "IP Version",
                    }),
                    e.jsxs("select", {
                      className: inputClass,
                      value: form.ip_version,
                      onChange: (event) =>
                        setForm((current) => ({ ...current, ip_version: event.target.value })),
                      children: [
                        e.jsx("option", { value: "ipv4", children: "IPv4" }),
                        e.jsx("option", { value: "ipv6", children: "IPv6" }),
                      ],
                    }),
                  ],
                }),
                e.jsxs("div", {
                  children: [
                    e.jsx("label", {
                      style: { display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" },
                      children: "Port",
                    }),
                    e.jsx("input", {
                      className: inputClass,
                      type: "number",
                      value: form.port,
                      onChange: (event) =>
                        setForm((current) => ({
                          ...current,
                          port: parseInt(event.target.value, 10) || 8443,
                        })),
                    }),
                  ],
                }),
                e.jsxs("div", {
                  children: [
                    e.jsx("label", {
                      style: { display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" },
                      children: "Username",
                    }),
                    e.jsx("input", {
                      className: inputClass,
                      value: form.username,
                      onChange: (event) =>
                        setForm((current) => ({ ...current, username: event.target.value })),
                    }),
                  ],
                }),
                e.jsxs("div", {
                  children: [
                    e.jsxs("label", {
                      style: { display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" },
                      children: ["Password ", editingSource ? "(leave blank to keep current)" : ""],
                    }),
                    e.jsx("input", {
                      className: inputClass,
                      type: "password",
                      value: form.password,
                      onChange: (event) =>
                        setForm((current) => ({ ...current, password: event.target.value })),
                    }),
                  ],
                }),
                e.jsxs("div", {
                  children: [
                    e.jsx("label", {
                      style: { display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" },
                      children: "Sync Days Back",
                    }),
                    e.jsx("input", {
                      className: inputClass,
                      type: "number",
                      min: 1,
                      max: 90,
                      value: form.sync_days_back,
                      onChange: (event) =>
                        setForm((current) => ({
                          ...current,
                          sync_days_back: parseInt(event.target.value, 10) || 7,
                        })),
                    }),
                  ],
                }),
                e.jsxs("div", {
                  children: [
                    e.jsx("label", {
                      style: { display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" },
                      children: "Device Model",
                    }),
                    e.jsx("input", {
                      className: inputClass,
                      placeholder: "e.g. ASI7213X-T1",
                      value: form.device_model,
                      onChange: (event) =>
                        setForm((current) => ({ ...current, device_model: event.target.value })),
                    }),
                  ],
                }),
                e.jsxs("div", {
                  style: { display: "flex", alignItems: "center", gap: "24px", paddingTop: "20px" },
                  children: [
                    e.jsxs("label", {
                      style: { display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", fontSize: "0.85rem" },
                      children: [
                        e.jsx("input", {
                          type: "checkbox",
                          checked: form.use_https,
                          onChange: (event) =>
                            setForm((current) => ({ ...current, use_https: event.target.checked })),
                        }),
                        "Use HTTPS",
                      ],
                    }),
                    e.jsxs("label", {
                      style: { display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", fontSize: "0.85rem" },
                      children: [
                        e.jsx("input", {
                          type: "checkbox",
                          checked: form.is_active,
                          onChange: (event) =>
                            setForm((current) => ({ ...current, is_active: event.target.checked })),
                        }),
                        "Active",
                      ],
                    }),
                  ],
                }),
                e.jsxs("div", {
                  style: { gridColumn: "1 / -1" },
                  children: [
                    e.jsx("label", {
                      style: { display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" },
                      children: "Notes",
                    }),
                    e.jsx("input", {
                      className: inputClass,
                      placeholder: "Optional notes",
                      value: form.notes,
                      onChange: (event) =>
                        setForm((current) => ({ ...current, notes: event.target.value })),
                    }),
                  ],
                }),
              ],
            }),
            formError &&
              e.jsx("p", {
                style: { color: "#f87171", fontSize: "0.8rem", marginTop: "12px" },
                children: formError,
              }),
            e.jsxs("div", {
              style: { display: "flex", gap: "10px", marginTop: "18px" },
              children: [
                e.jsx("button", {
                  className: primaryButton,
                  onClick: saveSource,
                  disabled: saving,
                  children: saving ? "Saving..." : editingSource ? "Update Source" : "Add Source",
                }),
                e.jsx("button", {
                  className: secondaryButton,
                  onClick: () => setShowForm(false),
                  children: "Cancel",
                }),
              ],
            }),
          ],
        }),
      loading
        ? e.jsx("div", {
            style: { ...panelStyle, borderRadius: "16px", padding: "40px", textAlign: "center", color: "#94a3b8" },
            children: "Loading SmartPSS sources...",
          })
        : sources.length === 0 && !showForm
          ? e.jsxs("div", {
              style: { ...panelStyle, borderRadius: "16px", padding: "48px", textAlign: "center" },
              children: [
                e.jsx("p", { style: { fontSize: "2rem", marginBottom: "12px" }, children: "PC" }),
                e.jsx("p", { style: { color: "#94a3b8", marginBottom: "8px" }, children: "No SmartPSS Lite sources configured yet." }),
                e.jsx("p", {
                  style: { color: "#64748b", fontSize: "0.8rem", marginBottom: "20px" },
                  children: "Add your SmartPSS Lite PC details to start pulling attendance data, or use CSV import below.",
                }),
                e.jsx("button", { className: primaryButton, onClick: openCreateForm, children: "+ Add SmartPSS Source" }),
              ],
            })
          : e.jsx("div", {
              style: { display: "flex", flexDirection: "column", gap: "16px", marginBottom: "32px" },
              children: sources.map((source) => {
                const testResult = testResults[source.id];
                const syncResult = syncResults[source.id];
                const lastSyncResult = parseSyncResult(source.last_sync_result);
                return e.jsxs(
                  "div",
                  {
                    style: { ...panelStyle, borderRadius: "16px", padding: "20px" },
                    children: [
                      e.jsxs("div", {
                        style: {
                          display: "flex",
                          flexWrap: "wrap",
                          alignItems: "flex-start",
                          justifyContent: "space-between",
                          gap: "12px",
                        },
                        children: [
                          e.jsxs("div", {
                            children: [
                              e.jsxs("div", {
                                style: { display: "flex", alignItems: "center", gap: "10px" },
                                children: [
                                  e.jsx("span", {
                                    style: { fontWeight: 600, fontSize: "1rem" },
                                    children: source.name,
                                  }),
                                  source.is_active
                                    ? e.jsx("span", {
                                        style: {
                                          background: "rgba(16,185,129,0.15)",
                                          color: "#10b981",
                                          borderRadius: "6px",
                                          fontSize: "0.7rem",
                                          padding: "2px 8px",
                                        },
                                        children: "Active",
                                      })
                                    : e.jsx("span", {
                                        style: {
                                          background: "rgba(148,163,184,0.12)",
                                          color: "#94a3b8",
                                          borderRadius: "6px",
                                          fontSize: "0.7rem",
                                          padding: "2px 8px",
                                        },
                                        children: "Inactive",
                                      }),
                                  e.jsx("span", {
                                    style: {
                                      background: "rgba(59,130,246,0.12)",
                                      color: "#93c5fd",
                                      borderRadius: "6px",
                                      fontSize: "0.7rem",
                                      padding: "2px 8px",
                                      textTransform: "uppercase",
                                    },
                                    children: source.ip_version || "ipv4",
                                  }),
                                ],
                              }),
                              e.jsxs("p", {
                                style: { color: "#94a3b8", fontSize: "0.8rem", marginTop: "4px" },
                                children: [
                                  source.api_url,
                                  " | Sync ",
                                  source.sync_days_back,
                                  "d back",
                                  source.device_model &&
                                    e.jsxs(e.Fragment, {
                                      children: [" | ", e.jsx("span", { style: { color: "#10b981" }, children: source.device_model })],
                                    }),
                                ],
                              }),
                              e.jsxs("p", {
                                style: { color: "#64748b", fontSize: "0.75rem", marginTop: "2px" },
                                children: [
                                  "Last sync: ",
                                  formatTimestamp(source.last_sync_at),
                                  lastSyncResult &&
                                    ` | ${lastSyncResult.records_saved ?? 0} saved, ${lastSyncResult.skipped ?? 0} skipped`,
                                ],
                              }),
                            ],
                          }),
                          e.jsxs("div", {
                            style: { display: "flex", gap: "8px", flexWrap: "wrap" },
                            children: [
                              e.jsx("button", {
                                className: secondaryButton,
                                onClick: () => testConnection(source),
                                disabled: testingId === source.id,
                                children: testingId === source.id ? "Testing..." : "Test",
                              }),
                              e.jsx("button", {
                                className: primaryButton,
                                onClick: () => pullSync(source),
                                disabled: syncingId === source.id || !source.is_active,
                                children: syncingId === source.id ? "Syncing..." : "Pull Sync",
                              }),
                              e.jsx("button", {
                                className: secondaryButton,
                                onClick: () => openEditForm(source),
                                children: "Edit",
                              }),
                              e.jsx("button", {
                                className: dangerButton,
                                onClick: () => deleteSource(source),
                                children: "Delete",
                              }),
                            ],
                          }),
                        ],
                      }),
                      testResult &&
                        e.jsxs("div", {
                          style: {
                            marginTop: "12px",
                            borderRadius: "10px",
                            padding: "10px 14px",
                            fontSize: "0.8rem",
                            background: testResult.ok ? "rgba(16,185,129,0.1)" : "rgba(248,113,113,0.1)",
                            border: `1px solid ${
                              testResult.ok ? "rgba(16,185,129,0.3)" : "rgba(248,113,113,0.3)"
                            }`,
                            color: testResult.ok ? "#6ee7b7" : "#fca5a5",
                          },
                          children: [
                            testResult.ok ? "OK " : "FAIL ",
                            testResult.message,
                          ],
                        }),
                      syncResult &&
                        e.jsx("div", {
                          style: {
                            marginTop: "12px",
                            borderRadius: "10px",
                            padding: "10px 14px",
                            fontSize: "0.8rem",
                            background: syncResult.error ? "rgba(248,113,113,0.1)" : "rgba(16,185,129,0.08)",
                            border: `1px solid ${
                              syncResult.error ? "rgba(248,113,113,0.3)" : "rgba(16,185,129,0.2)"
                            }`,
                          },
                          children: syncResult.error
                            ? e.jsxs(e.Fragment, {
                                children: [
                                  e.jsxs("p", { style: { color: "#fca5a5" }, children: ["Sync failed: ", syncResult.error] }),
                                  syncResult.tip &&
                                    e.jsx("p", {
                                      style: { color: "#94a3b8", marginTop: "6px", fontSize: "0.75rem" },
                                      children: syncResult.tip,
                                    }),
                                ],
                              })
                            : e.jsxs("div", {
                                style: { display: "flex", gap: "20px", flexWrap: "wrap", color: "#6ee7b7" },
                                children: [
                                  e.jsx("span", { children: "Sync complete" }),
                                  e.jsxs("span", { children: ["Found: ", e.jsx("strong", { children: syncResult.records_found })] }),
                                  e.jsxs("span", { children: ["Saved: ", e.jsx("strong", { style: { color: "#10b981" }, children: syncResult.records_saved })] }),
                                  e.jsxs("span", { children: ["Skipped: ", e.jsx("strong", { children: syncResult.skipped })] }),
                                  syncResult.errors > 0 &&
                                    e.jsxs("span", { style: { color: "#f87171" }, children: ["Errors: ", syncResult.errors] }),
                                ],
                              }),
                        }),
                    ],
                  },
                  source.id,
                );
              }),
            }),
      e.jsxs("div", {
        style: { ...panelStyle, borderRadius: "16px", padding: "24px", marginBottom: "32px" },
        children: [
          e.jsx("h2", { style: { fontWeight: 600, marginBottom: "4px", fontSize: "1rem" }, children: "CSV Import" }),
          e.jsx("p", {
            style: { color: "#94a3b8", fontSize: "0.8rem", marginBottom: "16px" },
            children: "Export attendance CSV from SmartPSS Lite and upload it here. IPv4 and IPv6 source records can both be linked.",
          }),
          e.jsxs("div", {
            style: { display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px" },
            children: [
              e.jsx("input", {
                type: "file",
                accept: ".csv,.xlsx,.xls",
                ref: fileInputRef,
                style: { color: "#94a3b8", fontSize: "0.85rem" },
              }),
              sources.length > 0 &&
                e.jsxs("select", {
                  value: selectedSourceId,
                  onChange: (event) => setSelectedSourceId(event.target.value),
                  style: {
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: "10px",
                    padding: "7px 12px",
                    color: "#e2e8f0",
                    fontSize: "0.85rem",
                  },
                  children: [
                    e.jsx("option", { value: "", children: "- Source (optional) -" }),
                    sources.map((source) =>
                      e.jsx("option", { value: source.id, children: source.name }, source.id),
                    ),
                  ],
                }),
              e.jsx("button", {
                className: primaryButton,
                onClick: importCsv,
                disabled: importing,
                children: importing ? "Importing..." : "Import CSV",
              }),
            ],
          }),
          importResult &&
            e.jsx("div", {
              style: {
                marginTop: "14px",
                borderRadius: "10px",
                padding: "12px 16px",
                fontSize: "0.85rem",
                background: importResult.error ? "rgba(248,113,113,0.1)" : "rgba(16,185,129,0.08)",
                border: `1px solid ${
                  importResult.error ? "rgba(248,113,113,0.3)" : "rgba(16,185,129,0.2)"
                }`,
              },
              children: importResult.error
                ? e.jsxs(e.Fragment, {
                    children: [
                      e.jsxs("p", { style: { color: "#fca5a5" }, children: ["Import failed: ", importResult.error] }),
                      importResult.tip &&
                        e.jsx("p", {
                          style: { color: "#94a3b8", marginTop: "6px", fontSize: "0.75rem" },
                          children: importResult.tip,
                        }),
                    ],
                  })
                : e.jsxs("div", {
                    style: { display: "flex", gap: "24px", flexWrap: "wrap", color: "#6ee7b7" },
                    children: [
                      e.jsxs("span", {
                        children: ["Imported ", e.jsx("em", { style: { color: "#94a3b8" }, children: importResult.filename })],
                      }),
                      e.jsxs("span", { children: ["Found: ", e.jsx("strong", { children: importResult.records_found })] }),
                      e.jsxs("span", { children: ["Saved: ", e.jsx("strong", { style: { color: "#10b981" }, children: importResult.records_saved })] }),
                      e.jsxs("span", { children: ["Skipped: ", e.jsx("strong", { children: importResult.skipped })] }),
                      importResult.errors > 0 &&
                        e.jsxs("span", { style: { color: "#f87171" }, children: ["Errors: ", importResult.errors] }),
                    ],
                  }),
            }),
        ],
      }),
      e.jsxs("div", {
        style: { ...panelStyle, borderRadius: "16px", padding: "24px" },
        children: [
          e.jsx("h2", { style: { fontWeight: 600, marginBottom: "16px", fontSize: "1rem" }, children: "Import / Sync History" }),
          logs.length === 0
            ? e.jsx("p", { style: { color: "#64748b", fontSize: "0.85rem" }, children: "No sync or import activity yet." })
            : e.jsx("div", {
                style: { overflowX: "auto" },
                children: e.jsxs("table", {
                  style: { width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" },
                  children: [
                    e.jsx("thead", {
                      children: e.jsx("tr", {
                        style: { borderBottom: "1px solid rgba(255,255,255,0.07)" },
                        children: ["Source", "Type", "Started", "Found", "Saved", "Skipped", "Errors"].map((label) =>
                          e.jsx(
                            "th",
                            {
                              style: { padding: "8px 10px", textAlign: "left", color: "#64748b", fontWeight: 500 },
                              children: label,
                            },
                            label,
                          ),
                        ),
                      }),
                    }),
                    e.jsx("tbody", {
                      children: logs.map((entry) =>
                        e.jsxs(
                          "tr",
                          {
                            style: { borderBottom: "1px solid rgba(255,255,255,0.04)" },
                            children: [
                              e.jsx("td", { style: { padding: "8px 10px", color: "#e2e8f0" }, children: entry.source_name ?? "-" }),
                              e.jsx("td", {
                                style: { padding: "8px 10px" },
                                children: e.jsx("span", {
                                  style: {
                                    background: entry.source_type === "API" ? "rgba(16,185,129,0.15)" : "rgba(99,102,241,0.15)",
                                    color: entry.source_type === "API" ? "#6ee7b7" : "#a5b4fc",
                                    borderRadius: "6px",
                                    padding: "2px 8px",
                                    fontWeight: 500,
                                  },
                                  children: entry.source_type,
                                }),
                              }),
                              e.jsx("td", { style: { padding: "8px 10px", color: "#94a3b8" }, children: formatTimestamp(entry.started_at) }),
                              e.jsx("td", { style: { padding: "8px 10px", textAlign: "center" }, children: entry.records_found }),
                              e.jsx("td", { style: { padding: "8px 10px", textAlign: "center", color: "#10b981", fontWeight: 600 }, children: entry.records_saved }),
                              e.jsx("td", { style: { padding: "8px 10px", textAlign: "center", color: "#94a3b8" }, children: entry.skipped }),
                              e.jsx("td", { style: { padding: "8px 10px", textAlign: "center", color: entry.errors > 0 ? "#f87171" : "#64748b" }, children: entry.errors }),
                            ],
                          },
                          entry.id,
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

export { SmartPSSPage as default };
