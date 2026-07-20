(() => {
  'use strict';

  const key = 'prismora.v4.session';
  const nativeRemoveItem = Storage.prototype.removeItem;
  let protectFirstStartupRemoval = sessionStorage.getItem(key) !== null;

  Storage.prototype.removeItem = function removeItem(name) {
    if (this === sessionStorage && name === key && protectFirstStartupRemoval) {
      protectFirstStartupRemoval = false;
      return;
    }
    return nativeRemoveItem.call(this, name);
  };

  window.setTimeout(() => {
    Storage.prototype.removeItem = nativeRemoveItem;
  }, 10000);
})();
