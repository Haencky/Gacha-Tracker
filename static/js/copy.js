document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;

    const source = document.querySelector(btn.dataset.copy);
    if (!source) return;

    if (!navigator.clipboard) {
        window.getSelection().selectAllChildren(source);
        showFeedback(btn, btn.dataset.copyManual);
        return;
    }

    navigator.clipboard
        .writeText(source.textContent)
        .then(() => showFeedback(btn, btn.dataset.copied))
        .catch(() => {
            window.getSelection().selectAllChildren(source);
            showFeedback(btn, btn.dataset.copyManual);
        });
});

function showFeedback(btn, message) {
    const tooltip = btn.closest(".tooltip");
    if (!tooltip || !message) return;

    tooltip.dataset.originalTip ??= tooltip.dataset.tip;
    tooltip.dataset.tip = message;
    tooltip.classList.add("tooltip-open");

    clearTimeout(tooltip.copyTimeout);
    tooltip.copyTimeout = setTimeout(() => {
        tooltip.dataset.tip = tooltip.dataset.originalTip;
        tooltip.classList.remove("tooltip-open");
    }, 2000);
}
