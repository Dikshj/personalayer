---
name: PersonaLayer
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#3d4a3d'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f0f1f1'
  outline: '#6d7b6c'
  outline-variant: '#bccbb9'
  surface-tint: '#006e2f'
  primary: '#006e2f'
  on-primary: '#ffffff'
  primary-container: '#22c55e'
  on-primary-container: '#004b1e'
  inverse-primary: '#4ae176'
  secondary: '#855300'
  on-secondary: '#ffffff'
  secondary-container: '#fea619'
  on-secondary-container: '#684000'
  tertiary: '#494bd6'
  on-tertiary: '#ffffff'
  tertiary-container: '#a1a3ff'
  on-tertiary-container: '#2623b8'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#6bff8f'
  primary-fixed-dim: '#4ae176'
  on-primary-fixed: '#002109'
  on-primary-fixed-variant: '#005321'
  secondary-fixed: '#ffddb8'
  secondary-fixed-dim: '#ffb95f'
  on-secondary-fixed: '#2a1700'
  on-secondary-fixed-variant: '#653e00'
  tertiary-fixed: '#e1e0ff'
  tertiary-fixed-dim: '#c0c1ff'
  on-tertiary-fixed: '#07006c'
  on-tertiary-fixed-variant: '#2f2ebe'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
typography:
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-bold:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-padding-mobile: 20px
  container-padding-desktop: 40px
  gutter: 24px
  stack-sm: 12px
  stack-md: 24px
  stack-lg: 48px
---

## Brand & Style
The design system is centered on the concept of "Digital Sanctuary"—a space where privacy is not a technical chore, but a state of calm. The brand personality is friendly, protective, and radically simple, specifically tailored for non-technical users who value security but feel overwhelmed by traditional privacy tools.

The visual style blends **Modern Minimalism** with **Tactile Consumer Softness**. It avoids the cold, clinical aesthetic of cybersecurity in favor of a warm, approachable atmosphere. Every interaction is designed to evoke a sense of relief and control, utilizing generous whitespace and a "soft-touch" interface that feels more like a wellness app than a utility.

## Colors
The palette uses color as a psychological cue for safety and status. 

- **Primary (Emerald Green):** Reserved exclusively for "Safe," "Protected," and "On-Device" states. It should be used sparingly but impactfully to reinforce the app's core value proposition.
- **Secondary (Warm Amber):** Used for moments requiring user attention or consent. It is warm rather than alarming, acting as a gentle nudge rather than a warning.
- **Background (Soft Pearl):** An off-white (#FAF9F6) base that reduces eye strain and provides a warmer, more human feel than pure white.
- **Text (Charcoal):** High-contrast (#1A1A1A) to ensure maximum legibility for all age groups.

## Typography
The typography utilizes **Plus Jakarta Sans** for its friendly, rounded terminals and exceptional legibility. The type scale is intentionally oversized to accommodate non-technical users and provide a "premium consumer" feel. 

Headlines use a tighter letter-spacing and heavier weights to feel grounded and authoritative, while body copy maintains a generous line height (1.5x or higher) to ensure text remains digestible and non-threatening. Avoid all-caps styling to maintain a conversational tone.

## Layout & Spacing
The layout follows a **Fixed-Width Fluid** model. Content is centered within a maximum container width of 1100px on desktop to prevent line lengths from becoming unreadable.

Spacing is aggressive; "when in doubt, add more space." Elements are grouped using a logical hierarchy of 8px increments. Mobile views transition to a single-column stack with 20px side margins to ensure touch targets are large and accessible. Content should never feel "crowded"—each card or module must have room to breathe to maintain the "calm" design narrative.

## Elevation & Depth
This design system avoids harsh borders, instead using **Tonal Layers** and **Ambient Shadows** to create a sense of physical presence.

- **Surface Level:** The main background is the base layer.
- **Card Level:** Interactive modules sit on white backgrounds with a very soft, diffused shadow (Blur: 20px, Opacity: 4%, Y-Offset: 4px).
- **Interactive Level:** On hover or tap, shadows slightly deepen and the element may scale by 1% to provide tactile feedback.
- **No Borders:** Structural separation is achieved through subtle shifts in background color (e.g., a slightly darker grey for secondary fields) rather than hard lines.

## Shapes
The shape language is defined by significant roundedness to eliminate "sharp" or "aggressive" corners. 

Standard cards and containers use a 16px (`rounded-lg`) radius. Buttons and status indicators use a fully rounded "Pill" shape (999px) to invite interaction. This softness is a key component of the trustworthy, non-technical aesthetic.

## Components

### Status: On-Device Indicator
A critical component for reassurance. This is a pill-shaped badge with a soft green background (10% opacity of primary) containing a solid primary green dot and the text "Running on your device." The dot should have a subtle "pulse" animation to indicate active protection.

### Action Cards
Cards should be white with a 16px corner radius. They include a large icon, a `headline-md` title, and `body-md` description. Avoid nested buttons inside cards where possible; make the entire card a clickable surface.

### Buttons
Primary buttons are pill-shaped, using the primary green with white text. Secondary buttons should be "Ghost" style with a subtle grey background and no border. Ensure a minimum touch target height of 56px for all primary actions.

### Consent Toggles
Use large, oversized switch components. When active, the switch should glow with a soft amber tint, signaling a "permission granted" state that feels warm and intentional.

### Progress & Protection
Use thick, rounded progress bars. Avoid thin lines. The visual weight of the UI should feel "sturdy" and reliable.