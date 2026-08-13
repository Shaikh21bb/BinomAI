const fs = require('fs');

const binomTheme = {
    "colors": {
            "on-tertiary-fixed": "#1b1c1c",
            "outline-variant": "#c7c4d8",
            "surface": "#f9f9f9",
            "inverse-primary": "#c3c0ff",
            "secondary-fixed": "#e5e2e1",
            "on-surface-variant": "#464555",
            "tertiary": "#484848",
            "background": "#f9f9f9",
            "surface-dim": "#dadada",
            "secondary-container": "#e5e2e1",
            "on-tertiary": "#ffffff",
            "on-error-container": "#93000a",
            "on-background": "#1a1c1c",
            "on-primary-fixed": "#0f0069",
            "on-error": "#ffffff",
            "tertiary-fixed-dim": "#c7c6c6",
            "surface-bright": "#f9f9f9",
            "on-tertiary-container": "#dcdbdb",
            "primary": "#3525cd",
            "surface-container-highest": "#e2e2e2",
            "outline": "#777587",
            "on-secondary-container": "#656464",
            "on-secondary-fixed-variant": "#474646",
            "surface-container": "#eeeeee",
            "surface-container-low": "#f3f3f3",
            "surface-container-high": "#e8e8e8",
            "on-surface": "#1a1c1c",
            "on-primary-container": "#dad7ff",
            "error-container": "#ffdad6",
            "on-primary-fixed-variant": "#3323cc",
            "primary-container": "#4f46e5",
            "on-secondary-fixed": "#1c1b1b",
            "secondary": "#5f5e5e",
            "primary-fixed-dim": "#c3c0ff",
            "tertiary-container": "#606060",
            "surface-tint": "#4d44e3",
            "surface-container-lowest": "#ffffff",
            "inverse-surface": "#2f3131",
            "inverse-on-surface": "#f1f1f1",
            "error": "#ba1a1a",
            "primary-fixed": "#e2dfff",
            "secondary-fixed-dim": "#c8c6c5",
            "on-tertiary-fixed-variant": "#464747",
            "on-primary": "#ffffff",
            "surface-variant": "#e2e2e2",
            "on-secondary": "#ffffff",
            "tertiary-fixed": "#e4e2e2"
    },
    "borderRadius": {
            "DEFAULT": "0.125rem",
            "lg": "0.25rem",
            "xl": "0.5rem",
            "full": "0.75rem"
    },
    "spacing": {
            "unit": "4px",
            "stack-gap-md": "16px",
            "section-padding": "48px",
            "gutter": "16px",
            "container-margin": "32px",
            "stack-gap-sm": "8px"
    },
    "fontFamily": {
            "mono-sm": ["JetBrains Mono", "monospace"],
            "body-lg": ["Inter", "sans-serif"],
            "headline-xl": ["Inter", "sans-serif"],
            "headline-md": ["Inter", "sans-serif"],
            "headline-lg": ["Inter", "sans-serif"],
            "label-md": ["Inter", "sans-serif"],
            "body-sm": ["Inter", "sans-serif"],
            "body-md": ["Inter", "sans-serif"]
    },
    "fontSize": {
            "mono-sm": ["12px", {"lineHeight": "16px", "letterSpacing": "0em", "fontWeight": "400"}],
            "body-lg": ["16px", {"lineHeight": "24px", "letterSpacing": "-0.01em", "fontWeight": "400"}],
            "headline-xl": ["32px", {"lineHeight": "40px", "letterSpacing": "-0.03em", "fontWeight": "600"}],
            "headline-md": ["20px", {"lineHeight": "28px", "letterSpacing": "-0.02em", "fontWeight": "600"}],
            "headline-lg": ["24px", {"lineHeight": "32px", "letterSpacing": "-0.02em", "fontWeight": "600"}],
            "label-md": ["12px", {"lineHeight": "16px", "letterSpacing": "0.01em", "fontWeight": "500"}],
            "body-sm": ["13px", {"lineHeight": "18px", "letterSpacing": "0em", "fontWeight": "400"}],
            "body-md": ["14px", {"lineHeight": "20px", "letterSpacing": "-0.01em", "fontWeight": "400"}]
    }
};

