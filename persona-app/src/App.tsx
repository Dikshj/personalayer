import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import RequireSession from "./components/RequireSession";
import Landing from "./pages/Landing";
import RequestAccess from "./pages/RequestAccess";
import Session from "./pages/Session";
import Onboarding from "./pages/Onboarding";
import Consent from "./pages/Consent";
import ContextPreview from "./pages/ContextPreview";
import Persona from "./pages/Persona";
import Apps from "./pages/Apps";
import Capture from "./pages/Capture";
import Privacy from "./pages/Privacy";
import Devices from "./pages/Devices";
import Activity from "./pages/Activity";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Routes>
      {/* Public landing page at the root. */}
      <Route path="/" element={<Landing />} />

      {/* Public business/builder inquiry form — not part of the consumer auth flow. */}
      <Route path="/request-access" element={<RequestAccess />} />

      {/* Session connection screen (outside the guarded shell). */}
      <Route path="/app/session" element={<Session />} />

      {/* Focused, full-screen guarded flows (no sidebar). */}
      <Route
        path="/app/onboarding"
        element={
          <RequireSession>
            <Onboarding />
          </RequireSession>
        }
      />
      <Route
        path="/app/consent/:appId"
        element={
          <RequireSession>
            <Consent />
          </RequireSession>
        }
      />
      <Route
        path="/app/context-preview/:previewId"
        element={
          <RequireSession>
            <ContextPreview />
          </RequireSession>
        }
      />

      {/* Authenticated app shell. First product screen is /app/persona. */}
      <Route
        path="/app"
        element={
          <RequireSession>
            <AppShell />
          </RequireSession>
        }
      >
        <Route index element={<Navigate to="/app/persona" replace />} />
        <Route path="persona" element={<Persona />} />
        <Route path="apps" element={<Apps />} />
        <Route path="capture" element={<Capture />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="devices" element={<Devices />} />
        <Route path="activity" element={<Activity />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
