import { usePwaInstallPrompt } from "../hooks/usePwaInstallPrompt";
import "./InstallPwaButton.css";

export function InstallPwaButton() {
  const { canInstall, promptInstall } = usePwaInstallPrompt();

  if (!canInstall) return null;

  return (
    <button type="button" className="install-pwa-button" onClick={() => void promptInstall()}>
      Install App
    </button>
  );
}
