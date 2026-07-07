/** @odoo-module **/

export const THEME_PACKS = {
    modern: {
        label: "Modern",
        icon: "fa-cube",
        vars: {},
    },
    enterprise: {
        label: "Enterprise",
        icon: "fa-building",
        vars: {
            "--core-ui-primary": "#1e40af",
            "--core-ui-primary-hover": "#1e3a8a",
            "--core-ui-primary-light": "#dbeafe",
            "--core-ui-primary-subtle": "#eff6ff",
            "--core-ui-radius-md": "4px",
            "--core-ui-radius-lg": "6px",
            "--core-ui-radius-xl": "8px",
        },
    },
    medical: {
        label: "Medical",
        icon: "fa-heartbeat",
        vars: {
            "--core-ui-primary": "#0d9488",
            "--core-ui-primary-hover": "#0f766e",
            "--core-ui-primary-light": "#ccfbf1",
            "--core-ui-primary-subtle": "#f0fdfa",
            "--core-ui-success": "#10b981",
            "--core-ui-warning": "#f59e0b",
            "--core-ui-danger": "#ef4444",
            "--core-ui-info": "#06b6d4",
        },
    },
    minimal: {
        label: "Minimal",
        icon: "fa-circle-o",
        vars: {
            "--core-ui-primary": "#18181b",
            "--core-ui-primary-hover": "#27272a",
            "--core-ui-primary-light": "#f4f4f5",
            "--core-ui-primary-subtle": "#fafafa",
            "--core-ui-surface": "#ffffff",
            "--core-ui-surface-alt": "#fafafa",
            "--core-ui-border": "#d4d4d8",
            "--core-ui-radius-md": "0px",
            "--core-ui-radius-lg": "0px",
            "--core-ui-radius-xl": "0px",
            "--core-ui-shadow-sm": "none",
            "--core-ui-shadow-md": "none",
            "--core-ui-shadow-lg": "none",
        },
    },
    glass: {
        label: "Glass",
        icon: "fa-window-maximize",
        vars: {
            "--core-ui-primary": "#6366f1",
            "--core-ui-primary-hover": "#4f46e5",
            "--core-ui-primary-light": "#e0e7ff",
            "--core-ui-primary-subtle": "#eef2ff",
            "--core-ui-surface": "rgba(255,255,255,0.7)",
            "--core-ui-surface-alt": "rgba(255,255,255,0.5)",
            "--core-ui-surface-hover": "rgba(255,255,255,0.85)",
            "--core-ui-border": "rgba(255,255,255,0.3)",
            "--core-ui-border-light": "rgba(255,255,255,0.15)",
            "--core-ui-shadow-sm": "0 1px 3px rgba(0,0,0,0.08)",
            "--core-ui-shadow-md": "0 4px 12px rgba(0,0,0,0.1)",
            "--core-ui-shadow-lg": "0 8px 24px rgba(0,0,0,0.12)",
            "--core-ui-radius-md": "12px",
            "--core-ui-radius-lg": "16px",
            "--core-ui-radius-xl": "20px",
        },
    },
    material: {
        label: "Material",
        icon: "fa-google",
        vars: {
            "--core-ui-primary": "#1976d2",
            "--core-ui-primary-hover": "#1565c0",
            "--core-ui-primary-light": "#e3f2fd",
            "--core-ui-primary-subtle": "#f5f5f5",
            "--core-ui-radius-md": "4px",
            "--core-ui-radius-lg": "4px",
            "--core-ui-radius-xl": "4px",
            "--core-ui-shadow-sm": "0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)",
            "--core-ui-shadow-md": "0 3px 6px rgba(0,0,0,0.15), 0 2px 4px rgba(0,0,0,0.12)",
            "--core-ui-shadow-lg": "0 10px 20px rgba(0,0,0,0.19), 0 6px 6px rgba(0,0,0,0.12)",
            "--core-ui-transition-fast": "200ms cubic-bezier(0.4, 0, 0.2, 1)",
            "--core-ui-transition-normal": "300ms cubic-bezier(0.4, 0, 0.2, 1)",
        },
    },
    fluent: {
        label: "Fluent",
        icon: "fa-windows",
        vars: {
            "--core-ui-primary": "#0078d4",
            "--core-ui-primary-hover": "#106ebe",
            "--core-ui-primary-light": "#deecf9",
            "--core-ui-primary-subtle": "#f0f0f0",
            "--core-ui-radius-md": "2px",
            "--core-ui-radius-lg": "2px",
            "--core-ui-radius-xl": "2px",
        },
    },
    apple: {
        label: "Apple",
        icon: "fa-apple",
        vars: {
            "--core-ui-primary": "#007aff",
            "--core-ui-primary-hover": "#0066d6",
            "--core-ui-primary-light": "#e8f1ff",
            "--core-ui-primary-subtle": "#f5f5f7",
            "--core-ui-radius-md": "8px",
            "--core-ui-radius-lg": "10px",
            "--core-ui-radius-xl": "12px",
            "--core-ui-font-family": "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', sans-serif",
            "--core-ui-shadow-sm": "0 1px 3px rgba(0,0,0,0.08)",
            "--core-ui-shadow-md": "0 4px 12px rgba(0,0,0,0.1)",
            "--core-ui-shadow-lg": "0 8px 24px rgba(0,0,0,0.12)",
        },
    },
    dashboard: {
        label: "Dashboard",
        icon: "fa-dashboard",
        vars: {
            "--core-ui-primary": "#7c3aed",
            "--core-ui-primary-hover": "#6d28d9",
            "--core-ui-primary-light": "#ede9fe",
            "--core-ui-primary-subtle": "#f5f3ff",
            "--core-ui-surface": "#ffffff",
            "--core-ui-surface-alt": "#f8fafc",
            "--core-ui-sidebar-width": "260px",
            "--core-ui-radius-md": "8px",
            "--core-ui-radius-lg": "12px",
            "--core-ui-radius-xl": "16px",
        },
    },
    neutral: {
        label: "Neutral",
        icon: "fa-adjust",
        vars: {
            "--core-ui-primary": "#525252",
            "--core-ui-primary-hover": "#404040",
            "--core-ui-primary-light": "#f5f5f5",
            "--core-ui-primary-subtle": "#fafafa",
            "--core-ui-text": "#171717",
            "--core-ui-text-secondary": "#525252",
            "--core-ui-text-muted": "#a3a3a3",
        },
    },
};

