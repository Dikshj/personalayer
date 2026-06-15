---
name: Fortress Logic
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#434655'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#006c49'
  on-secondary: '#ffffff'
  secondary-container: '#6cf8bb'
  on-secondary-container: '#00714d'
  tertiary: '#46566c'
  on-tertiary: '#ffffff'
  tertiary-container: '#5e6e85'
  on-tertiary-container: '#e9f0ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#d3e4fe'
  tertiary-fixed-dim: '#b7c8e1'
  on-tertiary-fixed: '#0b1c30'
  on-tertiary-fixed-variant: '#38485d'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  code-display:
    fontFamily: JetBrains Mono
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: 0.1em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 20px
  margin-desktop: 32px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style
The design system is engineered for high-stakes security contexts, specifically cross-device pairing and authentication. The brand personality is rooted in **Reliability, Precision, and Clarity**. It aims to evoke a sense of absolute safety and professional rigor, eliminating any visual noise that could lead to user error during sensitive flows.

The design style follows a **Modern Corporate** aesthetic with a heavy emphasis on **Systematic Minimalism**. It utilizes a structured hierarchy, ample white space to reduce cognitive load, and high-contrast functional elements to guide the user through the pairing process with confidence.

## Colors
The color palette is functionally driven. **Security Blue (#2563EB)** serves as the primary action color, signaling authority and trust. **Success Green (#10B981)** is reserved for completed states and verified pairings. 

The neutral palette utilizes a range of cool-toned grays to maintain a clean, clinical atmosphere. Backgrounds should primarily be pure white for clarity, with subtle grays used to differentiate surface levels or grouped input areas. Status colors are high-chroma to ensure critical alerts (errors or warnings) are immediately distinguishable.

## Typography
This design system prioritizes legibility above all. **Inter** is used for all UI text to provide a neutral, highly readable sans-serif experience. For the specific use case of secure code entry (OTP or pairing codes), **JetBrains Mono** is utilized to ensure that characters like '0' and 'O' or '1' and 'l' are visually distinct, preventing user frustration.

Headlines use tighter letter spacing and heavier weights to anchor the page, while body text maintains standard spacing for optimal reading comfort.

## Layout & Spacing
The layout employs a **Fixed Grid** approach for desktop (max-width 640px for authentication modals) and a **Fluid Grid** for mobile devices. This keeps the focus centered and prevents information from becoming too sparse on larger screens, mimicking the compact efficiency of high-end banking apps.

Spacing follows a strict 4px base unit. Vertical rhythm is maintained through "stacks"—standardized margins between headlines, descriptive text, and input fields (16px or 32px).

## Elevation & Depth
Depth is communicated through **Tonal Layers** and extremely subtle **Ambient Shadows**. 
- **Level 0 (Background):** Pure white or `#F8FAFC`.
- **Level 1 (Cards/Containers):** Pure white background with a 1px border of `#E2E8F0`.
- **Level 2 (Active Elements):** Small, diffused shadow (0px 4px 6px rgba(0,0,0,0.05)) to suggest interactivity.

Avoid heavy shadows or "floating" elements; the design should feel grounded and architectural. Borders are the primary method of defining container boundaries.

## Shapes
The design system utilizes a **Soft (0.25rem)** roundedness profile. This subtle rounding removes the harshness of sharp corners—making the app feel modern—while maintaining a rigid, professional structure that feels more "secure" than highly rounded or "pill-shaped" aesthetics. 
- Input fields and buttons: 4px (0.25rem)
- Cards and QR containers: 8px (0.5rem)

## Components
### Secure Code Inputs
Individual character boxes for pairing codes. Each box should have a 1px border that thickens to 2px and changes to Security Blue when focused. Use the `code-display` typography token.

### QR Code Containers
A Level 1 container with a white background and a subtle inner border. The QR code should be centered with a minimum of 24px padding on all sides to ensure scan-ability.

### Primary CTA Buttons
High-contrast Security Blue background with white text. Use `label-sm` or `body-md` bold. Buttons must span the full width of the container on mobile to ensure ease of use.

### Loading Spinners
A minimal, constant-thickness ring. Use Security Blue for the active segment and a light gray for the track. The motion should be smooth and linear to indicate active processing.

### Status Banners
Slim horizontal bars at the top of a surface. Use status colors with 10% opacity for backgrounds and 100% opacity for the text and icons within to ensure high legibility.