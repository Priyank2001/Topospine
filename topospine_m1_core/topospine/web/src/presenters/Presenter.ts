/**
 * Base of every presenter: owns its subscriptions and coalesces model changes.
 *
 * Models notify synchronously, and one user action can change several of them (opening a
 * dataset resets the thresholds and publishes the data). `invalidate()` therefore schedules a
 * single `present()` on the microtask queue: it runs after the action finishes and before the
 * browser paints, and sees one consistent state.
 *
 * A presenter takes ownership of its view and disposes it.
 */

export interface Disposable {
  dispose(): void;
}

export abstract class Presenter implements Disposable {
  private readonly subscriptions: (() => void)[] = [];
  private scheduled = false;
  private disposed = false;

  constructor(private readonly ownedView: Disposable) {}

  /** Keep these unsubscribe functions until dispose(). */
  protected listen(...unsubscribe: (() => void)[]): void {
    this.subscriptions.push(...unsubscribe);
  }

  /** Ask for a present() once the current action has finished. */
  protected invalidate(): void {
    if (this.scheduled || this.disposed) return;
    this.scheduled = true;
    queueMicrotask(() => {
      this.scheduled = false;
      if (!this.disposed) this.present();
    });
  }

  /** Map the current model state to a view model and hand it to the view. */
  protected abstract present(): void;

  dispose(): void {
    this.disposed = true;
    this.subscriptions.forEach((unsubscribe) => unsubscribe());
    this.subscriptions.length = 0;
    this.ownedView.dispose();
  }
}
