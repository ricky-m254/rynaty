import { r as React, b as api, j as e } from "./index-D7ltaYVC.js";
import { C as ConfirmDialog } from "./ConfirmDialog-WF6S4jMq.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.07)",
};

const inputClass =
  "w-full rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm outline-none focus:border-emerald-500 transition";

const monoInputClass =
  "w-full rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm font-mono outline-none focus:border-emerald-500 transition";

const QUICK_DEVICES = [
  {
    label: "Dahua ASI6214S",
    ip: "192.168.1.108",
    port: 37777,
    http_port: 80,
    rtsp_port: 37778,
    brand: "Dahua",
    model: "ASI6214S",
    username: "admin",
    password: "admin123",
  },
  {
    label: "ZKTeco",
    ip: "192.168.1.201",
    port: 4370,
    http_port: 80,
    rtsp_port: 0,
    brand: "ZKTeco",
    model: "",
    username: "admin",
    password: "12345",
  },
  {
    label: "Anviz",
    ip: "192.168.1.100",
    port: 5010,
    http_port: 80,
    rtsp_port: 0,
    brand: "Anviz",
    model: "",
    username: "admin",
    password: "12345",
  },
  {
    label: "FingerTec",
    ip: "192.168.1.200",
    port: 4008,
    http_port: 80,
    rtsp_port: 0,
    brand: "FingerTec",
    model: "",
    username: "admin",
    password: "",
  },
];

function defaultDeviceForm() {
  return {
    device_id: "",
    name: "",
    location: "",
    device_type: "BOTH",
    notes: "",
    ip_address: "",
    ip_version: "ipv4",
    port: 37777,
    http_port: 80,
    rtsp_port: 37778,
    channel: 1,
    username: "admin",
    password: "admin123",
    brand: "Dahua",
    model: "",
    serial_number: "",
    mac_address: "",
    firmware_version: "",
    discovery_method: "Manual",
  };
}

function defaultScanPrefix() {
  return "192.168.1";
}

function normalizeRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
}

function readError(err, fallback) {
  const data = err?.response?.data;
  if (typeof data === "string" && data) return data;
  if (typeof data?.detail === "string" && data.detail) return data.detail;
  if (Array.isArray(data?.device_id) && data.device_id[0]) return data.device_id[0];
  if (Array.isArray(data?.ip_address) && data.ip_address[0]) return data.ip_address[0];
  return fallback;
}

function inferIpVersion(value) {
  return typeof value === "string" && value.includes(":") ? "ipv6" : "ipv4";
}

function formatDateTime(value) {
  return value ? new Date(value).toLocaleString() : "Never";
}

function buildQuickDeviceForm(template) {
  return {
    ...defaultDeviceForm(),
    device_id: `${template.ip}:${template.port}`,
    name: `${template.brand}${template.model ? ` ${template.model}` : ""} - Main Entrance`,
    location: "Main Entrance",
    notes: `${template.brand}${template.model ? ` ${template.model}` : ""} - add using known defaults`,
    ip_address: template.ip,
    ip_version: inferIpVersion(template.ip),
    port: template.port,
    http_port: template.http_port,
    rtsp_port: template.rtsp_port,
    username: template.username,
    password: template.password,
    brand: template.brand,
    model: template.model,
    discovery_method: "Manual - Known Defaults",
  };
}

function buildDiscoveredDeviceForm(device) {
  const isDahua =
    (device.brand || "").toLowerCase().includes("dahua") ||
    device.port === 37777 ||
    device.port === 37778;
  return {
    ...defaultDeviceForm(),
    device_id: device.serial || device.device_id || `${device.ip || "device"}:${device.port || 0}`,
    name: `${device.model || device.brand || "Device"} @ ${device.ip || "USB"}`,
    notes: [
      device.discovery_method ? `Auto-detected via ${device.discovery_method}` : "",
      device.model ? `Model: ${device.model}` : "",
      device.serial ? `Serial: ${device.serial}` : "",
      device.mac ? `MAC: ${device.mac}` : "",
      device.technology ? `Tech: ${device.technology}` : "",
    ]
      .filter(Boolean)
      .join("\n"),
    ip_address: device.ip === "USB" ? "" : device.ip || "",
    ip_version: inferIpVersion(device.ip || ""),
    port: device.port === 80 ? 37777 : device.port || 37777,
    http_port: 80,
    rtsp_port: 37778,
    username: "admin",
    password: isDahua ? "admin123" : "",
    brand: device.brand?.split(" ")[0] || "Dahua",
    model: device.model || (isDahua ? "ASI6214S" : ""),
    serial_number: device.serial || "",
    mac_address: device.mac || "",
    discovery_method: device.discovery_method || "Discovery",
  };
}

