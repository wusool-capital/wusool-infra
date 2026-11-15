import type { Block } from "@blocknote/core";

// Generic so editors with a custom block schema (the notes editor) fit too.
interface MarkdownCapableEditor<B = Block> {
  blocksToMarkdownLossy: (blocks: B[]) => Promise<string>;
}

interface MarkdownConversionOptions {
  source: string;
  fallbackMarkdown?: string;
}

interface MarkdownConversionResult {
  markdown?: string;
  ok: boolean;
}

export async function blocksToMarkdownSafely<B = Block>(
  editor: MarkdownCapableEditor<B>,
  blocks: B[],
  options: MarkdownConversionOptions,
): Promise<MarkdownConversionResult> {
  try {
    return {
      markdown: await editor.blocksToMarkdownLossy(blocks),
      ok: true,
    };
  } catch (error) {
    console.error("Failed to convert BlockNote blocks to markdown", {
      source: options.source,
      blocksCount: blocks.length,
      error,
    });

    return {
      markdown: options.fallbackMarkdown,
      ok: false,
    };
  }
}
