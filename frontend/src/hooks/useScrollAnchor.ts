import { useLayoutEffect, useRef } from "react";

/**
 * Keeps a clicked element (e.g. a pagination bar) at the same viewport
 * position across a state update that reflows the page around it. A page
 * change that shortens/lengthens the table above (e.g. a partial last page)
 * otherwise shifts the pagination controls themselves, sometimes off the
 * visible viewport, even though the click itself never scrolled anything.
 *
 * Usage: call `anchor()` synchronously inside the click handler (before the
 * state update that will change layout), and attach `ref` to the element
 * that should stay put.
 */
export function useScrollAnchor<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const anchoredTop = useRef<number | null>(null);

  const anchor = () => {
    anchoredTop.current = ref.current?.getBoundingClientRect().top ?? null;
  };

  useLayoutEffect(() => {
    if (anchoredTop.current == null || !ref.current) return;
    const delta = ref.current.getBoundingClientRect().top - anchoredTop.current;
    anchoredTop.current = null;
    if (delta !== 0) window.scrollBy(0, delta);
  });

  return { ref, anchor };
}
