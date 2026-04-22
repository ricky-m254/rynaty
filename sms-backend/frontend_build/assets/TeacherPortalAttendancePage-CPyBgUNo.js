import{r,j as t,b}from"./index-D7ltaYVC.js";
import{P as z}from"./PageHero-Ct90nOAG.js";
import{S as D}from"./save-DVPXWNqk.js";
import{C as U}from"./circle-alert-QkR7CaoT.js";
import{C as A}from"./circle-check-big-gKc9ia_Q.js";
import{U as B}from"./user-Bmzaf-lk.js";
import{C as F}from"./clock-Cjp0BcMI.js";
import{C as G}from"./circle-x-lBvWwbCI.js";
import"./createLucideIcon-BLtbVmUp.js";

const y={
  background:"rgba(255,255,255,0.025)",
  border:"1px solid rgba(255,255,255,0.07)"
};

const S={
  P:{label:"Present",color:"#10b981",bg:"rgba(16,185,129,0.15)",icon:A},
  A:{label:"Absent",color:"#ef4444",bg:"rgba(239,68,68,0.15)",icon:G},
  L:{label:"Late",color:"#f59e0b",bg:"rgba(245,158,11,0.15)",icon:F},
  E:{label:"Excused",color:"#0ea5e9",bg:"rgba(14,165,233,0.15)",icon:B}
};

function C(o){
  return Array.isArray(o)?o:o?.results??[];
}

