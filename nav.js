// Shared top navigation, injected on every page.
(function () {
  const PAGES = [
    { href: "index.html",      label: "Overview" },
    { href: "technology.html", label: "What We Build" },
    { href: "speed.html",      label: "How Long It Takes" },
    { href: "politics.html",   label: "Does Party Matter?" },
  ];
  const here = (location.pathname.split("/").pop() || "index.html").toLowerCase();

  const links = PAGES.map(p => {
    const active = p.href.toLowerCase() === here ? " class=\"active\"" : "";
    return `<a href="${p.href}"${active}>${p.label}</a>`;
  }).join("");

  document.body.insertAdjacentHTML("afterbegin", `
    <nav class="nav">
      <div class="nav-inner">
        <a class="nav-brand" href="index.html"><span class="spark">●</span> The Politics of Power</a>
        <button class="nav-toggle" aria-label="Menu">Menu</button>
        <div class="nav-links">${links}</div>
      </div>
    </nav>`);

  const btn = document.querySelector(".nav-toggle");
  const menu = document.querySelector(".nav-links");
  btn && btn.addEventListener("click", () => menu.classList.toggle("open"));
})();
