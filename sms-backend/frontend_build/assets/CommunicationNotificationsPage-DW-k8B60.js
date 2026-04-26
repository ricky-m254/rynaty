import{r as a,j as e,b as x}from"./index-D7ltaYVC.js";
import{P as R}from"./PageHero-Ct90nOAG.js";
import{T as A}from"./triangle-alert-Ck2mduIA.js";
import{C as U}from"./circle-check-CyyLgyEu.js";
import{B as B}from"./bell-Biv8Yc7n.js";
import{L as S}from"./loader-circle-CXuHeF9o.js";
import{F as O}from"./filter-CluRG9j1.js";
import{T as D}from"./trash-2-Bs1RXa9v.js";
import{C as L}from"./clock-Cjp0BcMI.js";
import{U as C}from"./users-9FLXP15V.js";
import{S as P}from"./send-DtouTzJF.js";
import{R as H}from"./refresh-cw-DOVkzt4u.js";
import"./createLucideIcon-BLtbVmUp.js";

function F(t){return Array.isArray(t)?t:Array.isArray(t?.results)?t.results:[]}
function K(t){return t?new Date(t).toLocaleString("en-KE",{day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"}):"—"}
function M(t){return t===!0||t==="true"?"Read":t===!1||t==="false"?"Unread":"All"}
const T=["System","Financial","Academic","Behavioral","HR","Event","Emergency"];
const E=["Informational","Important","Urgent"];
const J={
System:"bg-blue-500/10 text-blue-300 border-blue-500/30",
Financial:"bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
Academic:"bg-violet-500/10 text-violet-300 border-violet-500/30",
Behavioral:"bg-amber-500/10 text-amber-300 border-amber-500/30",
HR:"bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
Event:"bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/30",
Emergency:"bg-red-500/10 text-red-300 border-red-500/30"
};
const I={
Informational:"bg-slate-700/50 text-slate-300 border-slate-600",
Important:"bg-amber-500/15 text-amber-300 border-amber-500/30",
Urgent:"bg-red-500/15 text-red-300 border-red-500/30"
};

function se(){
const[t,l]=a.useState([]),
[n,m]=a.useState(!0),
[r,o]=a.useState(!1),
[s,u]=a.useState(!1),
[d,i]=a.useState("mine"),
[f,c]=a.useState(""),
[g,p]=a.useState(""),
[h,j]=a.useState([]),
[N,v]=a.useState([]),
[y,w]=a.useState(""),
[k,b]=a.useState(!1),
[q,z]=a.useState(!1),
[V,Q]=a.useState(!1),
[W,Y]=a.useState(null),
[X,Z]=a.useState(null),
[tt,lt]=a.useState({title:"",message:"",notification_type:"System",priority:"Informational",action_url:""});

const et=a.useMemo(()=>d==="unread"?"false":d==="read"?"true":"",[d]);
const at=a.useMemo(()=>({
total:t.length,
unread:t.filter(_=>!_.is_read).length,
urgent:t.filter(_=>_.priority==="Urgent").length,
audit:d==="all"?t.length:0
}),[t,d]);

const nt=async()=>{
if(!s)return;
z(!0);
try{
const _=await x.get("/communication/notifications/recipients/",{params:{q:y}});
j(F(_.data))
} catch{
j([])
} finally{
z(!1)
}
};

const rt=async()=>{
m(!0);
try{
const _={};
f&&(_.notification_type=f);
et!==""&&(_.is_read=et);
if(d==="all"){
_.scope=!0;
g&&(_.recipient_id=g)
}
const G=await x.get("/communication/notifications/",{params:_});
l(F(G.data));
Y(null)
} catch{
Y("Unable to load notifications.")
} finally{
m(!1)
}
};

const st=async()=>{
if(s||V)return;
Q(!0);
try{
const _=await x.get("/communication/notifications/recipients/",{params:{q:""}});
j(F(_.data));
u(!0)
} catch{
u(!1);
if(d==="all")i("mine")
} finally{
Q(!1)
}
};

a.useEffect(()=>{rt()},[d,f,g,et]);
a.useEffect(()=>{st()},[]);
a.useEffect(()=>{
if(!s)return;
const _=setTimeout(()=>{nt()},250);
return()=>clearTimeout(_)
},[y,s]);

const ut=t=>{
v(_=>_.some(G=>G.id===t.id)?_:_[..._,t])
};
const it=t=>{
v(_=>_.filter(G=>G.id!==t))
};
const ct=()=>{
lt({title:"",message:"",notification_type:"System",priority:"Informational",action_url:""});
v([]);
u(s=>s)
};

const ot=async()=>{
if(!tt.title.trim()||!tt.message.trim()){
Y("Title and message are required.");
return
}
o(!0);
Y(null);
try{
const _={title:tt.title,message:tt.message,notification_type:tt.notification_type,priority:tt.priority,action_url:tt.action_url};
if(s&&N.length)_.recipient_ids=N.map(G=>G.id);
const G=await x.post("/communication/notifications/",_);
const $=G.data?.created??1;
ct();
u(!1);
Z($===1?"Notification created.":`${$} notifications created.`);
setTimeout(()=>Z(null),4e3);
await rt()
} catch(_){
Y(_.response?.data?.recipient_ids||"Unable to create notification.")
} finally{
o(!1)
}
};

const pt=async _=>{
try{
await x.patch(`/communication/notifications/${_}/read/`);
l(G=>G.map($=>$.id===_?{...$,is_read:!0,read_at:new Date().toISOString()}:$))
} catch{
Y("Unable to mark notification as read.")
}
};

const mt=async _=>{
try{
await x.delete(`/communication/notifications/${_}/`);
l(G=>G.filter($=>$.id!==_))
} catch{
Y("Unable to delete notification.")
}
};

const ft=t.filter(_=>!f||_.notification_type===f).filter(_=>d==="unread"?!_.is_read:d==="read"?_.is_read:!0);

return e.jsxs("div",{className:"space-y-5 pb-8",children:[
e.jsx(R,{badge:"COMMUNICATION",badgeColor:"rose",title:"In-App Notifications",subtitle:"Bulk recipient targeting, audit visibility, and real notification state for school operators.",icon:"🔔"}),
e.jsx("div",{className:"grid grid-cols-2 gap-3 sm:grid-cols-4",children:[
{label:"Visible",value:at.total,color:"text-slate-300",bg:"bg-slate-700/30"},
{label:"Unread",value:at.unread,color:"text-emerald-400",bg:"bg-emerald-500/10"},
{label:"Urgent",value:at.urgent,color:"text-red-400",bg:"bg-red-500/10"},
{label:"Audit Rows",value:at.audit,color:"text-blue-400",bg:"bg-blue-500/10"}
].map(_=>e.jsxs("div",{className:`rounded-xl border border-white/[0.07] ${_.bg} px-4 py-3`,children:[
e.jsx("p",{className:`text-2xl font-bold ${_.color}`,children:_.value}),
e.jsx("p",{className:"mt-0.5 text-[11px] text-slate-500",children:_.label})
]},_.label))}),
W&&e.jsxs("div",{className:"flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200",children:[
e.jsx(A,{size:14,className:"flex-shrink-0"}),
e.jsx("span",{children:W}),
e.jsx("button",{onClick:()=>Y(null),className:"ml-auto",children:"×"})
]}),
X&&e.jsxs("div",{className:"flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200",children:[
e.jsx(U,{size:14,className:"flex-shrink-0"}),
e.jsx("span",{children:X})
]}),
e.jsxs("div",{className:"flex flex-wrap items-center gap-3 rounded-xl glass-panel px-4 py-3",children:[
e.jsxs("div",{className:"flex gap-1 rounded-xl bg-slate-950/40 p-1",children:[
[
{value:"mine",label:"Mine"},
{value:"unread",label:"Unread"},
{value:"read",label:"Read"},
{value:"all",label:"Audit All",disabled:!s&&V===!1}
].map(_=>e.jsx("button",{onClick:()=>_.disabled||i(_.value),disabled:_.disabled,className:`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${d===_.value?"bg-emerald-500/20 text-emerald-300 border border-emerald-500/30":"text-slate-400 hover:text-slate-200"} disabled:opacity-40`,children:_.label},_.value))
]}),
e.jsxs("div",{className:"flex items-center gap-2 rounded-xl glass-panel px-3",children:[
e.jsx(O,{size:11,className:"text-slate-500"}),
e.jsxs("select",{value:f,onChange:_=>c(_.target.value),className:"bg-transparent py-2 pr-1 text-xs text-slate-300 focus:outline-none",children:[
e.jsx("option",{value:"",children:"All Types"}),
T.map(_=>e.jsx("option",{value:_,children:_},_))
]})
]}),
s&&d==="all"&&e.jsxs("div",{className:"flex items-center gap-2 rounded-xl glass-panel px-3",children:[
e.jsx(C,{size:12,className:"text-slate-500"}),
e.jsxs("select",{value:g,onChange:_=>p(_.target.value),className:"bg-transparent py-2 pr-1 text-xs text-slate-300 focus:outline-none",children:[
e.jsx("option",{value:"",children:"All Recipients"}),
h.map(_=>e.jsx("option",{value:_.id,children:_.label||_.username},_.id))
]})
]}),
e.jsxs("button",{onClick:rt,className:"ml-auto flex items-center gap-2 rounded-xl border border-white/[0.09] px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-white/[0.04] transition",children:[e.jsx(H,{size:12}),"Refresh"]}),
e.jsx("button",{onClick:()=>u(_=>!_),className:"rounded-xl bg-emerald-500 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-400 transition",children:s?"Close Composer":"New Notification"})
]}),
s&&e.jsxs("div",{className:"rounded-2xl border border-white/[0.09] bg-white/[0.025] p-5 space-y-4",children:[
e.jsxs("h2",{className:"flex items-center gap-2 text-sm font-bold text-white",children:[e.jsx(B,{size:14}),"Notification Composer"]}),
e.jsxs("div",{className:"grid gap-3 sm:grid-cols-2",children:[
e.jsx("input",{value:tt.title,onChange:_=>lt(G=>({...G,title:_.target.value})),placeholder:"Notification title",className:"rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50"}),
e.jsxs("select",{value:tt.notification_type,onChange:_=>lt(G=>({...G,notification_type:_.target.value})),className:"rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm text-white",children:T.map(_=>e.jsx("option",{value:_,children:_},_))}),
e.jsxs("select",{value:tt.priority,onChange:_=>lt(G=>({...G,priority:_.target.value})),className:"rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm text-white",children:E.map(_=>e.jsx("option",{value:_,children:_},_))}),
e.jsx("input",{value:tt.action_url,onChange:_=>lt(G=>({...G,action_url:_.target.value})),placeholder:"Action URL (optional)",className:"rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50"})
]}),
e.jsx("textarea",{value:tt.message,onChange:_=>lt(G=>({...G,message:_.target.value})),rows:4,placeholder:"Notification message",className:"w-full rounded-xl border border-white/[0.09] bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 resize-none"}),
s&&e.jsxs("div",{className:"space-y-3 rounded-xl border border-white/[0.07] bg-slate-950/40 p-4",children:[
e.jsxs("div",{className:"flex items-center gap-3",children:[
e.jsx(C,{size:14,className:"text-slate-400"}),
e.jsx("input",{value:y,onChange:_=>w(_.target.value),placeholder:"Search recipients by name, username, or email",className:"flex-1 bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"}),
q&&e.jsx(S,{size:12,className:"animate-spin text-slate-500"})
]}),
N.length>0&&e.jsx("div",{className:"flex flex-wrap gap-2",children:N.map(_=>e.jsxs("button",{onClick:()=>it(_.id),className:"rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-200",children:[_.username," ×"]},_.id))}),
e.jsx("div",{className:"max-h-48 space-y-2 overflow-auto",children:h.filter(_=>!N.some(G=>G.id===_.id)).slice(0,12).map(_=>e.jsxs("button",{onClick:()=>ut(_),className:"flex w-full items-start justify-between rounded-xl border border-white/[0.07] bg-white/[0.02] px-3 py-2 text-left hover:bg-white/[0.04] transition",children:[
e.jsxs("div",{className:"min-w-0",children:[
e.jsx("p",{className:"truncate text-sm font-medium text-white",children:_.full_name||_.username}),
e.jsxs("p",{className:"truncate text-[11px] text-slate-500",children:[_.role_name||"User"," • ",_.email||_.username]})
]}),
e.jsx("span",{className:"text-[10px] font-semibold text-emerald-300",children:"Add"})
]},_.id))})
]}),
e.jsx("p",{className:"text-xs text-slate-500",children:s?"Leave recipients empty to post to yourself, or add one or more users for bulk delivery.":"This notification will be created for your own account."}),
e.jsxs("div",{className:"flex gap-2",children:[
e.jsx("button",{onClick:()=>u(!1),className:"rounded-xl border border-white/[0.09] px-4 py-2 text-sm text-slate-400 hover:text-white transition",children:"Cancel"}),
e.jsxs("button",{onClick:ot,disabled:r,className:"flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2 text-sm font-bold text-white hover:bg-emerald-400 transition disabled:opacity-50",children:[r?e.jsx(S,{size:13,className:"animate-spin"}):e.jsx(P,{size:13}),"Create Notification"]})
]})
]}),
n?e.jsx("div",{className:"flex justify-center py-16",children:e.jsx(S,{size:24,className:"animate-spin text-emerald-400"})}):ft.length===0?e.jsxs("div",{className:"flex flex-col items-center justify-center py-20 text-center",children:[
e.jsx(B,{size:40,className:"mb-3 text-slate-700"}),
e.jsx("p",{className:"text-sm font-semibold text-slate-400",children:"No notifications visible"}),
e.jsxs("p",{className:"mt-1 text-xs text-slate-600",children:["Filter: ",M(et)," • ",d==="all"?"Admin audit scope":"My inbox"]})
]}):e.jsx("div",{className:"space-y-2",children:ft.map(_=>{
const G=J[_.notification_type]??J.System,$=I[_.priority]??I.Informational;
return e.jsxs("div",{className:`group rounded-2xl border px-4 py-3.5 transition-all ${_.is_read?"border-white/[0.07] bg-white/[0.02] opacity-80":"border-white/[0.09] bg-white/[0.03]"}`,children:[
e.jsxs("div",{className:"flex items-start gap-3",children:[
e.jsx("div",{className:`mt-0.5 rounded-xl border px-2.5 py-2 text-[10px] font-bold ${G}`,children:_.notification_type}),
e.jsxs("div",{className:"min-w-0 flex-1",children:[
e.jsxs("div",{className:"flex flex-wrap items-start justify-between gap-2",children:[
e.jsxs("div",{className:"min-w-0",children:[
e.jsx("p",{className:`truncate text-sm font-semibold ${_.is_read?"text-slate-300":"text-white"}`,children:_.title}),
e.jsx("p",{className:"mt-0.5 whitespace-pre-wrap text-xs leading-relaxed text-slate-400",children:_.message})
]}),
e.jsxs("div",{className:"flex items-center gap-2",children:[
e.jsx("span",{className:`rounded-full border px-2 py-0.5 text-[10px] font-bold ${$}`,children:_.priority}),
!_.is_read&&e.jsx("button",{onClick:()=>pt(_.id),className:"rounded-lg border border-emerald-500/30 px-2 py-1 text-[10px] font-semibold text-emerald-300 opacity-0 transition group-hover:opacity-100 hover:bg-emerald-500/10",children:"Mark Read"}),
e.jsx("button",{onClick:()=>mt(_.id),className:"flex h-7 w-7 items-center justify-center rounded-lg border border-red-500/20 opacity-0 transition group-hover:opacity-100 hover:bg-red-500/10",children:e.jsx(D,{size:11,className:"text-red-400"})})
]})
]}),
e.jsxs("div",{className:"mt-2 flex flex-wrap items-center gap-2 text-[10px] text-slate-500",children:[
e.jsxs("span",{className:"flex items-center gap-1",children:[e.jsx(L,{size:10}),K(_.sent_at)]}),
_.recipient_name&&d==="all"&&e.jsxs("span",{children:["Recipient: ",_.recipient_name]}),
_.created_by_name&&d==="all"&&e.jsxs("span",{children:["Created by: ",_.created_by_name]}),
_.action_url&&e.jsx("a",{href:_.action_url,className:"text-cyan-300 hover:text-cyan-200",children:"Open action"})
]})
]})
]}),
!_.is_read&&e.jsx("div",{className:"mt-2 h-1.5 w-1.5 rounded-full bg-emerald-400"})
]},_.id)
})})
]})
}

export{se as default};
