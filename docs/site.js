/* hamburger drawer + auto-hide header */
(function () {
  var menuBtn = document.getElementById("menuBtn"),
      drawer = document.getElementById("drawer"),
      scrim = document.getElementById("scrim");
  function setMenu(open) {
    menuBtn.classList.toggle("open", open);
    drawer.classList.toggle("open", open);
    scrim.classList.toggle("show", open);
  }
  menuBtn.addEventListener("click", function () {
    setMenu(!drawer.classList.contains("open"));
  });
  scrim.addEventListener("click", function () { setMenu(false); });
  drawer.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", function () { setMenu(false); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setMenu(false);
  });

  var lastY = window.scrollY, hdr = document.querySelector("header.site");
  window.addEventListener("scroll", function () {
    var y = window.scrollY;
    if (y > lastY + 4 && y > 140) { hdr.classList.add("hide"); }
    else if (y < lastY - 4) { hdr.classList.remove("hide"); }
    lastY = y;
  }, { passive: true });
})();