export const PALETTES = {
    default: {
        label: "Odoo Default",
        vars: {},
    },
    medical_green: {
        label: "Medical Green",
        vars: {
            "--core-ui-primary": "#0d9488",
            "--core-ui-primary-hover": "#0f766e",
            "--core-ui-primary-light": "#ccfbf1",
            "--core-ui-primary-subtle": "#f0fdfa",
            "--core-ui-success": "#10b981",
            "--core-ui-warning": "#f59e0b",
            "--core-ui-danger": "#ef4444",
            "--core-ui-info": "#06b6d4",
        },
    },
    corporate_blue: {
        label: "Corporate Blue",
        vars: {
            "--core-ui-primary": "#1e40af",
            "--core-ui-primary-hover": "#1e3a8a",
            "--core-ui-primary-light": "#dbeafe",
            "--core-ui-primary-subtle": "#eff6ff",
            "--core-ui-success": "#16a34a",
            "--core-ui-warning": "#ea580c",
            "--core-ui-danger": "#dc2626",
            "--core-ui-info": "#0891b2",
        },
    },
    finance_purple: {
        label: "Finance Purple",
        vars: {
            "--core-ui-primary": "#7c3aed",
            "--core-ui-primary-hover": "#6d28d9",
            "--core-ui-primary-light": "#ede9fe",
            "--core-ui-primary-subtle": "#f5f3ff",
            "--core-ui-success": "#059669",
            "--core-ui-warning": "#d97706",
            "--core-ui-danger": "#dc2626",
            "--core-ui-info": "#0284c7",
        },
    },
    warm_orange: {
        label: "Warm Orange",
        vars: {
            "--core-ui-primary": "#ea580c",
            "--core-ui-primary-hover": "#c2410c",
            "--core-ui-primary-light": "#ffedd5",
            "--core-ui-primary-subtle": "#fff7ed",
            "--core-ui-success": "#16a34a",
            "--core-ui-warning": "#ca8a04",
            "--core-ui-danger": "#dc2626",
            "--core-ui-info": "#0891b2",
        },
    },
    dark_professional: {
        label: "Dark Professional",
        vars: {
            "--core-ui-primary": "#1e293b",
            "--core-ui-primary-hover": "#0f172a",
            "--core-ui-primary-light": "#f1f5f9",
            "--core-ui-primary-subtle": "#f8fafc",
            "--core-ui-surface": "#ffffff",
            "--core-ui-text": "#0f172a",
            "--core-ui-text-secondary": "#475569",
            "--core-ui-text-muted": "#94a3b8",
        },
    },
    neutral_gray: {
        label: "Neutral Gray",
        vars: {
            "--core-ui-primary": "#525252",
            "--core-ui-primary-hover": "#404040",
            "--core-ui-primary-light": "#f5f5f5",
            "--core-ui-primary-subtle": "#fafafa",
            "--core-ui-success": "#737373",
            "--core-ui-warning": "#a3a3a3",
            "--core-ui-danger": "#737373",
            "--core-ui-info": "#737373",
        },
    },
    high_contrast: {
        label: "High Contrast",
        vars: {
            "--core-ui-primary": "#000000",
            "--core-ui-primary-hover": "#1a1a1a",
            "--core-ui-primary-light": "#ffffff",
            "--core-ui-primary-subtle": "#f5f5f5",
            "--core-ui-text": "#000000",
            "--core-ui-text-secondary": "#1a1a1a",
            "--core-ui-text-muted": "#404040",
            "--core-ui-surface": "#ffffff",
            "--core-ui-surface-alt": "#f5f5f5",
            "--core-ui-border": "#000000",
            "--core-ui-border-light": "#737373",
        },
    },
};

