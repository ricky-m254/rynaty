import { r as React, j as e, b as api } from "./index-D7ltaYVC.js";
import { P as PageHero } from "./PageHero-Ct90nOAG.js";
import { U as Upload } from "./upload-B5_nFvgY.js";
import { D as Download } from "./download-nEryqUKe.js";
import { F as FileText } from "./file-text-BMGjGS-3.js";
import { R as RefreshCw } from "./refresh-cw-DOVkzt4u.js";
import { U as Users } from "./users-9FLXP15V.js";
import { U as UserCheck } from "./user-check-Dt87sVKh.js";
import { D as DollarSign } from "./dollar-sign-BsYV7G3i.js";
import { C as ChevronRight } from "./chevron-right-CqgoY9nM.js";
import { E as Eye } from "./eye-CvqmTE-M.js";
import { S as Send } from "./send-DtouTzJF.js";
import { C as CircleCheck } from "./circle-check-big-gKc9ia_Q.js";
import "./createLucideIcon-BLtbVmUp.js";

const panelStyle = {
  background: "rgba(255,255,255,0.025)",
  border: "1px solid rgba(255,255,255,0.07)",
};

const importModules = [
  {
    key: "students",
    label: "Students",
    description: "Directory, admissions, and class placement data",
    icon: Users,
    color: "text-sky-400",
    endpoint: "/settings/import/students/",
  },
  {
    key: "staff",
    label: "Staff",
    description: "Employees, departments, and designation data",
    icon: UserCheck,
    color: "text-violet-400",
    endpoint: "/settings/import/staff/",
  },
  {
    key: "fees",
    label: "Fee Structures",
    description: "Recurring billing rules, vote heads, and migrated fee items",
    icon: DollarSign,
    color: "text-emerald-400",
    endpoint: "/settings/import/fees/",
  },
  {
    key: "payments",
    label: "Payments",
    description: "Historic receipts, opening balances, and migrated collections",
    icon: DollarSign,
    color: "text-amber-400",
    endpoint: "/settings/import/payments/",
  },
];

const exportOptions = [
  { module: "students", label: "Students Directory (CSV)", fmt: "CSV", url: "/students/export/csv/" },
  { module: "students", label: "Students Directory (PDF)", fmt: "PDF", url: "/students/export/pdf/" },
  { module: "students", label: "Student Documents (CSV)", fmt: "CSV", url: "/students/documents/export/csv/" },
  { module: "staff", label: "Staff Directory (CSV)", fmt: "CSV", url: "/staff/export/csv/" },
  { module: "fees", label: "Finance Summary (CSV)", fmt: "CSV", url: "/finance/reports/summary/export/csv/" },
  { module: "fees", label: "Receivables Aging (CSV)", fmt: "CSV", url: "/finance/reports/receivables-aging/export/csv/" },
  { module: "payments", label: "Overdue Accounts (CSV)", fmt: "CSV", url: "/finance/reports/overdue-accounts/export/csv/" },
];

const migrationModules = [
  "STUDENTS",
  "ADMISSIONS",
  "ACADEMICS",
  "STAFF",
  "HR",
  "FINANCE",
  "LIBRARY",
  "TRANSPORT",
  "HOSTEL",
  "ASSETS",
  "CLOCKIN",
  "COMMUNICATION",
  "REPORTING",
  "SETTINGS",
  "OTHER",
];

function downloadBlob(blob, filename) {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(objectUrl);
}

function ImportCard({ module, selected, onSelect }) {
  const Icon = module.icon;
  return e.jsxs("button", {
    onClick: () => onSelect(module.key),
    className: `rounded-xl border p-4 text-left transition ${
      selected ? "border-emerald-500/40 bg-emerald-500/5" : "border-white/7 bg-white/2 hover:border-white/15"
    }`,
    style: selected ? void 0 : panelStyle,
    children: [
      e.jsxs("div", {
        className: "flex items-start gap-3",
        children: [
          e.jsx(Icon, { className: `mt-0.5 h-6 w-6 ${module.color}` }),
          e.jsxs("div", {
            className: "flex-1",
            children: [
              e.jsx("div", { className: "text-sm font-medium text-white", children: module.label }),
              e.jsx("div", { className: "mt-1 text-xs text-white/40", children: module.description }),
            ],
          }),
          e.jsx(ChevronRight, { className: "mt-1 h-4 w-4 text-white/20" }),
        ],
      }),
    ],
  });
}

