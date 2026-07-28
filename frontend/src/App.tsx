import { useEffect, useState } from "react";
import { getSetupStatus } from "./api/client";
import { Dashboard } from "./components/Dashboard";
import { LoadingScreen } from "./components/LoadingScreen";
import { SetupWizard } from "./components/SetupWizard";

type View = "checking" | "setup" | "dashboard";

export function App() {
  const [view, setView] = useState<View>("checking");

  useEffect(() => {
    let cancelled = false;

    getSetupStatus()
      .then((status) => {
        if (!cancelled) setView(status.setup_complete ? "dashboard" : "setup");
      })
      .catch(() => {
        // API unreachable entirely — nothing to set up against yet.
        // The dashboard's own mock-data fallback covers this case.
        if (!cancelled) setView("dashboard");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (view === "checking") {
    return <LoadingScreen message="Starting StarPulse…" />;
  }

  if (view === "setup") {
    return <SetupWizard onComplete={() => setView("dashboard")} />;
  }

  return <Dashboard />;
}
