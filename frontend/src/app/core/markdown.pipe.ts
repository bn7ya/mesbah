import { Pipe, PipeTransform } from '@angular/core';
import { marked } from 'marked';

/**
 * Render Markdown → HTML for chat bubbles. Returns a plain string so Angular's
 * built-in `[innerHTML]` sanitizer strips anything unsafe while keeping the
 * structure the self-correction prompt produces (headings, tables, lists, code).
 *
 * `gfm` enables GitHub-flavoured tables; `breaks` turns single newlines into
 * `<br>` (chat replies are written line-by-line, not in Markdown paragraphs).
 */
@Pipe({ name: 'markdown', standalone: true })
export class MarkdownPipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    if (!value) return '';
    return marked.parse(value, { async: false, gfm: true, breaks: true }) as string;
  }
}
