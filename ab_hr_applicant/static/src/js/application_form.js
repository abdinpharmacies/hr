/** @odoo-module **/

const APPLICATION_DRAFT_KEY = "ab_hr_applicant_form_draft_v1";
const IS_ARABIC_UI = document.documentElement.lang.startsWith("ar");

function runtimeText(key) {
    const ar = {
        loading: "جار التحميل...",
        choose: "اختر...",
        chooseGovernorateFirst: "اختر المحافظة أولًا...",
        errorLoadingCities: "حدث خطأ أثناء تحميل المدن",
        stepTemplate: "الخطوة %s من %s",
    };
    const en = {
        loading: "Loading...",
        choose: "Choose...",
        chooseGovernorateFirst: "Choose governorate first...",
        errorLoadingCities: "Error loading cities",
        stepTemplate: "Step %s of %s",
    };
    return (IS_ARABIC_UI ? ar : en)[key];
}

function byId(id) {
    return document.getElementById(id);
}

function debounce(fn, delay = 250) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

function readDraft() {
    try {
        const raw = sessionStorage.getItem(APPLICATION_DRAFT_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

function writeDraft(data) {
    try {
        sessionStorage.setItem(APPLICATION_DRAFT_KEY, JSON.stringify(data));
    } catch {
        // Ignore storage write failures (private mode / quota).
    }
}

function clearDraft() {
    try {
        sessionStorage.removeItem(APPLICATION_DRAFT_KEY);
    } catch {
        // Ignore storage delete failures.
    }
}

function clearRowInputs(row) {
    row.querySelectorAll("input, select, textarea").forEach((el) => {
        if (el.type === "checkbox" || el.type === "radio") {
            el.checked = false;
        } else {
            el.value = "";
        }
    });
}

async function loadCities(govId) {
    const city = byId("city_select");
    if (!city) {
        return;
    }

    const selectedCity = city.dataset.selectedCity || "";
    city.innerHTML = `<option value="">${runtimeText("loading")}</option>`;

    try {
        const resp = await fetch(`/jobs/cities_http?governorate_id=${encodeURIComponent(govId)}`, {
            method: "GET",
        });

        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        const data = await resp.json();
        city.innerHTML = `<option value="">${runtimeText("choose")}</option>`;
        (data || []).forEach((item) => {
            const opt = document.createElement("option");
            opt.value = String(item.id);
            opt.textContent = item.name;
            if (selectedCity && selectedCity === String(item.id)) {
                opt.selected = true;
            }
            city.appendChild(opt);
        });
        city.dataset.selectedCity = "";
    } catch {
        city.innerHTML = `<option value="">${runtimeText("errorLoadingCities")}</option>`;
    }
}

function cloneRow(container, rowSelector) {
    const first = container.querySelector(rowSelector);
    if (!first) {
        return null;
    }
    const row = first.cloneNode(true);
    clearRowInputs(row);
    container.appendChild(row);
    return row;
}

function collectRowData(row, fieldNames) {
    const data = {};
    for (const fieldName of fieldNames) {
        const field = row.querySelector(`[name="${fieldName}"]`);
        data[fieldName] = field ? field.value : "";
    }
    return data;
}

function rowHasData(data) {
    return Object.values(data).some((value) => String(value || "").trim() !== "");
}

function restoreRows(container, rowSelector, rowsData) {
    if (!container) {
        return;
    }

    const target = rowsData.length || 1;
    let rows = Array.from(container.querySelectorAll(rowSelector));
    while (rows.length < target) {
        cloneRow(container, rowSelector);
        rows = Array.from(container.querySelectorAll(rowSelector));
    }
    while (rows.length > target) {
        rows[rows.length - 1].remove();
        rows = Array.from(container.querySelectorAll(rowSelector));
    }

    if (!rowsData.length) {
        clearRowInputs(rows[0]);
        return;
    }

    rowsData.forEach((rowData, index) => {
        const row = rows[index];
        Object.entries(rowData).forEach(([fieldName, fieldValue]) => {
            const field = row.querySelector(`[name="${fieldName}"]`);
            if (field) {
                field.value = fieldValue || "";
            }
        });
    });
}

function collectFormDraft(form, getCurrentStep) {
    const values = {};
    form.querySelectorAll("input[name], select[name], textarea[name]").forEach((field) => {
        const { name } = field;
        if (!name || name === "csrf_token" || name === "captcha_input" || name.endsWith("[]")) {
            return;
        }
        if (field.type === "checkbox") {
            values[name] = field.checked;
        } else if (field.type === "radio") {
            if (field.checked) {
                values[name] = field.value;
            } else if (!(name in values)) {
                values[name] = "";
            }
        } else {
            values[name] = field.value;
        }
    });

    const expRows = Array.from(form.querySelectorAll("#exp_container .exp_row"))
        .map((row) =>
            collectRowData(row, [
                "exp_company[]",
                "exp_title[]",
                "exp_from[]",
                "exp_to[]",
                "exp_reason[]",
                "exp_salary[]",
            ])
        )
        .filter(rowHasData);

    const courseRows = Array.from(form.querySelectorAll("#course_container .course_row"))
        .map((row) =>
            collectRowData(row, [
                "course_specialty[]",
                "course_org[]",
                "course_period[]",
                "course_grade[]",
            ])
        )
        .filter(rowHasData);

    return {
        values,
        expRows,
        courseRows,
        step: getCurrentStep ? getCurrentStep() : 0,
    };
}

function applyDraftToForm(form, draft) {
    if (!draft || !draft.values) {
        return;
    }

    const values = draft.values;
    form.querySelectorAll("input[name], select[name], textarea[name]").forEach((field) => {
        const { name } = field;
        if (!name || name === "csrf_token" || name === "captcha_input" || name.endsWith("[]")) {
            return;
        }
        if (!(name in values)) {
            return;
        }

        const savedValue = values[name];
        if (field.type === "checkbox") {
            field.checked = Boolean(savedValue);
        } else if (field.type === "radio") {
            field.checked = String(savedValue || "") === field.value;
        } else {
            field.value = savedValue == null ? "" : String(savedValue);
        }
    });

    const city = byId("city_select");
    if (city && values.city_id) {
        city.dataset.selectedCity = String(values.city_id);
    }

    restoreRows(byId("exp_container"), ".exp_row", draft.expRows || []);
    restoreRows(byId("course_container"), ".course_row", draft.courseRows || []);
}

function validateCurrentStep(stepElement) {
    if (!stepElement) {
        return true;
    }
    const fields = stepElement.querySelectorAll("input, select, textarea");
    for (const field of fields) {
        if (field.type === "hidden" || field.disabled) {
            continue;
        }
        if (!field.checkValidity()) {
            field.reportValidity();
            return false;
        }
    }
    return true;
}

function initWizard(initialStep = 0, onStepChange = null) {
    const steps = Array.from(document.querySelectorAll(".application-step"));
    const indicators = Array.from(document.querySelectorAll(".step-indicator"));
    const stepCounter = byId("application_step_counter");
    const progressBar = byId("application_progress_bar");
    const progressRoot = progressBar ? progressBar.closest(".progress") : null;
    const prevBtn = byId("prev_step_btn");
    const nextBtn = byId("next_step_btn");
    const submitBtn = byId("submit_step_btn");

    if (!steps.length || !prevBtn || !nextBtn || !submitBtn) {
        return;
    }

    let currentStep = Math.max(0, Math.min(Number(initialStep) || 0, steps.length - 1));

    function renderStep() {
        steps.forEach((step, index) => {
            step.classList.toggle("d-none", index !== currentStep);
        });

        indicators.forEach((indicator, index) => {
            indicator.classList.remove("text-bg-primary", "text-bg-secondary", "text-bg-success");
            if (index < currentStep) {
                indicator.classList.add("text-bg-success");
            } else if (index === currentStep) {
                indicator.classList.add("text-bg-primary");
            } else {
                indicator.classList.add("text-bg-secondary");
            }
        });

        if (stepCounter) {
            const template = stepCounter.dataset.stepTemplate || runtimeText("stepTemplate");
            stepCounter.textContent = template.replace("%s", String(currentStep + 1)).replace("%s", String(steps.length));
        }
        if (progressBar) {
            const progress = Math.round(((currentStep + 1) / steps.length) * 100);
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute("aria-valuenow", String(progress));
            if (progressRoot) {
                progressRoot.setAttribute("aria-valuenow", String(progress));
            }
        }
        if (onStepChange) {
            onStepChange(currentStep);
        }

        prevBtn.classList.toggle("d-none", currentStep === 0);
        nextBtn.classList.toggle("d-none", currentStep === steps.length - 1);
        submitBtn.classList.toggle("d-none", currentStep !== steps.length - 1);
    }

    nextBtn.addEventListener("click", (ev) => {
        ev.preventDefault();
        if (!validateCurrentStep(steps[currentStep])) {
            return;
        }
        if (currentStep < steps.length - 1) {
            currentStep += 1;
            renderStep();
        }
    });

    prevBtn.addEventListener("click", (ev) => {
        ev.preventDefault();
        if (currentStep > 0) {
            currentStep -= 1;
            renderStep();
        }
    });

    renderStep();
    return {
        getCurrentStep: () => currentStep,
    };
}

function init() {
    if (window.location.pathname.startsWith("/jobs/apply/thanks")) {
        clearDraft();
        return;
    }

    const form = byId("job_application_form");
    if (!form) {
        return;
    }

    const draft = readDraft();
    applyDraftToForm(form, draft);

    let wizardApi = null;
    const queueDraftSave = debounce(() => {
        writeDraft(collectFormDraft(form, () => (wizardApi ? wizardApi.getCurrentStep() : 0)));
    });

    const gov = byId("gov_select");
    const city = byId("city_select");

    if (gov && city) {
        if (gov.value) {
            loadCities(gov.value);
        }

        gov.addEventListener("change", () => {
            if (!gov.value) {
                city.innerHTML = `<option value="">${runtimeText("chooseGovernorateFirst")}</option>`;
                city.dataset.selectedCity = "";
                return;
            }
            loadCities(gov.value);
        });
    }

    const gender = byId("gender_select");
    const military = byId("military_status_select");
    if (gender && military) {
        const syncMilitary = () => {
            if (gender.value === "female") {
                military.value = "unrequired";
                military.disabled = true;
            } else {
                military.disabled = false;
            }
        };
        gender.addEventListener("change", syncMilitary);
        syncMilitary();
    }

    const expBtn = byId("add_exp");
    const expContainer = byId("exp_container");
    if (expBtn && expContainer) {
        expBtn.addEventListener("click", (ev) => {
            ev.preventDefault();
            cloneRow(expContainer, ".exp_row");
            queueDraftSave();
        });
    }

    const courseBtn = byId("add_course");
    const courseContainer = byId("course_container");
    if (courseBtn && courseContainer) {
        courseBtn.addEventListener("click", (ev) => {
            ev.preventDefault();
            cloneRow(courseContainer, ".course_row");
            queueDraftSave();
        });
    }

    const captchaImage = byId("captcha_image");
    const refreshCaptchaBtn = byId("refresh_captcha_btn");
    if (captchaImage && refreshCaptchaBtn) {
        refreshCaptchaBtn.addEventListener("click", (ev) => {
            ev.preventDefault();
            captchaImage.src = `/jobs/captcha/image?ts=${Date.now()}`;
        });
    }

    form.addEventListener("click", (ev) => {
        const btn = ev.target.closest(".remove_row");
        if (!btn) {
            return;
        }
        ev.preventDefault();

        const row = btn.closest(".exp_row, .course_row");
        if (!row) {
            return;
        }

        const expParent = row.closest("#exp_container");
        if (expParent) {
            const count = expParent.querySelectorAll(".exp_row").length;
            if (count > 1) {
                row.remove();
                queueDraftSave();
            }
            return;
        }

        const courseParent = row.closest("#course_container");
        if (courseParent) {
            const count = courseParent.querySelectorAll(".course_row").length;
            if (count > 1) {
                row.remove();
                queueDraftSave();
            }
        }
    });

    form.addEventListener("input", queueDraftSave);
    form.addEventListener("change", queueDraftSave);

    wizardApi = initWizard(draft && Number.isInteger(draft.step) ? draft.step : 0, queueDraftSave);
    queueDraftSave();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
