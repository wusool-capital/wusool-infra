import { useParams, useSearchParams } from "react-router";
import { useRouteAction } from "../ui/toast";

/** Posts an intent to the Deal view route action. */
export function useDealAction() {
  const { dealId } = useParams();
  return useRouteAction(`/deals/${dealId}`);
}

/**
 * The one open drawer lives in the URL as ?panel=kind:id, so a link (or a Slack alert)
 * can open it directly and Back closes it.
 */
export function usePanel() {
  const [params, setParams] = useSearchParams();
  const update = (value: string | null) =>
    setParams(
      (next) => {
        if (value) next.set("panel", value);
        else next.delete("panel");
        return next;
      },
      { preventScrollReset: true },
    );
  return { panel: params.get("panel") ?? "", openPanel: (value: string) => update(value), closePanel: () => update(null) };
}
