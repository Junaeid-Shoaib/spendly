// main.js — students will add JavaScript here as features are built

// Selects marked data-autosubmit submit their form as soon as a value is picked.
document.querySelectorAll("select[data-autosubmit]").forEach(function (select) {
    select.addEventListener("change", function () {
        if (select.value !== "") {
            select.form.submit();
        }
    });
});
