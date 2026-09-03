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
const PASSWORD_LEVELS = [
    {key: "very-weak", label: "ضعيفة جدًا", hint: "ابدأ بكلمة أطول ومزيج أوضح من الأحرف"},
    {key: "weak", label: "ضعيفة", hint: "أضف حرفًا كبيرًا ورقمًا أو رمزًا"},
    {key: "medium", label: "متوسطة", hint: "اقتربت. أضف عنصرًا آخر لزيادة الأمان"},
    {key: "good", label: "جيدة", hint: "كلمة جيدة. الرمز الخاص يجعلها أقوى"},
    {key: "strong", label: "قوية", hint: "كلمة مرور قوية"},
];
const PASSWORD_RULES = [
    {key: "length", test: (value) => value.length >= 8},
    {key: "upper", test: (value) => /[A-Z]/.test(value)},
    {key: "lower", test: (value) => /[a-z]/.test(value)},
    {key: "number", test: (value) => /\d/.test(value)},
    {key: "special", test: (value) => /[^A-Za-z0-9]/.test(value)},
];
const PASSWORD_GROUPS = {
    upper: "ABCDEFGHJKLMNPQRSTUVWXYZ",
    lower: "abcdefghijkmnopqrstuvwxyz",
    number: "23456789",
    special: "@#$%&*!?",
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

function randomInt(max) {
    if (!window.crypto?.getRandomValues) {
        return Math.floor(Math.random() * max);
    }
    const values = new Uint32Array(1);
    window.crypto.getRandomValues(values);
    return values[0] % max;
}

function shuffledPassword(chars) {
    const nextChars = [...chars];
    for (let index = nextChars.length - 1; index > 0; index--) {
        const swapIndex = randomInt(index + 1);
        [nextChars[index], nextChars[swapIndex]] = [nextChars[swapIndex], nextChars[index]];
    }
    return nextChars.join("");
}

function generateStrongPassword(length = 14) {
    const groups = Object.values(PASSWORD_GROUPS);
    const chars = groups.map((group) => group[randomInt(group.length)]);
    const allChars = groups.join("");
    while (chars.length < length) {
        chars.push(allChars[randomInt(allChars.length)]);
    }
    return shuffledPassword(chars);
}

function evaluatePassword(value = "") {
    const met = Object.fromEntries(PASSWORD_RULES.map((rule) => [rule.key, rule.test(value)]));
    const score = PASSWORD_RULES.reduce((total, rule) => total + (met[rule.key] ? 1 : 0), 0);
    const levelIndex = Math.max(0, Math.min(PASSWORD_LEVELS.length - 1, score - 1));
    return {
        met,
        score,
        level: value ? PASSWORD_LEVELS[levelIndex] : PASSWORD_LEVELS[0],
        isStrong: score === PASSWORD_RULES.length,
    };
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
        this.onPasswordFocus = this.onPasswordFocus.bind(this);
        this.onDelegatedPointerDown = this.onDelegatedPointerDown.bind(this);
        this.onDelegatedClick = this.onDelegatedClick.bind(this);
        this.onDelegatedInput = this.onDelegatedInput.bind(this);
        this.onDelegatedBlur = this.onDelegatedBlur.bind(this);
        this.onDelegatedFocus = this.onDelegatedFocus.bind(this);
        this.onDelegatedSubmit = this.onDelegatedSubmit.bind(this);
    }

    start() {
        this.el.addEventListener("pointerdown", this.onDelegatedPointerDown, true);
        this.el.addEventListener("click", this.onDelegatedClick);
        this.el.addEventListener("input", this.onDelegatedInput);
        this.el.addEventListener("blur", this.onDelegatedBlur, true);
        this.el.addEventListener("focusin", this.onDelegatedFocus);
        this.el.addEventListener("submit", this.onDelegatedSubmit);
        document.addEventListener("click", this.onDelegatedClick, true);
        document.addEventListener("submit", this.onDelegatedSubmit, true);
        this.prepareMotionItems();
        this.el.classList.add("is-auth-ready");
    }

    destroy() {
        this.el.removeEventListener("pointerdown", this.onDelegatedPointerDown, true);
        this.el.removeEventListener("click", this.onDelegatedClick);
        this.el.removeEventListener("input", this.onDelegatedInput);
        this.el.removeEventListener("blur", this.onDelegatedBlur, true);
        this.el.removeEventListener("focusin", this.onDelegatedFocus);
        this.el.removeEventListener("submit", this.onDelegatedSubmit);
        document.removeEventListener("click", this.onDelegatedClick, true);
        document.removeEventListener("submit", this.onDelegatedSubmit, true);
    }

    onDelegatedPointerDown(ev) {
        if (!ev.target.closest("[data-ab-auth-nav]")) {
            return;
        }
        this.isNavigatingAuthMode = true;
        window.setTimeout(() => {
            this.isNavigatingAuthMode = false;
        }, 500);
    }

    onDelegatedClick(ev) {
        if (ev.abAuthHandled) {
            return;
        }
        ev.abAuthHandled = true;
        const passwordField = ev.target.closest(".field-password");
        if (passwordField && this.el.contains(passwordField)) {
            const password = passwordField.querySelector("input[name='password']");
            if (password) {
                this.updatePasswordExperience(password, {reveal: true});
                this.ensurePasswordSuggestion(passwordField);
            }
        }
        if (!ev.target.closest(".field-password")) {
            this.hidePasswordExperiences();
        }
        const navLink = ev.target.closest("[data-ab-auth-nav]");
        if (navLink && this.el.contains(navLink)) {
            this.clearAuthModeValidation();
            this.onModeNavigation(this.withCurrentTarget(ev, navLink));
            return;
        }
        const passwordToggle = ev.target.closest(".ab-auth-password-toggle");
        if (passwordToggle && this.el.contains(passwordToggle)) {
            this.onPasswordToggle(this.withCurrentTarget(ev, passwordToggle));
            return;
        }
        const generateButton = ev.target.closest("[data-ab-password-generate]");
        if (generateButton && this.el.contains(generateButton)) {
            this.generatePasswordSuggestion(generateButton.closest(".ab-auth-field"));
            return;
        }
        const useButton = ev.target.closest("[data-ab-password-use]");
        if (useButton && this.el.contains(useButton)) {
            this.usePasswordSuggestion(useButton.closest(".ab-auth-field"));
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
        if (ev.target.matches("input[name='password']")) {
            this.updatePasswordExperience(ev.target, {reveal: true});
            this.ensurePasswordSuggestion(ev.target.closest(".ab-auth-field"));
            this.updateConfirmExperience(ev.target.form);
        }
        if (ev.target.matches("input[name='confirm_password']")) {
            this.updateConfirmExperience(ev.target.form, {shakeOnMismatch: true});
        }
        if (ev.target.matches("input")) {
            this.clearFieldError(ev.target);
        }
    }

    onDelegatedBlur(ev) {
        if (ev.target.matches("[data-ab-phone-input]")) {
            this.onPhoneBlur(this.withCurrentTarget(ev, ev.target));
        }
        if (ev.target.matches("input[name='confirm_password']")) {
            this.updateConfirmExperience(ev.target.form, {shakeOnMismatch: true});
        }
        if (ev.target.matches("input[name='password']")) {
            window.setTimeout(() => {
                if (!ev.target.closest(".field-password")?.contains(document.activeElement)) {
                    this.hidePasswordExperiences();
                }
            }, 0);
        }
    }

    onDelegatedFocus(ev) {
        if (ev.target.matches("input[name='password']")) {
            this.onPasswordFocus(this.withCurrentTarget(ev, ev.target));
        } else if (!ev.target.closest(".field-password")) {
            this.hidePasswordExperiences();
        }
    }

    onPasswordFocus(ev) {
        const input = ev.currentTarget;
        this.updatePasswordExperience(input, {reveal: true});
        this.ensurePasswordSuggestion(input.closest(".ab-auth-field"));
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
            relatedTarget: ev.relatedTarget,
            preventDefault: () => ev.preventDefault(),
            stopPropagation: () => ev.stopPropagation(),
        };
    }

    async onModeNavigation(ev) {
        if (ev.abAuthHandled) {
            return;
        }
        const link = ev.currentTarget;
        const url = this.getLocalizedAuthUrl(link.href);
        if (!url || this.isTransitioning || this.isSubmitting || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
            return;
        }
        if (new URL(url, window.location.href).origin !== window.location.origin) {
            return;
        }

        ev.preventDefault();
        this.clearAuthModeValidation();
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

    clearAuthModeValidation() {
        this.el.querySelectorAll(".ab-auth-field").forEach((field) => {
            field.classList.remove("has-error", "is-angry");
        });
        this.el.querySelectorAll(".ab-auth-form input").forEach((input) => {
            input.classList.remove("is-invalid");
            input.removeAttribute("aria-invalid");
        });
        this.el.querySelectorAll(".ab-auth-field-message").forEach((message) => {
            message.textContent = "";
        });
    }

    onPhoneBlur(ev) {
        if (this.isNavigatingAuthMode || ev.relatedTarget?.closest?.("[data-ab-auth-nav]")) {
            return;
        }
        this.validatePhone(ev.currentTarget, true);
    }

    onPasswordToggle(ev) {
        if (ev.abAuthHandled) {
            return;
        }
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
        if (password && form.matches(".oe_signup_form, .oe_reset_password_form")) {
            const strength = evaluatePassword(password.value);
            if (password.value && !strength.isStrong) {
                this.updatePasswordExperience(password, {reveal: true});
                this.setFieldError(password, "استخدم 8 أحرف على الأقل مع حرف كبير وصغير ورقم ورمز خاص");
                return password;
            }
        }
        if (password && confirm && password.value !== confirm.value) {
            this.setFieldError(confirm, "كلمتا المرور غير متطابقتين");
            this.updateConfirmExperience(form, {shakeOnMismatch: true});
            return confirm;
        }
        return null;
    }

    updatePasswordExperience(input, options = {}) {
        const field = input.closest(".ab-auth-field");
        const helper = field?.querySelector("[data-ab-password-strength]");
        if (!field || !helper) {
            return;
        }
        const value = input.value || "";
        const strength = evaluatePassword(value);
        helper.classList.toggle("is-revealed", Boolean(options.reveal));
        helper.classList.toggle("has-value", Boolean(value));
        helper.classList.toggle("is-strong", strength.isStrong);
        helper.dataset.strength = strength.level.key;

        helper.querySelectorAll("[data-ab-password-segment]").forEach((segment) => {
            const index = Number(segment.dataset.abPasswordSegment || 0);
            segment.classList.toggle("is-active", index <= strength.score);
        });
        helper.querySelectorAll("[data-ab-password-rule]").forEach((row) => {
            const isMet = Boolean(strength.met[row.dataset.abPasswordRule]);
            row.classList.toggle("is-met", isMet);
            const icon = row.querySelector("svg");
            if (icon) {
                icon.innerHTML = isMet
                    ? '<path d="M20 6 9 17l-5-5"/>'
                    : '<circle cx="12" cy="12" r="7"/>';
            }
        });

        const label = helper.querySelector("[data-ab-password-label]");
        if (label && label.textContent !== strength.level.label) {
            label.classList.remove("is-changing");
            void label.offsetWidth;
            label.textContent = strength.isStrong ? "كلمة مرور قوية" : strength.level.label;
            label.classList.add("is-changing");
        }
        const hint = helper.querySelector("[data-ab-password-hint]");
        if (hint) {
            hint.textContent = strength.isStrong ? "كلمة مرور قوية" : strength.level.hint;
        }
    }

    hidePasswordExperiences() {
        this.el.querySelectorAll("[data-ab-password-strength].is-revealed").forEach((helper) => {
            helper.classList.remove("is-revealed");
        });
    }

    ensurePasswordSuggestion(field) {
        const suggestion = field?.querySelector("[data-ab-password-suggestion]");
        if (suggestion && (!suggestion.textContent || suggestion.textContent.trim() === "--")) {
            this.setPasswordSuggestion(field, generateStrongPassword());
        }
    }

    generatePasswordSuggestion(field) {
        this.setPasswordSuggestion(field, generateStrongPassword());
    }

    setPasswordSuggestion(field, value) {
        const suggestion = field?.querySelector("[data-ab-password-suggestion]");
        const wrap = field?.querySelector("[data-ab-password-suggestion-wrap]");
        if (!suggestion || !wrap) {
            return;
        }
        wrap.classList.remove("is-refreshing");
        void wrap.offsetWidth;
        suggestion.textContent = value;
        wrap.classList.add("is-refreshing");
    }

    usePasswordSuggestion(field) {
        const password = field?.querySelector("input[name='password']");
        const suggestion = field?.querySelector("[data-ab-password-suggestion]")?.textContent?.trim();
        if (!password || !suggestion || suggestion === "--") {
            return;
        }
        password.value = suggestion;
        password.dispatchEvent(new Event("input", {bubbles: true}));
        this.updatePasswordExperience(password, {reveal: true});
    }

    updateConfirmExperience(form, options = {}) {
        const password = form?.querySelector("input[name='password']");
        const confirm = form?.querySelector("input[name='confirm_password']");
        const field = confirm?.closest(".ab-auth-field");
        const message = field?.querySelector("[data-ab-confirm-message]");
        if (!password || !confirm || !message) {
            return;
        }
        field.classList.remove("has-confirm-match", "has-confirm-mismatch");
        if (!confirm.value) {
            message.textContent = "";
            return;
        }
        const matches = password.value === confirm.value;
        field.classList.add(matches ? "has-confirm-match" : "has-confirm-mismatch");
        message.textContent = matches ? "كلمتا المرور متطابقتان" : "كلمتا المرور غير متطابقتين";
        if (!matches && options.shakeOnMismatch && field.dataset.abLastConfirmState !== "mismatch") {
            this.shakeField(field);
        }
        field.dataset.abLastConfirmState = matches ? "match" : "mismatch";
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
            this.services["public.interactions"]?.startInteractions(card);
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
        const selectedAvatar = this.el.querySelector(".ab-auth-avatar-choice .ab-storefront-avatar img")?.cloneNode(true);
        if (selectedAvatar) {
            const avatarWrap = document.createElement("div");
            avatarWrap.className = "ab-auth-success-avatar ab-storefront-avatar ab-storefront-avatar-xl";
            avatarWrap.appendChild(selectedAvatar);
            stage.appendChild(avatarWrap);
        }
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
        form.querySelectorAll("input[name='password']").forEach((input) => {
            this.updatePasswordExperience(input, {reveal: false});
            this.ensurePasswordSuggestion(input.closest(".ab-auth-field"));
        });
        this.updateConfirmExperience(form);
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
        this.el.querySelectorAll("input[name='password']:not([data-ab-password-bound])").forEach((input) => {
            input.dataset.abPasswordBound = "true";
            input.addEventListener("focus", this.onPasswordFocus);
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
