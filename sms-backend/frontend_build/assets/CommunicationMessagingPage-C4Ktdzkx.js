import { r as React, j as e, b as api } from "./index-D7ltaYVC.js";
import { P as Plus } from "./plus-CQ41G_RD.js";
import { L as Loader } from "./loader-circle-CXuHeF9o.js";
import { S as Search } from "./search-Di5NLvoc.js";
import { M as MessageSquare } from "./message-square-DPFLm7VG.js";
import { U as Users } from "./users-9FLXP15V.js";
import { H as Hash } from "./hash-Gb-Fyhtd.js";
import { A as ArrowLeft } from "./arrow-left-DHVb17E3.js";
import { R as RefreshCw } from "./refresh-cw-DOVkzt4u.js";
import { E as Ellipsis } from "./ellipsis-D6luNPMN.js";
import { A as Archive } from "./archive-lG33V3Lv.js";
import { T as Trash2 } from "./trash-2-Bs1RXa9v.js";
import { S as Send } from "./send-DtouTzJF.js";
import { U as Upload } from "./upload-B5_nFvgY.js";

function normalizeRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
}

function formatTimestamp(value) {
  if (!value) return "";
  const current = new Date();
  const parsed = new Date(value);
  if (parsed.toDateString() === current.toDateString()) {
    return parsed.toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" });
  }
  return parsed.toLocaleDateString("en-KE", { day: "2-digit", month: "short" });
}

function readError(err, fallback) {
  const data = err?.response?.data;
  if (typeof data === "string" && data) return data;
  if (typeof data?.detail === "string" && data.detail) return data.detail;
  if (Array.isArray(data?.content) && data.content[0]) return data.content[0];
  if (typeof data?.content === "string" && data.content) return data.content;
  return fallback;
}

function AttachmentPills({ files, onRemove }) {
  if (!files.length) return null;
  return e.jsx("div", {
    className: "flex flex-wrap gap-2 px-1",
    children: files.map((file, index) =>
      e.jsxs(
        "div",
        {
          className: "flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1.5 text-[11px] text-emerald-200",
          children: [
            e.jsx(Upload, { size: 12, className: "text-emerald-300" }),
            e.jsx("span", { className: "max-w-[180px] truncate", children: file.name }),
            e.jsx("button", {
              type: "button",
              onClick: () => onRemove(index),
              className: "text-emerald-100/70 hover:text-white transition",
              children: "x",
            }),
          ],
        },
        `${file.name}-${index}`,
      ),
    ),
  });
}

function MessageAttachments({ attachments }) {
  if (!attachments?.length) return null;
  return e.jsx("div", {
    className: "mt-2 space-y-2",
    children: attachments.map((attachment) =>
      attachment.is_image
        ? e.jsxs(
            "a",
            {
              href: attachment.url || attachment.preview_url,
              target: "_blank",
              rel: "noreferrer",
              className: "block overflow-hidden rounded-xl border border-white/[0.08] bg-slate-950/60",
              children: [
                e.jsx("img", {
                  src: attachment.preview_url || attachment.url,
                  alt: attachment.file_name || "attachment",
                  className: "max-h-56 w-full object-cover",
                }),
                e.jsx("div", {
                  className: "px-3 py-2 text-[11px] text-slate-400",
                  children: attachment.file_name || "Image attachment",
                }),
              ],
            },
            attachment.id,
          )
        : e.jsxs(
            "a",
            {
              href: attachment.url,
              target: "_blank",
              rel: "noreferrer",
              className: "flex items-center justify-between rounded-xl border border-white/[0.08] bg-slate-950/60 px-3 py-2 text-[11px] text-slate-300 hover:border-emerald-500/30 hover:text-white transition",
              children: [
                e.jsx("span", {
                  className: "truncate pr-3",
                  children: attachment.file_name || "Attachment",
                }),
                e.jsx("span", {
                  className: "text-slate-500",
                  children: attachment.file_extension ? `.${attachment.file_extension}` : "file",
                }),
              ],
            },
            attachment.id,
          ),
    ),
  });
}

