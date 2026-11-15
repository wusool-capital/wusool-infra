import "@fontsource-variable/inter";
import "./styles.css";
import { Links, Meta, Outlet, Scripts, ScrollRestoration, useMatches } from "react-router";
import type { Route } from "./+types/root";
import { LeftNav } from "./components/shell/left-nav";
import { PhoneNotice } from "./components/shell/phone-notice";
import { NoticeProvider, Toast } from "./components/ui/toast";
import { getCurrentUser } from "./api";
import { errorMessage } from "./lib/action-result";

export function meta() {
  return [{ title: "Wusool Engine" }];
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="data:," />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

// SPA mode allows a loading state only on the root route; shown until data loads.
export function HydrateFallback() {
  return <p className="page muted">Loading…</p>;
}

export async function clientLoader() {
  return { user: await getCurrentUser() };
}

// The signed-in person cannot change while the app is open, so /me runs once per page load.
export function shouldRevalidate() {
  return false;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  return (
    <main className="page">
      <h1 className="page-title">Something went wrong</h1>
      <p className="muted">{errorMessage(error)}</p>
      <button type="button" className="button" onClick={() => window.location.reload()}>
        Reload
      </button>
    </main>
  );
}

type RouteHandle = { phone?: boolean; bare?: boolean } | undefined;

export default function App({ loaderData }: Route.ComponentProps) {
  const handles = useMatches().map((match) => match.handle as RouteHandle);
  const hasPhoneLayout = handles.some((handle) => handle?.phone);

  // Pages outside the signed-in app (signed out) render without the nav.
  if (handles.some((handle) => handle?.bare)) return <Outlet />;

  return (
    // The notice provider wraps the nav too, so "Log bottleneck" can confirm on any page.
    <NoticeProvider>
      <div className="shell" data-phone={hasPhoneLayout ? "yes" : "no"}>
        <LeftNav user={loaderData.user} />
        <div className="shell__main">
          <main className="page">
            <div className="page__desktop">
              <Outlet />
            </div>
            <Toast />
            {!hasPhoneLayout && <PhoneNotice />}
          </main>
        </div>
      </div>
    </NoticeProvider>
  );
}
