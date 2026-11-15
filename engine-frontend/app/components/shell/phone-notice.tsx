import { Link } from "react-router";

export function PhoneNotice() {
  return (
    <section className="card phone-notice">
      <h1 className="page-title">Open this page on a computer</h1>
      <p>On a phone the Engine covers Home: to-dos, items to review and action emails.</p>
      <Link className="button" to="/">Go to Home</Link>
    </section>
  );
}
