import { useState } from "react";
import { useSearchParams } from "react-router";
import { Drawer } from "../components/ui/drawer";
import { EmptyState } from "../components/ui/empty-state";
import { FilterBar } from "../components/ui/filter-bar";
import { LabelItem as Item } from "../components/ui/record-parts";
import { useRouteAction } from "../components/ui/toast";
import { CURRENT_USER_ID, getSkills, saveSkillVersion } from "../demo/api";
import type { Skill, SkillsData } from "../demo/types";
import { byId } from "../lib/by-id";
import { anyOf, readList } from "../lib/filters";
import { formatDate } from "../lib/format";
import type { Route } from "./+types/skills";

export async function clientLoader() {
  return getSkills();
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  if (form.get("intent") === "save") {
    return saveSkillVersion(CURRENT_USER_ID, String(form.get("id")), String(form.get("body")), String(form.get("note")));
  }
}

// PRD ST1: every skill behind contracts, proposals, NDAs, emails, invoices, teasers and CIMs,
// with version, last edit and where the Engine uses it.
export default function Skills({ loaderData: data }: Route.ComponentProps) {
  const [params, setParams] = useSearchParams();
  const categories = readList(params, "category");
  const rows = data.skills.filter((skill) => anyOf(categories, [skill.category]));
  const open = data.skills.find((skill) => skill.id === params.get("skill"));
  const editing = params.get("panel") === "edit" && data.canEdit;
  const show = (id: string | null, edit = false) =>
    setParams(
      (url) => {
        if (id) url.set("skill", id);
        else url.delete("skill");
        if (edit) url.set("panel", "edit");
        else url.delete("panel");
        return url;
      },
      { preventScrollReset: true },
    );

  return (
    <>
      <h1 className="page-title">Skills</h1>
      <FilterBar filters={[{ kind: "list", key: "category", label: "Category", options: [...new Set(data.skills.map((skill) => skill.category))].sort() }]} shown={rows.length} total={data.skills.length} />
      <div className="page-body">
        {rows.length === 0 ? (
          <EmptyState>No skill in this category.</EmptyState>
        ) : (
          <div className="card card--flush">
            <table className="table table--fixed">
              <colgroup>
                <col style={{ width: "24%" }} />
                <col style={{ width: "10%" }} />
                <col style={{ width: "8%" }} />
                <col style={{ width: "14%" }} />
                <col />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Skill</th>
                  <th scope="col">Category</th>
                  <th scope="col" className="num">Version</th>
                  <th scope="col">Last edit</th>
                  <th scope="col">Used in</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((skill) => {
                  const latest = skill.versions[0];
                  return (
                    <tr key={skill.id} className="row-clickable" tabIndex={0} onClick={() => show(skill.id)} onKeyDown={(event) => event.key === "Enter" && show(skill.id)}>
                      <td>
                        <span className="cell-title cell-clip">{skill.title}</span>
                      </td>
                      <td>{skill.category}</td>
                      <td className="num">{latest.version}</td>
                      <td>
                        <span className="cell-clip">
                          {formatDate(latest.date)}, {byId(data.users, latest.byId)?.name}
                        </span>
                      </td>
                      <td className="cell-clip" title={skill.usedIn.join("; ")}>
                        {skill.usedIn.join("; ")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {open &&
        (editing ? (
          <EditSkill key={`${open.id}-edit`} skill={open} onBack={() => show(open.id)} onClose={() => show(null)} />
        ) : (
          <SkillDrawer key={open.id} skill={open} data={data} onEdit={() => show(open.id, true)} onClose={() => show(null)} />
        ))}
    </>
  );
}

function SkillDrawer({ skill, data, onEdit, onClose }: { skill: Skill; data: SkillsData; onEdit: () => void; onClose: () => void }) {
  return (
    <Drawer
      title={skill.title}
      status={`${skill.category}. Version ${skill.versions[0].version}`}
      onClose={onClose}
      notice={data.canEdit ? undefined : "Only admins can edit skills."}
      actions={
        data.canEdit && (
          <button type="button" className="button button--quiet" onClick={onEdit}>
            Edit
          </button>
        )
      }
    >
      <section className="drawer__section">
        <h3 className="panel-heading">Skill</h3>
        <dl className="label-grid label-grid--two">
          <Item label="File">{skill.file}</Item>
          <Item label="Used in">{skill.usedIn.join("; ")}</Item>
        </dl>
        <p className="record-notes">{skill.body}</p>
      </section>
      <section className="drawer__section">
        <h3 className="panel-heading">Versions</h3>
        <ul className="email-log">
          {skill.versions.map((version) => (
            <li key={version.version} className="email-log__item">
              <span className="email-log__subject">
                <strong>{version.version}</strong> {version.note}
              </span>
              <span className="email-log__date">
                {byId(data.users, version.byId)?.name}, {formatDate(version.date)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </Drawer>
  );
}

// Saving writes a new version of the shared skill file; Claude reads the same file.
function EditSkill({ skill, onBack, onClose }: { skill: Skill; onBack: () => void; onClose: () => void }) {
  const act = useRouteAction("/settings/skills");
  const [body, setBody] = useState(skill.body);
  const [note, setNote] = useState("");
  const dirty = body !== skill.body;
  const blocker = dirty && !note.trim() ? "Say what changed before saving." : "";

  return (
    <Drawer
      title={`Edit ${skill.title}`}
      status={`Current version ${skill.versions[0].version}`}
      dirty={dirty || Boolean(note.trim())}
      notice={blocker || undefined}
      onClose={onClose}
      actions={
        <>
          <button type="button" className="button button--quiet" onClick={onBack}>
            Back
          </button>
          <button
            type="button"
            className="button"
            disabled={!dirty || Boolean(blocker)}
            onClick={() => {
              act({ intent: "save", id: skill.id, body, note: note.trim() }, `${skill.title} saved as a new version.`);
              onBack();
            }}
          >
            Save
          </button>
        </>
      }
    >
      <section className="drawer__section">
        <div className="field">
          <label htmlFor="skill-body">Instructions</label>
          <textarea id="skill-body" rows={10} value={body} onChange={(event) => setBody(event.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="skill-note">What changed</label>
          <input id="skill-note" value={note} onChange={(event) => setNote(event.target.value)} />
        </div>
      </section>
    </Drawer>
  );
}
