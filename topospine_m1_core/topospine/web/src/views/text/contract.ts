/** A single line of text (status message, dataset description). */

export interface ITextView {
  render(text: string): void;
  dispose(): void;
}
