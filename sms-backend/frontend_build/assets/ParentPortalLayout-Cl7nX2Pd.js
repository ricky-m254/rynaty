import{a as c,u as x,r as m,j as e,N as p,O as Ol,b as ax}from"./index-D7ltaYVC.js";import{L as Out}from"./log-out-BT69D1Gr.js";import{M as Mnu}from"./menu-BnFzJFjV.js";import{X as Cls}from"./x-CEi3D4aT.js";import{L as Dsh}from"./layout-dashboard-rx0a-u-8.js";import{G as Grp}from"./graduation-cap-BhcfZJDw.js";import{A as Att}from"./activity-BUhxSvMT.js";import{D as Fin}from"./dollar-sign-BsYV7G3i.js";import{B as Bel}from"./bell-Biv8Yc7n.js";import{C as Cal}from"./calendar-ZTeAo9TL.js";import{C as Cli}from"./clipboard-list-e-NjQdb4.js";import{H as Hrt}from"./heart-Caszhu_e.js";import{B as Bus}from"./bus-2ixR5PZy.js";import{B as Bk}from"./book-open-DkSh7gF5.js";import"./createLucideIcon-BLtbVmUp.js";
const NAV=[{label:"Dashboard",to:"/modules/parent-portal/dashboard",icon:Dsh,exact:!0},{label:"Academics",to:"/modules/parent-portal/academics",icon:Grp},{label:"Attendance",to:"/modules/parent-portal/attendance",icon:Att},{label:"Finance",to:"/modules/parent-portal/finance",icon:Fin},{label:"Communication",to:"/modules/parent-portal/communication",icon:Bel},{label:"Schedule",to:"/modules/parent-portal/schedule",icon:Cal},{label:"Assignments",to:"/modules/parent-portal/assignments",icon:Cli},{label:"Health & Medical",to:"/modules/parent-portal/health",icon:Hrt},{label:"Transport",to:"/modules/parent-portal/transport",icon:Bus},{label:"Library & Profile",to:"/modules/parent-portal/library-profile",icon:Bk}];
function Layout(){
  const{username:un,logout:lo}=c(t=>({username:t.username,logout:t.logout}));
  const nav=x();
  const[open,setOpen]=m.useState(!1);
  const[kids,setKids]=m.useState([]);
  const[sel,setSel]=m.useState(null);
  const[cid,setCid]=m.useState(()=>sessionStorage.getItem("pp_child_id")||null);
  const doLogout=()=>{lo();nav("/login");};
  m.useEffect(()=>{
    ax.get("/parent-portal/dashboard/").then(r=>{
      const d=r.data;
      if(d&&Array.isArray(d.children)){
        setKids(d.children);
        if(d.selected_child){
          const stored=sessionStorage.getItem("pp_child_id");
          const found=stored?d.children.find(k=>String(k.id)===String(stored)):null;
          setSel(found||d.selected_child);
          if(!found){setCid(String(d.selected_child.id));sessionStorage.setItem("pp_child_id",String(d.selected_child.id));}
        }
      }
    }).catch(()=>{});
  },[]);
  const switchChild=id=>{
    const found=kids.find(k=>String(k.id)===String(id));
    setCid(String(id));
    setSel(found||null);
    sessionStorage.setItem("pp_child_id",String(id));
  };
  const lk=base=>cid?base+"?child_id="+cid:base;
  const initial=((un||"P")[0]||"P").toUpperCase();
  return e.jsxs("div",{className:"min-h-screen flex flex-col md:flex-row",style:{background:"#070b12"},children:[
    e.jsxs("aside",{className:"fixed inset-0 z-40 md:static md:block md:w-[220px] md:flex-shrink-0 transition-transform "+(open?"translate-x-0":"-translate-x-full md:translate-x-0"),style:{background:"linear-gradient(180deg,#0a1a12 0%,#07110d 100%)",borderRight:"1px solid rgba(255,255,255,0.07)"},children:[
      e.jsxs("div",{className:"flex items-center justify-between px-4 py-4 border-b border-white/[0.07]",children:[
        e.jsxs("div",{className:"flex items-center gap-2.5",children:[
          e.jsx("div",{className:"h-8 w-8 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center flex-shrink-0",children:e.jsx("span",{className:"text-xs font-bold text-emerald-300",children:initial})}),
          e.jsxs("div",{className:"min-w-0",children:[
            e.jsx("p",{className:"text-xs font-semibold text-slate-200 truncate",children:un}),
            e.jsx("p",{className:"text-[10px] text-emerald-400",children:"Parent Portal"})
          ]})
        ]}),
        e.jsx("button",{className:"md:hidden text-slate-400",onClick:()=>setOpen(!1),children:e.jsx(Cls,{size:20})})
      ]}),
      kids.length>1
        ?e.jsxs("div",{className:"px-3 py-2 border-b border-white/[0.05]",children:[
            e.jsx("p",{className:"text-[10px] text-slate-500 uppercase tracking-wider mb-1",children:"Viewing child"}),
            e.jsx("select",{
              className:"w-full rounded-lg border border-white/[0.09] bg-slate-900/80 px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/40",
              value:cid??"",
              onChange:ev=>switchChild(ev.target.value),
              children:kids.map(k=>e.jsx("option",{value:k.id,children:k.name+(k.admission_number?" ("+k.admission_number+")":"")},k.id))
            })
          ]}
        )
        :sel?e.jsxs("div",{className:"px-4 py-2.5 border-b border-white/[0.05]",children:[
            e.jsx("p",{className:"text-[10px] text-slate-500 uppercase tracking-wider",children:"Child"}),
            e.jsx("p",{className:"text-xs font-semibold text-slate-200 mt-0.5 truncate",children:sel.name}),
            sel.admission_number&&e.jsx("p",{className:"text-[10px] text-emerald-400",children:sel.admission_number})
          ]}
        ):null,
      e.jsx("nav",{className:"flex-1 p-3 space-y-0.5",children:NAV.map(item=>e.jsxs(p,{to:lk(item.to),end:item.exact,onClick:()=>setOpen(!1),className:({isActive:a})=>"flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all "+(a?"bg-emerald-500/15 text-emerald-200 font-semibold":"text-slate-400 hover:bg-white/[0.035] hover:text-slate-200"),children:[e.jsx(item.icon,{size:15,className:"flex-shrink-0"}),item.label]},item.to))}),
      e.jsx("div",{className:"p-3 border-t border-white/[0.07]",children:
        e.jsxs("button",{onClick:doLogout,className:"flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 hover:bg-red-500/10 hover:text-red-400 transition-all",children:[e.jsx(Out,{size:15}),"Sign out"]})
      })
    ]}),
    open&&e.jsx("div",{className:"fixed inset-0 z-30 bg-black/50 md:hidden",onClick:()=>setOpen(!1)}),
    e.jsxs("div",{className:"flex-1 flex flex-col min-h-screen min-w-0",children:[
      e.jsxs("header",{className:"md:hidden flex items-center justify-between px-4 py-3 border-b border-white/[0.07]",style:{background:"#0a1a12"},children:[
        e.jsx("button",{className:"text-slate-400",onClick:()=>setOpen(!0),children:e.jsx(Mnu,{size:20})}),
        e.jsx("span",{className:"text-sm font-semibold text-emerald-400",children:"Parent Portal"}),
        e.jsx("div",{className:"w-5"})
      ]}),
      e.jsx("main",{className:"flex-1 p-4 sm:p-6 lg:p-8",children:e.jsx(Ol,{})}),
      e.jsx("footer",{className:"px-6 py-3 border-t border-white/[0.05]",children:
        e.jsxs("p",{className:"text-[10px] text-slate-700 text-center",children:["© ",new Date().getFullYear()," RynatySpace Technologies Ltd. · RynatySchool SmartCampus"]})
      })
    ]})
  ]});
}
export{Layout as default};
