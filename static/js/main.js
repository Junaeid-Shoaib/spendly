// main.js — students will add JavaScript here as features are built

// Selects marked data-autosubmit submit their form as soon as a value is picked.
document.querySelectorAll("select[data-autosubmit]").forEach(function (select) {
    select.addEventListener("change", function () {
        if (select.value !== "") {
            select.form.submit();
        }
    });
});

// Light/dark theme toggle. The initial theme is set by an inline script in base.html.
(function () {
    var toggle = document.getElementById("theme-toggle");
    if (!toggle) { return; }
    toggle.addEventListener("click", function () {
        var root = document.documentElement;
        var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        try { localStorage.setItem("spendly-theme", next); } catch (e) {}
    });
})();