function DeviceActionsCard({ device }) {
  const [copyState, setCopyState] = React.useState(false);
  const [syncing, setSyncing] = React.useState(false);
  const [message, setMessage] = React.useState("");
  const [showGuide, setShowGuide] = React.useState(false);

  const isDahua =
    (device.brand || "").toLowerCase().includes("dahua") || (device.model || "").includes("ASI");
  const endpoint = `${window.location.origin}/api/clockin/dahua/event/?key=${device.api_key}`;

  const copyEndpoint = async () => {
    try {
      await navigator.clipboard.writeText(endpoint);
      setCopyState(true);
      setTimeout(() => setCopyState(false), 2000);
    } catch {
      setMessage("Copy failed. Select and copy the endpoint manually.");
    }
  };

  const syncNow = async () => {
    setSyncing(true);
    setMessage("");
    try {
      const response = await api.post(`/clockin/dahua/${device.id}/sync/`, {
        date: new Date().toISOString().slice(0, 10),
      });
      setMessage(
        `Synced ${response.data.records_created} new event(s), ${response.data.records_skipped} already recorded.`,
      );
    } catch (err) {
      setMessage(readError(err, "Could not reach device."));
    } finally {
      setSyncing(false);
    }
  };

  return e.jsxs("div", {
    className: "space-y-3",
    children: [
      e.jsxs("div", {
        className: "rounded-xl bg-slate-950 p-3 border border-white/[0.05] space-y-2",
        children: [
          e.jsxs("div", {
            className: "space-y-1",
            children: [
              e.jsx("p", {
                className: "text-[9px] font-bold text-emerald-500 uppercase tracking-widest",
                children: isDahua ? "Dahua HTTP Upload" : "Webhook Endpoint",
              }),
              e.jsxs("div", {
                className: "flex items-center gap-2",
                children: [
                  e.jsx("p", {
                    className: "flex-1 break-all text-[10px] font-mono text-emerald-400",
                    children: endpoint,
                  }),
                  e.jsx("button", {
                    onClick: copyEndpoint,
                    className:
                      "shrink-0 rounded-md bg-emerald-500/10 px-2 py-0.5 text-[9px] font-semibold text-emerald-400 hover:bg-emerald-500/20 transition",
                    children: copyState ? "Copied" : "Copy",
                  }),
                ],
              }),
              e.jsx("p", {
                className: "text-[9px] text-slate-600",
                children:
                  "Use this endpoint for device push events. Dahua devices can post JSON access events directly.",
              }),
            ],
          }),
          isDahua &&
            e.jsxs("div", {
              className: "border-t border-white/[0.04] pt-2 space-y-2",
              children: [
                e.jsxs("div", {
                  className: "flex items-center justify-between",
                  children: [
                    e.jsx("p", {
                      className: "text-[10px] font-bold uppercase tracking-widest text-slate-500",
                      children: "Pull Today's Records",
                    }),
                    e.jsx("button", {
                      onClick: syncNow,
                      disabled: syncing,
                      className:
                        "rounded-lg bg-sky-500/10 px-3 py-1 text-[10px] font-semibold text-sky-400 hover:bg-sky-500/20 transition disabled:opacity-50",
                      children: syncing ? "Syncing..." : "Sync Now",
                    }),
                  ],
                }),
                e.jsx("button", {
                  onClick: () => setShowGuide((current) => !current),
                  className: "text-[10px] font-semibold uppercase tracking-wider text-emerald-400 hover:text-emerald-300",
                  children: showGuide ? "Hide Setup Guide" : "Show Setup Guide",
                }),
                showGuide &&
                  e.jsxs("ol", {
                    className: "space-y-1 text-[10px] text-slate-400",
                    children: [
                      e.jsxs("li", { children: ["1. Open the device UI at ", `http://${device.ip_address || "192.168.1.108"}`] }),
                      e.jsx("li", { children: "2. Go to Setup > Network > Integration Protocol > HTTP Subscription." }),
                      e.jsx("li", { children: "3. Paste the endpoint above as the server URL and save." }),
                      e.jsx("li", { children: "4. Use JSON + POST and enable AccessControl or all events." }),
                    ],
                  }),
                message &&
                  e.jsx("p", {
                    className: `rounded-lg px-3 py-1.5 text-[10px] ${
                      message.toLowerCase().includes("synced")
                        ? "bg-emerald-500/10 text-emerald-400"
                        : "bg-rose-500/10 text-rose-400"
                    }`,
                    children: message,
                  }),
              ],
            }),
        ],
      }),
    ],
  });
}