export const TYPOGRAPHY = {
    default: {
        label: "Default",
        family: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    },
    inter: {
        label: "Inter",
        family: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    },
    ibm_plex: {
        label: "IBM Plex Sans",
        family: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    },
    roboto: {
        label: "Roboto",
        family: "'Roboto', -apple-system, BlinkMacSystemFont, sans-serif",
    },
    sf_pro: {
        label: "SF Pro",
        family: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', sans-serif",
    },
    poppins: {
        label: "Poppins",
        family: "'Poppins', -apple-system, BlinkMacSystemFont, sans-serif",
    },
    nunito: {
        label: "Nunito",
        family: "'Nunito', -apple-system, BlinkMacSystemFont, sans-serif",
    },
    cairo: {
        label: "Cairo",
        family: "'Cairo', -apple-system, BlinkMacSystemFont, sans-serif",
    },
};

export const SPACING = {
    compact: {
        label: "Compact",
        vars: {
            "--core-ui-space-xs": "0.125rem",
            "--core-ui-space-sm": "0.25rem",
            "--core-ui-space-md": "0.5rem",
            "--core-ui-space-lg": "1rem",
            "--core-ui-space-xl": "1.5rem",
            "--core-ui-space-2xl": "2rem",
            "--core-ui-space-3xl": "3rem",
        },
    },
    default: {
        label: "Default",
        vars: {},
    },
    comfortable: {
        label: "Comfortable",
        vars: {
            "--core-ui-space-xs": "0.375rem",
            "--core-ui-space-sm": "0.625rem",
            "--core-ui-space-md": "1.25rem",
            "--core-ui-space-lg": "1.75rem",
            "--core-ui-space-xl": "2.5rem",
            "--core-ui-space-2xl": "3.5rem",
            "--core-ui-space-3xl": "5rem",
        },
    },
    relaxed: {
        label: "Relaxed",
        vars: {
            "--core-ui-space-xs": "0.5rem",
            "--core-ui-space-sm": "0.75rem",
            "--core-ui-space-md": "1.5rem",
            "--core-ui-space-lg": "2rem",
            "--core-ui-space-xl": "3rem",
            "--core-ui-space-2xl": "4rem",
            "--core-ui-space-3xl": "6rem",
        },
    },
    enterprise: {
        label: "Enterprise",
        vars: {
            "--core-ui-space-xs": "0.25rem",
            "--core-ui-space-sm": "0.5rem",
            "--core-ui-space-md": "1rem",
            "--core-ui-space-lg": "1.5rem",
            "--core-ui-space-xl": "2rem",
            "--core-ui-space-2xl": "3rem",
            "--core-ui-space-3xl": "4rem",
            "--core-ui-sidebar-width": "320px",
            "--core-ui-inspector-width": "400px",
        },
    },
};

