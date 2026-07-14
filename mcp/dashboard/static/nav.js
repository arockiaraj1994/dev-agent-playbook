/* Collapsible sidebar groups + icon-rail mode */
(function () {
  var GROUPS_KEY = "dp-nav-groups";
  var COLLAPSED_KEY = "dp-sidebar-collapsed";
  var app = document.querySelector(".app");
  var btn = document.getElementById("sidebar-collapse-btn");
  if (!app) return;

  function readGroups() {
    try {
      var raw = localStorage.getItem(GROUPS_KEY);
      if (!raw) return {};
      var parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function writeGroups(state) {
    try {
      localStorage.setItem(GROUPS_KEY, JSON.stringify(state));
    } catch (e) { /* ignore quota */ }
  }

  function setGroupOpen(group, open) {
    var toggle = group.querySelector(".nav-group-toggle");
    var items = group.querySelector(".nav-group-items");
    if (!toggle || !items) return;
    group.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) items.removeAttribute("hidden");
    else items.setAttribute("hidden", "");
  }

  function persistOpenState() {
    var state = {};
    document.querySelectorAll(".nav-group[data-group]").forEach(function (g) {
      state[g.dataset.group] = g.classList.contains("open");
    });
    writeGroups(state);
  }

  function applyCollapsed(collapsed) {
    app.classList.toggle("sidebar-collapsed", collapsed);
    if (btn) {
      btn.setAttribute(
        "aria-label",
        collapsed ? "Expand sidebar" : "Collapse sidebar"
      );
      btn.setAttribute(
        "title",
        collapsed ? "Expand sidebar" : "Collapse sidebar"
      );
    }
    try {
      localStorage.setItem(COLLAPSED_KEY, collapsed ? "1" : "0");
    } catch (e) { /* ignore */ }
  }

  /* Restore group open state; force-open group with active link */
  var saved = readGroups();
  document.querySelectorAll(".nav-group[data-group]").forEach(function (group) {
    var key = group.dataset.group;
    var hasActive = !!group.querySelector(".nav-item.active");
    var open = hasActive || saved[key] === true;
    setGroupOpen(group, open);
  });
  persistOpenState();

  document.querySelectorAll(".nav-group-toggle").forEach(function (toggle) {
    toggle.addEventListener("click", function () {
      var group = toggle.closest(".nav-group");
      if (!group) return;
      setGroupOpen(group, !group.classList.contains("open"));
      persistOpenState();
    });
  });

  /* Icon-rail collapse */
  var collapsed = false;
  try {
    collapsed = localStorage.getItem(COLLAPSED_KEY) === "1";
  } catch (e) { /* ignore */ }
  applyCollapsed(collapsed);

  if (btn) {
    btn.addEventListener("click", function () {
      applyCollapsed(!app.classList.contains("sidebar-collapsed"));
    });
  }

  /* Mobile off-canvas (<900px): hamburger opens, scrim/Escape/nav click closes */
  var openBtn = document.getElementById("sidebar-open-btn");
  var scrim = document.getElementById("sidebar-scrim");

  function setMobileOpen(open) {
    app.classList.toggle("sidebar-mobile-open", open);
    if (openBtn) openBtn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  if (openBtn) {
    openBtn.addEventListener("click", function () {
      setMobileOpen(!app.classList.contains("sidebar-mobile-open"));
    });
  }
  if (scrim) {
    scrim.addEventListener("click", function () { setMobileOpen(false); });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && app.classList.contains("sidebar-mobile-open")) {
      setMobileOpen(false);
    }
  });
  /* Navigating away naturally closes it, but same-page anchor taps should too */
  document.querySelectorAll(".sidebar .nav-item").forEach(function (link) {
    link.addEventListener("click", function () { setMobileOpen(false); });
  });
})();
