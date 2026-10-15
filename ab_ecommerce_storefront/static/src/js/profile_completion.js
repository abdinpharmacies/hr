/** @odoo-module **/

const initializeProfileCompletion = () => {
    const completion = document.querySelector("[data-ab-profile-completion]");
    if (!completion || completion.dataset.abCompletionReady) {
        return;
    }
    completion.dataset.abCompletionReady = "true";
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let inView = false;
    let pending = false;
    let claimed = false;
    let dismissed = false;
    let timer;
    let observer;

    const dismiss = () => {
        dismissed = true;
        completion.hidden = true;
        completion.classList.remove("is-celebrating");
        window.clearTimeout(timer);
        observer?.disconnect();
        completion.removeEventListener("ab:profile-completion-changed", claim);
        completion.removeEventListener("animationend", onAnimationEnd);
        document.removeEventListener("visibilitychange", onVisibilityChange);
        window.removeEventListener("pagehide", onPageHide);
        motion.removeEventListener("change", onMotionChange);
    };

    const claim = async () => {
        if (pending || claimed || dismissed || !inView || document.hidden || completion.dataset.abProfileCompletion !== "100") {
            return;
        }
        pending = true;
        try {
            const body = new FormData();
            body.set("csrf_token", completion.dataset.abCompletionCsrf);
            const response = await fetch("/ab_storefront/profile/completion/claim", {
                method: "POST", credentials: "same-origin", body,
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            if (!response.ok) {
                return;
            }
            const result = await response.json();
            if (!result.seen) {
                return;
            }
            claimed = true;
            if (!result.celebrate || dismissed || document.hidden || !inView || !completion.isConnected) {
                dismiss();
                return;
            }
            completion.classList.add("is-celebrating");
            timer = window.setTimeout(dismiss, motion.matches ? 1200 : 8000);
        } catch {
            return;
        } finally {
            pending = false;
        }
    };

    const onAnimationEnd = (event) => {
        if (event.target === completion && event.animationName === "ab-account-completion-complete") {
            dismiss();
        }
    };
    const onVisibilityChange = () => {
        if (claimed && document.hidden) {
            dismiss();
        } else {
            claim();
        }
    };
    const onPageHide = () => {
        if (claimed || pending) {
            dismiss();
        }
    };
    const onMotionChange = () => {
        if (claimed) {
            dismiss();
        }
    };

    completion.addEventListener("ab:profile-completion-changed", claim);
    completion.addEventListener("animationend", onAnimationEnd);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("pagehide", onPageHide);
    motion.addEventListener("change", onMotionChange);
    if ("IntersectionObserver" in window) {
        observer = new IntersectionObserver((entries) => {
            inView = entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.5);
            claim();
        }, { threshold: 0.5 });
        observer.observe(completion);
    } else {
        inView = true;
        claim();
    }
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeProfileCompletion, { once: true });
} else {
    initializeProfileCompletion();
}
