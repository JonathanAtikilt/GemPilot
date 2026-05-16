---
name: Terminal Prime
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353943'
  surface-container-lowest: '#0a0e17'
  surface-container-low: '#181b25'
  surface-container: '#1c1f29'
  surface-container-high: '#262a34'
  surface-container-highest: '#31353f'
  on-surface: '#dfe2ef'
  on-surface-variant: '#b9cacb'
  inverse-surface: '#dfe2ef'
  inverse-on-surface: '#2c303a'
  outline: '#849495'
  outline-variant: '#3a494b'
  surface-tint: '#00dbe7'
  primary: '#e1fdff'
  on-primary: '#00363a'
  primary-container: '#00f2ff'
  on-primary-container: '#006a71'
  inverse-primary: '#00696f'
  secondary: '#4edea3'
  on-secondary: '#003824'
  secondary-container: '#00a572'
  on-secondary-container: '#00311f'
  tertiary: '#fff6f0'
  on-tertiary: '#472a00'
  tertiary-container: '#ffd4a3'
  on-tertiary-container: '#875500'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#74f5ff'
  primary-fixed-dim: '#00dbe7'
  on-primary-fixed: '#002022'
  on-primary-fixed-variant: '#004f54'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#0f131c'
  on-background: '#dfe2ef'
  surface-variant: '#31353f'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  code-lg:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.1em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 40px
  xl: 64px
  grid-gutter: 20px
  container-padding: 32px
---

## Brand & Style

This design system establishes a high-fidelity "Mission Control" environment for advanced development workflows. The brand personality is technical, precise, and authoritative, moving away from consumer-grade softness toward a professional "Pro-Tool" aesthetic. It evokes the feeling of a futuristic cockpit or a high-end IDE, optimized for long-duration focus and complex data visualization.

The design style is a hybrid of **Minimalist Glassmorphism** and **Technical Brutalism**. It utilizes deep, void-like backgrounds contrasted with high-energy neon accents. Interfaces should feel like "light on glass"—utilizing semi-transparent layers, subtle grid overlays, and sharp, monospaced data points to maintain a serious, hackathon-ready atmosphere.

## Colors

The palette is anchored in a "Deep Space" navy to reduce eye strain and provide maximum contrast for glowing elements. 

- **Primary (Cyan):** Used for active states, data "pings," and primary focus indicators. It should appear as if emitting light.
- **Secondary (Emerald):** Reserved strictly for "System Nominal" states, successful deployments, and valid code metrics.
- **Tertiary (Amber):** Used for "System Alerts" and warnings that require developer attention without immediate failure.
- **Surface Glass:** The primary container color, utilizing a 70% opacity fill to allow underlying grid systems or blurs to peek through, simulating a multi-layered glass display.

## Typography

The typography strategy balances high-speed legibility with a technical "digital readout" feel. 

**Inter** is the workhorse for structural UI and content, providing a neutral, modern foundation. **JetBrains Mono** is utilized for all data-heavy roles, labels, and status indicators to reinforce the developer-centric nature of the tool.

Use `label-caps` for all non-interactive headers in sidebars or small card descriptors. Use `code-sm` for system logs and terminal outputs. All typography on glass surfaces should maintain a high contrast ratio against the deep navy background.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid Grid**. The primary dashboard workspace is fluid, while the "Telemetry" sidebars and "Command" panels are fixed-width to ensure complex data-readouts do not reflow awkwardly.

A subtle, 20px CSS background grid should be visible across the primary `#0a0e17` surface, acting as a visual guide for component alignment. 

- **Desktop:** 12-column grid with 20px gutters. Sidebars are fixed at 280px.
- **Tablet:** 8-column grid. Sidebars collapse into icons or a bottom drawer.
- **Mobile:** 4-column grid with 16px margins. Dashboard cards stack vertically.

## Elevation & Depth

Depth is achieved through **Tonal Stacking** and **Backdrop Blurs** rather than traditional shadows.

1.  **Floor:** The base `#0a0e17` surface with a dim Cyan grid overlay (2% opacity).
2.  **Panels:** Surface-glass containers with a `20px` backdrop-blur and a `1px` inner border of `rgba(0, 242, 255, 0.15)`.
3.  **Floating Elements (Modals/Tooltips):** Higher opacity glass (90%) with a vibrant Cyan outer glow (`box-shadow: 0 0 15px rgba(0, 242, 255, 0.2)`).

Avoid drop shadows on buttons or cards; use border illumination to indicate "lift."

## Shapes

The shape language is "Soft-Technical." Elements use small, precise radii to maintain a clean, engineered feel without the harshness of a pure 0px system. 

- **Standard Buttons/Inputs:** 4px radius.
- **Main Cards/Panels:** 8px radius.
- **Status Pips:** Full circles (pill).
- **Radar Elements:** Circular or hexagonal to imply scanning/technical instrumentation.

## Components

### Buttons
Primary buttons use a solid Cyan background with black text for maximum punch. Secondary buttons use a transparent background with a 1px Cyan border and Cyan text ("Ghost Style"). All buttons feature a subtle outer glow on hover.

### Inputs
Fields are dark-filled with a bottom-only Cyan border that expands to a full-border stroke on focus. Use JetBrains Mono for input text.

### Glass Cards
The core container for all dashboard widgets. Must include a thin top-light highlight (a 1px white line at 10% opacity) to simulate the edge of a glass pane.

### Radar Metrics
Visualizations for system health should use circular "sweeping" animations and concentric ring markers. Use thin 0.5px lines to maintain a "blueprint" aesthetic.

### Status Chips
Small, capsule-shaped indicators. Emerald for `STABLE`, Amber for `DEGRADED`, and Cyan for `SYNCING`. Text inside chips must be `label-caps`.