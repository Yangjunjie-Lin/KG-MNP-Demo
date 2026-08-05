import { BusinessRoleNode } from "./BusinessRoleNode";
import type { VisualProjection } from "../../unified-graph/graphTypes";

interface ExtensionNodeProps {
  node: VisualProjection;
  selected: boolean;
  opacity: number;
  onSelect: (projectionId: string) => void;
}

export function ExtensionNode(props: ExtensionNodeProps) {
  return <BusinessRoleNode {...props} />;
}
