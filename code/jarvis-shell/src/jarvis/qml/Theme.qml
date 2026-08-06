pragma Singleton
import QtQuick

/**
 * Design tokens for the Jarvis visual language.
 *
 * Every color, font size, spacing value, animation curve, and shadow parameter
 * lives here. Components never hard-code values — they reference Theme.
 *
 * Palette inspired by cinematic HUD systems: deep void blacks, holographic cyan
 * accents, alert amber, and translucent glass panels.
 */
QtObject {
    // ── Core palette ───────────────────────────────────────────────────
    readonly property color void_:        "#050508"
    readonly property color surface:      "#0a0e14"
    readonly property color surfaceLight: "#0f1620"
    readonly property color panel:        "#0d141d"
    readonly property color border:       "#1c2733"
    readonly property color borderGlow:   "#14324a"

    // ── Accent system ──────────────────────────────────────────────────
    readonly property color cyan:         "#00F0FF"
    readonly property color cyanDim:      "#0a7a82"
    readonly property color cyanGlow:     "#00F0FF"
    readonly property color teal:         "#4fd6c9"
    readonly property color blue:         "#4fa3ff"
    readonly property color amber:        "#FF9900"
    readonly property color amberDim:     "#8a5500"
    readonly property color red:          "#ff4757"
    readonly property color green:        "#2ed573"
    readonly property color greenDim:     "#1a7a42"
    readonly property color purple:       "#a55eea"

    // ── Text ───────────────────────────────────────────────────────────
    readonly property color textPrimary:   "#e8f0f8"
    readonly property color textSecondary: "#9fb3c8"
    readonly property color textDim:       "#5b6b7d"
    readonly property color textInverse:   "#050508"

    // ── Status mapping ─────────────────────────────────────────────────
    function statusColor(state) {
        switch (state) {
            case "ready":        return green;
            case "initializing": return amber;
            case "degraded":     return amber;
            case "unavailable":  return textDim;
            case "error":        return red;
            default:             return textDim;
        }
    }

    // ── Glass / blur ───────────────────────────────────────────────────
    readonly property real glassOpacity:  0.55
    readonly property real glassBlur:     40.0
    readonly property color glassColor:   Qt.rgba(0.04, 0.055, 0.082, glassOpacity)
    readonly property color glassBorder:  Qt.rgba(0.11, 0.15, 0.20, 0.6)

    // ── Typography (sizes in px, weights as Qt constants) ──────────────
    readonly property string fontFamily:  "Inter, Segoe UI, system-ui, sans-serif"
    readonly property int fontMono:       13
    readonly property int fontSmall:      12
    readonly property int fontBody:       14
    readonly property int fontLarge:      16
    readonly property int fontTitle:      20
    readonly property int fontHero:       28

    // ── Spacing ────────────────────────────────────────────────────────
    readonly property int spaceXS:  4
    readonly property int spaceS:   8
    readonly property int spaceM:  12
    readonly property int spaceL:  16
    readonly property int spaceXL: 24
    readonly property int spaceXXL:32

    // ── Radius ─────────────────────────────────────────────────────────
    readonly property int radiusS:   6
    readonly property int radiusM:  12
    readonly property int radiusL:  20
    readonly property int radiusXL: 32
    readonly property int radiusFull: 9999

    // ── Animation ──────────────────────────────────────────────────────
    readonly property int durationFast:   150
    readonly property int durationNormal: 300
    readonly property int durationSlow:   600
    readonly property int durationBreath: 3000
    readonly property int easing:         Easing.OutCubic

    // ── Shadows (for glow effects) ─────────────────────────────────────
    readonly property real glowRadius:    20
    readonly property real glowSpread:    0.3
}
