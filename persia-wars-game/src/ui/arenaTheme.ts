/**
 * Per-arena theming.
 *
 * Climbing the ladder re-skins the whole interface: Anshan is sand and brick
 * under a pale sky, Ecbatana is cold and high, Babylon is glazed blue, the
 * Persian Gates is winter rock. Each theme is a set of overrides for the
 * semantic tokens the stylesheet already uses, so re-skinning is one variable
 * swap rather than thirteen stylesheets.
 *
 * Two things deliberately do NOT change:
 *   - gold stays the primary action, so BATTLE is always the same button;
 *   - text stays stone white on a dark surface, so contrast never depends on
 *     which arena the player happens to be standing in.
 *
 * Every colour below is a blend of the six Achaemenid palette hues.
 */
export interface ArenaTheme {
  /** Background gradient, sky to ground. */
  bgTop: string;
  bgMid: string;
  bgDeep: string;
  /** Panel surfaces, dark enough to carry stone-white text. */
  surface: string;
  surface2: string;
  surface3: string;
  rim: string;
  rimLight: string;
  /** The arena's signature colour, used for highlights and the trophy bar. */
  accent: string;
}

export const ARENA_THEMES: Record<string, ArenaTheme> = {
  // Sand and mud-brick under a pale sky, gold trim — the key art.
  anshan: {
    bgTop: '#6f93a0', bgMid: '#8a7a63', bgDeep: '#4a3b2c',
    surface: '#5a4835', surface2: '#453626', surface3: '#33281c',
    rim: '#1d160f', rimLight: '#c2a184', accent: '#d4a22b',
  },
  /**
   * Tuned against its clip and panel — but NOT to what they average to.
   *
   * The sampler reads Ecbatana as almost exactly Anshan (`#b4916e` against
   * `#b49172`): both are warm sand cities and the mean colour cannot tell them
   * apart. Taking that literally would make the first two rungs of the ladder
   * look identical and kill the promise that the world changes as you climb.
   *
   * What actually separates them is water. Ecbatana's panel has a river through
   * it, orchards, a wheat field and a paddock of horses; Anshan has none of
   * that. So this pulls toward pasture and turquoise while keeping the sand
   * base, which is also the history — well-watered slopes below Alvand, and the
   * horse country the empire's cavalry depended on.
   */
  ecbatana: {
    bgTop: '#8fb0bd', bgMid: '#7d8f76', bgDeep: '#33403a',
    surface: '#3a4f48', surface2: '#2c3d38', surface3: '#1f2c28',
    rim: '#0e1614', rimLight: '#9dc0b4', accent: '#2e9c9a',
  },
  // Lydian gold, warm western light off the Aegean.
  sardis: {
    bgTop: '#c9a45f', bgMid: '#8a6c33', bgDeep: '#4a3818',
    surface: '#5c4620', surface2: '#463517', surface3: '#33260f',
    rim: '#1a1207', rimLight: '#d9bd7f', accent: '#eec95f',
  },
  // Irrigated oasis green against grey desert.
  bactra: {
    bgTop: '#7fa89e', bgMid: '#4f7168', bgDeep: '#2c3f39',
    surface: '#2f4a43', surface2: '#243832', surface3: '#1a2925',
    rim: '#0d1614', rimLight: '#8fc0b5', accent: '#2e9c9a',
  },
  // Blue-glazed brick and the Ishtar Gate.
  babylon: {
    bgTop: '#4a77b8', bgMid: '#23477f', bgDeep: '#10203c',
    surface: '#1f3b6e', surface2: '#172c53', surface3: '#101f3b',
    rim: '#08111f', rimLight: '#6f9ad4', accent: '#d4a22b',
  },
  // A watered garden-plain, pale stone, 1,900 m up.
  pasargadae: {
    bgTop: '#9db99a', bgMid: '#5e7a5c', bgDeep: '#33452f',
    surface: '#3a5237', surface2: '#2c3f2a', surface3: '#1f2e1e',
    rim: '#101a0f', rimLight: '#a8c9a3', accent: '#d4a22b',
  },
  // Nile sun and Egyptian faience.
  memphis: {
    bgTop: '#d9b877', bgMid: '#9a7b3f', bgDeep: '#4d3d1c',
    surface: '#4f4526', surface2: '#3c341c', surface3: '#2b2513',
    rim: '#141108', rimLight: '#dcc48c', accent: '#2e9c9a',
  },
  // Limestone cliff in late-afternoon shadow.
  bisotun: {
    bgTop: '#a89279', bgMid: '#6d5c49', bgDeep: '#3a3128',
    surface: '#4a3f33', surface2: '#382f26', surface3: '#28221b',
    rim: '#12100c', rimLight: '#bda78d', accent: '#b8412a',
  },
  // Hot, low, riverine; glazed guard friezes in yellow and green.
  susa: {
    bgTop: '#c2b06a', bgMid: '#7e7a3e', bgDeep: '#3f4020',
    surface: '#45482a', surface2: '#343620', surface3: '#252716',
    rim: '#101107', rimLight: '#cfc386', accent: '#2e9c9a',
  },
  // Monsoon-side green under high mountains.
  gandara: {
    bgTop: '#7fb0a0', bgMid: '#3f6f60', bgDeep: '#21382f',
    surface: '#2b4a3e', surface2: '#21382f', surface3: '#172821',
    rim: '#0b1410', rimLight: '#8fcbb6', accent: '#d4a22b',
  },
  // Gold and lapis paint on stone — the empire's showpiece.
  persepolis: {
    bgTop: '#6f8fd0', bgMid: '#2f4d8f', bgDeep: '#16224a',
    surface: '#24356b', surface2: '#1b2851', surface3: '#131c3a',
    rim: '#090f1f', rimLight: '#d4a22b', accent: '#eec95f',
  },
  // Dust and distance; the empire as logistics.
  'royal-road': {
    bgTop: '#b8a68c', bgMid: '#7a6b55', bgDeep: '#3f382c',
    surface: '#4a4335', surface2: '#383327', surface3: '#28241b',
    rim: '#12100b', rimLight: '#c6b79f', accent: '#d4a22b',
  },
  // Winter rock, snow, and the last stand.
  'persian-gates': {
    bgTop: '#8fa3b8', bgMid: '#4a5c72', bgDeep: '#232d3a',
    surface: '#2f3b4a', surface2: '#242d38', surface3: '#1a2028',
    rim: '#0b0e12', rimLight: '#a3b8cc', accent: '#b8412a',
  },
};

const FALLBACK: ArenaTheme = ARENA_THEMES.anshan;

export function themeFor(slug: string): ArenaTheme {
  return ARENA_THEMES[slug] ?? FALLBACK;
}

/**
 * Writes the theme onto the document root. The stylesheet reads these names
 * everywhere, so one call re-skins every screen at once.
 */
export function applyArenaTheme(slug: string): void {
  if (typeof document === 'undefined') return;
  const t = themeFor(slug);
  const root = document.documentElement.style;
  root.setProperty('--lapis-hi', t.bgTop);
  root.setProperty('--lapis', t.bgMid);
  root.setProperty('--lapis-deep', t.bgDeep);
  root.setProperty('--surface', t.surface);
  root.setProperty('--surface-2', t.surface2);
  root.setProperty('--surface-3', t.surface3);
  root.setProperty('--rim', t.rim);
  root.setProperty('--rim-light', t.rimLight);
  root.setProperty('--accent', t.accent);
  document.documentElement.dataset.arena = slug;
}