const tenderProTheme = {
    "colors": {
        "surface-container-highest": "#dae2fd",
        "surface-container": "#eaedff",
        "inverse-primary": "#b4c5ff",
        "on-error-container": "#93000a",
        "on-tertiary-container": "#ffede6",
        "tertiary": "#943700",
        "error-container": "#ffdad6",
        "outline-variant": "#c3c6d7",
        "on-primary-fixed-variant": "#003ea8",
        "on-error": "#ffffff",
        "tertiary-fixed-dim": "#ffb596",
        "surface-container-high": "#e2e7ff",
        "inverse-on-surface": "#eef0ff",
        "surface-variant": "#dae2fd",
        "surface-dim": "#d2d9f4",
        "on-tertiary": "#ffffff",
        "on-primary": "#ffffff",
        "on-secondary-container": "#57657a",
        "surface-bright": "#faf8ff",
        "surface": "#faf8ff",
        "secondary-fixed-dim": "#b9c7df",
        "primary": "#004ac6",
        "background": "#faf8ff",
        "on-tertiary-fixed": "#360f00",
        "on-background": "#131b2e",
        "on-primary-container": "#eeefff",
        "primary-fixed-dim": "#b4c5ff",
        "outline": "#737686",
        "secondary-fixed": "#d5e3fc",
        "on-secondary": "#ffffff",
        "on-surface-variant": "#434655",
        "error": "#ba1a1a",
        "on-secondary-fixed-variant": "#3a485b",
        "tertiary-container": "#bc4800",
        "primary-fixed": "#dbe1ff",
        "surface-tint": "#0053db",
        "secondary-container": "#d5e3fc",
        "surface-container-low": "#f2f3ff",
        "surface-container-lowest": "#ffffff",
        "on-secondary-fixed": "#0d1c2e",
        "tertiary-fixed": "#ffdbcd",
        "secondary": "#515f74",
        "inverse-surface": "#283044",
        "on-primary-fixed": "#00174b",
        "primary-container": "#2563eb",
        "on-tertiary-fixed-variant": "#7d2d00",
        "on-surface": "#131b2e"
    },
    "borderRadius": {
        "DEFAULT": "0.125rem",
        "lg": "0.25rem",
        "xl": "0.5rem",
        "full": "0.75rem"
    },
    "spacing": {
        "container-max": "1440px",
        "stack-md": "16px",
        "unit": "4px",
        "gutter": "24px",
        "stack-lg": "32px",
        "stack-sm": "8px",
        "margin-page": "40px",
        "section-padding": "48px",
        "container-margin": "32px",
        "stack-gap-md": "16px",
        "stack-gap-sm": "8px"
    },
    "fontFamily": {
        "headline-lg": ["Inter"],
        "body-md": ["Inter"],
        "display": ["Inter"],
        "headline-md": ["Inter"],
        "mono-sm": ["JetBrains Mono"],
        "label-md": ["Geist"],
        "body-lg": ["Inter"],
        "headline-xl": ["Inter"],
        "body-sm": ["Inter"]
    },
    "fontSize": {
        "headline-lg": ["24px", { "lineHeight": "32px", "letterSpacing": "-0.015em", "fontWeight": "600" }],
        "body-md": ["14px", { "lineHeight": "20px", "fontWeight": "400" }],
        "display": ["36px", { "lineHeight": "44px", "letterSpacing": "-0.02em", "fontWeight": "600" }],
        "headline-md": ["20px", { "lineHeight": "28px", "letterSpacing": "-0.01em", "fontWeight": "600" }],
        "mono-sm": ["12px", { "lineHeight": "18px", "fontWeight": "400" }],
        "label-md": ["12px", { "lineHeight": "16px", "letterSpacing": "0.02em", "fontWeight": "500" }],
        "body-lg": ["16px", { "lineHeight": "24px", "fontWeight": "400" }],
        "headline-xl": ["32px", { "lineHeight": "40px", "letterSpacing": "-0.03em", "fontWeight": "600" }],
        "body-sm": ["13px", { "lineHeight": "18px", "letterSpacing": "0em", "fontWeight": "400" }]
    }
};

let css = '@import "tailwindcss";\n\n@theme {\n';

// Add all variables as default (from tenderProTheme, plus binom missing ones)
const allColors = new Set([...Object.keys(tenderProTheme.colors), ...Object.keys(binomTheme.colors)]);
for (const key of allColors) {
    const val = tenderProTheme.colors[key] || binomTheme.colors[key];
    css += '  --color-' + key + ': ' + val + ';\n';
}

const allRadii = new Set([...Object.keys(tenderProTheme.borderRadius), ...Object.keys(binomTheme.borderRadius)]);
for (const key of allRadii) {
    const val = tenderProTheme.borderRadius[key] || binomTheme.borderRadius[key];
    css += '  --radius-' + key + ': ' + val + ';\n';
}

const allSpacing = new Set([...Object.keys(tenderProTheme.spacing), ...Object.keys(binomTheme.spacing)]);
for (const key of allSpacing) {
    const val = tenderProTheme.spacing[key] || binomTheme.spacing[key];
    css += '  --spacing-' + key + ': ' + val + ';\n';
}

