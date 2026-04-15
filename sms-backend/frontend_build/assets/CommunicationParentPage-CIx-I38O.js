import{r,j as t,b as T}from"./index-D7ltaYVC.js";import{P as B}from"./PageHero-Ct90nOAG.js";import{T as y}from"./triangle-alert-Ck2mduIA.js";import{U as z}from"./users-9FLXP15V.js";import{M as $}from"./mail-CocVKSC1.js";import{P as F}from"./phone-COc4dYHt.js";import{B as L}from"./book-open-DkSh7gF5.js";import{D}from"./dollar-sign-BsYV7G3i.js";import{U as E}from"./user-x-BU11mz3P.js";import{C as H}from"./calendar-ZTeAo9TL.js";import{G as O}from"./graduation-cap-BhcfZJDw.js";import{L as G}from"./loader-circle-CXuHeF9o.js";import{S as I}from"./send-DtouTzJF.js";import{M as K}from"./message-square-DPFLm7VG.js";import{C as R}from"./circle-check-CyyLgyEu.js";import"./createLucideIcon-BLtbVmUp.js";const c=[{key:"report-card",label:"Report Card Notification",description:"Notify parents that end-of-term report cards are ready for collection.",icon:L,color:"violet",gradient:"from-violet-500/20 via-violet-500/5 to-transparent",border:"border-violet-500/25",badgeBg:"bg-violet-500/10",badgeColor:"text-violet-400",endpoint:"/communication/parent/report-card-notify/",defaultSubject:"Report Cards Ready for Collection — {{school_name}}",defaultMessage:`Dear Parent/Guardian,

The end of term report cards for Term 1, 2025 are now ready for collection from the school office.

Office hours: Monday – Friday, 8:00 AM – 4:00 PM.

Please carry your national ID when collecting.

{{school_name}}`},{key:"fee-reminder",label:"Fee Reminder",description:"Send fee payment reminders including outstanding balance details.",icon:D,color:"emerald",gradient:"from-emerald-500/20 via-emerald-500/5 to-transparent",border:"border-emerald-500/25",badgeBg:"bg-emerald-500/10",badgeColor:"text-emerald-400",endpoint:"/communication/parent/fee-reminder/",defaultSubject:"Fee Payment Reminder — Term 1 2025",defaultMessage:`Dear Parent/Guardian,

This is a reminder that school fees for Term 1, 2025 are due for payment by 14th February 2025.

Fee structure:
• Tuition: Ksh 12,000
• Boarding: Ksh 15,000
• Activity Fee: Ksh 2,500
• Lunch: Ksh 3,500
• ICT Levy: Ksh 1,500
• Games & Sports: Ksh 1,000

Total: Ksh 36,000

Payment methods: M-Pesa Paybill 522200 (Acc: Admission No.), Bank, or Cash at Bursar's Office.

Contact: 0722 000 000 or bursar@school.ac.ke

{{school_name}}`},{key:"attendance-alert",label:"Attendance Alert",description:"Alert parents when a student has been recorded absent or late.",icon:E,color:"amber",gradient:"from-amber-500/20 via-amber-500/5 to-transparent",border:"border-amber-500/25",badgeBg:"bg-amber-500/10",badgeColor:"text-amber-400",endpoint:"/communication/parent/attendance-alert/",defaultSubject:"Attendance Alert — {{school_name}}",defaultMessage:`Dear Parent/Guardian,

This is to inform you that your child was absent from school today without prior notice.

Please contact the school as soon as possible to explain the absence.

Contact: 0722 000 000

{{school_name}}`},{key:"meeting-invite",label:"Meeting Invitation",description:"Send invitations to parents for scheduled meetings or events.",icon:H,color:"cyan",gradient:"from-cyan-500/20 via-cyan-500/5 to-transparent",border:"border-cyan-500/25",badgeBg:"bg-cyan-500/10",badgeColor:"text-cyan-400",endpoint:"/communication/parent/meeting-invite/",defaultSubject:"Parents' Meeting Invitation — {{school_name}}",defaultMessage:`Dear Parent/Guardian,

You are cordially invited to the Annual Parents' and Guardians' Meeting.

Date: Saturday, 15th February 2025
Time: 9:00 AM – 12:00 PM
Venue: School Main Hall

Agenda:
• Academic performance review
• Fee structure update
• School developments and programs
• Any Other Business

Light refreshments will be provided. Please RSVP by 12th February 2025.

Yours faithfully,
The Principal
{{school_name}}`}];function oe(){const[j,N]=r.useState(null),[m,v]=r.useState(""),[h,S]=r.useState(""),[k,w]=r.useState({}),[C,M]=r.useState({}),[o,P]=r.useState("both"),[i,p]=r.useState(null),[x,b]=r.useState([]),[u,l]=r.useState(null),g=e=>k[e]??c.find(a=>a.key===e)?.defaultSubject??"",f=e=>C[e]??c.find(a=>a.key===e)?.defaultMessage??"",A=async e=>{const a=m.split(",").map(s=>s.trim()).filter(Boolean),n=h.split(",").map(s=>s.trim()).filter(Boolean);if(a.length===0&&n.length===0){l("Enter at least one email or phone number.");return}p(e.key),l(null);try{await T.post(e.endpoint,{emails:a,phones:n,subject:g(e.key),message:f(e.key)}),b(s=>[{type:e.label,channel:o,success:!0,message:`Sent to ${a.length} email(s) and ${n.length} phone(s)`,time:new Date().toLocaleTimeString("en-KE")},...s.slice(0,9)])}catch{b(s=>[{type:e.label,channel:o,success:!1,message:"Failed — check communication settings",time:new Date().toLocaleTimeString("en-KE")},...s.slice(0,9)])}finally{p(null)}};return t.jsxs("div",{className:"space-y-5 pb-8",children:[t.jsx(B,{badge:"COMMUNICATION",badgeColor:"rose",title:"Parent Broadcasts",subtitle:"Mass messages and announcements to parents",icon:"📣"}),u&&t.jsxs("div",{className:"flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200",children:[t.jsx(y,{size:14,className:"flex-shrink-0"}),u,t.jsx("button",{onClick:()=>l(null),className:"ml-auto",children:"✕"})]}),t.jsxs("div",{className:"rounded-2xl glass-panel p-5 space-y-4",children:[t.jsxs("h2",{className:"text-sm font-semibold text-white flex items-center gap-2",children:[t.jsx(z,{size:14,className:"text-slate-400"})," Recipients"]}),t.jsxs("div",{className:"grid gap-3 sm:grid-cols-2",children:[t.jsxs("div",{className:"flex items-center gap-2 rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5",children:[t.jsx($,{size:13,className:"text-slate-500 flex-shrink-0"}),t.jsx("input",{value:m,onChange:e=>v(e.target.value),placeholder:"Email addresses, comma-separated",className:"flex-1 bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"})]}),t.jsxs("div",{className:"flex items-center gap-2 rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5",children:[t.jsx(F,{size:13,className:"text-slate-500 flex-shrink-0"}),t.jsx("input",{value:h,onChange:e=>S(e.target.value),placeholder:"Phone numbers, comma-separated",className:"flex-1 bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"})]})]}),t.jsx("div",{className:"flex gap-1 rounded-xl border border-white/[0.07] bg-white/[0.02] p-1 w-fit",children:[["both","Email + SMS"],["email","Email Only"],["sms","SMS Only"]].map(([e,a])=>t.jsx("button",{onClick:()=>P(e),className:`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${o===e?"bg-emerald-500/20 text-emerald-300 border border-emerald-500/30":"text-slate-400 hover:text-slate-200"}`,children:a},e))})]}),t.jsx("div",{className:"grid gap-4 md:grid-cols-2",children:c.map(e=>{const a=e.icon,n=j===e.key;return t.jsxs("div",{className:`rounded-2xl border glass-panel overflow-hidden transition-all ${n?`border-${e.color}-500/30`:"border-white/[0.07]"}`,children:[t.jsxs("button",{onClick:()=>N(n?null:e.key),className:"w-full flex items-center gap-3 p-4 text-left hover:bg-white/[0.02] transition",children:[t.jsx("div",{className:`flex-shrink-0 rounded-xl p-2.5 ${e.badgeBg} border ${e.border}`,children:t.jsx(a,{size:16,className:e.badgeColor})}),t.jsxs("div",{className:"flex-1",children:[t.jsx("p",{className:"text-sm font-semibold text-white",children:e.label}),t.jsx("p",{className:"text-xs text-slate-400 mt-0.5",children:e.description})]}),t.jsx(O,{size:13,className:`flex-shrink-0 ${n?e.badgeColor:"text-slate-600"}`})]}),n&&t.jsxs("div",{className:"border-t border-white/[0.07] p-4 space-y-3",children:[t.jsxs("div",{children:[t.jsx("label",{className:"text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1 block",children:"Subject"}),t.jsx("input",{value:g(e.key),onChange:s=>w(d=>({...d,[e.key]:s.target.value})),className:"w-full rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50"})]}),t.jsxs("div",{children:[t.jsx("label",{className:"text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1 block",children:"Message"}),t.jsx("textarea",{value:f(e.key),onChange:s=>M(d=>({...d,[e.key]:s.target.value})),rows:6,className:"w-full rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 resize-none"})]}),t.jsxs("button",{onClick:()=>A(e),disabled:i===e.key,className:`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold text-white transition disabled:opacity-50 ${e.badgeBg} border ${e.border} hover:opacity-90`,children:[i===e.key?t.jsx(G,{size:14,className:"animate-spin"}):t.jsx(I,{size:14}),i===e.key?"Sending…":`Send ${e.label}`]})]})]},e.key)})}),x.length>0&&t.jsxs("div",{children:[t.jsxs("h2",{className:"text-sm font-semibold text-white mb-3 flex items-center gap-2",children:[t.jsx(K,{size:14,className:"text-slate-400"})," Send History"]}),t.jsx("div",{className:"space-y-2",children:x.map((e,a)=>t.jsxs("div",{className:`flex items-center gap-3 rounded-xl border px-4 py-3 ${e.success?"border-emerald-500/20 bg-emerald-500/5":"border-red-500/20 bg-red-500/5"}`,children:[e.success?t.jsx(R,{size:14,className:"text-emerald-400 flex-shrink-0"}):t.jsx(y,{size:14,className:"text-red-400 flex-shrink-0"}),t.jsxs("div",{className:"flex-1 min-w-0",children:[t.jsx("p",{className:"text-xs font-semibold text-slate-200",children:e.type}),t.jsx("p",{className:"text-[11px] text-slate-400",children:e.message})]}),t.jsx("span",{className:"text-[10px] text-slate-600 flex-shrink-0",children:e.time})]},a))})]})]})}export{oe as default};
