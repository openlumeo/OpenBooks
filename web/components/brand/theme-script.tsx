// Ported from Lumeo theme-script.tsx. Runs before first paint so a stored theme never flashes.
// Dark is the brand default: light applies only when the visitor explicitly chose it.
export const THEME_STORAGE_KEY = "openbooks-theme";

const script = `(function(){try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t)}}catch(e){}})();`;

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