function SettingsImportExportPage() {
  const [tab, setTab] = React.useState("import");
  const [step, setStep] = React.useState("select");
  const [selectedModule, setSelectedModule] = React.useState(null);
  const [selectedFile, setSelectedFile] = React.useState(null);
  const [importResult, setImportResult] = React.useState(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [busyKey, setBusyKey] = React.useState(null);
  const [exportFilter, setExportFilter] = React.useState("all");
  const [migrationForm, setMigrationForm] = React.useState({
    module: "STUDENTS",
    sourceSystem: "",
    batch: "",
    files: [],
  });
  const [migrationResult, setMigrationResult] = React.useState(null);
  const importInputRef = React.useRef(null);
  const migrationInputRef = React.useRef(null);

  const chosenModule = importModules.find((item) => item.key === selectedModule) || null;

  const resetImport = () => {
    setStep("select");
    setSelectedModule(null);
    setSelectedFile(null);
    setImportResult(null);
    if (importInputRef.current) importInputRef.current.value = "";
  };

  const downloadTemplate = async (moduleKey) => {
    setBusyKey(`template-${moduleKey}`);
    try {
      const response = await api.get(`/settings/import/${moduleKey}/template/`, { responseType: "blob" });
      downloadBlob(response.data, `${moduleKey}_import_template.csv`);
    } finally {
      setBusyKey(null);
    }
  };

  const submitImport = async (validateOnly) => {
    if (!chosenModule || !selectedFile) return;
    setIsSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("validate_only", validateOnly ? "true" : "false");
      const response = await api.post(chosenModule.endpoint, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setImportResult(response.data);
      setStep(response.data.committed ? "done" : "preview");
    } catch (err) {
      const message = err?.response?.data?.error || "Import failed";
      setImportResult({
        valid_rows: 0,
        error_rows: 1,
        errors: [{ row: 0, errors: [message] }],
        preview: [],
        committed: false,
      });
      setStep("preview");
    } finally {
      setIsSubmitting(false);
    }
  };

  const downloadExport = async (url, label) => {
    setBusyKey(url);
    try {
      const response = await api.get(url, { responseType: "blob" });
      const extension = url.includes("/pdf/") ? "pdf" : "csv";
      downloadBlob(response.data, `${label.replace(/[^a-z0-9]/gi, "_").toLowerCase()}.${extension}`);
    } finally {
      setBusyKey(null);
    }
  };

  const submitMigrationFiles = async () => {
    if (!migrationForm.files.length) return;
    setBusyKey("migration-upload");
    try {
      const formData = new FormData();
      formData.append("module", migrationForm.module);
      formData.append("source_system", migrationForm.sourceSystem);
      formData.append("migration_batch", migrationForm.batch);
      migrationForm.files.forEach((file) => formData.append("files", file));
      const response = await api.post("/settings/media/upload/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setMigrationResult(response.data);
      setMigrationForm((current) => ({ ...current, files: [] }));
      if (migrationInputRef.current) migrationInputRef.current.value = "";
    } catch (err) {
      setMigrationResult({
        error: err?.response?.data?.error || "Migration upload failed.",
      });
    } finally {
      setBusyKey(null);
    }
  };

  const filteredExports =
    exportFilter === "all" ? exportOptions : exportOptions.filter((item) => item.module === exportFilter);

  return e.jsxs("div", {
    className: "space-y-6",
    children: [
      e.jsx(PageHero, {
        title: "Import & Export",
        subtitle: "Bulk-import migrated data, collect legacy files, and export operational datasets.",
        icon: e.jsx(Upload, { className: "h-6 w-6 text-sky-400" }),
      }),
      e.jsx("div", {
        className: "w-fit rounded-xl p-1",
        style: panelStyle,
        children: ["import", "export"].map((value) =>
          e.jsx(
            "button",
            {
              onClick: () => {
                setTab(value);
                resetImport();
              },
              className: `rounded-lg px-5 py-2 text-sm font-medium capitalize transition ${
                tab === value ? "bg-emerald-500 text-black" : "text-white/50 hover:text-white"
              }`,
              children: value === "import"
                ? e.jsxs("span", { className: "flex items-center gap-2", children: [e.jsx(Upload, { className: "h-3.5 w-3.5" }), "Import"] })
                : e.jsxs("span", { className: "flex items-center gap-2", children: [e.jsx(Download, { className: "h-3.5 w-3.5" }), "Export"] }),
            },
            value,
          ),
        ),
      }),
      tab === "import"
        ? e.jsxs("div", {
            className: "grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]",
            children: [
              e.jsx("div", {
                className: "rounded-2xl p-6",
                style: panelStyle,
                children:
                  step === "select"
                    ? e.jsxs("div", {
                        className: "space-y-4",
                        children: [
                          e.jsx("div", {
                            className: "text-sm text-white/50",
                            children: "Select the dataset you want to import from the previous tenant or external system.",
                          }),
                          e.jsx("div", {
                            className: "grid gap-3 md:grid-cols-2",
                            children: importModules.map((module) =>
                              e.jsx(ImportCard, {
                                module,
                                selected: selectedModule === module.key,
                                onSelect: (moduleKey) => {
                                  setSelectedModule(moduleKey);
                                  setStep("upload");
                                },
                              }, module.key),
                            ),
                          }),
                        ],
                      })
                    : chosenModule &&
                      e.jsxs("div", {
                        className: "space-y-5",
                        children: [
                          e.jsxs("div", {
                            className: "flex items-center gap-2 text-sm text-white/40",
                            children: [
                              e.jsx("button", {
                                onClick: () => setStep("select"),
                                className: "transition hover:text-white",
                                children: "Select dataset",
                              }),
                              e.jsx(ChevronRight, { className: "h-3 w-3" }),
                              e.jsx("span", { className: "text-white", children: chosenModule.label }),
                            ],
                          }),
                          e.jsxs("div", {
                            className: "flex items-center gap-4 rounded-xl p-4",
                            style: panelStyle,
                            children: [
                              e.jsx(FileText, { className: "h-8 w-8 flex-shrink-0 text-sky-400" }),
                              e.jsxs("div", {
                                className: "flex-1",
                                children: [
                                  e.jsx("div", { className: "text-sm font-medium text-white", children: "Step 1 - Download template" }),
                                  e.jsxs("div", {
                                    className: "mt-0.5 text-xs text-white/40",
                                    children: ["Get the correct CSV headers for ", chosenModule.label.toLowerCase(), "."],
                                  }),
                                ],
                              }),
                              e.jsxs("button", {
                                onClick: () => downloadTemplate(chosenModule.key),
                                disabled: busyKey === `template-${chosenModule.key}`,
                                className: "flex items-center gap-2 rounded-lg border border-sky-500/20 bg-sky-500/10 px-3 py-1.5 text-xs text-sky-400 transition hover:bg-sky-500/20",
                                children: [
                                  busyKey === `template-${chosenModule.key}`
                                    ? e.jsx(RefreshCw, { className: "h-3 w-3 animate-spin" })
                                    : e.jsx(Download, { className: "h-3 w-3" }),
                                  "Template",
                                ],
                              }),
                            ],
                          }),
                          e.jsxs("div", {
                            className: "space-y-3 rounded-xl p-4",
                            style: panelStyle,
                            children: [
                              e.jsx("div", { className: "text-sm font-medium text-white", children: "Step 2 - Upload import CSV" }),
                              e.jsxs("div", {
                                onClick: () => importInputRef.current?.click(),
                                className: "cursor-pointer rounded-xl border-2 border-dashed border-white/10 p-8 text-center transition hover:border-emerald-500/30 hover:bg-emerald-500/3",
                                children: [
                                  e.jsx(Upload, { className: "mx-auto mb-2 h-8 w-8 text-white/20" }),
                                  selectedFile
                                    ? e.jsx("div", { className: "text-sm font-medium text-emerald-400", children: selectedFile.name })
                                    : e.jsx("div", { className: "text-sm text-white/30", children: "Click to choose a CSV file" }),
                                  e.jsx("div", { className: "mt-1 text-xs text-white/20", children: "UTF-8 encoded, comma-separated values" }),
                                ],
                              }),
                              e.jsx("input", {
                                ref: importInputRef,
                                type: "file",
                                accept: ".csv,text/csv",
                                className: "hidden",
                                onChange: (event) => setSelectedFile(event.target.files?.[0] || null),
                              }),
                            ],
                          }),
                          e.jsxs("div", {
                            className: "flex gap-3",
                            children: [
                              e.jsxs("button", {
                                onClick: () => submitImport(true),
                                disabled: !selectedFile || isSubmitting,
                                className: "flex flex-1 items-center justify-center gap-2 rounded-lg border border-white/10 px-4 py-2.5 text-sm text-white/70 transition hover:bg-white/5 disabled:opacity-40",
                                children: [
                                  isSubmitting ? e.jsx(RefreshCw, { className: "h-4 w-4 animate-spin" }) : e.jsx(Eye, { className: "h-4 w-4" }),
                                  "Validate Only",
                                ],
                              }),
                              e.jsxs("button", {
                                onClick: () => submitImport(false),
                                disabled: !selectedFile || isSubmitting,
                                className: "flex flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-black transition hover:bg-emerald-400 disabled:opacity-40",
                                children: [
                                  isSubmitting ? e.jsx(RefreshCw, { className: "h-4 w-4 animate-spin" }) : e.jsx(Send, { className: "h-4 w-4" }),
                                  "Validate & Import",
                                ],
                              }),
                            ],
                          }),
                          importResult &&
                            e.jsxs("div", {
                              className: "space-y-4",
                              children: [
                                e.jsx("div", {
                                  className: "grid grid-cols-3 gap-3",
                                  children: [
                                    { label: "Valid rows", value: importResult.valid_rows, color: "text-emerald-400" },
                                    {
                                      label: "Errors",
                                      value: importResult.error_rows,
                                      color: importResult.error_rows > 0 ? "text-red-400" : "text-white/40",
                                    },
                                    {
                                      label: importResult.committed ? "Imported" : "Preview only",
                                      value: importResult.committed ? importResult.created ?? importResult.valid_rows : "-",
                                      color: importResult.committed ? "text-sky-400" : "text-white/40",
                                    },
                                  ].map((metric) =>
                                    e.jsxs(
                                      "div",
                                      {
                                        className: "rounded-xl p-3 text-center",
                                        style: panelStyle,
                                        children: [
                                          e.jsx("div", { className: `text-2xl font-bold ${metric.color}`, children: metric.value }),
                                          e.jsx("div", { className: "mt-1 text-xs text-white/40", children: metric.label }),
                                        ],
                                      },
                                      metric.label,
                                    ),
                                  ),
                                }),
                                importResult.error_rows > 0 &&
                                  e.jsxs("div", {
                                    className: "max-h-48 space-y-2 overflow-y-auto rounded-xl p-4",
                                    style: { ...panelStyle, border: "1px solid rgba(239,68,68,0.2)" },
                                    children: [
                                      e.jsx("div", {
                                        className: "text-xs font-semibold uppercase tracking-wide text-red-400",
                                        children: "Validation Errors",
                                      }),
                                      importResult.errors.map((entry, index) =>
                                        e.jsxs("div", {
                                          className: "text-xs text-red-300/70",
                                          children: ["Row ", entry.row, ": ", entry.errors.join(", ")],
                                        }, index),
                                      ),
                                    ],
                                  }),
                                importResult.preview?.length > 0 &&
                                  !importResult.committed &&
                                  e.jsxs("div", {
                                    className: "overflow-hidden rounded-xl",
                                    style: panelStyle,
                                    children: [
                                      e.jsxs("div", {
                                        className: "border-b border-white/7 p-3 text-xs font-semibold uppercase tracking-wide text-white/50",
                                        children: ["Preview (first ", importResult.preview.length, ")"],
                                      }),
                                      e.jsx("div", {
                                        className: "overflow-x-auto",
                                        children: e.jsx("table", {
                                          className: "w-full text-xs",
                                          children: e.jsx("tbody", {
                                            children: importResult.preview.map((row, index) =>
                                              e.jsxs(
                                                "tr",
                                                {
                                                  className: "border-b border-white/5 last:border-0",
                                                  children: [
                                                    e.jsxs("td", { className: "px-3 py-2 text-white/30", children: ["Row ", row.row] }),
                                                    Object.entries(row)
                                                      .filter(([key]) => key !== "row")
                                                      .map(([key, value]) =>
                                                        e.jsx("td", { className: "px-3 py-2 text-white/70", children: String(value) }, key),
                                                      ),
                                                  ],
                                                },
                                                index,
                                              ),
                                            ),
                                          }),
                                        }),
                                      }),
                                    ],
                                  }),
                                importResult.committed &&
                                  e.jsxs("div", {
                                    className: "flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-emerald-400",
                                    children: [
                                      e.jsx(CircleCheck, { className: "h-5 w-5" }),
                                      "Import complete - ",
                                      importResult.created ?? importResult.valid_rows,
                                      " records created.",
                                    ],
                                  }),
                                e.jsx("button", {
                                  onClick: resetImport,
                                  className: "w-full py-2 text-sm text-white/40 transition hover:text-white",
                                  children: "Import another dataset",
                                }),
                              ],
                            }),
                        ],
                      }),
              }),
              e.jsxs("div", {
                className: "space-y-4 rounded-2xl p-6",
                style: panelStyle,
                children: [
                  e.jsx("div", {
                    className: "text-sm font-semibold text-white",
                    children: "Tenant Migration File Intake",
                  }),
                  e.jsx("p", {
                    className: "text-xs text-white/45",
                    children:
                      "Store bulk migration packs for every module, including spreadsheets, JSON/XML exports, ZIP archives, PDFs, images, and scanned documents from the previous system.",
                  }),
                  e.jsxs("div", {
                    className: "grid gap-3",
                    children: [
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", { className: "mb-1 block text-xs font-semibold uppercase tracking-wide text-white/45", children: "Module" }),
                          e.jsx("select", {
                            value: migrationForm.module,
                            onChange: (event) => setMigrationForm((current) => ({ ...current, module: event.target.value })),
                            className: "w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500/40",
                            children: migrationModules.map((module) => e.jsx("option", { value: module, children: module }, module)),
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", { className: "mb-1 block text-xs font-semibold uppercase tracking-wide text-white/45", children: "Source System" }),
                          e.jsx("input", {
                            value: migrationForm.sourceSystem,
                            onChange: (event) => setMigrationForm((current) => ({ ...current, sourceSystem: event.target.value })),
                            placeholder: "e.g. Legacy ERP / Excel / SchoolMIS",
                            className: "w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500/40",
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", { className: "mb-1 block text-xs font-semibold uppercase tracking-wide text-white/45", children: "Batch ID" }),
                          e.jsx("input", {
                            value: migrationForm.batch,
                            onChange: (event) => setMigrationForm((current) => ({ ...current, batch: event.target.value })),
                            placeholder: "e.g. 2026-migration-wave-1",
                            className: "w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500/40",
                          }),
                        ],
                      }),
                      e.jsxs("div", {
                        children: [
                          e.jsx("label", { className: "mb-1 block text-xs font-semibold uppercase tracking-wide text-white/45", children: "Files" }),
                          e.jsxs("div", {
                            onClick: () => migrationInputRef.current?.click(),
                            className: "cursor-pointer rounded-xl border-2 border-dashed border-white/10 p-5 text-center transition hover:border-emerald-500/30 hover:bg-emerald-500/3",
                            children: [
                              e.jsx(Upload, { className: "mx-auto mb-2 h-6 w-6 text-white/20" }),
                              e.jsx("div", {
                                className: "text-sm text-white/70",
                                children: migrationForm.files.length
                                  ? `${migrationForm.files.length} file(s) selected`
                                  : "Choose multiple migration files",
                              }),
                              e.jsx("div", {
                                className: "mt-1 text-xs text-white/25",
                                children: "CSV, XLSX, JSON, XML, ZIP, PDF, DOCX, images, and scanned records",
                              }),
                            ],
                          }),
                          e.jsx("input", {
                            ref: migrationInputRef,
                            type: "file",
                            multiple: true,
                            className: "hidden",
                            onChange: (event) =>
                              setMigrationForm((current) => ({
                                ...current,
                                files: Array.from(event.target.files || []),
                              })),
                          }),
                        ],
                      }),
                    ],
                  }),
                  e.jsxs("button", {
                    onClick: submitMigrationFiles,
                    disabled: !migrationForm.files.length || busyKey === "migration-upload",
                    className: "flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-black transition hover:bg-emerald-400 disabled:opacity-40",
                    children: [
                      busyKey === "migration-upload"
                        ? e.jsx(RefreshCw, { className: "h-4 w-4 animate-spin" })
                        : e.jsx(Upload, { className: "h-4 w-4" }),
                      "Upload Migration Files",
                    ],
                  }),
                  migrationResult &&
                    (migrationResult.error
                      ? e.jsx("div", {
                          className: "rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300",
                          children: migrationResult.error,
                        })
                      : e.jsxs("div", {
                          className: "space-y-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3",
                          children: [
                            e.jsxs("div", {
                              className: "text-sm text-emerald-300",
                              children: ["Stored ", migrationResult.count, " migration file(s)."],
                            }),
                            e.jsx("div", {
                              className: "space-y-2",
                              children: (migrationResult.results || []).map((row) =>
                                e.jsxs(
                                  "div",
                                  {
                                    className: "flex items-center justify-between gap-3 rounded-lg border border-white/7 bg-white/2 px-3 py-2 text-xs text-white/70",
                                    children: [
                                      e.jsxs("div", {
                                        className: "min-w-0",
                                        children: [
                                          e.jsx("div", { className: "truncate text-white", children: row.original_name }),
                                          e.jsxs("div", {
                                            className: "mt-0.5 text-white/35",
                                            children: [row.module, " - ", row.file_type],
                                          }),
                                        ],
                                      }),
                                      e.jsx("a", {
                                        href: row.url,
                                        target: "_blank",
                                        rel: "noreferrer",
                                        className: "text-emerald-300 transition hover:text-emerald-200",
                                        children: "Open",
                                      }),
                                    ],
                                  },
                                  row.id,
                                ),
                              ),
                            }),
                          ],
                        })),
                ],
              }),
            ],
          })
        : e.jsxs("div", {
            className: "space-y-4",
            children: [
              e.jsx("div", {
                className: "flex flex-wrap gap-2",
                children: ["all", "students", "staff", "fees", "payments"].map((value) =>
                  e.jsx(
                    "button",
                    {
                      onClick: () => setExportFilter(value),
                      className: `rounded-lg border px-3 py-1.5 text-xs capitalize transition ${
                        exportFilter === value
                          ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-400"
                          : "border-white/10 text-white/40 hover:text-white"
                      }`,
                      children: value === "all" ? "All" : value,
                    },
                    value,
                  ),
                ),
              }),
              e.jsx("div", {
                className: "grid gap-3 md:grid-cols-2",
                children: filteredExports.map((item) =>
                  e.jsxs(
                    "div",
                    {
                      className: "flex items-center gap-4 rounded-xl p-4",
                      style: panelStyle,
                      children: [
                        e.jsx("div", {
                          className: "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-white/5",
                          children: e.jsx(FileText, { className: "h-4 w-4 text-white/40" }),
                        }),
                        e.jsxs("div", {
                          className: "min-w-0 flex-1",
                          children: [
                            e.jsx("div", { className: "truncate text-sm text-white/80", children: item.label }),
                            e.jsxs("div", { className: "mt-0.5 text-xs text-white/30", children: [item.fmt, " - ", item.module] }),
                          ],
                        }),
                        e.jsxs("button", {
                          onClick: () => downloadExport(item.url, item.label),
                          disabled: busyKey === item.url,
                          className: "flex items-center gap-1.5 rounded-lg bg-white/5 px-3 py-1.5 text-xs text-white/60 transition hover:bg-white/10 hover:text-white disabled:opacity-40",
                          children: [
                            busyKey === item.url
                              ? e.jsx(RefreshCw, { className: "h-3.5 w-3.5 animate-spin" })
                              : e.jsx(Download, { className: "h-3.5 w-3.5" }),
                            "Download",
                          ],
                        }),
                      ],
                    },
                    item.url,
                  ),
                ),
              }),
              e.jsx("div", {
                className: "text-xs text-white/20",
                children: "* Additional module-specific exports remain available inside each module's reports area.",
              }),
            ],
          }),
    ],
  });
}

export { SettingsImportExportPage as default };