export const RADIUS = {
    sharp: { label: "Sharp", vars: { "--core-ui-radius-sm": "0px", "--core-ui-radius-md": "0px", "--core-ui-radius-lg": "0px", "--core-ui-radius-xl": "0px", "--core-ui-radius-2xl": "0px" } },
    px4: { label: "4px", vars: { "--core-ui-radius-sm": "2px", "--core-ui-radius-md": "4px", "--core-ui-radius-lg": "4px", "--core-ui-radius-xl": "4px", "--core-ui-radius-2xl": "4px" } },
    px8: { label: "8px", vars: { "--core-ui-radius-sm": "4px", "--core-ui-radius-md": "6px", "--core-ui-radius-lg": "8px", "--core-ui-radius-xl": "8px", "--core-ui-radius-2xl": "8px" } },
    px12: { label: "12px", vars: { "--core-ui-radius-sm": "6px", "--core-ui-radius-md": "8px", "--core-ui-radius-lg": "12px", "--core-ui-radius-xl": "12px", "--core-ui-radius-2xl": "12px" } },
    px16: { label: "16px", vars: { "--core-ui-radius-sm": "8px", "--core-ui-radius-md": "10px", "--core-ui-radius-lg": "12px", "--core-ui-radius-xl": "16px", "--core-ui-radius-2xl": "16px" } },
    pill: { label: "Pill", vars: { "--core-ui-radius-sm": "9999px", "--core-ui-radius-md": "9999px", "--core-ui-radius-lg": "9999px", "--core-ui-radius-xl": "9999px", "--core-ui-radius-2xl": "9999px" } },
};

export const SHADOWS = {
    none: { label: "None", vars: { "--core-ui-shadow-sm": "none", "--core-ui-shadow-md": "none", "--core-ui-shadow-lg": "none", "--core-ui-shadow-xl": "none", "--core-ui-shadow-2xl": "none" } },
    soft: { label: "Soft", vars: { "--core-ui-shadow-sm": "0 1px 2px rgba(0,0,0,0.05)", "--core-ui-shadow-md": "0 4px 6px rgba(0,0,0,0.07)", "--core-ui-shadow-lg": "0 10px 15px rgba(0,0,0,0.07)", "--core-ui-shadow-xl": "0 20px 25px rgba(0,0,0,0.08)", "--core-ui-shadow-2xl": "0 25px 50px rgba(0,0,0,0.1)" } },
    medium: { label: "Medium", vars: { "--core-ui-shadow-sm": "0 1px 3px rgba(0,0,0,0.1)", "--core-ui-shadow-md": "0 4px 8px rgba(0,0,0,0.12)", "--core-ui-shadow-lg": "0 10px 20px rgba(0,0,0,0.12)", "--core-ui-shadow-xl": "0 20px 30px rgba(0,0,0,0.14)", "--core-ui-shadow-2xl": "0 25px 50px rgba(0,0,0,0.18)" } },
    strong: { label: "Strong", vars: { "--core-ui-shadow-sm": "0 2px 4px rgba(0,0,0,0.15)", "--core-ui-shadow-md": "0 6px 12px rgba(0,0,0,0.18)", "--core-ui-shadow-lg": "0 12px 24px rgba(0,0,0,0.2)", "--core-ui-shadow-xl": "0 24px 36px rgba(0,0,0,0.22)", "--core-ui-shadow-2xl": "0 32px 64px rgba(0,0,0,0.25)" } },
    floating: { label: "Floating", vars: { "--core-ui-shadow-sm": "0 4px 6px rgba(0,0,0,0.07)", "--core-ui-shadow-md": "0 10px 20px rgba(0,0,0,0.08)", "--core-ui-shadow-lg": "0 20px 30px rgba(0,0,0,0.1)", "--core-ui-shadow-xl": "0 30px 40px rgba(0,0,0,0.12)", "--core-ui-shadow-2xl": "0 40px 60px rgba(0,0,0,0.15)" } },
    material: { label: "Material", vars: { "--core-ui-shadow-sm": "0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)", "--core-ui-shadow-md": "0 3px 6px rgba(0,0,0,0.15), 0 2px 4px rgba(0,0,0,0.12)", "--core-ui-shadow-lg": "0 10px 20px rgba(0,0,0,0.19), 0 6px 6px rgba(0,0,0,0.12)", "--core-ui-shadow-xl": "0 14px 28px rgba(0,0,0,0.25), 0 10px 10px rgba(0,0,0,0.22)", "--core-ui-shadow-2xl": "0 19px 38px rgba(0,0,0,0.3), 0 15px 12px rgba(0,0,0,0.22)" } },
    glass: { label: "Glass", vars: { "--core-ui-shadow-sm": "0 1px 3px rgba(0,0,0,0.06)", "--core-ui-shadow-md": "0 4px 12px rgba(0,0,0,0.08)", "--core-ui-shadow-lg": "0 8px 24px rgba(0,0,0,0.1)", "--core-ui-shadow-xl": "0 16px 32px rgba(0,0,0,0.12)", "--core-ui-shadow-2xl": "0 24px 48px rgba(0,0,0,0.15)" } },
};

