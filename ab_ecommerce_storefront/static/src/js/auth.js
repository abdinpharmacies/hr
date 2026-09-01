/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹";
const LATIN_DIGITS = "01234567890123456789";
const EGYPT_MOBILE_RE = /^01[0125]\d{8}$/;
const MOTION_MS = {
    exit: 260,
    enter: 420,
    success: 1180,
};

function normalizeEgyptianPhone(value = "") {
    let phone = "";
    for (const char of value.trim()) {
        const digitIndex = ARABIC_DIGITS.indexOf(char);
        phone += digitIndex >= 0 ? LATIN_DIGITS[digitIndex] : char;
    }
    phone = phone.replace(/[^\d+]/g, "");
    if (phone.startsWith("0020")) {
        phone = `0${phone.slice(4)}`;
    } else if (phone.startsWith("+20")) {
        phone = `0${phone.slice(3)}`;
    } else if (phone.startsWith("20") && phone.length === 12) {
        phone = `0${phone.slice(2)}`;
    } else if (phone.startsWith("1") && phone.length === 10) {
        phone = `0${phone}`;
    }
    return phone;
}

function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

export class AbStorefrontAuth extends Interaction {
    static selector = ".ab-auth-page";

    setup() {
        this.isTransitioning = false;
        this.isSubmitting = false;
        this.onModeNavigation = this.onModeNavigation.bind(this);
        this.onSubmit = this.onSubmit.bind(this);
        this.onPhoneInput = this.onPhoneInput.bind(this);
        this.onPhoneBlur = this.onPhoneBlur.bind(this);
        this.onPasswordToggle = this.onPasswordToggle.bind(this);
        this.onDelegatedClick = this.onDelegatedClick.bind(this);
        this.onDelegatedInput = this.onDelegatedInput.bind(this);
        this.onDelegatedBlur = this.onDelegatedBlur.bind(this);
        this.onDelegatedSubmit = this.onDelegatedSubmit.bind(this);
    }

    start() {
        this.el.addEventListener("click", this.onDelegatedClick);
        this.el.addEventListener("input", this.onDelegatedInput);
        this.el.addEventListener("blur", this.onDelegatedBlur, true);
        this.el.addEventListener("submit", this.onDelegatedSubmit);
        document.addEventListener("click", this.onDelegatedClick, true);
        document.addEventListener("submit", this.onDelegatedSubmit, true);
        this.prepareMotionItems();
        this.el.classList.add("is-auth-ready");
    }

    destroy() {
        this.el.removeEventListener("click", this.onDelegatedClick);
        this.el.removeEventListener("input", this.onDelegatedInput);
        this.el.removeEventListener("blur", this.onDelegatedBlur, true);
        this.el.removeEventListener("submit", this.onDelegatedSubmit);
        document.removeEventListener("click", this.onDelegatedClick, true);
        document.removeEventListener("submit", this.onDelegatedSubmit, true);
    }

    onDelegatedClick(ev) {
        const navLink = ev.target.closest("[data-ab-auth-nav]");
        if (navLink && this.el.contains(navLink)) {
            this.onModeNavigation(this.withCurrentTarget(ev, navLink));
            return;
        }
        const passwordToggle = ev.target.closest(".ab-auth-password-toggle");
        if (passwordToggle && this.el.contains(passwordToggle)) {
            this.onPasswordToggle(this.withCurrentTarget(ev, passwordToggle));
            return;
        }
        const submitButton = ev.target.closest("[data-ab-auth-submit]");
        if (submitButton && this.el.contains(submitButton)) {
            const form = submitButton.closest("[data-ab-auth-form]");
            if (form) {
                this.onSubmit(this.withCurrentTarget(ev, form));
            }
        }
    }

    onDelegatedInput(ev) {
        if (ev.target.matches("[data-ab-phone-input]")) {
            this.onPhoneInput(this.withCurrentTarget(ev, ev.target));
            return;
        }
        if (ev.target.matches("input")) {
            this.clearFieldError(ev.target);
        }
    }

