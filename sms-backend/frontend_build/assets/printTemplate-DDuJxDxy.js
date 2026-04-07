const i=t=>{const o=t.tenant?.name??t.tenant?.schema??"Tenant",e=t.tenant?.address,r=t.tenant?.phone,a=t.tenant?.logoUrl?`<img class="logo" src="${t.tenant.logoUrl}" alt="Logo" />`:'<div class="logo-placeholder">Logo</div>',n=[e?`<p class="muted">${e}</p>`:"",r?`<p class="muted">${r}</p>`:""].join("");return`
    <div class="header">
      <div class="header-left">
        ${a}
        <div>
          <p class="badge">${t.badge??"Report"}</p>
          <h1>${t.title}</h1>
          ${t.subtitle?`<p class="muted">${t.subtitle}</p>`:""}
          ${t.generatedAt?`<p class="muted">Generated ${t.generatedAt}</p>`:""}
        </div>
      </div>
      <div class="header-right">
        <p class="meta-title">${o}</p>
        ${n}
        ${t.metaRight?`<p class="muted">${t.metaRight}</p>`:""}
      </div>
    </div>
  `},d=({title:t,header:o,bodyHtml:e})=>`
  <html>
    <head>
      <title>${t}</title>
      <style>
        :root {
          --ink: #0f172a;
          --muted: #64748b;
          --border: #e2e8f0;
          --surface: #ffffff;
          --accent: #16a34a;
        }
        body { font-family: "Segoe UI", Arial, sans-serif; padding: 32px; color: var(--ink); background: var(--surface); }
        h1 { font-size: 22px; margin: 0; }
        h2 { font-size: 15px; margin: 22px 0 10px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); }
        h3 { font-size: 13px; margin: 16px 0 8px; color: var(--ink); }
        p { margin: 4px 0; font-size: 12px; }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th, td { border: 1px solid var(--border); padding: 8px; font-size: 11px; text-align: left; }
        th { background: #f8fafc; color: var(--muted); font-weight: 600; }
        .muted { color: var(--muted); font-size: 11px; }
        .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
        .card { border: 1px solid var(--border); border-radius: 10px; padding: 12px; }
        .header { display: flex; align-items: flex-start; justify-content: space-between; border-bottom: 1px solid var(--border); padding-bottom: 12px; margin-bottom: 16px; gap: 20px; }
        .header-left { display: flex; align-items: center; gap: 12px; }
        .header-right { text-align: right; }
        .meta-title { font-weight: 600; font-size: 12px; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 999px; background: rgba(22, 163, 74, 0.12); color: var(--accent); font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; }
        .section { margin-top: 18px; }
        .divider { height: 1px; background: var(--border); margin: 18px 0; }
        .logo { width: 48px; height: 48px; object-fit: cover; border-radius: 10px; border: 1px solid var(--border); }
        .logo-placeholder { width: 48px; height: 48px; border-radius: 10px; border: 1px dashed var(--border); color: var(--muted); font-size: 10px; display: flex; align-items: center; justify-content: center; }
      </style>
    </head>
    <body>
      ${i(o)}
      ${e}
    </body>
  </html>
`,p=(t,o)=>{const e=window.open("","_blank","width=900,height=700");if(!e)throw new Error("Popup blocked");e.document.title=t,e.document.write(o),e.document.close(),e.focus(),e.print()};export{d as b,p as o};
