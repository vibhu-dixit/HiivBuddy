export type Turn = {
  kind: "primary" | "interjection";
  agent: string;
  name: string;
  turn: number;
  text: string;
  reasoning?: string;
  targetAgent?: string;
  targetName?: string;
};
