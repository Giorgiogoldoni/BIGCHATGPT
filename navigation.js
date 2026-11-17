(() => {
  const links = [
    ["index.html", "Segnali"],
    ["top20.html", "Top 20"],
    ["classifica.html", "Classifica"],
    ["mercato.html", "Mercato"],
    ["benchmark.html", "Benchmark"],
    ["research.html", "Ricerca"]
  ];
  const path = location.pathname.split("/").pop() || "index.html";
  const active = path === "grafico.html" ? "index.html" : path;
  const style = document.createElement("style");
  style.textContent = `
    body { padding-bottom: calc(76px + env(safe-area-inset-bottom, 0px)) !important; }
    #big-bottom-nav {
      position: fixed; z-index: 99999; left: 0; right: 0; bottom: 0;
      display: flex; gap: 6px; align-items: center; justify-content: flex-start;
      overflow-x: auto; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch;
      padding: 9px 10px calc(9px + env(safe-area-inset-bottom, 0px));
      background: rgba(255,255,255,.97); border-top: 1px solid #d9dee7;
      box-shadow: 0 -3px 14px rgba(16,24,40,.08);
      scrollbar-width: none; backdrop-filter: blur(12px);
    }
    #big-bottom-nav::-webkit-scrollbar { display:none; }
    #big-bottom-nav a {
      flex: 0 0 auto; min-width: 76px; text-align: center;
      padding: 9px 12px; border-radius: 9px; border: 1px solid #e2e6ec;
      color: #344054; background: #fff; text-decoration: none;
      font: 600 12px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;
      white-space: nowrap; -webkit-tap-highlight-color: transparent;
    }
    #big-bottom-nav a[aria-current="page"] {
      color: #fff; background: #1d4ed8; border-color: #1d4ed8;
    }
    @media (min-width: 900px) {
      #big-bottom-nav { justify-content: center; }
      #big-bottom-nav a { min-width: 112px; font-size: 13px; }
    }
  `;
  document.head.appendChild(style);
  const nav = document.createElement("nav");
  nav.id = "big-bottom-nav";
  nav.setAttribute("aria-label", "Navigazione risultati BIGCHATGPT");
  links.forEach(([href, label]) => {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = label;
    if (href === active) a.setAttribute("aria-current", "page");
    nav.appendChild(a);
  });
  document.body.appendChild(nav);
})();