export const BORDERS = {
    minimal: {
        label: "Minimal",
        vars: {
            "--core-ui-border": "#f0f0f0",
            "--core-ui-border-light": "#f5f5f5",
        },
    },
    outlined: {
        label: "Outlined",
        vars: {
            "--core-ui-border": "#e2e8f0",
            "--core-ui-border-light": "#f1f5f9",
        },
    },
    strong: {
        label: "Strong",
        vars: {
            "--core-ui-border": "#94a3b8",
            "--core-ui-border-light": "#cbd5e1",
        },
    },
    soft: {
        label: "Soft",
        vars: {
            "--core-ui-border": "rgba(0,0,0,0.08)",
            "--core-ui-border-light": "rgba(0,0,0,0.04)",
        },
    },
};

export const GRADIENTS = {
    off: {
        label: "Off",
        vars: {},
    },
    subtle: {
        label: "Subtle",
        vars: {},
    },
    modern: {
        label: "Modern",
        vars: {},
    },
    premium: {
        label: "Premium",
        vars: {},
    },
    vibrant: {
        label: "Vibrant",
        vars: {},
    },
};

export const MOTION = {
    off: { label: "Off", vars: { "--core-ui-transition-fast": "0ms", "--core-ui-transition-normal": "0ms", "--core-ui-transition-slow": "0ms", "--core-ui-transition-spring": "0ms" } },
    fast: { label: "Fast", vars: { "--core-ui-transition-fast": "100ms", "--core-ui-transition-normal": "150ms", "--core-ui-transition-slow": "200ms", "--core-ui-transition-spring": "300ms" } },
    normal: { label: "Normal", vars: {} },
    premium: { label: "Premium", vars: { "--core-ui-transition-fast": "200ms cubic-bezier(0.4, 0, 0.2, 1)", "--core-ui-transition-normal": "350ms cubic-bezier(0.4, 0, 0.2, 1)", "--core-ui-transition-slow": "500ms cubic-bezier(0.4, 0, 0.2, 1)", "--core-ui-transition-spring": "600ms cubic-bezier(0.34, 1.56, 0.64, 1)" } },
};

export const HOVER_EFFECTS = {
    subtle: { label: "Subtle" },
    modern: { label: "Modern" },
    expressive: { label: "Expressive" },
};

export const DEFAULT_LAB_STATE = {
    theme: "modern",
    palette: "default",
    typography: "default",
    spacing: "default",
    radius: "px8",
    shadow: "soft",
    border: "outlined",
    gradient: "subtle",
    motion: "normal",
    hoverEffects: "modern",
    accessibility: {
        highContrast: false,
        largeFont: false,
        touchMode: false,
        reducedMotion: false,
    },
    previewMode: "component",
};

