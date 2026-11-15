import { useState } from "react";
import { Link } from "react-router";
import { Drawer } from "../components/ui/drawer";
import { EmptyState } from "../components/ui/empty-state";
import { LabelItem as Item } from "../components/ui/record-parts";
import { useRouteAction } from "../components/ui/toast";
import { connect, disconnect, getProfile, updateProfile } from "../demo/api";
import type { ConnectionStatus, Profile as ProfileFields, ProfileData } from "../demo/types";
import { count, formatWhen } from "../lib/format";
import type { Route } from "./+types/profile";

export async function clientLoader() {
  return getProfile();
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const id = String(form.get("id"));
  if (form.get("intent") === "profile") {
    return updateProfile({ fullName: String(form.get("fullName")), title: String(form.get("title")), whatsapp: String(form.get("whatsapp")) });
  }
  if (form.get("intent") === "connect") return connect(id);
  if (form.get("intent") === "disconnect") return disconnect(id);
}

const TONES: Record<ConnectionStatus, string> = {
  Connected: "pill pill--closed",
  "Needs attention": "pill pill--talks",
  "Not connected": "pill pill--not-started",
};
// Problems first, so a broken connection is the first thing you see.
const ORDER: ConnectionStatus[] = ["Needs attention", "Not connected", "Connected"];

export default function Profile({ loaderData: data }: Route.ComponentProps) {
  const act = useRouteAction("/profile");
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(false);
  const { profile, user } = data;
  const rows = [...data.connections].sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status));
  const countOf = (status: ConnectionStatus) => data.connections.filter((row) => row.status === status).length;

  return (
    <>
      <h1 className="page-title">Profile</h1>
      <div className="page-body">
        <section className="card profile-head" aria-label="You">
          <div className="profile-head__who">
            <span className="avatar avatar--large" aria-hidden="true">
              {profile.fullName.charAt(0)}
            </span>
            <div>
              <h2 className="section-title">{profile.fullName}</h2>
              <p className="muted">{profile.title}</p>
            </div>
            {/* Log out lives here, not in the nav footer, so the footer has room for the full job title. */}
            <div className="profile-head__actions">
              <button type="button" className="button button--small button--quiet" onClick={() => setEditing(true)}>
                Edit
              </button>
              <Link className="button button--small button--quiet" to="/signed-out">
                Log out
              </Link>
            </div>
          </div>
          {/* One row of labelled facts, read left to right, instead of details floating at the far edge. */}
          <dl className="profile-head__facts">
            <Fact label="Email">{profile.email}</Fact>
            <Fact label="WhatsApp">{profile.whatsapp}</Fact>
            <Fact label="Role">{user.role}</Fact>
            <Fact label="Access">{profile.admin ? "Admin" : "Member"}</Fact>
          </dl>
        </section>

        <section className="card profile-connections" aria-labelledby="connections-title">
          <div className="card__head">
            <h2 id="connections-title" className="section-title">Connected accounts</h2>
            <span className="card__meta">
              {countOf("Connected")} connected, {count(countOf("Needs attention"), "needs", "need")} attention, {countOf("Not connected")} not connected
            </span>
            <button type="button" className="button button--small" onClick={() => setAdding(true)}>
              Add connector
            </button>
          </div>
          <div className="profile-connections__scroll">
            <table className="table table--fixed">
              <colgroup>
                <col style={{ width: "30%" }} />
                <col style={{ width: "20%" }} />
                <col style={{ width: "22%" }} />
                <col style={{ width: "12%" }} />
                <col style={{ width: "144px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Service</th>
                  <th scope="col">Account</th>
                  <th scope="col">Status</th>
                  <th scope="col">Last sync</th>
                  <th scope="col">
                    <span className="visually-hidden">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className="cell-title">{row.name}</span>
                      <span className="cell-sub">{row.purpose}</span>
                    </td>
                    <td className="cell-clip">{row.account || <span className="muted">Not set</span>}</td>
                    <td>
                      <span className={TONES[row.status]}>{row.status}</span>
                      {row.issue && <span className="cell-sub connection__issue">{row.issue}</span>}
                    </td>
                    <td>{row.lastSyncAt ? formatWhen(row.lastSyncAt, data.now) : <span className="muted">Never</span>}</td>
                    <td>
                      {row.status === "Connected" ? (
                        <button type="button" className="button button--small button--quiet button--row" onClick={() => act({ intent: "disconnect", id: row.id }, `${row.name} disconnected.`)}>
                          Disconnect
                        </button>
                      ) : (
                        <button type="button" className="button button--small button--row" onClick={() => act({ intent: "connect", id: row.id }, `${row.name} connected. Demo: no sign-in opened.`)}>
                          {row.status === "Needs attention" ? "Reconnect" : "Connect"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {adding && <AddConnector data={data} onClose={() => setAdding(false)} />}
      {editing && <EditProfile profile={profile} onClose={() => setEditing(false)} />}
    </>
  );
}

function AddConnector({ data, onClose }: { data: ProfileData; onClose: () => void }) {
  const act = useRouteAction("/profile");
  return (
    <Drawer title="Add connector" onClose={onClose} actions={null}>
      <section className="drawer__section">
        {data.available.length === 0 ? (
          <EmptyState>Every available connector is already added.</EmptyState>
        ) : (
          <ul className="plain-list">
            {data.available.map((choice) => (
              <li key={choice.id} className="connector-choice">
                <span>
                  <span className="cell-title">{choice.name}</span>
                  <span className="cell-sub">{choice.purpose}</span>
                </span>
                <button
                  type="button"
                  className="button button--small button--row"
                  onClick={() => {
                    act({ intent: "connect", id: choice.id }, `${choice.name} connected. Demo: no sign-in opened.`);
                    onClose();
                  }}
                >
                  Connect
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Drawer>
  );
}

function EditProfile({ profile, onClose }: { profile: ProfileFields; onClose: () => void }) {
  const act = useRouteAction("/profile");
  const [fields, setFields] = useState({ fullName: profile.fullName, title: profile.title, whatsapp: profile.whatsapp });
  const dirty = fields.fullName !== profile.fullName || fields.title !== profile.title || fields.whatsapp !== profile.whatsapp;
  const blocker = fields.fullName.trim() ? "" : "Add your name before saving.";
  const set = (key: keyof typeof fields) => (event: React.ChangeEvent<HTMLInputElement>) => setFields({ ...fields, [key]: event.target.value });

  return (
    <Drawer
      title="Edit profile"
      dirty={dirty}
      notice={blocker || undefined}
      onClose={onClose}
      actions={
        <button
          type="button"
          className="button"
          disabled={!dirty || Boolean(blocker)}
          onClick={() => {
            act({ intent: "profile", fullName: fields.fullName.trim(), title: fields.title.trim(), whatsapp: fields.whatsapp.trim() }, "Profile saved.");
            onClose();
          }}
        >
          Save
        </button>
      }
    >
      <section className="drawer__section">
        <div className="field">
          <label htmlFor="profile-name">Full name</label>
          <input id="profile-name" value={fields.fullName} onChange={set("fullName")} />
        </div>
        <div className="field">
          <label htmlFor="profile-title">Title</label>
          <input id="profile-title" value={fields.title} onChange={set("title")} />
        </div>
        <div className="field">
          <label htmlFor="profile-whatsapp">WhatsApp</label>
          <input id="profile-whatsapp" type="tel" value={fields.whatsapp} onChange={set("whatsapp")} />
        </div>
      </section>
    </Drawer>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="profile-fact">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
