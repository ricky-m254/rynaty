import{r as s,j as e,b as i}from"./index-D7ltaYVC.js";
import{P as ae}from"./PageHero-Ct90nOAG.js";

const DAY_OPTIONS=[
  {id:1,label:"Monday"},
  {id:2,label:"Tuesday"},
  {id:3,label:"Wednesday"},
  {id:4,label:"Thursday"},
  {id:5,label:"Friday"}
];

const PERIODS=[1,2,3,4,5,6,7,8];
const DEFAULT_START="08:00";
const DEFAULT_END="08:40";

function normalize(value){
  return Array.isArray(value)?value:value?.results??[];
}

function buildBlankForm(scope,selectedId,day=1,period=1){
  return {
    day_of_week:String(day),
    period_number:String(period),
    start_time:DEFAULT_START,
    end_time:DEFAULT_END,
    teacher:scope==="teacher"&&selectedId?String(selectedId):"",
    subject:"",
    school_class:scope==="class"&&selectedId?String(selectedId):"",
    room:"",
    term:"",
    notes:"",
    is_active:true
  };
}

function readTime(value,fallback){
  return String(value||fallback||DEFAULT_START).slice(0,5);
}

function ie(){
  const[grid,setGrid]=s.useState({});
  const[loadingMeta,setLoadingMeta]=s.useState(true);
  const[loadingGrid,setLoadingGrid]=s.useState(false);
  const[error,setError]=s.useState(null);
  const[notice,setNotice]=s.useState(null);
  const[scope,setScope]=s.useState("class");
  const[selectedId,setSelectedId]=s.useState("");
  const[classes,setClasses]=s.useState([]);
  const[teachers,setTeachers]=s.useState([]);
  const[subjects,setSubjects]=s.useState([]);
  const[terms,setTerms]=s.useState([]);
  const[modalOpen,setModalOpen]=s.useState(false);
  const[editingId,setEditingId]=s.useState(null);
  const[busy,setBusy]=s.useState(false);
  const[form,setForm]=s.useState(()=>buildBlankForm("class",""));

  const selectedItem=scope==="class"
    ?classes.find(row=>String(row.id)===String(selectedId))
    :teachers.find(row=>String(row.id)===String(selectedId));
  const selectedLabel=selectedItem
    ?scope==="class"
      ?`${selectedItem.display_name??selectedItem.name}${selectedItem.stream?` - ${selectedItem.stream}`:""}`
      :selectedItem.full_name
    :`Select a ${scope}`;

  const loadMetadata=async()=>{
    setLoadingMeta(true);
    setError(null);
    try{
      const[classRes,employeeRes,subjectRes,termRes]=await Promise.all([
        i.get("/academics/classes/"),
        i.get("/hr/employees/"),
        i.get("/academics/subjects/"),
        i.get("/academics/terms/")
      ]);
      setClasses(normalize(classRes.data));
      setTeachers(
        normalize(employeeRes.data)
          .map(row=>({
            id:row.user,
            full_name:`${row.first_name} ${row.last_name}`.trim()||row.employee_id
          }))
          .filter(row=>row.id)
      );
      setSubjects(normalize(subjectRes.data));
      setTerms(normalize(termRes.data));
    }catch{
      setError("Failed to load timetable metadata.");
    }finally{
      setLoadingMeta(false);
    }
  };

  const loadGrid=async(nextScope=scope,nextSelectedId=selectedId)=>{
    if(!nextSelectedId){
      setGrid({});
      return;
    }
    setLoadingGrid(true);
    setError(null);
    setNotice(null);
    try{
      const params=nextScope==="class"
        ?{class_id:nextSelectedId}
        :{teacher_id:nextSelectedId};
      const response=await i.get("/timetable/grid/",{params});
      setGrid(response.data||{});
    }catch{
      setError("Failed to load timetable grid.");
    }finally{
      setLoadingGrid(false);
    }
  };

  s.useEffect(()=>{
    loadMetadata();
  },[]);

  s.useEffect(()=>{
    if(loadingMeta)return;
    if(selectedId)return;
    const pool=scope==="class"?classes:teachers;
    if(pool.length>0&&pool[0]?.id!=null){
      setSelectedId(String(pool[0].id));
    }
  },[loadingMeta,scope,classes,teachers,selectedId]);

  s.useEffect(()=>{
    if(selectedId){
      loadGrid(scope,selectedId);
    }else if(!loadingMeta){
      setGrid({});
    }
  },[scope,selectedId]);

  const openCreate=(day=1,period=1)=>{
    setEditingId(null);
    setForm(buildBlankForm(scope,selectedId,day,period));
    setError(null);
    setNotice(null);
    setModalOpen(true);
  };

  const openEdit=slot=>{
    setEditingId(slot.id);
    setForm({
      day_of_week:String(slot.day_of_week??1),
      period_number:String(slot.period_number??1),
      start_time:readTime(slot.start_time,DEFAULT_START),
      end_time:readTime(slot.end_time,DEFAULT_END),
      teacher:slot.teacher?String(slot.teacher):"",
      subject:slot.subject?String(slot.subject):"",
      school_class:slot.school_class?String(slot.school_class):"",
      room:slot.room||"",
      term:slot.term?String(slot.term):"",
      notes:slot.notes||"",
      is_active:slot.is_active!==false
    });
    setError(null);
    setNotice(null);
    setModalOpen(true);
  };

  const changeScope=nextScope=>{
    setScope(nextScope);
    setSelectedId("");
    setError(null);
    setNotice(null);
  };

  const saveSlot=async()=>{
    const isEditing=editingId!==null;
    if(!form.subject||!form.school_class||!form.start_time||!form.end_time){
      setError("Class, subject, start time, and end time are required.");
      return;
    }

    setBusy(true);
    setError(null);
    setNotice(null);
    try{
      const payload={
        day_of_week:Number(form.day_of_week),
        period_number:Number(form.period_number),
        start_time:form.start_time,
        end_time:form.end_time,
        teacher:form.teacher?Number(form.teacher):null,
        subject:Number(form.subject),
        school_class:Number(form.school_class),
        room:(form.room||"").trim(),
        term:form.term?Number(form.term):null,
        notes:form.notes||"",
        is_active:!!form.is_active
      };

      if(isEditing){
        await i.patch(`/timetable/slots/${editingId}/`,payload);
      }else{
        await i.post("/timetable/slots/",payload);
      }

      setModalOpen(false);
      setEditingId(null);
      await loadGrid(scope,selectedId);
      setNotice(isEditing?"Slot updated.":"Slot added.");
    }catch{
      setError(isEditing?"Unable to update slot.":"Unable to add slot.");
    }finally{
      setBusy(false);
    }
  };

  const deleteSlot=async slotId=>{
    if(!confirm("Delete this timetable slot?"))return;
    setError(null);
    setNotice(null);
    try{
      await i.delete(`/timetable/slots/${slotId}/`);
      await loadGrid(scope,selectedId);
      setNotice("Slot deleted.");
    }catch{
      setError("Unable to delete slot.");
    }
  };

  const cellSlot=(day,period)=>(grid[day]??[]).find(slot=>Number(slot.period_number)===Number(period));

  return e.jsxs("div",{className:"space-y-6",children:[
    e.jsx(ae,{badge:"TIMETABLE",badgeColor:"violet",title:"Timetable Grid",subtitle:"Visual weekly timetable for all classes",icon:"📅"}),
    e.jsxs("header",{className:"rounded-2xl glass-panel p-6 flex flex-col md:flex-row md:items-center justify-between gap-4",children:[
      e.jsxs("div",{children:[
        e.jsx("h1",{className:"text-xl font-display font-semibold",children:"Weekly Timetable"}),
        e.jsx("p",{className:"mt-1 text-sm text-slate-400",children:"Manage, edit, and print lesson schedules."}),
        e.jsx("p",{className:"mt-1 text-xs text-slate-500",children:selectedLabel})
      ]}),
      e.jsxs("div",{className:"flex gap-2",children:[
        e.jsx("button",{onClick:()=>window.print(),className:"rounded-xl border border-white/[0.09] px-4 py-2 text-sm font-medium text-slate-200 hover:border-white/20 transition",children:"Print"}),
        e.jsx("button",{onClick:()=>openCreate(),className:"rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-emerald-400 transition",children:"+ Add Slot"})
      ]})
    ]}),
    notice&&e.jsx("div",{className:"rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-200",children:notice}),
    error&&e.jsx("div",{className:"rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200",children:error}),
    e.jsxs("section",{className:"rounded-2xl glass-panel p-6",children:[
      e.jsxs("div",{className:"flex flex-wrap gap-4 mb-6",children:[
        e.jsxs("div",{className:"flex rounded-xl bg-slate-950 p-1",children:[
          e.jsx("button",{onClick:()=>changeScope("class"),className:`px-4 py-1.5 text-xs font-medium rounded-lg transition ${scope==="class"?"bg-slate-800 text-white":"text-slate-400 hover:text-slate-200"}`,children:"By Class"}),
          e.jsx("button",{onClick:()=>changeScope("teacher"),className:`px-4 py-1.5 text-xs font-medium rounded-lg transition ${scope==="teacher"?"bg-slate-800 text-white":"text-slate-400 hover:text-slate-200"}`,children:"By Teacher"})
        ]}),
        e.jsxs("select",{value:selectedId,onChange:ev=>setSelectedId(ev.target.value),className:"bg-slate-950 border border-white/[0.07] rounded-xl px-4 py-2 text-sm text-slate-200 min-w-[220px]",children:[
          e.jsx("option",{value:"",children:["Select ",scope==="class"?"Class":"Teacher","..."]}),
          scope==="class"
            ?classes.map(row=>e.jsx("option",{value:row.id,children:row.display_name??row.name},row.id))
            :teachers.map(row=>e.jsx("option",{value:row.id,children:row.full_name},row.id))
        ]})
      ]}),
      loadingMeta&&e.jsx("div",{className:"py-20 text-center",children:e.jsx("p",{className:"text-slate-400 animate-pulse",children:"Loading timetable data..."})}),
      !loadingMeta&&selectedId&&loadingGrid&&e.jsx("div",{className:"mb-4 rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-2 text-xs text-slate-400",children:"Refreshing timetable..."}),
      !loadingMeta&&selectedId
        ?e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"min-w-full border-collapse",children:[
          e.jsx("thead",{children:e.jsxs("tr",{children:[
            e.jsx("th",{className:"p-2 border border-white/[0.07] bg-slate-950/50 text-xs text-slate-500 font-medium uppercase tracking-wider w-20",children:"Period"}),
            DAY_OPTIONS.map(day=>e.jsx("th",{className:"p-3 border border-white/[0.07] bg-slate-950/50 text-sm font-semibold text-slate-200",children:day.label},day.id))
          ]})}),
          e.jsx("tbody",{children:PERIODS.map(period=>e.jsxs("tr",{children:[
            e.jsx("td",{className:"p-2 border border-white/[0.07] text-center bg-slate-950/30",children:e.jsx("span",{className:"text-lg font-bold text-slate-700",children:period})}),
            DAY_OPTIONS.map(day=>{
              const slot=cellSlot(day.id,period);
              return e.jsx("td",{className:"p-1 border border-white/[0.07] h-28 w-40 vertical-top",children:slot
                ?e.jsxs("div",{onClick:()=>openEdit(slot),title:"Click to edit slot",className:`h-full w-full rounded-lg p-2 border ${slot.subject?`bg-blue-500/20 border-blue-500/50 text-blue-200`:"bg-slate-800"} flex flex-col justify-between relative group cursor-pointer hover:brightness-110 transition`,children:[
                  e.jsxs("div",{children:[
                    e.jsx("div",{className:"text-xs font-bold truncate",children:slot.subject_name||"Untitled Slot"}),
                    e.jsx("div",{className:"text-[10px] opacity-80 truncate",children:scope==="class"?slot.teacher_name||"No teacher":slot.class_name||"No class"}),
                    e.jsx("div",{className:"text-[10px] mt-1 flex items-center gap-1 opacity-70",children:e.jsxs("span",{children:["Room: ",slot.room||"No Room"]})}),
                    slot.notes&&e.jsx("div",{className:"text-[10px] mt-1 truncate opacity-70",children:slot.notes})
                  ]}),
                  e.jsxs("div",{className:"text-[10px] font-mono mt-auto pt-1 border-t border-white/10",children:[
                    String(slot.start_time||"").substring(0,5),
                    " - ",
                    String(slot.end_time||"").substring(0,5)
                  ]}),
                  e.jsx("button",{onClick:ev=>{ev.stopPropagation();deleteSlot(slot.id);},className:"absolute top-1 left-1 opacity-0 group-hover:opacity-100 text-[9px] text-rose-400 hover:text-rose-200 transition px-1",children:"✕"}),
                  slot.coverage_status==="Uncovered"&&e.jsxs("div",{className:"absolute -top-1 -right-1 flex h-4 w-4",children:[
                    e.jsx("span",{className:"animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"}),
                    e.jsx("span",{className:"relative inline-flex rounded-full h-4 w-4 bg-rose-500 text-[8px] items-center justify-center font-bold text-white",children:"!"})
                  ]})
                ]})
                :e.jsx("div",{className:"h-full w-full rounded-lg bg-[#0d1421]/20 border border-transparent group hover:border-white/[0.07] transition flex items-center justify-center",children:e.jsx("button",{onClick:()=>openCreate(day.id,period),className:"opacity-0 group-hover:opacity-100 text-slate-400 text-lg leading-none transition hover:text-emerald-400",children:"+"})})},`${day.id}-${period}`)})
          ]},period))})})
        :e.jsx("div",{className:"py-20 text-center border-2 border-dashed border-white/[0.07] rounded-2xl",children:e.jsxs("p",{className:"text-slate-500",children:["Select a ",scope," to view the timetable."]})})
    ]}),
    modalOpen&&e.jsx("div",{className:"fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 backdrop-blur-sm",children:e.jsxs("div",{className:"w-full max-w-md rounded-2xl border border-white/[0.07] bg-slate-950 p-6 space-y-3",children:[
      e.jsx("h2",{className:"text-lg font-display font-semibold",children:editingId?"Edit Timetable Slot":"Add Timetable Slot"}),
      e.jsxs("div",{className:"grid grid-cols-2 gap-3",children:[
        e.jsxs("div",{children:[
          e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Day"}),
          e.jsx("select",{value:form.day_of_week,onChange:ev=>setForm(current=>({...current,day_of_week:ev.target.value})),className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm",children:DAY_OPTIONS.map(day=>e.jsx("option",{value:day.id,children:day.label},day.id))})
        ]}),
        e.jsxs("div",{children:[
          e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Period"}),
          e.jsx("select",{value:form.period_number,onChange:ev=>setForm(current=>({...current,period_number:ev.target.value})),className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm",children:PERIODS.map(period=>e.jsxs("option",{value:period,children:["Period ",period]},period))})
        ]})
      ]}),
      e.jsxs("div",{className:"grid grid-cols-2 gap-3",children:[
        e.jsxs("div",{children:[
          e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Start time"}),
          e.jsx("input",{type:"time",value:form.start_time,onChange:ev=>setForm(current=>({...current,start_time:ev.target.value})),className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm"})
        ]}),
        e.jsxs("div",{children:[
          e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"End time"}),
          e.jsx("input",{type:"time",value:form.end_time,onChange:ev=>setForm(current=>({...current,end_time:ev.target.value})),className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm"})
        ]})
      ]}),
      e.jsxs("div",{children:[
        e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Class *"}),
        e.jsxs("select",{value:form.school_class,onChange:ev=>setForm(current=>({...current,school_class:ev.target.value})),className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm",children:[
          e.jsx("option",{value:"",children:"Select class"}),
          classes.map(row=>e.jsx("option",{value:row.id,children:row.display_name??row.name},row.id))
        ]})
      ]}),
      e.jsxs("div",{children:[
        e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Subject *"}),
        e.jsxs("select",{value:form.subject,onChange:ev=>setForm(current=>({...current,subject:ev.target.value})),className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm",children:[
          e.jsx("option",{value:"",children:"Select subject"}),
          subjects.map(row=>e.jsx("option",{value:row.id,children:row.name},row.id))
        ]})
      ]}),
      e.jsxs("div",{children:[
        e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Teacher"}),
        e.jsxs("select",{value:form.teacher,onChange:ev=>setForm(current=>({...current,teacher:ev.target.value})),className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm",children:[
          e.jsx("option",{value:"",children:"No teacher assigned"}),
          teachers.map(row=>e.jsx("option",{value:row.id,children:row.full_name},row.id))
        ]})
      ]}),
      e.jsxs("div",{className:"grid grid-cols-2 gap-3",children:[
        e.jsxs("div",{children:[
          e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Room"}),
          e.jsx("input",{value:form.room,onChange:ev=>setForm(current=>({...current,room:ev.target.value})),placeholder:"Room / Lab",className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm"})
        ]}),
        e.jsxs("div",{children:[
          e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Term"}),
          e.jsxs("select",{value:form.term,onChange:ev=>setForm(current=>({...current,term:ev.target.value})),className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm",children:[
            e.jsx("option",{value:"",children:"Any term"}),
            terms.map(row=>e.jsx("option",{value:row.id,children:row.name},row.id))
          ]})
        ]})
      ]}),
      e.jsxs("div",{children:[
        e.jsx("label",{className:"text-xs text-slate-400 mb-1 block",children:"Notes"}),
        e.jsx("textarea",{value:form.notes,onChange:ev=>setForm(current=>({...current,notes:ev.target.value})),rows:3,className:"w-full rounded-lg border border-white/[0.09] bg-[#0d1421] px-3 py-2 text-sm text-slate-200 resize-none"})
      ]}),
      e.jsxs("label",{className:"flex items-center gap-2 text-sm text-slate-300",children:[
        e.jsx("input",{type:"checkbox",checked:form.is_active,onChange:ev=>setForm(current=>({...current,is_active:ev.target.checked})),className:"rounded"}),
        "Active slot"
      ]}),
      e.jsxs("div",{className:"flex gap-3 pt-1",children:[
        e.jsx("button",{onClick:saveSlot,disabled:busy,className:"flex-1 rounded-xl bg-emerald-500/20 border border-emerald-500/40 px-4 py-2 text-sm font-semibold text-emerald-200 disabled:opacity-50",children:busy?"Saving...":editingId?"Update Slot":"Add Slot"}),
        e.jsx("button",{onClick:()=>{setModalOpen(false);setEditingId(null);},className:"flex-1 rounded-xl border border-white/[0.09] px-4 py-2 text-sm text-slate-300",children:"Cancel"})
      ]})
    ]})})
  ]});
}

export{ie as default};