export const BUILTIN_PROFILES = {
    default: {
        label: "Core UI Default",
        config: {
            theme: "modern",
            palette: "default",
            typography: "default",
            spacing: "default",
            radius: "px8",
            shadow: "soft",
            border: "outlined",
            gradient: "subtle",
            motion: "normal",
            hoverEffects: "modern",
        },
    },
    enterprise_default: {
        label: "Enterprise Default",
        config: {
            theme: "enterprise",
            palette: "corporate_blue",
            typography: "inter",
            spacing: "enterprise",
            radius: "px4",
            shadow: "medium",
            border: "outlined",
            gradient: "off",
            motion: "normal",
            hoverEffects: "subtle",
        },
    },
    medical_green: {
        label: "Medical Green",
        config: {
            theme: "medical",
            palette: "medical_green",
            typography: "inter",
            spacing: "default",
            radius: "px8",
            shadow: "soft",
            border: "outlined",
            gradient: "subtle",
            motion: "normal",
            hoverEffects: "modern",
        },
    },
    modern_glass: {
        label: "Modern Glass",
        config: {
            theme: "glass",
            palette: "default",
            typography: "sf_pro",
            spacing: "comfortable",
            radius: "px12",
            shadow: "glass",
            border: "soft",
            gradient: "premium",
            motion: "premium",
            hoverEffects: "expressive",
        },
    },
    minimal: {
        label: "Minimal",
        config: {
            theme: "minimal",
            palette: "neutral_gray",
            typography: "inter",
            spacing: "compact",
            radius: "sharp",
            shadow: "none",
            border: "minimal",
            gradient: "off",
            motion: "fast",
            hoverEffects: "subtle",
        },
    },
    finance: {
        label: "Finance",
        config: {
            theme: "dashboard",
            palette: "finance_purple",
            typography: "ibm_plex",
            spacing: "default",
            radius: "px4",
            shadow: "medium",
            border: "strong",
            gradient: "off",
            motion: "normal",
            hoverEffects: "modern",
        },
    },
    dashboard: {
        label: "Dashboard",
        config: {
            theme: "dashboard",
            palette: "default",
            typography: "inter",
            spacing: "default",
            radius: "px8",
            shadow: "soft",
            border: "outlined",
            gradient: "subtle",
            motion: "normal",
            hoverEffects: "modern",
        },
    },
};

function getAllVarsFromConfig(configMap) {
    const all = new Set();
    for (const entry of Object.values(configMap)) {
        if (entry.vars) {
            for (const k of Object.keys(entry.vars)) {
                all.add(k);
            }
        }
    }
    return all;
}

const FONT_VAR = "--core-ui-font-family";
const A11Y_FONT_VARS = ["--core-ui-font-size-base", "--core-ui-font-size-sm", "--core-ui-font-size-xs"];
const A11Y_MOTION_VARS = ["--core-ui-transition-fast", "--core-ui-transition-normal", "--core-ui-transition-slow", "--core-ui-transition-spring"];
const A11Y_TOUCH_VARS = ["--core-ui-touch-target-min", "--core-ui-space-xs", "--core-ui-space-sm", "--core-ui-space-md"];

function isDefault(key) {
    return key === "default" || key === "off";
}

function collectConfigVars(configMap, key, varsToSet, varsToRemove) {
    const entry = configMap[key];
    if (entry && entry.vars) {
        for (const [vk, vv] of Object.entries(entry.vars)) {
            varsToSet[vk] = vv;
        }
    }
    if (isDefault(key)) {
        for (const vk of getAllVarsFromConfig(configMap)) {
            if (!(vk in varsToSet)) {
                varsToRemove.add(vk);
            }
        }
    }
}

