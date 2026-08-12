/**
 * Stand-in for the feedback widget in non-test builds.
 *
 * Vite aliases `@feedback` to this file unless VITE_TEST_BUILD=1, so a real
 * release does not merely skip rendering the widget — the widget's code, its
 * copy and its localStorage key never enter the bundle at all.
 */
export function Feedback() {
  return null;
}
