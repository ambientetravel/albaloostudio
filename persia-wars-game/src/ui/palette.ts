/**
 * The official Achaemenid palette.
 *
 * These six drive the **entire** UI — the tokens in styles.css and the Pixi
 * PALETTE in render/silhouettes.ts are tints and shades of exactly these hues.
 * This file is the copy the player picks a banner colour from, so it carries
 * the reference codes and original names alongside the hex.
 *
 * Hex values were read off the supplied palette sheet and are close but not
 * guaranteed exact — if the source file has precise values, replace them here,
 * then mirror them into the `:root` block in styles.css and into
 * render/silhouettes.ts. Those three places are the whole colour surface.
 */
export interface BannerColor {
  id: string;
  code: string;
  name: string;
  /** The name on the supplied sheet, kept so the sheet stays traceable. */
  originalName: string;
  hex: string;
  /** Text colour that stays readable on top of `hex`. */
  ink: string;
}

export const ACHAEMENID_PALETTE: BannerColor[] = [
  {
    id: 'lapis',
    code: 'MXR-ACH-01',
    name: 'Imperial Lapis',
    originalName: 'لاجوردی شاهنشاهی',
    hex: '#1f3b6e',
    ink: '#ffffff',
  },
  {
    id: 'gold',
    code: 'MXR-ACH-02',
    name: 'Achaemenid Gold',
    originalName: 'طلایی هخامنشی',
    hex: '#d4a22b',
    ink: '#2b1259',
  },
  {
    id: 'stone-white',
    code: 'MXR-ACH-03',
    name: 'Stone White',
    originalName: 'سفید سنگی',
    hex: '#ede8db',
    ink: '#2b1259',
  },
  {
    id: 'turquoise',
    code: 'MXR-ACH-04',
    name: 'Persian Turquoise',
    originalName: 'فیروزه پارسی',
    hex: '#2e9c9a',
    ink: '#ffffff',
  },
  {
    id: 'stone-brown',
    code: 'MXR-ACH-05',
    name: 'Stone Brown',
    originalName: 'قهوه‌ای سنگ',
    hex: '#7a5b45',
    ink: '#ffffff',
  },
  {
    id: 'ochre-red',
    code: 'MXR-ACH-06',
    name: 'Ochre Red',
    originalName: 'قرمز اخرایی',
    hex: '#b8412a',
    ink: '#ffffff',
  },
];

export function bannerAt(index: number): BannerColor {
  const n = ACHAEMENID_PALETTE.length;
  return ACHAEMENID_PALETTE[((index % n) + n) % n];
}
