import { Link } from "react-router";

// Outside the signed-in app, so the shell renders it without the nav.
export const handle = { bare: true, phone: true };

export default function SignedOut() {
  return (
    <main className="signed-out">
      <section className="card">
        <h1 className="page-title">You are signed out</h1>
        <p>In the demo nothing changes. Sign-in with Google comes with Cloudflare Access.</p>
        <Link className="button" to="/">Sign in again</Link>
      </section>
    </main>
  );
}
