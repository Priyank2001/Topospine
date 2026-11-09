/** One line of text in an element; optionally hidden while empty (the status overlay). */

import { ITextView } from "./contract";

export class TextView implements ITextView {
  constructor(
    private readonly el: HTMLElement,
    private readonly hideWhenEmpty = false,
  ) {}

  render(text: string): void {
    this.el.textContent = text;
    if (this.hideWhenEmpty) this.el.hidden = !text;
  }

  dispose(): void {}
}
