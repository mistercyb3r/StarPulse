import { useEffect, useState } from "react";
import { getHealth, getSetupStatus } from "./api/client";
import { AboutPage } from "./components/AboutPage";
import { Dashboard } from "./components/Dashboard";
import { LoadingScreen } from "./components/LoadingScreen";
import { LocationSettingsPage } from "./components/LocationSettingsPage";
import { NotificationsSettingsPage } from "./components/NotificationsSettingsPage";
import { SetupWizard } from "./components/SetupWizard";
import { WeatherImpactPage } from "./components/WeatherImpactPage";

type View =
  | "checking"
  | "setup"
  | "dashboard"
  | "weather-impact"
  | "location-settings"
  | "notifications"
  | "about";

export function App() {
  const [view, setView] = useState<View>("checking");
  const [appVersion, setAppVersion] = useState("1.0.0");

  useEffect(() => {
    let cancelled = false;

    Promise.all([getSetupStatus(), getHealth().catch(() => null)])
      .then(([status, health]) => {
        if (cancelled) return;
        if (health?.version) setAppVersion(health.version);
        setView(status.setup_complete ? "dashboard" : "setup");
      })
      .catch(() => {
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

  if (view === "weather-impact") {
    return <WeatherImpactPage onBack={() => setView("dashboard")} />;
  }

  if (view === "location-settings") {
    return <LocationSettingsPage onBack={() => setView("dashboard")} />;
  }

  if (view === "notifications") {
    return <NotificationsSettingsPage onBack={() => setView("dashboard")} />;
  }

  if (view === "about") {
    return <AboutPage onBack={() => setView("dashboard")} />;
  }

  return (
    <Dashboard
      appVersion={appVersion}
      onOpenWeatherImpact={() => setView("weather-impact")}
      onOpenLocationSettings={() => setView("location-settings")}
      onOpenNotifications={() => setView("notifications")}
      onOpenAbout={() => setView("about")}
    />
  );
}
