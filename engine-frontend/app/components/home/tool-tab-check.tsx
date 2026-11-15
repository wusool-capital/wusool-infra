import { useState } from "react";
import type { ToolTabAnswer } from "../../demo/types";
import { formatDate } from "../../lib/format";
import { useHomeAction } from "./home-context";

// The PRD's tool-tab test: did the user need another tool today?
const TOOLS = ["Attio", "Notion", "Slack", "Gmail"];

export function ToolTabCheck({ answer }: { answer: ToolTabAnswer | null }) {
  const act = useHomeAction();
  const [choosing, setChoosing] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);

  const save = (tools: string[]) => act({ intent: "tool-tab", tools: JSON.stringify(tools) }, "End of day answer saved.");

  return (
    <section className="card home__desktop-only" aria-labelledby="tooltab-title">
      <div className="card__head">
        <h2 id="tooltab-title" className="section-title">End of day check</h2>
      </div>
      {answer ? (
        <p>
          Saved for {formatDate(answer.date)}: {answer.tools.length ? `you opened ${answer.tools.join(", ")}.` : "no other tool needed."}
        </p>
      ) : (
        <>
          <p>Did you open Attio, Notion or Slack today, or Gmail for mail that needed action?</p>
          {!choosing ? (
            <div className="button-row">
              <button type="button" className="button button--small" onClick={() => save([])}>No</button>
              <button type="button" className="button button--small button--quiet" onClick={() => setChoosing(true)}>Yes</button>
            </div>
          ) : (
            <>
              <div className="button-row" role="group" aria-label="Tools you opened">
                {TOOLS.map((tool) => (
                  <button
                    key={tool}
                    type="button"
                    className="toggle"
                    aria-pressed={picked.includes(tool)}
                    onClick={() => setPicked(picked.includes(tool) ? picked.filter((t) => t !== tool) : [...picked, tool])}
                  >
                    {tool}
                  </button>
                ))}
              </div>
              <div className="button-row">
                <button type="button" className="button button--small" disabled={picked.length === 0} onClick={() => save(picked)}>Save</button>
                <button type="button" className="text-button" onClick={() => setChoosing(false)}>Cancel</button>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
