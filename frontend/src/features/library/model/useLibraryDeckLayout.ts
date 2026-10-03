import { useState } from "react";

export type LibraryDeckLayout = "full" | "compact";

const STORAGE_KEY = "etch.library.deckLayout";

function readDeckLayout(): LibraryDeckLayout {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "compact" ? "compact" : "full";
  } catch {
    return "full";
  }
}

export function useLibraryDeckLayout() {
  const [deckLayout, setDeckLayout] = useState(readDeckLayout);

  function changeDeckLayout(layout: LibraryDeckLayout): void {
    setDeckLayout(layout);
    try {
      window.localStorage.setItem(STORAGE_KEY, layout);
    } catch {
      // Keep switching available when browser storage is unavailable.
    }
  }

  return { deckLayout, changeDeckLayout };
}
