/** @odoo-module **/

const initializeDeliveryCelebration = () => {
    const card = document.querySelector("[data-ab-delivery-celebration]");
    if (!card || card.dataset.abCelebrationReady) {
        return;
    }
    card.dataset.abCelebrationReady = "true";
    const storageKey = `ab:delivery-celebration:v1:${card.dataset.abDeliveryCelebration}`;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let observer;
    let finishTimer;
    let inView = false;

    const stop = () => {
        card.classList.remove("is-celebrating");
        window.clearTimeout(finishTimer);
        observer?.disconnect();
        document.removeEventListener("visibilitychange", onVisibilityChange);
        window.removeEventListener("pagehide", stop);
        reducedMotion.removeEventListener("change", stop);
    };

    const celebrate = () => {
        if (!inView || document.hidden) {
            return;
        }
        stop();
        try {
            if (window.localStorage.getItem(storageKey)) {
                return;
            }
            window.localStorage.setItem(storageKey, "seen");
        } catch {
            return;
        }
        if (reducedMotion.matches) {
            return;
        }
        card.querySelectorAll(".ab-order-delivered__confetti i").forEach((particle, index) => {
            const angle = (index / 20) * Math.PI * 2;
            const radius = 74 + (index % 3) * 19;
            particle.style.setProperty("--ab-burst-x", `${Math.cos(angle) * radius}px`);
            particle.style.setProperty("--ab-burst-y", `${Math.sin(angle) * radius}px`);
            particle.style.setProperty("--ab-burst-turn", `${index * 47}deg`);
            particle.style.setProperty("--ab-burst-delay", `${240 + (index % 4) * 35}ms`);
        });
        card.classList.add("is-celebrating");
        finishTimer = window.setTimeout(stop, 2000);
        window.addEventListener("pagehide", stop, { once: true });
        document.addEventListener("visibilitychange", onVisibilityChange);
        reducedMotion.addEventListener("change", stop, { once: true });
    };

    const onVisibilityChange = () => {
        if (card.classList.contains("is-celebrating")) {
            stop();
        } else {
            celebrate();
        }
    };

    if (!("IntersectionObserver" in window)) {
        return;
    }
    observer = new IntersectionObserver((entries) => {
        inView = entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.4);
        celebrate();
    }, { threshold: 0.4 });
    observer.observe(card);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("pagehide", stop, { once: true });
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeDeliveryCelebration, { once: true });
} else {
    initializeDeliveryCelebration();
}