function W(){
  const[o,w]=r.useState([]);
  const[n,P]=r.useState([]);
  const[i,u]=r.useState("");
  const[c,E]=r.useState(new Date().toISOString().split("T")[0]);
  const[d,x]=r.useState({});
  const[$,p]=r.useState({});
  const[g,h]=r.useState({});
  const[f,j]=r.useState(!0);
  const[v,N]=r.useState(!1);
  const[m,L]=r.useState(null);
  const[R,O]=r.useState(null);

  const selectedCount=Object.values(g).filter(Boolean).length;
  const visibleStudentIds=selectedCount>0?n.filter(s=>g[s.id]).map(s=>s.id):n.map(s=>s.id);
  const selectedClass=n.find(s=>String(s.id)===i);
  const selectedClassLabel=selectedClass?`${selectedClass.name}${selectedClass.stream?` - ${selectedClass.stream}`:""}`:"Select a class";

  const loadRoster=async(classId=i,dateValue=c)=>{
    j(!0);
    L(null);
    O(null);
    try{
      const params={};
      if(classId)params.class_id=classId;
      if(dateValue)params.date=dateValue;
      const response=await b.get("/teacher-portal/attendance/",{params});
      const data=response.data||{};
      const classes=C(data.classes);
      const roster=C(data.students);
      w(classes);
      const nextClassId=String(data.selected_class_id??classId??classes[0]?.id??"");
      u(nextClassId);
      const nextDate=data.date??dateValue;
      E(nextDate);
      n(roster);
      const statuses={};
      const notes={};
      roster.forEach(student=>{
        statuses[student.id]=student.status&&S[student.status]?student.status:"P";
        notes[student.id]=student.notes??"";
      });
      x(statuses);
      p(notes);
      h({});
    }catch{
      L("Unable to load attendance roster.");
    }finally{
      j(!1);
    }
  };

  r.useEffect(()=>{
    loadRoster();
  },[]);

  const setStudentStatus=(studentId,statusCode)=>{
    x(current=>({...current,[studentId]:statusCode}));
    R(null);
  };

  const toggleStudentSelection=studentId=>{
    h(current=>({...current,[studentId]:!current[studentId]}));
    R(null);
  };

  const selectAll=()=>{
    const next={};
    n.forEach(student=>{
      next[student.id]=!0;
    });
    h(next);
    R(null);
  };

  const clearSelection=()=>{
    h({});
    R(null);
  };

  const applyBulkStatus=statusCode=>{
    if(!visibleStudentIds.length)return;
    x(current=>{
      const next={...current};
      visibleStudentIds.forEach(studentId=>{
        next[studentId]=statusCode;
      });
      return next;
    });
    R(null);
  };

  const saveAttendance=async()=>{
    if(!i){
      L("Select a class before saving attendance.");
      return;
    }
    if(!n.length){
      L("No students are loaded for this class.");
      return;
    }
    v(!0);
    L(null);
    R(null);
    const records=n.map(student=>({
      student_id:student.id,
      status:d[student.id]??"P",
      notes:$[student.id]??student.notes??""
    }));
    try{
      await b.post("/teacher-portal/attendance/",{
        class_id:Number(i),
        date:c,
        records
      });
      R(`Attendance saved for ${n.length} students on ${c}.`);
      h({});
    }catch{
      L("Failed to save attendance. Some records may already exist for this date.");
    }finally{
      v(!1);
    }
  };

  const counts={
    P:Object.values(d).filter(e=>e==="P").length,
    A:Object.values(d).filter(e=>e==="A").length,
    L:Object.values(d).filter(e=>e==="L").length,
    E:Object.values(d).filter(e=>e==="E").length
  };

  return t.jsxs("div",{className:"space-y-6",children:[
    t.jsx(z,{badge:"TEACHER",badgeColor:"purple",title:"Attendance Management",subtitle:"Record class attendance quickly and accurately",icon:"✅"}),
    t.jsx("div",{className:"rounded-2xl p-5",style:y,children:t.jsxs("div",{className:"grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_auto]",children:[
      t.jsxs("div",{children:[
        t.jsx("label",{className:"block text-xs font-semibold text-slate-400 mb-1.5",children:"Select Class"}),
        t.jsx("select",{value:i,onChange:e=>{const next=e.target.value;u(next);loadRoster(next,c);},className:"w-full rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2.5 text-sm text-white outline-none",children:[
          t.jsx("option",{value:"",children:"Select class"}),
          o.map(e=>t.jsx("option",{value:e.id,children:[e.name,e.stream?` - ${e.stream}`:""]},e.id))
        ]})
      ]}),
      t.jsxs("div",{children:[
        t.jsx("label",{className:"block text-xs font-semibold text-slate-400 mb-1.5",children:"Date"}),
        t.jsx("input",{type:"date",value:c,onChange:e=>{const next=e.target.value;E(next);loadRoster(i,next);},className:"w-full rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2.5 text-sm text-white outline-none"})
      ]}),
      t.jsx("div",{className:"flex items-end",children:t.jsxs("button",{onClick:saveAttendance,disabled:v||f||!n.length,className:"w-full flex items-center justify-center gap-2 rounded-xl bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-slate-900 hover:bg-emerald-400 disabled:opacity-50 transition",children:[
        t.jsx(D,{size:14}),
        v?"Saving…":"Save Attendance"
      ]})})
    ]})}),
    t.jsx("div",{className:"grid grid-cols-2 gap-3 md:grid-cols-4",children:[
      {label:"Present",value:counts.P,color:"#10b981",bg:"rgba(16,185,129,0.1)"},
      {label:"Absent",value:counts.A,color:"#ef4444",bg:"rgba(239,68,68,0.1)"},
      {label:"Late",value:counts.L,color:"#f59e0b",bg:"rgba(245,158,11,0.1)"},
      {label:"Excused",value:counts.E,color:"#0ea5e9",bg:"rgba(14,165,233,0.1)"}
    ].map(e=>t.jsxs("div",{className:"rounded-2xl p-4 text-center",style:{background:e.bg,border:`1px solid ${e.color}25`},children:[
      t.jsx("p",{className:"text-2xl font-bold text-white",children:e.value}),
      t.jsx("p",{className:"text-xs text-slate-400",children:e.label})
    ]},e.label))}),
    m&&t.jsxs("div",{className:"flex items-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200",children:[
      t.jsx(U,{size:14}),
      m
    ]}),
    R&&t.jsxs("div",{className:"flex items-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200",children:[
      t.jsx(A,{size:14}),
      R
    ]}),
    n.length>0&&t.jsxs("div",{className:"rounded-2xl p-4",style:y,children:[
      t.jsxs("div",{className:"flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between",children:[
        t.jsxs("div",{children:[
          t.jsx("p",{className:"text-sm font-bold text-white",children:selectedClassLabel}),
          t.jsx("p",{className:"text-xs text-slate-500",children:selectedCount>0?`${selectedCount} selected. Bulk actions apply to selected rows.`:"No rows selected. Bulk actions apply to the whole class."})
        ]}),
        t.jsxs("div",{className:"flex flex-wrap items-center gap-2",children:[
          t.jsx("span",{className:"rounded-full border border-white/[0.08] px-3 py-1 text-[11px] font-semibold text-slate-400",children:selectedCount>0?`${selectedCount} selected`:"All rows active"}),
          t.jsx("button",{onClick:selectAll,disabled:f||!n.length,className:"rounded-lg border border-white/[0.09] px-3 py-1.5 text-xs font-semibold text-slate-200 hover:border-white/20 disabled:opacity-50 transition",children:"Select all"}),
          t.jsx("button",{onClick:clearSelection,disabled:f||!n.length,className:"rounded-lg border border-white/[0.09] px-3 py-1.5 text-xs font-semibold text-slate-200 hover:border-white/20 disabled:opacity-50 transition",children:"Unselect all"})
        ]})
      ]}),
      t.jsxs("div",{className:"mt-4 flex flex-wrap items-center gap-2",children:[
        t.jsx("p",{className:"text-xs text-slate-500",children:"Bulk status:"}),
        Object.entries(S).map(([code,meta])=>t.jsx("button",{onClick:()=>applyBulkStatus(code),disabled:f||!n.length,className:"rounded-lg px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50",style:{background:meta.bg,color:meta.color,border:`1px solid ${meta.color}30`},children:meta.label},code))
      ]})
    ]}),
    t.jsxs("div",{className:"rounded-2xl overflow-hidden",style:y,children:[
      t.jsx("div",{className:"px-5 py-4 border-b",style:{borderColor:"rgba(255,255,255,0.07)"},children:t.jsx("p",{className:"text-sm font-bold text-white",children:selectedClassLabel})}),
      f?t.jsx("p",{className:"px-5 py-8 text-center text-slate-500",children:"Loading attendance roster…"}):n.length===0?t.jsx("p",{className:"px-5 py-8 text-center text-slate-500",children:"No students found for this class."}):t.jsx("div",{className:"divide-y",style:{divideColor:"rgba(255,255,255,0.04)"},children:n.map((student,index)=>{
        const currentStatus=d[student.id]??"P";
        const isSelected=!!g[student.id];
        return t.jsxs("div",{className:"px-5 py-3.5 flex items-start gap-4 transition",style:{borderBottom:"1px solid rgba(255,255,255,0.04)",background:isSelected?"rgba(16,185,129,0.04)":"transparent"},children:[
          t.jsx("label",{className:"pt-1",children:t.jsx("input",{type:"checkbox",checked:isSelected,onChange:()=>toggleStudentSelection(student.id),className:"h-4 w-4 rounded border-white/20 bg-slate-950 text-emerald-500 focus:ring-emerald-500/40"})}),
          t.jsx("span",{className:"text-xs text-slate-600 w-6 tabular-nums shrink-0 pt-1",children:index+1}),
          t.jsxs("div",{className:"flex-1 min-w-0",children:[
            t.jsx("p",{className:"text-sm font-semibold text-white truncate",children:student.full_name}),
            t.jsx("p",{className:"text-xs text-slate-500",children:student.admission_number})
          ]}),
          t.jsx("div",{className:"flex items-center gap-1.5 flex-wrap justify-end",children:Object.entries(S).map(([code,meta])=>t.jsx("button",{onClick:()=>setStudentStatus(student.id,code),className:"rounded-lg px-2.5 py-1.5 text-xs font-bold transition-all",style:{background:currentStatus===code?meta.bg:"rgba(255,255,255,0.03)",color:currentStatus===code?meta.color:"#475569",border:currentStatus===code?`1px solid ${meta.color}40`:"1px solid rgba(255,255,255,0.06)",transform:currentStatus===code?"scale(1.05)":"scale(1)"},title:meta.label,children:code},code))})
        ]},student.id)
      })})
    ]})
  ]});
}

export{W as default};