// Fonts
css += '\n  --font-mono-sm: "JetBrains Mono", monospace;\n';
css += '  --font-body-lg: "Inter", sans-serif;\n';
css += '  --font-headline-xl: "Inter", sans-serif;\n';
css += '  --font-headline-md: "Inter", sans-serif;\n';
css += '  --font-headline-lg: "Inter", sans-serif;\n';
css += '  --font-label-md: "Inter", sans-serif;\n';
css += '  --font-body-sm: "Inter", sans-serif;\n';
css += '  --font-body-md: "Inter", sans-serif;\n';
css += '  --font-display: "Inter", sans-serif;\n';
css += '}\n\n';

// Now create the overrides for .theme-binom
css += '@layer base {\n';
css += '  .theme-binom {\n';
for (const key of Object.keys(binomTheme.colors)) {
    if (binomTheme.colors[key] !== tenderProTheme.colors[key]) {
        css += '    --color-' + key + ': ' + binomTheme.colors[key] + ';\n';
    }
}
for (const key of Object.keys(binomTheme.spacing)) {
    if (binomTheme.spacing[key] !== tenderProTheme.spacing[key]) {
        css += '    --spacing-' + key + ': ' + binomTheme.spacing[key] + ';\n';
    }
}
css += '  }\n';

css += '  .theme-tenderpro {\n';
for (const key of Object.keys(tenderProTheme.colors)) {
    if (binomTheme.colors[key] !== tenderProTheme.colors[key]) {
        css += '    --color-' + key + ': ' + tenderProTheme.colors[key] + ';\n';
    }
}
for (const key of Object.keys(tenderProTheme.spacing)) {
    if (binomTheme.spacing[key] !== tenderProTheme.spacing[key]) {
        css += '    --spacing-' + key + ': ' + tenderProTheme.spacing[key] + ';\n';
    }
}
css += '  }\n';
css += '}\n\n';

// Now add the font size utilities from both themes
css += '/* Typography Utilities */\n';
css += '@utility font-mono-sm { font-family: var(--font-mono-sm); }\n';
css += '@utility font-body-lg { font-family: var(--font-body-lg); }\n';
css += '@utility font-headline-xl { font-family: var(--font-headline-xl); }\n';
css += '@utility font-headline-md { font-family: var(--font-headline-md); }\n';
css += '@utility font-headline-lg { font-family: var(--font-headline-lg); }\n';
css += '@utility font-label-md { font-family: var(--font-label-md); }\n';
css += '@utility font-body-sm { font-family: var(--font-body-sm); }\n';
css += '@utility font-body-md { font-family: var(--font-body-md); }\n';
css += '@utility font-display { font-family: var(--font-display); }\n\n';

// Add binom typography sizes scoped
css += '.theme-binom {\n';
for(const [key, val] of Object.entries(binomTheme.fontSize)) {
    css += '  --' + key + '-size: ' + val[0] + ';\n';
    css += '  --' + key + '-lh: ' + val[1].lineHeight + ';\n';
    css += '  --' + key + '-ls: ' + (val[1].letterSpacing || 'normal') + ';\n';
    css += '  --' + key + '-fw: ' + val[1].fontWeight + ';\n';
}
css += '}\n\n';

// Add tenderpro typography sizes scoped
css += '.theme-tenderpro {\n';
for(const [key, val] of Object.entries(tenderProTheme.fontSize)) {
    css += '  --' + key + '-size: ' + val[0] + ';\n';
    css += '  --' + key + '-lh: ' + val[1].lineHeight + ';\n';
    css += '  --' + key + '-ls: ' + (val[1].letterSpacing || 'normal') + ';\n';
    css += '  --' + key + '-fw: ' + val[1].fontWeight + ';\n';
}
css += '}\n\n';

// Generate the text- utilities using these variables
for(const key of new Set([...Object.keys(binomTheme.fontSize), ...Object.keys(tenderProTheme.fontSize)])) {
    css += '@utility text-' + key + ' {\n';
    css += '  font-size: var(--' + key + '-size);\n';
    css += '  line-height: var(--' + key + '-lh);\n';
    css += '  letter-spacing: var(--' + key + '-ls);\n';
    css += '  font-weight: var(--' + key + '-fw);\n';
    css += '}\n';
}

css += '\n/* Custom Utilities */\n';
css += '::-webkit-scrollbar { width: 4px; height: 4px; }\n';
css += '::-webkit-scrollbar-track { background: transparent; }\n';
css += '::-webkit-scrollbar-thumb { background: var(--color-secondary-fixed); border-radius: 4px; }\n';
css += '::-webkit-scrollbar-thumb:hover { background: var(--color-outline-variant); }\n\n';
css += '@utility border-crisp { border-width: 1px; border-style: solid; }\n';

fs.writeFileSync('src/app/globals.css', css);
console.log('globals.css generated!');
