import{r,b as o,j as e}from"./index-D7ltaYVC.js";import{F as N}from"./file-text-BMGjGS-3.js";import{C as h}from"./circle-check-CyyLgyEu.js";import{C as b}from"./circle-alert-QkR7CaoT.js";import{C as v}from"./clock-Cjp0BcMI.js";import"./createLucideIcon-BLtbVmUp.js";
const c={background:"rgba(255,255,255,0.025)",border:"1px solid rgba(255,255,255,0.07)"};
const fmt=s=>s!=null?"KES "+Number(s).toLocaleString():"KES 0";
const badge=s=>({PAID:"bg-emerald-500/15 text-emerald-400",PARTIAL:"bg-amber-500/15 text-amber-400",PENDING:"bg-sky-500/15 text-sky-400",OVERDUE:"bg-rose-500/15 text-rose-400"})[s?.toUpperCase()]??"bg-slate-500/15 text-slate-400";
function E(){
  const[sum,setSum]=r.useState({});
  const[inv,setInv]=r.useState([]);
  const[pay,setPay]=r.useState([]);
  const[loading,setLoading]=r.useState(!0);
  const[tab,setTab]=r.useState("invoices");
  const[mpOpen,setMpOpen]=r.useState(!1);
  const[mpPhone,setMpPhone]=r.useState("");
  const[mpAmt,setMpAmt]=r.useState("");
  const[mpStatus,setMpStatus]=r.useState(null);
  const[mpErr,setMpErr]=r.useState(null);
  const[mpBusy,setMpBusy]=r.useState(!1);
  const[mpCheckout,setMpCheckout]=r.useState(null);
  const[mpPolling,setMpPolling]=r.useState(!1);
  const[mpResult,setMpResult]=r.useState(null);
  const pollRef=r.useRef(null);
  r.useEffect(()=>{
    Promise.all([
      o.get("/parent-portal/finance/summary/"),
      o.get("/parent-portal/finance/invoices/"),
      o.get("/parent-portal/finance/payments/")
    ]).then(([a,b2,c2])=>{
      setSum(a.data??{});
      setInv(Array.isArray(b2.data)?b2.data:[]);
      setPay(Array.isArray(c2.data)?c2.data:[]);
    }).catch(()=>{}).finally(()=>setLoading(!1));
  },[]);
  r.useEffect(()=>{
    return()=>{if(pollRef.current)clearInterval(pollRef.current);};
  },[]);
  const bal=Number(sum.outstanding_balance??0);
  const openMpesa=()=>{
    setMpOpen(!0);
    setMpPhone("");
    setMpAmt(bal>0?String(Math.ceil(bal)):"");
    setMpErr(null);
    setMpStatus(null);
    setMpCheckout(null);
    setMpResult(null);
  };
  const closeMpesa=()=>{
    if(pollRef.current)clearInterval(pollRef.current);
    setMpOpen(!1);
    setMpBusy(!1);
    setMpPolling(!1);
  };
  const startPoll=checkout=>{
    setMpPolling(!0);
    setMpStatus("Waiting for M-Pesa PIN prompt on your phone…");
    let tries=0;
    pollRef.current=setInterval(async()=>{
      tries++;
      try{
        const res=await o.get("/parent-portal/finance/mpesa-status/?checkout_request_id="+checkout);
        const d=res.data;
        if(d.result_code==="0"||d.status==="completed"){
          clearInterval(pollRef.current);
          setMpPolling(!1);
          setMpResult("success");
          setMpStatus("Payment successful! Your account has been updated.");
          o.get("/parent-portal/finance/summary/").then(r2=>setSum(r2.data??{}));
          o.get("/parent-portal/finance/payments/").then(r2=>setPay(Array.isArray(r2.data)?r2.data:[]));
        } else if(d.result_code&&d.result_code!=="0"){
          clearInterval(pollRef.current);
          setMpPolling(!1);
          setMpResult("failed");
          setMpStatus("Payment failed: "+(d.result_desc||"Transaction not completed."));
        }
      }catch(err){}
      if(tries>=20){
        clearInterval(pollRef.current);
        setMpPolling(!1);
        setMpStatus("M-Pesa confirmation is taking longer than expected. Check your payments list shortly.");
      }
    },4000);
  };
  const initiateMpesa=async()=>{
    if(!mpPhone.trim()||!mpAmt.trim())return;
    setMpBusy(!0);
    setMpErr(null);
    setMpStatus(null);
    try{
      const res=await o.post("/parent-portal/finance/pay/",{payment_method:"mpesa",phone:mpPhone.trim(),amount:mpAmt.trim()});
      const d=res.data;
      const chk=d.checkout_request_id||d.CheckoutRequestID;
      if(chk){
        setMpCheckout(chk);
        startPoll(chk);
      } else {
        setMpStatus("STK push sent. Please check your phone for the M-Pesa prompt.");
      }
    }catch(err){
      const msg=err?.response?.data?.error||err?.response?.data?.detail||"Failed to initiate M-Pesa payment.";
      setMpErr(msg);
    }finally{
      setMpBusy(!1);
    }
  };
  return e.jsxs("div",{className:"space-y-6",children:[
    e.jsxs("div",{children:[
      e.jsx("p",{className:"text-[10px] font-bold uppercase tracking-widest text-amber-400 mb-1",children:"FINANCE"}),
      e.jsx("h1",{className:"text-2xl font-display font-bold text-white",children:"Financial Information"}),
      e.jsx("p",{className:"text-slate-500 text-sm mt-1",children:"Fees, invoices and payment history for your child"})
    ]}),
    e.jsx("div",{className:"grid grid-cols-1 gap-3 sm:grid-cols-3",children:[
      {label:"Total Billed",value:fmt(sum.total_billed),icon:N,color:"#38bdf8",bg:"rgba(14,165,233,0.1)"},
      {label:"Total Paid",value:fmt(sum.total_paid),icon:h,color:"#10b981",bg:"rgba(16,185,129,0.1)"},
      {label:"Outstanding Balance",value:fmt(bal),icon:bal>0?b:h,color:bal>0?"#f59e0b":"#10b981",bg:bal>0?"rgba(245,158,11,0.1)":"rgba(16,185,129,0.1)"}
    ].map(t=>e.jsxs("div",{className:"rounded-2xl p-5 flex items-center gap-4",style:c,children:[
      e.jsx("div",{className:"w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0",style:{background:t.bg},children:e.jsx(t.icon,{size:18,style:{color:t.color}})}),
      e.jsxs("div",{children:[
        e.jsx("p",{className:"text-[10px] text-slate-500 uppercase tracking-wider",children:t.label}),
        e.jsx("p",{className:"text-lg font-bold font-mono",style:{color:t.color},children:t.value})
      ]})
    ]},t.label))}),
    bal>0&&e.jsxs("div",{className:"rounded-2xl px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-4",style:{background:"rgba(245,158,11,0.06)",border:"1px solid rgba(245,158,11,0.22)"},children:[
      e.jsxs("div",{className:"flex items-start gap-3 flex-1",children:[
        e.jsx(b,{size:18,className:"text-amber-400 flex-shrink-0 mt-0.5"}),
        e.jsxs("p",{className:"text-sm text-amber-200",children:["Your child has an outstanding balance of ",e.jsx("strong",{children:fmt(bal)}),". Settle via M-Pesa STK Push directly from this portal."]})
      ]}),
      e.jsxs("button",{
        onClick:openMpesa,
        className:"flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold transition-all flex-shrink-0",
        style:{background:"linear-gradient(135deg,#1a7a4a,#16a34a)",color:"#fff",border:"1px solid rgba(16,163,74,0.5)"},
        children:[
          e.jsx("span",{style:{fontSize:16},children:"💳"}),
          "Pay via M-Pesa"
        ]
      })
    ]}),
    mpOpen&&e.jsx("div",{className:"fixed inset-0 z-50 flex items-center justify-center p-4",style:{background:"rgba(0,0,0,0.75)"},children:
      e.jsxs("div",{className:"rounded-2xl p-6 w-full max-w-md space-y-5",style:{background:"#0d1a13",border:"1px solid rgba(16,185,129,0.25)"},children:[
        e.jsxs("div",{className:"flex items-center justify-between",children:[
          e.jsxs("div",{children:[
            e.jsx("h2",{className:"text-lg font-bold text-white",children:"M-Pesa STK Push"}),
            e.jsx("p",{className:"text-xs text-slate-400 mt-0.5",children:"You will receive a PIN prompt on your phone"})
          ]}),
          e.jsx("button",{onClick:closeMpesa,className:"text-slate-500 hover:text-slate-300 text-xl font-bold",children:"×"})
        ]}),
        !mpCheckout&&!mpResult&&e.jsxs("div",{className:"space-y-3",children:[
          e.jsxs("div",{children:[
            e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Safaricom Phone Number"}),
            e.jsx("input",{
              type:"tel",
              value:mpPhone,
              onChange:ev=>setMpPhone(ev.target.value),
              placeholder:"e.g. 0712345678",
              className:"w-full rounded-xl border border-white/[0.09] bg-slate-900 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-emerald-500/50"
            })
          ]}),
          e.jsxs("div",{children:[
            e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Amount (KES)"}),
            e.jsx("input",{
              type:"number",
              value:mpAmt,
              onChange:ev=>setMpAmt(ev.target.value),
              min:1,
              className:"w-full rounded-xl border border-white/[0.09] bg-slate-900 px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500/50"
            })
          ]}),
          mpErr&&e.jsx("div",{className:"rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-2.5 text-xs text-rose-300",children:mpErr}),
          e.jsxs("button",{
            onClick:initiateMpesa,
            disabled:mpBusy||!mpPhone.trim()||!mpAmt.trim(),
            className:"w-full rounded-xl py-3 text-sm font-bold transition-all disabled:opacity-50",
            style:{background:"linear-gradient(135deg,#1a7a4a,#16a34a)",color:"#fff"},
            children:mpBusy?"Sending STK Push…":"Send M-Pesa Request"
          })
        ]}),
        mpStatus&&e.jsxs("div",{className:"rounded-xl px-4 py-3 text-sm flex items-start gap-3",style:{background:mpResult==="success"?"rgba(16,185,129,0.1)":mpResult==="failed"?"rgba(239,68,68,0.1)":"rgba(14,165,233,0.1)",border:mpResult==="success"?"1px solid rgba(16,185,129,0.3)":mpResult==="failed"?"1px solid rgba(239,68,68,0.3)":"1px solid rgba(14,165,233,0.3)"},children:[
          mpPolling&&e.jsx("span",{className:"animate-spin",children:"⟳"}),
          e.jsx("span",{className:mpResult==="success"?"text-emerald-300":mpResult==="failed"?"text-red-300":"text-sky-300",children:mpStatus})
        ]}),
        mpResult&&e.jsx("button",{onClick:closeMpesa,className:"w-full rounded-xl py-2.5 text-sm font-semibold text-slate-300 border border-white/[0.09] hover:bg-white/[0.04] transition",children:"Close"})
      ]})
    }),
    e.jsx("div",{className:"flex gap-2",children:["invoices","payments"].map(t=>e.jsx("button",{onClick:()=>setTab(t),className:"rounded-xl px-4 py-2 text-sm font-medium transition-all "+(tab===t?"bg-amber-500/20 text-amber-300":"text-slate-500 hover:text-slate-300"),children:t==="invoices"?"Invoices ("+inv.length+")":"Payments ("+pay.length+")"},t))}),
    loading?e.jsx("div",{className:"py-12 text-center text-slate-500 text-sm",children:"Loading financial records…"}):tab==="invoices"
      ?e.jsx("div",{className:"space-y-3",children:inv.length===0?e.jsx("div",{className:"rounded-2xl p-10 text-center text-sm text-slate-500",style:c,children:"No invoices found."}):inv.map(t=>e.jsx("div",{className:"rounded-2xl p-5",style:c,children:
        e.jsxs("div",{className:"flex items-start justify-between gap-4",children:[
          e.jsxs("div",{className:"flex-1 min-w-0",children:[
            e.jsxs("div",{className:"flex items-center gap-2 mb-1",children:[
              e.jsx("span",{className:"px-2 py-0.5 rounded-full text-[10px] font-bold "+badge(t.status),children:t.status}),
              e.jsx("span",{className:"text-xs text-slate-500 font-mono",children:t.invoice_number})
            ]}),
            e.jsx("p",{className:"font-semibold text-slate-200 truncate",children:t.description||"School Fees"}),
            e.jsxs("div",{className:"flex flex-wrap gap-3 mt-1.5 text-xs text-slate-500",children:[
              t.term&&e.jsxs("span",{children:["Term: ",t.term]}),
              t.academic_year&&e.jsxs("span",{children:["Year: ",t.academic_year]}),
              t.due_date&&e.jsxs("span",{className:"flex items-center gap-1",children:[e.jsx(v,{size:10}),"Due: ",new Date(t.due_date).toLocaleDateString()]})
            ]})
          ]}),
          e.jsxs("div",{className:"text-right flex-shrink-0",children:[
            e.jsx("p",{className:"text-sm font-bold text-white",children:fmt(t.amount)}),
            t.amount_paid>0&&e.jsxs("p",{className:"text-xs text-emerald-400",children:["Paid: ",fmt(t.amount_paid)]}),
            Number(t.balance)>0&&e.jsxs("p",{className:"text-xs text-amber-400",children:["Due: ",fmt(t.balance)]})
          ]})
        ]})
      },t.id))}
      :e.jsx("div",{className:"rounded-2xl overflow-hidden",style:c,children:pay.length===0
        ?e.jsx("p",{className:"py-10 text-center text-sm text-slate-500",children:"No payments recorded."})
        :e.jsxs("table",{className:"w-full text-sm",children:[
          e.jsx("thead",{children:e.jsx("tr",{className:"border-b border-white/[0.07]",children:["Date","Amount","Method","Reference"].map(t=>e.jsx("th",{className:"px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500",children:t},t))})}),
          e.jsx("tbody",{className:"divide-y divide-white/[0.04]",children:pay.map((t,idx)=>e.jsxs("tr",{className:"hover:bg-white/[0.015] "+(idx%2!==0?"bg-white/[0.008]":""),children:[
            e.jsx("td",{className:"px-4 py-3 text-slate-400",children:t.payment_date?new Date(t.payment_date).toLocaleDateString():"—"}),
            e.jsx("td",{className:"px-4 py-3 font-semibold text-emerald-300",children:fmt(t.amount)}),
            e.jsx("td",{className:"px-4 py-3 text-slate-400 capitalize",children:t.payment_method?.replace(/_/g," ")??"—"}),
            e.jsx("td",{className:"px-4 py-3 text-slate-500 font-mono text-xs",children:t.reference_number||t.transaction_reference||"—"})
          ]},t.id))})
        ]})
      })
  ]});
}
export{E as default};
