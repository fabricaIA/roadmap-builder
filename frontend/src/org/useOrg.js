import { useContext } from "react";
import { OrgContext } from "./context";

export function useOrg() {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrg deve ser usado dentro de <OrgProvider>");
  return ctx;
}
