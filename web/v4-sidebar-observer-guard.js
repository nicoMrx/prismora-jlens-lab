(() => {
  'use strict';

  const NativeMutationObserver = window.MutationObserver;
  if (!NativeMutationObserver || window.__prismoraSidebarObserverGuard) return;

  class PrismoraMutationObserver {
    constructor(callback) {
      this.callback = callback;
      this.sidebarGuarded = false;
      this.suppressUntilNextFrame = false;
      this.native = new NativeMutationObserver((records) => {
        if (!this.sidebarGuarded) {
          this.callback(records, this);
          return;
        }
        if (this.suppressUntilNextFrame) return;
        this.suppressUntilNextFrame = true;
        try {
          this.callback(records, this);
        } finally {
          requestAnimationFrame(() => {
            this.suppressUntilNextFrame = false;
          });
        }
      });
    }

    observe(target, options) {
      if (target?.id === 'sidebar-nav' && options?.childList) {
        this.sidebarGuarded = true;
      }
      return this.native.observe(target, options);
    }

    disconnect() {
      return this.native.disconnect();
    }

    takeRecords() {
      return this.native.takeRecords();
    }
  }

  window.MutationObserver = PrismoraMutationObserver;
  window.__prismoraSidebarObserverGuard = true;
})();
