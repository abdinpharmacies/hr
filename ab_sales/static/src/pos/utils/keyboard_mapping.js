/** @odoo-module **/

const ARABIC_TO_US_QWERTY_MAP = Object.freeze({
    "\u0630": "`",
    "\u0636": "q",
    "\u0635": "w",
    "\u062B": "e",
    "\u0642": "r",
    "\u0641": "t",
    "\u063A": "y",
    "\u0639": "u",
    "\u0647": "i",
    "\u062E": "o",
    "\u062D": "p",
    "\u062C": "[",
    "\u062F": "]",
    "\u0634": "a",
    "\u0633": "s",
    "\u064A": "d",
    "\u06CC": "d",
    "\u0628": "f",
    "\u0644": "g",
    "\u0627": "h",
    "\u062A": "j",
    "\u0646": "k",
    "\u0645": "l",
    "\u0643": ";",
    "\u06A9": ";",
    "\u0637": "'",
    "\u0626": "z",
    "\u0621": "x",
    "\u0624": "c",
    "\u0631": "v",
    "\u0649": "n",
    "\u0629": "m",
    "\u0648": ",",
    "\u0632": ".",
    "\u0638": "/",
    "\u060C": ",",
    "\u061B": ";",
    "\u061F": "/",
});

const ARABIC_CHAR_RE = /[\u0600-\u06FF]/;
const LATIN_KEY_CHAR_RE = /[A-Za-z`\[\];',./]/;
const LAM_ALEF_REPLACEMENTS = Object.freeze({
    "\u0644\u0627": "b",
    "\uFEF5": "b",
    "\uFEF6": "b",
    "\uFEF7": "b",
    "\uFEF8": "b",
    "\uFEF9": "b",
    "\uFEFA": "b",
    "\uFEFB": "b",
    "\uFEFC": "b",
});
const US_TO_ARABIC_QWERTY_MAP = Object.freeze({
    "`": "\u0630",
    "q": "\u0636",
    "w": "\u0635",
    "e": "\u062B",
    "r": "\u0642",
    "t": "\u0641",
    "y": "\u063A",
    "u": "\u0639",
    "i": "\u0647",
    "o": "\u062E",
    "p": "\u062D",
    "[": "\u062C",
    "]": "\u062F",
    "a": "\u0634",
    "s": "\u0633",
    "d": "\u064A",
    "f": "\u0628",
    "g": "\u0644",
    "h": "\u0627",
    "j": "\u062A",
    "k": "\u0646",
    "l": "\u0645",
    ";": "\u0643",
    "'": "\u0637",
    "z": "\u0626",
    "x": "\u0621",
    "c": "\u0624",
    "v": "\u0631",
    "b": "\u0644\u0627",
    "n": "\u0649",
    "m": "\u0629",
    ",": "\u0648",
    ".": "\u0632",
    "/": "\u0638",
});

export function hasArabicChars(text) {
    return ARABIC_CHAR_RE.test(String(text || ""));
}

export function hasLatinKeyboardChars(text) {
    return LATIN_KEY_CHAR_RE.test(String(text || ""));
}

export function mapArabicToUsQwerty(text) {
    let normalized = String(text || "");
    for (const [source, target] of Object.entries(LAM_ALEF_REPLACEMENTS)) {
        normalized = normalized.split(source).join(target);
    }
    return Array.from(normalized, (char) => ARABIC_TO_US_QWERTY_MAP[char] || char).join("").trim();
}

export function mapUsToArabicQwerty(text) {
    return Array.from(String(text || ""), (char) => {
        const key = String(char || "").toLowerCase();
        return US_TO_ARABIC_QWERTY_MAP[key] || char;
    }).join("").trim();
}

