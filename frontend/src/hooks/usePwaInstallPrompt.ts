import { useCallback, useEffect, useState } from "react";

/**
 * Chrome/Edge (desktop and Android) fire `beforeinstallprompt` instead of
 * showing their own install UI immediately, so the app can offer its own
 * "Install" button and trigger the native prompt on demand. Not
 * standardized in the DOM lib types yet, hence the manual interface.
 */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
}

export interface PwaInstallState {
  /** True once the browser has signaled the app is installable and it hasn't been installed yet. */
  canInstall: boolean;
  promptInstall: () => Promise<void>;
}

export function usePwaInstallPrompt(): PwaInstallState {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    const handleBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      setDeferredPrompt(event as BeforeInstallPromptEvent);
    };
    const handleAppInstalled = () => {
      setDeferredPrompt(null);
      setIsInstalled(true);
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      window.removeEventListener("appinstalled", handleAppInstalled);
    };
  }, []);

  const promptInstall = useCallback(async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    // Each BeforeInstallPromptEvent can only be prompted once.
    setDeferredPrompt(null);
  }, [deferredPrompt]);

  return { canInstall: deferredPrompt !== null && !isInstalled, promptInstall };
}
