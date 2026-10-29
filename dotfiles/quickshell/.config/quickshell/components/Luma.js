.pragma library

// Relative luminance and WCAG contrast, on colours given as "#rrggbb" or as a Qt colour (r, g, b in 0-1). Luminance is
// 0 (black) to 1 (white), in linear light, so a blend of two luminances is a physical blend of the two lights.
function lin(c) { return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4) }

function rgb(c) {
    if (typeof c === "string") {
        const m = /^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/.exec(c)
        return m ? [parseInt(m[1], 16) / 255, parseInt(m[2], 16) / 255, parseInt(m[3], 16) / 255] : [0, 0, 0]
    }
    return [c.r, c.g, c.b]
}

function luminance(c) {
    const [r, g, b] = rgb(c)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

// Contrast of two colours (1 to 21).
function contrast(a, b) { return contrastLuma(a, luminance(b)) }

// Contrast of a colour against a background known only by its luminance.
function contrastLuma(c, luma) {
    const l = luminance(c)
    return (Math.max(l, luma) + 0.05) / (Math.min(l, luma) + 0.05)
}

// Luminance of a tint at `alpha` (0-1) over a backdrop of luminance `backdropLuma`.
function blend(tint, backdropLuma, alpha) { return alpha * luminance(tint) + (1 - alpha) * backdropLuma }

// `preferred` when it reaches `min` contrast against the backdrop, else whichever of the two reads better.
function pick(preferred, alternate, backdropLuma, min) {
    const cp = contrastLuma(preferred, backdropLuma)
    return (cp >= min || cp >= contrastLuma(alternate, backdropLuma)) ? preferred : alternate
}
