/** @odoo-module **/
import { loadAll } from "../core_ui/preferences";

let _savedTheme = null;

function applyThemeToLauncher(theme) {
    const launcher = document.getElementById("core_ui_launcher");
    if (!launcher) return false;
    launcher.classList.toggle("core_ui_theme_dark", theme === "dark");
    return true;
}

function observeLauncher() {
    if (!document.body) {
        let tries = 0;
        const retry = () => {
            if (document.body) {
                startObserver();
            } else if (tries < 20) {
                tries++;
                setTimeout(retry, 100);
            }
        };
        retry();
        return;
    }
    startObserver();
}

function startObserver() {
    if (window.__coreUiLauncherObserver) return;
    const observer = new MutationObserver(() => {
        if (_savedTheme !== null) {
            applyThemeToLauncher(_savedTheme);
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    window.__coreUiLauncherObserver = observer;
}

function initFromStorage() {
    const prefs = loadAll();
    if (prefs.theme) {
        _savedTheme = prefs.theme;
        applyThemeToLauncher(_savedTheme);
        observeLauncher();
    }
}

initFromStorage();

document.addEventListener("core_ui_prefs_changed", (e) => {
    const detail = e.detail || {};
    if (detail.theme) {
        _savedTheme = detail.theme;
        applyThemeToLauncher(_savedTheme);
        observeLauncher();
    }
});