export function applyDesignVars(el, labState) {
    if (!el) return;

    const varsToSet = {};
    const varsToRemove = new Set();

    collectConfigVars(THEME_PACKS, labState.theme, varsToSet, varsToRemove);
    collectConfigVars(PALETTES, labState.palette, varsToSet, varsToRemove);
    collectConfigVars(SPACING, labState.spacing, varsToSet, varsToRemove);
    collectConfigVars(RADIUS, labState.radius, varsToSet, varsToRemove);
    collectConfigVars(SHADOWS, labState.shadow, varsToSet, varsToRemove);
    collectConfigVars(BORDERS, labState.border, varsToSet, varsToRemove);
    collectConfigVars(MOTION, labState.motion, varsToSet, varsToRemove);

    if (labState.typography && labState.typography !== "default") {
        const typo = TYPOGRAPHY[labState.typography];
        if (typo) {
            varsToSet[FONT_VAR] = typo.family;
        }
    } else {
        varsToRemove.add(FONT_VAR);
    }

    if (labState.accessibility) {
        const a11y = labState.accessibility;
        if (a11y.highContrast) {
            for (const [vk, vv] of Object.entries(PALETTES.high_contrast.vars)) {
                varsToSet[vk] = vv;
            }
        }
        if (a11y.largeFont) {
            varsToSet[A11Y_FONT_VARS[0]] = "1.125rem";
            varsToSet[A11Y_FONT_VARS[1]] = "1rem";
            varsToSet[A11Y_FONT_VARS[2]] = "0.875rem";
        } else {
            for (const vk of A11Y_FONT_VARS) {
                varsToRemove.add(vk);
            }
        }
        if (a11y.reducedMotion) {
            for (const vk of A11Y_MOTION_VARS) {
                varsToSet[vk] = "0ms";
            }
        } else {
            for (const vk of A11Y_MOTION_VARS) {
                varsToRemove.add(vk);
            }
        }
        if (a11y.touchMode) {
            varsToSet["--core-ui-touch-target-min"] = "44px";
            varsToSet["--core-ui-space-xs"] = "0.5rem";
            varsToSet["--core-ui-space-sm"] = "0.75rem";
            varsToSet["--core-ui-space-md"] = "1.25rem";
        } else {
            for (const vk of A11Y_TOUCH_VARS) {
                varsToRemove.add(vk);
            }
        }
    } else {
        for (const vk of [...A11Y_FONT_VARS, ...A11Y_MOTION_VARS, ...A11Y_TOUCH_VARS]) {
            varsToRemove.add(vk);
        }
    }

    for (const vk of varsToRemove) {
        if (!(vk in varsToSet)) {
            el.style.removeProperty(vk);
        }
    }

    for (const [vk, vv] of Object.entries(varsToSet)) {
        if (vv !== undefined && vv !== null) {
            el.style.setProperty(vk, vv);
        }
    }
}

export function getActiveProfileConfig(labState) {
    return {
        theme: labState.theme,
        palette: labState.palette,
        typography: labState.typography,
        spacing: labState.spacing,
        radius: labState.radius,
        shadow: labState.shadow,
        border: labState.border,
        gradient: labState.gradient,
        motion: labState.motion,
        hoverEffects: labState.hoverEffects,
    };
}

export function getProfileVars(profileConfig) {
    const varsToSet = {};
    const varsToRemove = new Set();

    collectConfigVars(THEME_PACKS, profileConfig.theme, varsToSet, varsToRemove);
    collectConfigVars(PALETTES, profileConfig.palette, varsToSet, varsToRemove);
    collectConfigVars(SPACING, profileConfig.spacing, varsToSet, varsToRemove);
    collectConfigVars(RADIUS, profileConfig.radius, varsToSet, varsToRemove);
    collectConfigVars(SHADOWS, profileConfig.shadow, varsToSet, varsToRemove);
    collectConfigVars(BORDERS, profileConfig.border, varsToSet, varsToRemove);
    collectConfigVars(MOTION, profileConfig.motion, varsToSet, varsToRemove);

    if (profileConfig.typography && profileConfig.typography !== "default") {
        const typo = TYPOGRAPHY[profileConfig.typography];
        if (typo) {
            varsToSet[FONT_VAR] = typo.family;
        }
    }

    const result = {};
    for (const [vk, vv] of Object.entries(varsToSet)) {
        if (vv !== undefined && vv !== null) {
            result[vk] = vv;
        }
    }
    return result;
}

export function generateAiPrompt(componentId, labState) {
    const config = getActiveProfileConfig(labState);
    const lines = [
        `Use component:`,
        componentId,
        ``,
        `Design Profile:`,
        ...Object.entries(config).map(([k, v]) => `  ${k}: ${v}`),
        ``,
        `Reuse the existing Core UI component.`,
        `Do not recreate it.`,
        `Respect the selected Design Lab profile.`,
        `Do not duplicate styles.`,
        `Keep centralized architecture.`,
    ];
    return lines.join("\n");
}
