// @ts-nocheck

/**
 * @description RFC 9457 problem details; `code` is stable and meant for the Engine to branch on.
 * @type object
 */
export type ProblemDetail = {
  code: string;
  detail: string;
  errors?: string[];
  landed?: string[];
  status: number;
  title: string;
  /**
   * @default 'about:blank'
   * @type string | undefined
   */
  type?: string;
};
