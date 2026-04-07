import{r as s,j as e,b as l}from"./index-D7ltaYVC.js";import{C as Y}from"./ConfirmDialog-WF6S4jMq.js";import{P as Z}from"./PageHero-Ct90nOAG.js";
function p(r){return Array.isArray(r)?r:r.results??[]}
function ae(){
  const[schemes,setSchemes]=s.useState([]);
  const[subjects,setSubjects]=s.useState([]);
  const[classes,setClasses]=s.useState([]);
  const[terms,setTerms]=s.useState([]);
  const[templates,setTemplates]=s.useState([]);
  const[loading,setLoading]=s.useState(!0);
  const[err,setErr]=s.useState(null);
  const[ok,setOk]=s.useState(null);
  const[tab,setTab]=s.useState("schemes");
  const[newTitle,setNewTitle]=s.useState("");
  const[newSubj,setNewSubj]=s.useState("");
  const[newClass,setNewClass]=s.useState("");
  const[newTerm,setNewTerm]=s.useState("");
  const[newObj,setNewObj]=s.useState("");
  const[creating,setCreating]=s.useState(!1);
  const[expanded,setExpanded]=s.useState(null);
  const[topicText,setTopicText]=s.useState("");
  const[topicWk,setTopicWk]=s.useState("1");
  const[addingTopic,setAddingTopic]=s.useState(!1);
  const[delScheme,setDelScheme]=s.useState(null);
  const[deleting,setDeleting]=s.useState(!1);
  const[delErr,setDelErr]=s.useState(null);
  const[editScheme,setEditScheme]=s.useState(null);
  const[editTitle,setEditTitle]=s.useState("");
  const[editObj,setEditObj]=s.useState("");
  const[editBusy,setEditBusy]=s.useState(!1);
  const[tplExpanded,setTplExpanded]=s.useState(null);
  const[tplApplyId,setTplApplyId]=s.useState(null);
  const[tplClass,setTplClass]=s.useState("");
  const[tplTerm,setTplTerm]=s.useState("");
  const[tplApplying,setTplApplying]=s.useState(!1);
  const[newTplName,setNewTplName]=s.useState("");
  const[newTplDesc,setNewTplDesc]=s.useState("");
  const[newTplSubj,setNewTplSubj]=s.useState("");
  const[newTplTitle,setNewTplTitle]=s.useState("");
  const[creatingTpl,setCreatingTpl]=s.useState(!1);
  const[delTpl,setDelTpl]=s.useState(null);
  const[deletingTpl,setDeletingTpl]=s.useState(!1);
  const[delTplErr,setDelTplErr]=s.useState(null);
  const reload=async()=>{
    setLoading(!0);
    try{
      const[a,b2,c2,d,t]=await Promise.all([
        l.get("/curriculum/schemes/"),
        l.get("/academics/subjects/"),
        l.get("/academics/classes/"),
        l.get("/academics/terms/"),
        l.get("/curriculum/schemes/templates/")
      ]);
      setSchemes(p(a.data));
      setSubjects(p(b2.data));
      setClasses(p(c2.data));
      setTerms(p(d.data));
      setTemplates(p(t.data));
    }catch{setErr("Unable to load data.");}
    finally{setLoading(!1);}
  };
  s.useEffect(()=>{reload();},[]);
  const createScheme=async()=>{
    if(!newTitle.trim()||!newSubj||!newClass||!newTerm)return;
    setCreating(!0);setErr(null);setOk(null);
    try{
      await l.post("/curriculum/schemes/",{title:newTitle.trim(),subject:Number(newSubj),school_class:Number(newClass),term:Number(newTerm),objectives:newObj});
      setNewTitle("");setNewObj("");setOk("Scheme created.");await reload();
    }catch{setErr("Unable to create scheme.");}
    finally{setCreating(!1);}
  };
  const addTopic=async id=>{
    if(!topicText.trim())return;
    setAddingTopic(!0);
    try{
      await l.post("/curriculum/topics/",{scheme:id,week_number:Number(topicWk),topic:topicText.trim()});
      setTopicText("");setTopicWk("1");await reload();
    }catch{setErr("Unable to add topic.");}
    finally{setAddingTopic(!1);}
  };
  const deleteTopic=async tid=>{
    try{await l.delete("/curriculum/topics/"+tid+"/");await reload();}catch{setErr("Unable to delete topic.");}
  };
  const markCovered=async(tid,covered)=>{
    try{await l.patch("/curriculum/topics/"+tid+"/",{is_covered:!covered});await reload();}catch{setErr("Unable to update topic.");}
  };
  const deleteScheme=async()=>{
    if(!delScheme)return;
    setDeleting(!0);setDelErr(null);
    try{await l.delete("/curriculum/schemes/"+delScheme.id+"/");setDelScheme(null);await reload();}
    catch{setDelErr("Unable to delete scheme.");}
    finally{setDeleting(!1);}
  };
  const openEdit=sc=>{setEditScheme(sc);setEditTitle(sc.title);setEditObj(sc.objectives||"");};
  const saveEdit=async()=>{
    if(!editScheme)return;
    setEditBusy(!0);setErr(null);
    try{
      await l.patch("/curriculum/schemes/"+editScheme.id+"/",{title:editTitle.trim(),objectives:editObj});
      setEditScheme(null);setOk("Scheme updated.");await reload();
    }catch{setErr("Unable to update scheme.");}
    finally{setEditBusy(!1);}
  };
  const applyTemplate=async()=>{
    if(!tplApplyId||!tplClass||!tplTerm)return;
    setTplApplying(!0);setErr(null);
    try{
      await l.post("/curriculum/schemes/"+tplApplyId+"/use-template/",{school_class:Number(tplClass),term:Number(tplTerm)});
      setTplApplyId(null);setTplClass("");setTplTerm("");
      setOk("Template applied! New scheme created — check the Schemes tab.");
      setTab("schemes");await reload();
    }catch(ex){setErr(ex?.response?.data?.error||"Unable to apply template.");}
    finally{setTplApplying(!1);}
  };
  const createTemplate=async()=>{
    if(!newTplName.trim()||!newTplSubj||!newTplTitle.trim())return;
    setCreatingTpl(!0);setErr(null);
    try{
      await l.post("/curriculum/schemes/",{title:newTplTitle.trim(),subject:Number(newTplSubj),is_template:!0,template_name:newTplName.trim(),template_description:newTplDesc.trim()});
      setNewTplName("");setNewTplDesc("");setNewTplSubj("");setNewTplTitle("");
      setOk("Template created.");await reload();
    }catch{setErr("Unable to create template.");}
    finally{setCreatingTpl(!1);}
  };
  const deleteTemplate=async()=>{
    if(!delTpl)return;
    setDeletingTpl(!0);setDelTplErr(null);
    try{await l.delete("/curriculum/schemes/"+delTpl.id+"/");setDelTpl(null);await reload();}
    catch{setDelTplErr("Unable to delete template.");}
    finally{setDeletingTpl(!1);}
  };
  const gp={background:"rgba(255,255,255,0.025)",border:"1px solid rgba(255,255,255,0.07)"};
  const inp="rounded-xl border border-white/[0.09] bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-emerald-500/40";
  const btn="rounded-xl px-4 py-2 text-sm font-semibold transition-all disabled:opacity-50";
  return e.jsxs("div",{className:"space-y-6",children:[
    e.jsx(Z,{badge:"ACADEMICS",badgeColor:"blue",title:"Schemes of Work",subtitle:"Create, manage and apply curriculum templates across classes.",icon:"\uD83D\uDCD6"}),
    err&&e.jsx("div",{className:"rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200",children:err}),
    ok&&e.jsx("div",{className:"rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200",children:ok}),
    e.jsx("div",{className:"flex gap-2 flex-wrap",children:["schemes","templates"].map(t=>e.jsx("button",{
      key:t,onClick:()=>setTab(t),
      className:"rounded-xl px-5 py-2 text-sm font-semibold transition-all "+(tab===t?"bg-emerald-500/20 text-emerald-300":"text-slate-500 hover:text-slate-300 border border-white/[0.06]"),
      children:t==="schemes"?"\uD83D\uDCCB Schemes ("+(loading?"…":schemes.length)+")":"\uD83D\uDDC2 Templates ("+(loading?"…":templates.length)+")"
    }))}),
    tab==="schemes"&&e.jsxs("div",{className:"space-y-5",children:[
      e.jsxs("div",{className:"rounded-2xl p-6",style:gp,children:[
        e.jsx("h2",{className:"mb-4 text-sm font-semibold text-slate-200",children:"New Scheme of Work"}),
        e.jsxs("div",{className:"grid gap-3 sm:grid-cols-2 lg:grid-cols-4",children:[
          e.jsx("input",{value:newTitle,onChange:t=>setNewTitle(t.target.value),placeholder:"Title *",className:inp+" lg:col-span-2"}),
          e.jsxs("select",{value:newSubj,onChange:t=>setNewSubj(t.target.value),className:inp,children:[e.jsx("option",{value:"",children:"Subject *"}),subjects.map(t=>e.jsx("option",{value:t.id,children:t.name},t.id))]}),
          e.jsxs("select",{value:newClass,onChange:t=>setNewClass(t.target.value),className:inp,children:[e.jsx("option",{value:"",children:"Class *"}),classes.map(t=>e.jsx("option",{value:t.id,children:t.name},t.id))]}),
          e.jsxs("select",{value:newTerm,onChange:t=>setNewTerm(t.target.value),className:inp,children:[e.jsx("option",{value:"",children:"Term *"}),terms.map(t=>e.jsx("option",{value:t.id,children:t.name},t.id))]}),
          e.jsx("textarea",{value:newObj,onChange:t=>setNewObj(t.target.value),placeholder:"Objectives (optional)",rows:2,className:inp+" sm:col-span-2 lg:col-span-3"})
        ]}),
        e.jsx("button",{onClick:createScheme,disabled:creating||!newTitle.trim()||!newSubj||!newClass||!newTerm,className:btn+" mt-4 bg-emerald-500 text-slate-900",children:creating?"Saving…":"Create Scheme"})
      ]}),
      loading?e.jsx("p",{className:"text-sm text-slate-400 px-2",children:"Loading…"}):
      schemes.length===0?e.jsx("p",{className:"text-sm text-slate-500 px-2",children:"No schemes yet. Create one above or apply a template from the Templates tab."}):
      e.jsx("div",{className:"space-y-3",children:schemes.map(sc=>e.jsxs("div",{className:"rounded-2xl overflow-hidden",style:gp,children:[
        e.jsxs("div",{className:"flex items-start justify-between gap-4 p-4",children:[
          e.jsxs("div",{className:"flex-1 min-w-0",children:[
            e.jsx("p",{className:"font-semibold text-slate-100 truncate",children:sc.title}),
            e.jsxs("p",{className:"mt-0.5 text-xs text-slate-400",children:[sc.subject_name," \xB7 ",sc.school_class_name," \xB7 ",sc.term_name]}),
            e.jsxs("p",{className:"mt-1 text-xs text-slate-500",children:[(sc.topics?.length??0)," topics"]}),
            sc.objectives&&e.jsx("p",{className:"mt-1 text-xs text-slate-600 italic truncate",children:sc.objectives})
          ]}),
          e.jsxs("div",{className:"flex shrink-0 gap-2 text-xs flex-wrap justify-end",children:[
            e.jsx("button",{onClick:()=>setExpanded(expanded===sc.id?null:sc.id),className:"font-semibold text-sky-400 hover:text-sky-300",children:expanded===sc.id?"\u25B2 Topics":"\u25BC Topics"}),
            e.jsx("button",{onClick:()=>openEdit(sc),className:"font-semibold text-amber-400 hover:text-amber-300",children:"Edit"}),
            e.jsx("button",{onClick:()=>setDelScheme(sc),className:"font-semibold text-rose-400 hover:text-rose-300",children:"Delete"})
          ]})
        ]}),
        editScheme?.id===sc.id&&e.jsxs("div",{className:"border-t border-white/[0.07] p-4 space-y-3",children:[
          e.jsx("p",{className:"text-xs font-semibold text-amber-400",children:"Edit Scheme"}),
          e.jsx("input",{value:editTitle,onChange:t=>setEditTitle(t.target.value),placeholder:"Title",className:inp+" w-full"}),
          e.jsx("textarea",{value:editObj,onChange:t=>setEditObj(t.target.value),placeholder:"Objectives",rows:2,className:inp+" w-full"}),
          e.jsxs("div",{className:"flex gap-2",children:[
            e.jsx("button",{onClick:saveEdit,disabled:editBusy||!editTitle.trim(),className:btn+" bg-amber-500/20 text-amber-200",children:editBusy?"Saving…":"Save Changes"}),
            e.jsx("button",{onClick:()=>setEditScheme(null),className:btn+" text-slate-500 border border-white/[0.07]",children:"Cancel"})
          ]})
        ]}),
        expanded===sc.id&&e.jsxs("div",{className:"border-t border-white/[0.07] p-4 space-y-3",children:[
          e.jsxs("div",{className:"flex gap-2",children:[
            e.jsx("input",{type:"number",value:topicWk,onChange:t=>setTopicWk(t.target.value),placeholder:"Wk",min:1,className:inp+" w-16"}),
            e.jsx("input",{value:topicText,onChange:t=>setTopicText(t.target.value),placeholder:"Topic name",className:inp+" flex-1"}),
            e.jsx("button",{onClick:()=>addTopic(sc.id),disabled:addingTopic||!topicText.trim(),className:btn+" bg-emerald-500/20 text-emerald-200 text-xs px-3",children:"Add"})
          ]}),
          e.jsx("div",{className:"space-y-1.5",children:
            (sc.topics??[]).length===0?e.jsx("p",{className:"text-xs text-slate-500",children:"No topics yet."}):
            (sc.topics??[]).sort((a,b2)=>a.week_number-b2.week_number).map(t=>e.jsxs("div",{className:"flex items-center gap-3 rounded-lg px-3 py-2 text-xs "+(t.is_covered?"bg-emerald-950/40":"bg-slate-950/60"),children:[
              e.jsx("span",{className:"w-12 shrink-0 text-slate-500",children:"Wk "+t.week_number}),
              e.jsx("span",{className:"flex-1 "+(t.is_covered?"line-through text-slate-500":"text-slate-300"),children:t.topic}),
              e.jsx("button",{onClick:()=>markCovered(t.id,t.is_covered),className:"text-[10px] px-2 py-0.5 rounded-full transition-all "+(t.is_covered?"bg-emerald-500/20 text-emerald-400":"bg-slate-800 text-slate-500 hover:bg-emerald-500/10 hover:text-emerald-400"),children:t.is_covered?"\u2713 Covered":"Mark done"}),
              e.jsx("button",{onClick:()=>deleteTopic(t.id),className:"text-rose-500 hover:text-rose-400 font-bold",title:"Remove",children:"\u2715"})
            ]},t.id))
          })
        ]})
      ]},sc.id))})
    ]}),
    tab==="templates"&&e.jsxs("div",{className:"space-y-5",children:[
      e.jsxs("div",{className:"rounded-2xl p-6",style:gp,children:[
        e.jsx("h2",{className:"mb-1 text-sm font-semibold text-slate-200",children:"Create Reusable Template"}),
        e.jsx("p",{className:"text-xs text-slate-500 mb-4",children:"Templates are generic schemes (no class/term) you can reuse across classes each term."}),
        e.jsxs("div",{className:"grid gap-3 sm:grid-cols-2",children:[
          e.jsx("input",{value:newTplName,onChange:t=>setNewTplName(t.target.value),placeholder:"Template name * (e.g. CBC Maths Gr 6 \u2014 12 Weeks)",className:inp+" sm:col-span-2"}),
          e.jsx("textarea",{value:newTplDesc,onChange:t=>setNewTplDesc(t.target.value),placeholder:"Description (learning outcomes, approach\u2026)",rows:2,className:inp+" sm:col-span-2"}),
          e.jsx("input",{value:newTplTitle,onChange:t=>setNewTplTitle(t.target.value),placeholder:"Scheme title *",className:inp}),
          e.jsxs("select",{value:newTplSubj,onChange:t=>setNewTplSubj(t.target.value),className:inp,children:[e.jsx("option",{value:"",children:"Subject *"}),subjects.map(t=>e.jsx("option",{value:t.id,children:t.name},t.id))]})
        ]}),
        e.jsx("button",{onClick:createTemplate,disabled:creatingTpl||!newTplName.trim()||!newTplTitle.trim()||!newTplSubj,className:btn+" mt-4 bg-emerald-500 text-slate-900",children:creatingTpl?"Creating…":"Create Template"})
      ]}),
      loading?e.jsx("p",{className:"text-sm text-slate-400 px-2",children:"Loading templates…"}):
      templates.length===0?e.jsx("p",{className:"text-sm text-slate-500 px-2",children:"No templates yet. Create one above or use the 3 seeded CBC starter templates (Mathematics, English, Science)."}):
      e.jsx("div",{className:"space-y-3",children:templates.map(tpl=>e.jsxs("div",{className:"rounded-2xl overflow-hidden",style:gp,children:[
        e.jsxs("div",{className:"p-4",children:[
          e.jsxs("div",{className:"flex items-start justify-between gap-3",children:[
            e.jsxs("div",{className:"flex-1 min-w-0",children:[
              e.jsxs("div",{className:"flex items-center gap-2 mb-1.5",children:[
                e.jsx("span",{className:"px-2 py-0.5 rounded-full text-[10px] font-bold bg-violet-500/15 text-violet-300",children:"TEMPLATE"}),
                e.jsx("span",{className:"text-xs text-slate-400",children:tpl.subject_name})
              ]}),
              e.jsx("p",{className:"font-semibold text-slate-100",children:tpl.template_name||tpl.title}),
              tpl.template_description&&e.jsx("p",{className:"text-xs text-slate-500 mt-0.5",children:tpl.template_description}),
              e.jsxs("p",{className:"text-xs text-slate-600 mt-1",children:[(tpl.topics?.length??0)," topics seeded"]})
            ]}),
            e.jsxs("div",{className:"flex gap-2 shrink-0 text-xs",children:[
              e.jsx("button",{onClick:()=>setTplExpanded(tplExpanded===tpl.id?null:tpl.id),className:"font-semibold text-sky-400 hover:text-sky-300",children:tplExpanded===tpl.id?"\u25B2 Topics":"\u25BC Topics"}),
              e.jsx("button",{onClick:()=>{setTplApplyId(tpl.id);setTplClass("");setTplTerm("");},className:"font-bold text-emerald-400 hover:text-emerald-300",children:"\u25B6 Use Template"}),
              e.jsx("button",{onClick:()=>setDelTpl(tpl),className:"font-semibold text-rose-400 hover:text-rose-300",children:"Delete"})
            ]})
          ]}),
          tplApplyId===tpl.id&&e.jsxs("div",{className:"mt-4 rounded-xl p-4 space-y-3",style:{background:"rgba(16,185,129,0.06)",border:"1px solid rgba(16,185,129,0.2)"},children:[
            e.jsx("p",{className:"text-xs font-semibold text-emerald-400",children:"Select class and term to apply this template"}),
            e.jsxs("div",{className:"flex gap-2 flex-wrap",children:[
              e.jsxs("select",{value:tplClass,onChange:t=>setTplClass(t.target.value),className:inp+" flex-1 min-w-[140px]",children:[e.jsx("option",{value:"",children:"Select Class *"}),classes.map(t=>e.jsx("option",{value:t.id,children:t.name},t.id))]}),
              e.jsxs("select",{value:tplTerm,onChange:t=>setTplTerm(t.target.value),className:inp+" flex-1 min-w-[140px]",children:[e.jsx("option",{value:"",children:"Select Term *"}),terms.map(t=>e.jsx("option",{value:t.id,children:t.name},t.id))]})
            ]}),
            e.jsxs("div",{className:"flex gap-2",children:[
              e.jsx("button",{onClick:applyTemplate,disabled:tplApplying||!tplClass||!tplTerm,className:btn+" bg-emerald-500 text-slate-900",children:tplApplying?"Applying…":"Apply Template \u2192"}),
              e.jsx("button",{onClick:()=>setTplApplyId(null),className:btn+" text-slate-500 border border-white/[0.07]",children:"Cancel"})
            ]})
          ]}),
          tplExpanded===tpl.id&&e.jsxs("div",{className:"mt-3 space-y-1.5",children:[
            (tpl.topics??[]).length===0?e.jsx("p",{className:"text-xs text-slate-500",children:"No topics seeded in this template yet."}):
            (tpl.topics??[]).sort((a,b2)=>a.week_number-b2.week_number).map(t=>e.jsxs("div",{className:"flex items-center gap-3 rounded-lg bg-slate-950/60 px-3 py-2 text-xs",children:[
              e.jsx("span",{className:"w-12 shrink-0 text-slate-500",children:"Wk "+t.week_number}),
              e.jsx("span",{className:"flex-1 text-slate-300",children:t.topic})
            ]},t.id))
          ]})
        ])
      ]},tpl.id))})
    ]}),
    e.jsx(Y,{open:!!delScheme,title:"Delete Scheme",description:"Delete \""+( delScheme?.title||"")+"\u201d? All its topics will also be removed.",confirmLabel:"Delete",isProcessing:deleting,error:delErr,onConfirm:deleteScheme,onCancel:()=>setDelScheme(null)}),
    e.jsx(Y,{open:!!delTpl,title:"Delete Template",description:"Delete template \""+( delTpl?.template_name||delTpl?.title||"")+"\u201d?",confirmLabel:"Delete",isProcessing:deletingTpl,error:delTplErr,onConfirm:deleteTemplate,onCancel:()=>setDelTpl(null)})
  ]});
}
export{ae as default};
