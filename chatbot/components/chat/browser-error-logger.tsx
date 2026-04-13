"use client";

import { useEffect } from "react";

export function BrowserErrorLogger() {
  useEffect(() => {
    const onResourceError = (event: Event) => {
      const target = event.target;

      if (target instanceof HTMLScriptElement) {
        console.warn("[script-load-error]", {
          async: target.async,
          crossOrigin: target.crossOrigin || null,
          defer: target.defer,
          id: target.id || null,
          referrerPolicy: target.referrerPolicy || null,
          src: target.src || "(inline)",
          type: target.type || null,
        });
      }
    };

    const onWindowError = (event: ErrorEvent) => {
      // Keep this terse in dev logs but include source location for debugging.
      console.warn("[window-error]", {
        column: event.colno,
        file: event.filename,
        line: event.lineno,
        message: event.message,
      });
    };

    window.addEventListener("error", onResourceError, true);
    window.addEventListener("error", onWindowError);

    return () => {
      window.removeEventListener("error", onResourceError, true);
      window.removeEventListener("error", onWindowError);
    };
  }, []);

  return null;
}
