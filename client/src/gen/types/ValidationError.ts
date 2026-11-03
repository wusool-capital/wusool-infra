// @ts-nocheck

export type ValidationError = {
  ctx?: object;
  input?: unknown;
  loc: (string | number)[];
  msg: string;
  type: string;
};
