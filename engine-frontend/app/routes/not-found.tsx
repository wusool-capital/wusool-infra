import { Link } from "react-router";

export const handle = { phone: true };

export default function NotFound() {
  return (
    <>
      <h1 className="page-title">Page not found</h1>
      <section className="card">
        <p>This address does not match any page in the Engine.</p>
        <Link className="button" to="/">Go to Home</Link>
      </section>
    </>
  );
}