function CommunicationMessagingPage() {
  const [conversations, setConversations] = React.useState([]);
  const [messages, setMessages] = React.useState([]);
  const [activeConversationId, setActiveConversationId] = React.useState(null);
  const [draft, setDraft] = React.useState("");
  const [pendingFiles, setPendingFiles] = React.useState([]);
  const [groupName, setGroupName] = React.useState("");
  const [showCreate, setShowCreate] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [showThread, setShowThread] = React.useState("list");
  const [showActions, setShowActions] = React.useState(false);
  const endRef = React.useRef(null);
  const fileInputRef = React.useRef(null);

  const loadConversations = React.useCallback(async () => {
    const response = await api.get("/communication/conversations/");
    const rows = normalizeRows(response.data);
    setConversations(rows);
    if (!activeConversationId && rows.length > 0) {
      setActiveConversationId(rows[0].id);
    }
  }, [activeConversationId]);

  const loadMessages = React.useCallback(async (conversationId) => {
    const response = await api.get("/communication/messages/", { params: { conversation: conversationId } });
    setMessages(normalizeRows(response.data));
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }, []);

  React.useEffect(() => {
    (async () => {
      try {
        await loadConversations();
      } catch (err) {
        setError(readError(err, "Unable to load conversations."));
      }
    })();
  }, [loadConversations]);

  React.useEffect(() => {
    if (!activeConversationId) return;
    loadMessages(activeConversationId).catch(() => setError("Unable to load messages."));
  }, [activeConversationId, loadMessages]);

  const filteredConversations = conversations.filter((item) =>
    (item.title || `Conversation #${item.id}`).toLowerCase().includes(search.toLowerCase()),
  );
  const activeConversation = conversations.find((item) => item.id === activeConversationId);

  const resetComposer = () => {
    setDraft("");
    setPendingFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const createConversation = async () => {
    if (!groupName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.post("/communication/conversations/", {
        conversation_type: "Group",
        title: groupName.trim(),
      });
      setGroupName("");
      setShowCreate(false);
      await loadConversations();
    } catch (err) {
      setError(readError(err, "Unable to create conversation."));
    } finally {
      setCreating(false);
    }
  };

  const sendMessage = async () => {
    if (!activeConversationId || (!draft.trim() && !pendingFiles.length)) return;
    setSending(true);
    setError(null);
    try {
      if (pendingFiles.length) {
        const formData = new FormData();
        formData.append("conversation", String(activeConversationId));
        formData.append("content", draft.trim());
        pendingFiles.forEach((file) => formData.append("attachments", file));
        await api.post("/communication/messages/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      } else {
        await api.post("/communication/messages/", {
          conversation: activeConversationId,
          content: draft.trim(),
        });
      }
      resetComposer();
      await loadMessages(activeConversationId);
    } catch (err) {
      setError(readError(err, "Unable to send message."));
    } finally {
      setSending(false);
    }
  };

  const archiveConversation = async () => {
    if (!activeConversationId) return;
    setShowActions(false);
    try {
      await api.patch(`/communication/conversations/${activeConversationId}/`, { is_archived: true });
      setActiveConversationId(null);
      setMessages([]);
      setShowThread("list");
      await loadConversations();
    } catch (err) {
      setError(readError(err, "Unable to archive conversation."));
    }
  };

  const deleteConversation = async () => {
    if (!activeConversationId) return;
    setShowActions(false);
    try {
      await api.delete(`/communication/conversations/${activeConversationId}/`);
      setActiveConversationId(null);
      setMessages([]);
      setShowThread("list");
      await loadConversations();
    } catch (err) {
      setError(readError(err, "Unable to delete conversation."));
    }
  };

  const onFilesSelected = (event) => {
    const files = Array.from(event.target.files || []);
    setPendingFiles((existing) => [...existing, ...files]);
  };

  const removePendingFile = (index) => {
    setPendingFiles((existing) => existing.filter((_, fileIndex) => fileIndex !== index));
  };

  return e.jsxs("div", {
    className: "flex h-full flex-col",
    children: [
      e.jsxs("div", {
        className: "flex flex-shrink-0 items-center gap-3 border-b border-white/[0.06] px-4 pb-3 pt-4",
        children: [
          e.jsx("div", {
            className: "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl text-lg",
            style: { background: "rgba(244,63,94,0.15)", border: "1px solid rgba(244,63,94,0.25)" },
            children: "CM",
          }),
          e.jsxs("div", {
            className: "min-w-0 flex-1",
            children: [
              e.jsx("h1", {
                className: "font-display text-base font-bold leading-tight text-white",
                children: "In-App Conversations",
              }),
              e.jsx("p", {
                className: "text-[11px] leading-tight text-slate-500",
                children: "Manage in-app messaging, attachments, and conversation threads",
              }),
            ],
          }),
        ],
      }),
      error &&
        e.jsxs("div", {
          className: "mx-4 mt-2 flex flex-shrink-0 items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-200",
          children: [
            error,
            e.jsx("button", {
              onClick: () => setError(null),
              className: "ml-auto text-xs opacity-60 hover:opacity-100",
              children: "x",
            }),
          ],
        }),
      e.jsxs("div", {
        className: "grid flex-1 min-h-0 grid-cols-1 gap-3 p-4 pt-3 md:grid-cols-[280px_1fr] lg:grid-cols-[300px_1fr]",
        children: [
          e.jsxs("div", {
            className: `glass-panel flex flex-col overflow-hidden rounded-2xl ${showThread === "thread" ? "hidden md:flex" : "flex"}`,
            children: [
              e.jsxs("div", {
                className: "flex-shrink-0 border-b border-white/[0.07] px-4 pb-3 pt-4",
                children: [
                  e.jsxs("div", {
                    className: "mb-3 flex items-center gap-2",
                    children: [
                      e.jsx("h2", { className: "flex-1 text-sm font-semibold text-white", children: "Conversations" }),
                      e.jsx("button", {
                        onClick: () => {
                          setShowCreate((value) => !value);
                          setGroupName("");
                        },
                        className: "flex h-7 w-7 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/20 transition hover:bg-emerald-500/30",
                        title: showCreate ? "Cancel" : "New conversation",
                        children: e.jsx(Plus, { size: 13, className: "text-emerald-400" }),
                      }),
                    ],
                  }),
                  showCreate &&
                    e.jsxs("div", {
                      className: "mb-3",
                      children: [
                        e.jsx("p", {
                          className: "mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500",
                          children: "New Group / Channel",
                        }),
                        e.jsxs("div", {
                          className: "flex gap-2",
                          children: [
                            e.jsx("input", {
                              value: groupName,
                              onChange: (event) => setGroupName(event.target.value),
                              onKeyDown: (event) => {
                                if (event.key === "Enter") createConversation();
                              },
                              placeholder: "Enter name...",
                              autoFocus: true,
                              className:
                                "flex-1 rounded-lg border border-white/[0.09] bg-slate-950 px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-emerald-500/50 focus:outline-none",
                            }),
                            e.jsx("button", {
                              onClick: createConversation,
                              disabled: creating || !groupName.trim(),
                              className:
                                "rounded-lg bg-emerald-500 px-3 text-xs font-bold text-white transition hover:bg-emerald-400 disabled:opacity-50",
                              children: creating ? e.jsx(Loader, { size: 11, className: "animate-spin" }) : "Create",
                            }),
                          ],
                        }),
                      ],
                    }),
                  e.jsxs("div", {
                    className: "relative",
                    children: [
                      e.jsx(Search, { size: 12, className: "absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" }),
                      e.jsx("input", {
                        value: search,
                        onChange: (event) => setSearch(event.target.value),
                        placeholder: "Search conversations...",
                        className:
                          "w-full rounded-lg border border-white/[0.07] bg-slate-950/60 py-1.5 pl-7 pr-3 text-xs text-slate-300 placeholder-slate-600 focus:border-slate-600 focus:outline-none",
                      }),
                    ],
                  }),
                ],
              }),
              e.jsx("div", {
                className: "flex-1 overflow-y-auto",
                children:
                  filteredConversations.length === 0
                    ? e.jsxs("div", {
                        className: "flex flex-col items-center justify-center px-4 py-12 text-center",
                        children: [
                          e.jsx(MessageSquare, { size: 28, className: "mb-2 text-slate-700" }),
                          e.jsx("p", { className: "mb-3 text-xs text-slate-500", children: "No conversations yet" }),
                          e.jsxs("button", {
                            onClick: () => setShowCreate(true),
                            className: "flex items-center gap-1 text-xs font-semibold text-emerald-400 transition hover:text-emerald-300",
                            children: [e.jsx(Plus, { size: 11 }), "Start one"],
                          }),
                        ],
                      })
                    : filteredConversations.map((item) =>
                        e.jsxs(
                          "button",
                          {
                            onClick: () => {
                              setActiveConversationId(item.id);
                              setShowThread("thread");
                            },
                            className: `w-full border-b border-white/[0.05] px-4 py-3 text-left transition hover:bg-white/[0.025] ${
                              activeConversationId === item.id ? "border-l-2 border-l-emerald-500 bg-emerald-500/10" : ""
                            }`,
                            children: [
                              e.jsxs("div", {
                                className: "flex items-center gap-3",
                                children: [
                                  e.jsx("div", {
                                    className: "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-slate-700",
                                    children:
                                      item.conversation_type === "Group"
                                        ? e.jsx(Users, { size: 12, className: "text-slate-300" })
                                        : e.jsx(Hash, { size: 12, className: "text-slate-300" }),
                                  }),
                                  e.jsxs("div", {
                                    className: "min-w-0 flex-1",
                                    children: [
                                      e.jsx("p", {
                                        className: "truncate text-xs font-semibold text-slate-200",
                                        children: item.title || `Conversation #${item.id}`,
                                      }),
                                      e.jsx("p", {
                                        className: "text-[10px] text-slate-500",
                                        children: item.conversation_type,
                                      }),
                                    ],
                                  }),
                                  activeConversationId === item.id &&
                                    e.jsx("span", {
                                      className: "h-2 w-2 flex-shrink-0 rounded-full bg-emerald-400",
                                    }),
                                ],
                              }),
                            ],
                          },
                          item.id,
                        ),
                      ),
              }),
            ],
          }),
          e.jsxs("div", {
            className: `glass-panel flex flex-col overflow-hidden rounded-2xl ${showThread === "list" && !activeConversationId ? "hidden md:flex" : "flex"}`,
            children: [
              e.jsxs("div", {
                className: "flex flex-shrink-0 items-center gap-3 border-b border-white/[0.07] px-5 py-3.5",
                children: [
                  e.jsx("button", {
                    onClick: () => setShowThread("list"),
                    className: "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg border border-white/[0.09] transition hover:bg-slate-700 md:hidden",
                    title: "Back to list",
                    children: e.jsx(ArrowLeft, { size: 12, className: "text-slate-400" }),
                  }),
                  activeConversation
                    ? e.jsxs(React.Fragment, {
                        children: [
                          e.jsx("div", {
                            className: "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-slate-700",
                            children: e.jsx(Users, { size: 13, className: "text-slate-300" }),
                          }),
                          e.jsxs("div", {
                            className: "min-w-0 flex-1",
                            children: [
                              e.jsx("p", {
                                className: "truncate text-sm font-semibold text-white",
                                children: activeConversation.title || `Conversation #${activeConversation.id}`,
                              }),
                              e.jsx("p", {
                                className: "text-[10px] text-slate-500",
                                children: activeConversation.conversation_type,
                              }),
                            ],
                          }),
                          e.jsx("button", {
                            onClick: () => activeConversationId && loadMessages(activeConversationId),
                            className: "flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.09] transition hover:bg-slate-700",
                            title: "Refresh messages",
                            children: e.jsx(RefreshCw, { size: 11, className: "text-slate-400" }),
                          }),
                          e.jsxs("div", {
                            className: "relative",
                            children: [
                              e.jsx("button", {
                                onClick: () => setShowActions((value) => !value),
                                className: "flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.09] transition hover:bg-slate-700",
                                title: "More options",
                                children: e.jsx(Ellipsis, { size: 13, className: "text-slate-400" }),
                              }),
                              showActions &&
                                e.jsxs("div", {
                                  className:
                                    "absolute right-0 top-9 z-30 w-48 rounded-xl border border-white/[0.09] bg-slate-900 py-1 shadow-xl",
                                  children: [
                                    e.jsxs("button", {
                                      onClick: archiveConversation,
                                      className:
                                        "flex w-full items-center gap-2.5 px-3.5 py-2.5 text-xs text-slate-300 transition hover:bg-white/[0.06] hover:text-white",
                                      children: [e.jsx(Archive, { size: 12, className: "text-amber-400" }), "Archive conversation"],
                                    }),
                                    e.jsxs("button", {
                                      onClick: deleteConversation,
                                      className: "flex w-full items-center gap-2.5 px-3.5 py-2.5 text-xs text-rose-400 transition hover:bg-rose-500/10",
                                      children: [e.jsx(Trash2, { size: 12 }), "Delete conversation"],
                                    }),
                                  ],
                                }),
                            ],
                          }),
                        ],
                      })
                    : e.jsx("p", { className: "text-sm text-slate-500", children: "Select a conversation to start" }),
                ],
              }),
              e.jsxs("div", {
                className: "flex-1 space-y-3 overflow-y-auto px-4 py-4",
                children: [
                  activeConversationId
                    ? messages.length === 0
                      ? e.jsxs("div", {
                          className: "flex h-full flex-col items-center justify-center text-center",
                          children: [
                            e.jsx(MessageSquare, { size: 32, className: "mb-3 text-slate-700" }),
                            e.jsx("p", { className: "text-sm text-slate-500", children: "No messages yet" }),
                            e.jsx("p", { className: "mt-1 text-xs text-slate-600", children: "Start the conversation below." }),
                          ],
                        })
                      : messages.map((message) =>
                          e.jsxs(
                            "div",
                            {
                              className: `flex gap-2.5 ${message.is_own ? "flex-row-reverse" : ""}`,
                              children: [
                                e.jsx("div", {
                                  className: "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-slate-700 text-[10px] font-bold text-slate-300",
                                  children: (message.sender_name?.[0] || "?").toUpperCase(),
                                }),
                                e.jsxs("div", {
                                  className: `flex max-w-[82%] flex-col gap-1 ${message.is_own ? "items-end" : "items-start"}`,
                                  children: [
                                    e.jsxs("div", {
                                      className: `rounded-2xl border px-3.5 py-2.5 ${
                                        message.is_own
                                          ? "border-emerald-500/30 bg-emerald-500/20"
                                          : "border-white/[0.09] bg-slate-800"
                                      }`,
                                      children: [
                                        !message.is_own &&
                                          e.jsx("p", {
                                            className: "mb-1 text-[10px] font-bold text-emerald-400",
                                            children: message.sender_name,
                                          }),
                                        !!message.content &&
                                          e.jsx("p", {
                                            className: "whitespace-pre-wrap text-xs leading-relaxed text-slate-200",
                                            children: message.content,
                                          }),
                                        e.jsx(MessageAttachments, { attachments: message.attachments || [] }),
                                      ],
                                    }),
                                    e.jsx("p", {
                                      className: "px-1 text-[10px] text-slate-600",
                                      children: formatTimestamp(message.sent_at),
                                    }),
                                  ],
                                }),
                              ],
                            },
                            message.id,
                          ),
                        )
                    : e.jsxs("div", {
                        className: "flex h-full flex-col items-center justify-center text-center",
                        children: [
                          e.jsx(MessageSquare, { size: 40, className: "mb-3 text-slate-700" }),
                          e.jsx("p", { className: "mb-1 text-sm text-slate-500", children: "No conversation selected" }),
                          e.jsx("p", { className: "text-xs text-slate-600", children: "Choose one from the list or create a new one" }),
                        ],
                      }),
                  e.jsx("div", { ref: endRef }),
                ],
              }),
              e.jsxs("div", {
                className: "flex-shrink-0 border-t border-white/[0.07] p-3",
                children: [
                  e.jsx(AttachmentPills, { files: pendingFiles, onRemove: removePendingFile }),
                  e.jsxs("div", {
                    className: "mt-2 flex items-end gap-2",
                    children: [
                      e.jsxs("div", {
                        className: "flex flex-col gap-2",
                        children: [
                          e.jsx("input", {
                            ref: fileInputRef,
                            type: "file",
                            multiple: true,
                            className: "hidden",
                            onChange: onFilesSelected,
                          }),
                          e.jsx("button", {
                            type: "button",
                            onClick: () => fileInputRef.current?.click(),
                            disabled: !activeConversationId,
                            className:
                              "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-white/[0.09] bg-slate-950 text-slate-300 transition hover:border-emerald-500/40 hover:text-emerald-300 disabled:opacity-40",
                            title: "Attach files",
                            children: e.jsx(Upload, { size: 15 }),
                          }),
                        ],
                      }),
                      e.jsx("textarea", {
                        value: draft,
                        onChange: (event) => setDraft(event.target.value),
                        onKeyDown: (event) => {
                          if (event.key === "Enter" && !event.shiftKey) {
                            event.preventDefault();
                            sendMessage();
                          }
                        },
                        placeholder: activeConversationId
                          ? "Type a message... (Enter to send, Shift+Enter for new line)"
                          : "Select a conversation first",
                        disabled: !activeConversationId,
                        rows: 2,
                        className:
                          "flex-1 resize-none rounded-xl border border-white/[0.09] bg-slate-950 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-emerald-500/50 focus:outline-none disabled:opacity-40",
                      }),
                      e.jsx("button", {
                        onClick: sendMessage,
                        disabled: !activeConversationId || (!draft.trim() && !pendingFiles.length) || sending,
                        className:
                          "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-emerald-500 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40",
                        children: sending
                          ? e.jsx(Loader, { size: 15, className: "animate-spin text-white" })
                          : e.jsx(Send, { size: 15, className: "text-white" }),
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

export { CommunicationMessagingPage as default };