function ClockInDevicesPage() {
  const [devices, setDevices] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [showForm, setShowForm] = React.useState(false);
  const [showDiscovery, setShowDiscovery] = React.useState(false);
  const [form, setForm] = React.useState(defaultDeviceForm());
  const [saving, setSaving] = React.useState(false);
  const [deleteId, setDeleteId] = React.useState(null);
  const [deleting, setDeleting] = React.useState(false);
  const [scanPrefix, setScanPrefix] = React.useState(defaultScanPrefix());
  const [scanTimeout, setScanTimeout] = React.useState(0.5);
  const [scanResults, setScanResults] = React.useState([]);
  const [scanLogs, setScanLogs] = React.useState([]);
  const [discovering, setDiscovering] = React.useState(false);
  const [usbScanning, setUsbScanning] = React.useState(false);

  const appendLog = React.useCallback((message) => {
    setScanLogs((current) => [...current, `[${new Date().toLocaleTimeString()}] ${message}`]);
  }, []);

  const loadDevices = React.useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("/clockin/devices/");
      setDevices(normalizeRows(response.data));
    } catch {
      setError("Unable to load devices.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadDevices();
  }, [loadDevices]);

  const resetForm = () => {
    setForm(defaultDeviceForm());
  };

  const populateQuickDevice = (template) => {
    setForm(buildQuickDeviceForm(template));
    setShowDiscovery(false);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const populateDiscoveredDevice = (device) => {
    setForm(buildDiscoveredDeviceForm(device));
    setShowDiscovery(false);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const saveDevice = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.post("/clockin/devices/", form);
      resetForm();
      setShowForm(false);
      await loadDevices();
    } catch (err) {
      setError(readError(err, "Failed to add device."));
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteId) return;
    setDeleting(true);
    try {
      await api.delete(`/clockin/devices/${deleteId}/`);
      setDeleteId(null);
      await loadDevices();
    } catch {
      setError("Failed to delete device.");
    } finally {
      setDeleting(false);
    }
  };

  const scanUsbDevices = async () => {
    setUsbScanning(true);
    appendLog("Checking for USB-connected biometric devices...");
    if (!("hid" in navigator)) {
      appendLog("WebHID not supported in this browser. Use Chrome or Edge for USB detection.");
      setUsbScanning(false);
      return;
    }

    try {
      const selected = await navigator.hid.requestDevice({
        filters: [
          { vendorId: 8711 },
          { vendorId: 11143 },
          { vendorId: 6997 },
          { vendorId: 1466 },
          { vendorId: 5427 },
          { vendorId: 1155 },
          { vendorId: 1204 },
          { vendorId: 6777 },
          { usagePage: 13 },
        ],
      });

      if (!selected?.length) {
        appendLog("No USB biometric device selected.");
      } else {
        const usbDevices = selected.map((item) => {
          const isDahua = item.vendorId === 8711 || item.vendorId === 11143;
          const brand = isDahua ? item.productName || "Dahua ASI6214S" : item.productName || "USB Biometric Device";
          return {
            ip: "USB",
            port: 0,
            brand,
            technology: isDahua ? "Dahua USB" : "USB HID",
            device_id: `USB-HID:${item.vendorId.toString(16).padStart(4, "0")}:${item.productId
              .toString(16)
              .padStart(4, "0")}`,
            already_registered: devices.some(
              (registered) =>
                registered.device_id ===
                `USB-HID:${item.vendorId.toString(16).padStart(4, "0")}:${item.productId
                  .toString(16)
                  .padStart(4, "0")}`,
            ),
          };
        });
        setScanResults((current) => [...current, ...usbDevices]);
        appendLog(`Found ${usbDevices.length} USB biometric device(s).`);
      }
    } catch (err) {
      appendLog(`USB scan failed: ${err.message}`);
    } finally {
      setUsbScanning(false);
    }
  };

  const scanNetworkDevices = async () => {
    setDiscovering(true);
    appendLog(`Starting network scan on ${scanPrefix}.1 - ${scanPrefix}.254...`);
    try {
      const response = await api.post("/clockin/devices/discover/", {
        ip_prefix: scanPrefix,
        timeout: scanTimeout,
      });
      const found = response.data?.devices || [];
      setScanResults((current) => {
        const knownIds = new Set(current.map((item) => item.device_id));
        const additional = found.filter((item) => !knownIds.has(item.device_id));
        return [...current, ...additional];
      });
      appendLog(`Network scan complete: ${response.data?.scanned || "?"} probes, ${found.length} device(s) found.`);
    } catch (err) {
      appendLog(readError(err, "Network scan failed."));
    } finally {
      setDiscovering(false);
    }
  };

  const openDiscovery = () => {
    setShowForm(false);
    setShowDiscovery((current) => !current);
  };

  const startDiscovery = async () => {
    setScanResults([]);
    setScanLogs([]);
    await scanUsbDevices();
    await scanNetworkDevices();
  };

  return e.jsxs("div", {
    className: "space-y-6 font-sans text-slate-100",
    children: [
      e.jsx(PageHero, {
        badge: "CLOCK-IN",
        badgeColor: "emerald",
        title: "Devices",
        subtitle: "Manage biometric and RFID clock-in devices",
        icon: "⏰",
      }),
      e.jsxs("header", {
        className: "rounded-2xl p-5 space-y-4",
        style: panelStyle,
        children: [
          e.jsxs("div", {
            className: "flex flex-wrap items-start justify-between gap-3",
            children: [
              e.jsxs("div", {
                children: [
                  e.jsx("h1", { className: "text-xl font-display font-semibold", children: "Biometric Devices" }),
                  e.jsx("p", {
                    className: "mt-1 text-sm text-slate-400",
                    children: "Fingerprint scanners, RFID terminals and network endpoints.",
                  }),
                  error && e.jsx("p", { className: "mt-1 text-xs text-rose-300", children: error }),
                ],
              }),
              e.jsxs("div", {
                className: "flex flex-wrap gap-3",
                children: [
                  e.jsx("button", {
                    onClick: openDiscovery,
                    className:
                      "rounded-xl border border-white/[0.09] px-4 py-2 text-sm font-semibold text-slate-400 hover:text-slate-200 transition",
                    children: showDiscovery ? "Hide Discovery" : "Discover Devices",
                  }),
                  e.jsx("button", {
                    onClick: () => {
                      setShowForm((current) => !current);
                      setShowDiscovery(false);
                    },
                    className:
                      "rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-emerald-400 transition",
                    children: showForm ? "Cancel" : "Register Device",
                  }),
                ],
              }),
            ],
          }),
          e.jsxs("div", {
            className: "flex flex-wrap gap-2 border-t border-white/[0.05] pt-1",
            children: [
              e.jsx("p", {
                className: "mb-1 w-full text-[10px] font-bold uppercase tracking-widest text-slate-500",
                children: "Quick add known device:",
              }),
              QUICK_DEVICES.map((template) =>
                e.jsx(
                  "button",
                  {
                    onClick: () => populateQuickDevice(template),
                    className:
                      "rounded-lg border border-white/[0.07] px-3 py-1.5 text-xs font-semibold text-slate-400 hover:border-white/20 hover:text-slate-200 transition",
                    children: template.label,
                  },
                  template.label,
                ),
              ),
            ],
          }),
        ],
      }),
      showDiscovery &&
        e.jsxs("section", {
          className: "rounded-2xl p-6 space-y-5",
          style: panelStyle,
          children: [
            e.jsxs("div", {
              className: "flex flex-wrap items-start justify-between gap-4",
              children: [
                e.jsxs("div", {
                  className: "space-y-1.5",
                  children: [
                    e.jsx("h2", {
                      className: "text-lg font-display font-semibold text-emerald-400",
                      children: "Device Discovery",
                    }),
                    e.jsx("p", {
                      className: "text-sm text-slate-400",
                      children:
                        "Use USB detection or network discovery to prefill device details. IPv6 selection is still available in the registration form.",
                    }),
                  ],
                }),
                e.jsx("button", {
                  onClick: () => {
                    setShowDiscovery(false);
                    setScanResults([]);
                    setScanLogs([]);
                  },
                  className: "text-xs text-slate-500 hover:text-slate-300",
                  children: "Close",
                }),
              ],
            }),
            e.jsxs("div", {
              className: "flex flex-wrap items-end gap-4",
              children: [
                e.jsxs("div", {
                  className: "space-y-1",
                  children: [
                    e.jsx("label", {
                      className: "text-[10px] font-bold uppercase tracking-widest text-slate-500",
                      children: "Network prefix",
                    }),
                    e.jsx("input", {
                      className: "w-44 rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm font-mono",
                      placeholder: "192.168.1",
                      value: scanPrefix,
                      onChange: (event) => setScanPrefix(event.target.value),
                    }),
                  ],
                }),
                e.jsxs("div", {
                  className: "space-y-1",
                  children: [
                    e.jsx("label", {
                      className: "text-[10px] font-bold uppercase tracking-widest text-slate-500",
                      children: "Timeout (s)",
                    }),
                    e.jsxs("select", {
                      className: "rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm",
                      value: scanTimeout,
                      onChange: (event) => setScanTimeout(Number(event.target.value)),
                      children: [
                        e.jsx("option", { value: 0.3, children: "0.3" }),
                        e.jsx("option", { value: 0.5, children: "0.5" }),
                        e.jsx("option", { value: 1, children: "1.0" }),
                        e.jsx("option", { value: 2, children: "2.0" }),
                      ],
                    }),
                  ],
                }),
                e.jsx("button", {
                  onClick: startDiscovery,
                  className:
                    "rounded-xl bg-emerald-500 px-5 py-2 text-sm font-semibold text-slate-900 hover:bg-emerald-400 transition",
                  disabled: discovering || usbScanning,
                  children: discovering || usbScanning ? "Scanning..." : "Run Discovery",
                }),
                e.jsx("button", {
                  onClick: scanUsbDevices,
                  className:
                    "rounded-xl border border-white/[0.09] px-5 py-2 text-sm font-semibold text-slate-300 hover:text-white transition",
                  disabled: usbScanning,
                  children: usbScanning ? "Checking USB..." : "USB Only",
                }),
              ],
            }),
            scanLogs.length > 0 &&
              e.jsx("div", {
                className: "rounded-xl border border-white/[0.06] bg-slate-950 p-4 font-mono text-[11px] text-slate-400",
                children: scanLogs.map((entry, index) => e.jsx("p", { children: entry }, `${index}-${entry}`)),
              }),
            scanResults.length > 0 &&
              e.jsx("div", {
                className: "grid gap-3",
                children: scanResults.map((device, index) =>
                  e.jsxs(
                    "div",
                    {
                      className:
                        "flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-white/[0.02] p-4 md:flex-row md:items-center md:justify-between",
                      children: [
                        e.jsxs("div", {
                          children: [
                            e.jsx("p", {
                              className: "text-sm font-semibold text-slate-100",
                              children: `${device.brand || "Device"}${device.model ? ` ${device.model}` : ""}`,
                            }),
                            e.jsxs("p", {
                              className: "mt-1 text-xs text-slate-400",
                              children: [
                                device.ip || "USB",
                                device.port ? ` | port ${device.port}` : "",
                                device.serial ? ` | S/N ${device.serial}` : "",
                                device.mac ? ` | MAC ${device.mac}` : "",
                              ],
                            }),
                            e.jsx("p", {
                              className: "mt-1 text-[10px] uppercase tracking-widest text-slate-500",
                              children: device.discovery_method || device.technology || "Discovery",
                            }),
                          ],
                        }),
                        device.already_registered
                          ? e.jsx("span", {
                              className:
                                "rounded-full border border-white/[0.07] px-3 py-1 text-xs text-slate-500",
                              children: "Already registered",
                            })
                          : e.jsx("button", {
                              onClick: () => populateDiscoveredDevice(device),
                              className:
                                "rounded-xl bg-emerald-500/20 border border-emerald-500/30 px-4 py-1.5 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/30 transition",
                              children: "Register",
                            }),
                      ],
                    },
                    `${device.device_id || device.ip || "device"}-${index}`,
                  ),
                ),
              }),
          ],
        }),
      showForm &&
        e.jsx("form", {
          onSubmit: saveDevice,
          className: "rounded-2xl p-6 space-y-5",
          style: panelStyle,
          children: e.jsxs(React.Fragment, {
            children: [
              e.jsxs("div", {
                className: "flex flex-wrap items-center justify-between gap-3",
                children: [
                  e.jsx("h2", {
                    className: "text-lg font-display font-semibold text-emerald-400",
                    children: "Register Device",
                  }),
                  e.jsx("span", {
                    className:
                      "rounded-full border border-white/[0.07] px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-slate-500",
                    children: "IPv4 / IPv6 Ready",
                  }),
                ],
              }),
              e.jsxs("div", {
                children: [
                  e.jsx("p", {
                    className: "mb-3 text-[10px] font-bold uppercase tracking-widest text-slate-500",
                    children: "Device Identity",
                  }),
                  e.jsxs("div", {
                    className: "grid gap-4 md:grid-cols-2 lg:grid-cols-3",
                    children: [
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Serial / Device ID *" }),
                          e.jsx("input", {
                            required: true,
                            className: monoInputClass,
                            placeholder: "e.g. 4A2F... or 192.168.1.108:37777",
                            value: form.device_id,
                            onChange: (event) => setForm((current) => ({ ...current, device_id: event.target.value })),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Friendly Name *" }),
                          e.jsx("input", {
                            required: true,
                            className: inputClass,
                            placeholder: "Main Entrance Terminal",
                            value: form.name,
                            onChange: (event) => setForm((current) => ({ ...current, name: event.target.value })),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Location *" }),
                          e.jsx("input", {
                            required: true,
                            className: inputClass,
                            placeholder: "Front Gate",
                            value: form.location,
                            onChange: (event) => setForm((current) => ({ ...current, location: event.target.value })),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Brand" }),
                          e.jsxs("select", {
                            className: inputClass,
                            value: form.brand,
                            onChange: (event) => setForm((current) => ({ ...current, brand: event.target.value })),
                            children: [
                              e.jsx("option", { value: "Dahua", children: "Dahua" }),
                              e.jsx("option", { value: "ZKTeco", children: "ZKTeco" }),
                              e.jsx("option", { value: "Anviz", children: "Anviz" }),
                              e.jsx("option", { value: "FingerTec", children: "FingerTec" }),
                              e.jsx("option", { value: "Suprema", children: "Suprema" }),
                              e.jsx("option", { value: "Other", children: "Other" }),
                            ],
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Model" }),
                          e.jsx("input", {
                            className: monoInputClass,
                            placeholder: "ASI6214S",
                            value: form.model,
                            onChange: (event) => setForm((current) => ({ ...current, model: event.target.value })),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Function" }),
                          e.jsxs("select", {
                            className: inputClass,
                            value: form.device_type,
                            onChange: (event) => setForm((current) => ({ ...current, device_type: event.target.value })),
                            children: [
                              e.jsx("option", { value: "ENTRY", children: "Entry Only" }),
                              e.jsx("option", { value: "EXIT", children: "Exit Only" }),
                              e.jsx("option", { value: "BOTH", children: "Entry & Exit" }),
                            ],
                          }),
                        ],
                      }),
                    ],
                  }),
                ],
              }),
              e.jsxs("div", {
                children: [
                  e.jsx("p", {
                    className: "mb-3 text-[10px] font-bold uppercase tracking-widest text-slate-500",
                    children: "Network Connection",
                  }),
                  e.jsxs("div", {
                    className: "grid gap-4 md:grid-cols-2 lg:grid-cols-4",
                    children: [
                      e.jsxs("div", {
                        className: "space-y-1 md:col-span-2",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "IP Address" }),
                          e.jsx("input", {
                            className: monoInputClass,
                            placeholder: form.ip_version === "ipv6" ? "2001:db8::108" : "192.168.1.108",
                            value: form.ip_address,
                            onChange: (event) => {
                              const nextValue = event.target.value;
                              setForm((current) => ({
                                ...current,
                                ip_address: nextValue,
                                ip_version: nextValue.includes(":") ? "ipv6" : current.ip_version,
                              }));
                            },
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "IP Version" }),
                          e.jsxs("select", {
                            className: inputClass,
                            value: form.ip_version,
                            onChange: (event) => setForm((current) => ({ ...current, ip_version: event.target.value })),
                            children: [
                              e.jsx("option", { value: "ipv4", children: "IPv4" }),
                              e.jsx("option", { value: "ipv6", children: "IPv6" }),
                            ],
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "SDK Port" }),
                          e.jsx("input", {
                            type: "number",
                            className: monoInputClass,
                            placeholder: "37777",
                            value: form.port,
                            onChange: (event) =>
                              setForm((current) => ({ ...current, port: Number(event.target.value) || 0 })),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "HTTP Port" }),
                          e.jsx("input", {
                            type: "number",
                            className: monoInputClass,
                            placeholder: "80",
                            value: form.http_port,
                            onChange: (event) =>
                              setForm((current) => ({ ...current, http_port: Number(event.target.value) || 0 })),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Username" }),
                          e.jsx("input", {
                            className: monoInputClass,
                            placeholder: "admin",
                            value: form.username,
                            onChange: (event) => setForm((current) => ({ ...current, username: event.target.value })),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Password" }),
                          e.jsx("input", {
                            type: "password",
                            className: monoInputClass,
                            placeholder: "admin123",
                            value: form.password,
                            onChange: (event) => setForm((current) => ({ ...current, password: event.target.value })),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "RTSP Port" }),
                          e.jsx("input", {
                            type: "number",
                            className: monoInputClass,
                            placeholder: "37778",
                            value: form.rtsp_port,
                            onChange: (event) =>
                              setForm((current) => ({ ...current, rtsp_port: Number(event.target.value) || 0 })),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "space-y-1",
                        children: [
                          e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Channel" }),
                          e.jsx("input", {
                            type: "number",
                            className: monoInputClass,
                            placeholder: "1",
                            value: form.channel,
                            onChange: (event) =>
                              setForm((current) => ({ ...current, channel: Number(event.target.value) || 1 })),
                          }),
                        ],
                      }),
                    ],
                  }),
                ],
              }),
              e.jsxs("div", {
                className: "space-y-1",
                children: [
                  e.jsx("label", { className: "text-xs font-bold uppercase tracking-wider text-slate-400", children: "Notes" }),
                  e.jsx("textarea", {
                    className:
                      "w-full rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm outline-none focus:border-emerald-500 transition resize-none",
                    rows: 3,
                    placeholder: "Hardware specs, firmware version, maintenance notes or discovery info...",
                    value: form.notes,
                    onChange: (event) => setForm((current) => ({ ...current, notes: event.target.value })),
                  }),
                ],
              }),
              e.jsxs("div", {
                className: "flex justify-end gap-3",
                children: [
                  e.jsx("button", {
                    type: "button",
                    onClick: () => setShowForm(false),
                    className:
                      "rounded-xl border border-white/[0.09] px-5 py-2 text-sm text-slate-400 hover:text-slate-200 transition",
                    children: "Cancel",
                  }),
                  e.jsx("button", {
                    type: "submit",
                    disabled: saving,
                    className:
                      "rounded-xl bg-emerald-500 px-6 py-2.5 text-sm font-semibold text-slate-900 hover:bg-emerald-400 disabled:opacity-50 transition",
                    children: saving ? "Registering..." : "Confirm Registration",
                  }),
                ],
              }),
            ],
          }),
        }),
      e.jsx("div", {
        className: "grid gap-6",
        children: loading
          ? e.jsx("div", { className: "p-12 text-center text-slate-400", children: "Loading devices..." })
          : devices.length === 0
            ? e.jsxs("div", {
                className:
                  "rounded-2xl border border-white/[0.07] bg-white/[0.02] p-10 flex flex-col items-center gap-5 text-center",
                children: [
                  e.jsx("div", { className: "text-4xl", children: "PC" }),
                  e.jsxs("div", {
                    children: [
                      e.jsx("p", { className: "font-semibold text-slate-300", children: "No devices registered yet" }),
                      e.jsx("p", {
                        className: "mt-1 max-w-md text-sm text-slate-500",
                        children:
                          "Register a clock-in device manually or use device discovery to prefill the form, including IPv6 connections.",
                      }),
                    ],
                  }),
                  e.jsx("button", {
                    onClick: () => populateQuickDevice(QUICK_DEVICES[0]),
                    className:
                      "rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-slate-900 hover:bg-emerald-400 transition",
                    children: "Quick Add Dahua ASI6214S",
                  }),
                ],
              })
            : devices.map((device) =>
                e.jsxs(
                  "article",
                  {
                    className: "rounded-2xl p-6 flex flex-col gap-6 md:flex-row",
                    style: panelStyle,
                    children: [
                      e.jsxs("div", {
                        className: "flex-1 space-y-4",
                        children: [
                          e.jsxs("div", {
                            className: "flex flex-wrap items-center gap-3",
                            children: [
                              e.jsx("h3", { className: "text-xl font-display font-semibold", children: device.name }),
                              e.jsx("span", {
                                className: `rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                  device.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-500/10 text-slate-400"
                                }`,
                                children: device.is_active ? "ACTIVE" : "INACTIVE",
                              }),
                              e.jsx("span", {
                                className: "rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-400",
                                children: device.device_type,
                              }),
                              device.brand &&
                                e.jsx("span", {
                                  className:
                                    "rounded-full border border-sky-500/20 bg-sky-500/10 px-2 py-0.5 text-[10px] font-bold uppercase text-sky-400",
                                  children: `${device.brand}${device.model ? ` ${device.model}` : ""}`,
                                }),
                            ],
                          }),
                          e.jsxs("div", {
                            className: "grid grid-cols-2 gap-4 text-sm md:grid-cols-3",
                            children: [
                              e.jsxs("div", {
                                children: [
                                  e.jsx("p", { className: "text-[10px] font-bold uppercase tracking-widest text-slate-500", children: "Device ID" }),
                                  e.jsx("p", { className: "mt-1 break-all font-mono text-xs text-emerald-400", children: device.device_id }),
                                ],
                              }),
                              e.jsxs("div", {
                                children: [
                                  e.jsx("p", { className: "text-[10px] font-bold uppercase tracking-widest text-slate-500", children: "Location" }),
                                  e.jsx("p", { className: "mt-1 text-slate-300", children: device.location }),
                                ],
                              }),
                              e.jsxs("div", {
                                children: [
                                  e.jsx("p", { className: "text-[10px] font-bold uppercase tracking-widest text-slate-500", children: "Last Seen" }),
                                  e.jsx("p", { className: "mt-1 italic text-slate-300", children: formatDateTime(device.last_seen) }),
                                ],
                              }),
                              device.ip_address &&
                                e.jsxs("div", {
                                  children: [
                                    e.jsx("p", { className: "text-[10px] font-bold uppercase tracking-widest text-slate-500", children: "IP Address" }),
                                    e.jsx("p", {
                                      className: "mt-1 font-mono text-sky-400",
                                      children: `${device.ip_address} (${device.ip_version || inferIpVersion(device.ip_address)})`,
                                    }),
                                  ],
                                }),
                              device.serial_number &&
                                e.jsxs("div", {
                                  children: [
                                    e.jsx("p", { className: "text-[10px] font-bold uppercase tracking-widest text-slate-500", children: "Serial" }),
                                    e.jsx("p", { className: "mt-1 font-mono text-xs text-slate-400", children: device.serial_number }),
                                  ],
                                }),
                              device.mac_address &&
                                e.jsxs("div", {
                                  children: [
                                    e.jsx("p", { className: "text-[10px] font-bold uppercase tracking-widest text-slate-500", children: "MAC" }),
                                    e.jsx("p", { className: "mt-1 font-mono text-xs text-slate-400", children: device.mac_address }),
                                  ],
                                }),
                            ],
                          }),
                          device.notes &&
                            e.jsx("p", {
                              className:
                                "whitespace-pre-line border-l-2 border-white/[0.09] pl-3 py-1 text-xs italic text-slate-500",
                              children: device.notes,
                            }),
                        ],
                      }),
                      e.jsxs("div", {
                        className: "w-full space-y-4 border-l border-white/[0.07] pl-0 md:w-80 md:pl-6",
                        children: [
                          device.ip_address &&
                            e.jsxs("div", {
                              children: [
                                e.jsx("h4", {
                                  className: "mb-3 text-xs font-bold uppercase tracking-widest text-slate-400",
                                  children: "Connection",
                                }),
                                e.jsxs("div", {
                                  className:
                                    "space-y-2 rounded-xl border border-white/[0.05] bg-slate-950 p-4 text-[11px] font-mono",
                                  children: [
                                    e.jsxs("div", {
                                      className: "flex justify-between",
                                      children: [
                                        e.jsx("span", { className: "text-slate-500", children: "IP" }),
                                        e.jsx("span", { className: "text-sky-400", children: device.ip_address }),
                                      ],
                                    }),
                                    e.jsxs("div", {
                                      className: "flex justify-between",
                                      children: [
                                        e.jsx("span", { className: "text-slate-500", children: "Version" }),
                                        e.jsx("span", {
                                          className: "text-slate-300 uppercase",
                                          children: device.ip_version || inferIpVersion(device.ip_address),
                                        }),
                                      ],
                                    }),
                                    e.jsxs("div", {
                                      className: "flex justify-between",
                                      children: [
                                        e.jsx("span", { className: "text-slate-500", children: "SDK Port" }),
                                        e.jsx("span", { className: "text-slate-300", children: device.port }),
                                      ],
                                    }),
                                    e.jsxs("div", {
                                      className: "flex justify-between",
                                      children: [
                                        e.jsx("span", { className: "text-slate-500", children: "HTTP Port" }),
                                        e.jsx("span", { className: "text-slate-300", children: device.http_port }),
                                      ],
                                    }),
                                    e.jsxs("div", {
                                      className: "flex justify-between",
                                      children: [
                                        e.jsx("span", { className: "text-slate-500", children: "Username" }),
                                        e.jsx("span", { className: "text-emerald-400", children: device.username }),
                                      ],
                                    }),
                                  ],
                                }),
                              ],
                            }),
                          e.jsx(DeviceActionsCard, { device }),
                          e.jsx("div", {
                            className: "flex gap-3 pt-2",
                            children: e.jsx("button", {
                              onClick: () => setDeleteId(device.id),
                              className: "text-xs font-semibold uppercase tracking-wider text-rose-400 hover:text-rose-300",
                              children: "Delete",
                            }),
                          }),
                        ],
                      }),
                    ],
                  },
                  device.id,
                ),
              ),
      }),
      e.jsx(ConfirmDialog, {
        open: !!deleteId,
        title: "Delete Device Registration",
        description:
          "Are you sure you want to remove this device? This will invalidate its API key and stop new scans until it is registered again.",
        confirmLabel: "Delete",
        isProcessing: deleting,
        onConfirm: confirmDelete,
        onCancel: () => setDeleteId(null),
      }),
    ],
  });
}

export { ClockInDevicesPage as default };
