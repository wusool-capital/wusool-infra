import { useState } from "react";
import type { Person } from "../../demo/types";

const MAX_RESULTS = 5;

type Props = {
  /** Unique per page, since several adders can be open at once. */
  id: string;
  addLabel: string;
  people: Person[];
  metIds: string[];
  suggestedIds: string[];
  onAdd: (person: Person) => void;
};

// PRD K3 and K4: tag someone from a search box, or confirm a suggestion from the calendar.
// Shared by the Home scorecard and each metric on the Scorecards tab.
export function MetAdder({ id, addLabel, people, metIds, suggestedIds, onAdd }: Props) {
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const suggestions = people.filter((person) => suggestedIds.includes(person.id) && !metIds.includes(person.id));
  const matches = query.trim()
    ? people
        .filter((person) => !metIds.includes(person.id))
        .filter((person) => `${person.name} ${person.org}`.toLowerCase().includes(query.trim().toLowerCase()))
        .slice(0, MAX_RESULTS)
    : [];

  const add = (person: Person) => {
    onAdd(person);
    setAdding(false);
    setQuery("");
  };

  if (!adding)
    return (
      <button type="button" className="button button--small button--quiet" onClick={() => setAdding(true)}>
        {addLabel}
      </button>
    );

  return (
    <div className="met-add">
      {suggestions.length > 0 && (
        <>
          <p className="group-label">From the calendar</p>
          <div className="met-add__options">
            {suggestions.map((person) => (
              <button key={person.id} type="button" className="button button--small button--quiet" onClick={() => add(person)}>
                {person.name}
              </button>
            ))}
          </div>
        </>
      )}
      <div className="field">
        <label htmlFor={`${id}-search`}>Search people</label>
        <input id={`${id}-search`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name or company" autoComplete="off" autoFocus />
      </div>
      {matches.length > 0 && (
        <ul className="met-add__results">
          {matches.map((person) => (
            <li key={person.id}>
              <button type="button" className="met-add__result" onClick={() => add(person)}>
                {person.name} <span className="muted">{person.org}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {query.trim() && matches.length === 0 && <p className="muted">No one matches.</p>}
      <button type="button" className="text-button" onClick={() => setAdding(false)}>
        Cancel
      </button>
    </div>
  );
}