    onDelegatedBlur(ev) {
        if (ev.target.matches("[data-ab-phone-input]")) {
            this.onPhoneBlur(this.withCurrentTarget(ev, ev.target));
        }
    }

    onDelegatedSubmit(ev) {
        const form = ev.target.closest("[data-ab-auth-form]");
        if (form && this.el.contains(form)) {
            this.onSubmit(this.withCurrentTarget(ev, form));
        }
    }

    withCurrentTarget(ev, currentTarget) {
        return {
            currentTarget,
            target: ev.target,
            button: ev.button,
            metaKey: ev.metaKey,
            ctrlKey: ev.ctrlKey,
            shiftKey: ev.shiftKey,
            altKey: ev.altKey,
            preventDefault: () => ev.preventDefault(),
            stopPropagation: () => ev.stopPropagation(),
        };
    }

    async onModeNavigation(ev) {
        const link = ev.currentTarget;
        const url = this.getLocalizedAuthUrl(link.href);
        if (!url || this.isTransitioning || this.isSubmitting || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
            return;
        }
        if (new URL(url, window.location.href).origin !== window.location.origin) {
            return;
        }

        ev.preventDefault();
        this.isTransitioning = true;
        this.el.classList.add("is-auth-transitioning");

        const card = this.el.querySelector(".ab-auth-card");
        try {
            const response = await fetch(url, {
                credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            const html = await response.text();
            const nextCard = this.extractAuthCard(html);
            if (!nextCard || !card) {
                window.location.href = url;
                return;
            }

            const fromHeight = card.getBoundingClientRect().height;
            card.style.height = `${fromHeight}px`;
            card.classList.add("is-auth-exiting");
            await wait(MOTION_MS.exit);

            card.innerHTML = nextCard.innerHTML;
            this.prepareMotionItems();
            const toHeight = card.scrollHeight;
            card.classList.remove("is-auth-exiting");
            card.classList.add("is-auth-entering");
            card.style.height = `${toHeight}px`;
            window.history.pushState({abAuth: true}, "", url);

            await wait(MOTION_MS.enter);
            card.classList.remove("is-auth-entering");
            card.style.height = "";
        } catch {
            window.location.href = url;
        } finally {
            this.el.classList.remove("is-auth-transitioning");
            this.isTransitioning = false;
        }
    }

    onPhoneInput(ev) {
        const input = ev.currentTarget;
        input.classList.remove("is-invalid");
        input.closest(".ab-auth-field")?.classList.remove("is-angry");
        const message = this.getPhoneMessage(input);
        if (message) {
            message.textContent = "";
        }
    }

    onPhoneBlur(ev) {
        this.validatePhone(ev.currentTarget, true);
    }

    onPasswordToggle(ev) {
        const button = ev.currentTarget;
        const input = button.closest(".ab-auth-input")?.querySelector("input[type='password'], input[type='text']");
        if (!input) {
            return;
        }
        const shouldShow = input.type === "password";
        input.type = shouldShow ? "text" : "password";
        button.classList.toggle("is-visible", shouldShow);
        button.setAttribute("aria-label", shouldShow ? "إخفاء كلمة المرور" : "إظهار كلمة المرور");
    }

    async onSubmit(ev) {
        const form = ev.currentTarget;
        if (this.isTransitioning || this.isSubmitting) {
            ev.preventDefault();
            return;
        }
        ev.preventDefault();

        const firstInvalid = this.validateForm(form);
        if (firstInvalid) {
            firstInvalid.focus();
            return;
        }

        const phoneInput = form.querySelector("[data-ab-phone-input]");
        if (phoneInput) {
            const normalized = normalizeEgyptianPhone(phoneInput.value);
            phoneInput.value = normalized;
            const hiddenLogin = form.querySelector("input[type='hidden'][name='login']");
            if (hiddenLogin) {
                hiddenLogin.value = normalized;
            }
        }

        const button = form.querySelector("[data-ab-auth-submit]");
        this.isSubmitting = true;
        this.el.classList.add("is-auth-submitting");
        if (button && !button.disabled) {
            button.disabled = true;
            button.dataset.originalText = button.textContent.trim();
            button.classList.add("is-loading");
            button.textContent = button.dataset.loadingText || "جاري المتابعة...";
        }

        try {
            const response = await fetch(form.action || window.location.href, {
                method: "POST",
                body: new FormData(form),
                credentials: "same-origin",
            });
            const html = await response.text();
            const nextCard = this.extractAuthCard(html);
            const hasBackendError = Boolean(nextCard?.querySelector(".ab-auth-alert-error"));
            const hasAuthForm = Boolean(nextCard?.querySelector("[data-ab-auth-form]"));

            if (!response.ok || hasBackendError || hasAuthForm) {
                this.renderBackendResponse(nextCard, html);
                this.shakeBackendError();
                return;
            }

            await this.playSuccessSequence(response.url || form.querySelector("input[name='redirect']")?.value || "/shop");
        } catch {
            this.showInlineFailure(form, "حدث خطأ غير متوقع. حاول مرة أخرى.");
        } finally {
            if (!this.el.classList.contains("is-auth-success")) {
                this.isSubmitting = false;
                this.el.classList.remove("is-auth-submitting");
            }
        }
    }

    validatePhone(input, showMessage = false) {
        const normalized = normalizeEgyptianPhone(input.value);
        const message = this.getPhoneMessage(input);
        let error = "";
        if (!normalized) {
            error = "رقم الهاتف مطلوب";
        } else if (!EGYPT_MOBILE_RE.test(normalized)) {
            error = "برجاء إدخال رقم هاتف صحيح";
        }

        input.classList.toggle("is-invalid", Boolean(error));
        input.closest(".ab-auth-field")?.classList.toggle("has-error", Boolean(error));
        if (message) {
            message.textContent = showMessage ? error : "";
        }
        if (error && showMessage) {
            this.shakeField(input.closest(".ab-auth-field"));
        }
        return !error;
    }

    getPhoneMessage(input) {
        return input.closest(".ab-auth-field")?.querySelector("[data-ab-phone-message]");
    }

    validateForm(form) {
        const requiredInputs = [...form.querySelectorAll("input[required]")];
        for (const input of requiredInputs) {
            if (input.matches("[data-ab-phone-input]")) {
                if (!this.validatePhone(input, true)) {
                    return input;
                }
                continue;
            }
            if (!input.value.trim()) {
                this.setFieldError(input, input.type === "password" ? "هذا الحقل مطلوب" : "برجاء إدخال هذا الحقل");
                return input;
            }
            this.clearFieldError(input);
        }

        const password = form.querySelector("input[name='password']");
        const confirm = form.querySelector("input[name='confirm_password']");
        if (password && confirm && password.value !== confirm.value) {
            this.setFieldError(confirm, "كلمتا المرور غير متطابقتين");
            return confirm;
        }
        return null;
    }

    setFieldError(input, text) {
        input.classList.add("is-invalid");
        const field = input.closest(".ab-auth-field");
        field?.classList.add("has-error");
        let message = field?.querySelector(".ab-auth-field-message");
        if (!message && field) {
            message = document.createElement("p");
            message.className = "ab-auth-field-message";
            message.setAttribute("aria-live", "polite");
            field.appendChild(message);
        }
        if (message) {
            message.textContent = text;
        }
        this.shakeField(field);
    }

    clearFieldError(input) {
        input.classList.remove("is-invalid");
        const field = input.closest(".ab-auth-field");
        field?.classList.remove("has-error", "is-angry");
        const message = field?.querySelector(".ab-auth-field-message:not([data-ab-phone-message])");
        if (message) {
            message.textContent = "";
        }
    }

    shakeField(field) {
        if (!field) {
            return;
        }
        field.classList.remove("is-angry");
        void field.offsetWidth;
        field.classList.add("is-angry");
    }

    shakeBackendError() {
        const field = this.el.querySelector(".ab-auth-alert-error")?.previousElementSibling?.matches?.(".ab-auth-field")
            ? this.el.querySelector(".ab-auth-alert-error").previousElementSibling
            : this.el.querySelector(".ab-auth-field");
        this.shakeField(field);
    }

    renderBackendResponse(nextCard, fallbackHtml) {
        const card = this.el.querySelector(".ab-auth-card");
        if (nextCard && card) {
            card.innerHTML = nextCard.innerHTML;
            this.prepareMotionItems();
            return;
        }
        const form = this.el.querySelector("[data-ab-auth-form]");
        this.showInlineFailure(form, fallbackHtml ? "حدث خطأ غير متوقع. حاول مرة أخرى." : "تعذر الاتصال بالخادم. حاول مرة أخرى.");
    }

    showInlineFailure(form, text) {
        if (!form) {
            return;
        }
        let alert = form.querySelector(".ab-auth-alert-error");
        if (!alert) {
            alert = document.createElement("p");
            alert.className = "ab-auth-alert ab-auth-alert-error";
            alert.setAttribute("role", "alert");
            form.querySelector(".ab-auth-actions")?.before(alert);
        }
        alert.textContent = text;
        this.shakeField(form.querySelector(".ab-auth-field"));
    }

    async playSuccessSequence(destination) {
        const card = this.el.querySelector(".ab-auth-card");
        const logo = this.el.querySelector(".ab-auth-brand img")?.cloneNode(true);
        if (!card || !logo || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            window.location.href = destination || "/shop";
            return;
        }

        const stage = document.createElement("div");
        stage.className = "ab-auth-success-stage";
        const logoWrap = document.createElement("div");
        logoWrap.className = "ab-auth-success-logo ab-storefront-brand-logo is-celebrating";
        logoWrap.appendChild(logo);
        stage.appendChild(logoWrap);
        this.el.appendChild(stage);

        this.el.classList.add("is-auth-success");
        card.classList.add("is-success-compressing");
        await wait(MOTION_MS.success);
        window.location.href = destination || "/shop";
    }

    extractAuthCard(html) {
        const doc = new DOMParser().parseFromString(html, "text/html");
        return doc.querySelector(".ab-auth-card");
    }

    getLocalizedAuthUrl(url) {
        const nextUrl = new URL(url, window.location.href);
        const currentLang = window.location.pathname.match(/^\/([a-z]{2})(?=\/web\/)/)?.[1];
        if (currentLang && nextUrl.origin === window.location.origin && nextUrl.pathname.startsWith("/web/")) {
            nextUrl.pathname = `/${currentLang}${nextUrl.pathname}`;
        }
        return nextUrl.toString();
    }

    prepareMotionItems() {
        const form = this.el.querySelector(".ab-auth-form");
        if (!form) {
            return;
        }
        [...form.children].forEach((child, index) => {
            child.classList.add("ab-auth-motion-item");
            child.style.setProperty("--ab-auth-motion-index", index);
        });
        this.bindCurrentControls();
    }

    bindCurrentControls() {
        this.el.querySelectorAll("[data-ab-auth-nav]:not([data-ab-motion-bound])").forEach((link) => {
            link.dataset.abMotionBound = "true";
            link.addEventListener("click", this.onModeNavigation);
        });
        this.el.querySelectorAll("[data-ab-auth-form]:not([data-ab-motion-bound])").forEach((form) => {
            form.dataset.abMotionBound = "true";
            form.addEventListener("submit", this.onSubmit);
        });
        this.el.querySelectorAll("[data-ab-phone-input]:not([data-ab-motion-bound])").forEach((input) => {
            input.dataset.abMotionBound = "true";
            input.addEventListener("input", this.onPhoneInput);
            input.addEventListener("blur", this.onPhoneBlur);
        });
        this.el.querySelectorAll(".ab-auth-password-toggle:not([data-ab-motion-bound])").forEach((button) => {
            button.dataset.abMotionBound = "true";
            button.addEventListener("click", this.onPasswordToggle);
        });
        this.el.querySelectorAll("[data-ab-auth-submit]:not([data-ab-motion-bound])").forEach((button) => {
            button.dataset.abMotionBound = "true";
            button.addEventListener("click", (ev) => {
                const form = button.closest("[data-ab-auth-form]");
                if (form) {
                    this.onSubmit(this.withCurrentTarget(ev, form));
                }
            });
        });
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.auth", AbStorefrontAuth);
