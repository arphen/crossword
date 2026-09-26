import React, {
  useEffect,
  useLayoutEffect,
  useState,
  useSyncExternalStore,
} from 'react';
import { createController } from '../controller';
import { createOptions } from '../behavior/desktop';
import CrosswordView from '../CrosswordView';
import { catalog } from './episteme';

export function futureOptions(dependencies, weekday) {
  const options = /** @type {Record<string, any>} */ (
    createOptions(dependencies)
  );
  // Only startup preferences differ. Every grid, clue, selection, keyboard,
  // check/reveal and multiplayer handler is the daily solver's own handler.
  options.watch.selectedWeekday = () => {};
  options.computed.weekdayOptions = () =>
    catalog.days.map((day) => ({ value: day.id, label: day.label }));
  options.created = /** @this {Record<string, any>} */ function () {
    this.selectedWeekday = weekday;
    window.addEventListener('online', this.handleOnlineStatus);
    window.addEventListener('offline', this.handleOnlineStatus);
    this.isOffline = !navigator.onLine;
    this.updateCachedCounts();
    this.loadCrossword(weekday);
    document.addEventListener('click', this.handleDocumentClick);
    dependencies.socket.on('cell_updated', (data) => {
      if (
        this.grid?.[data.row] &&
        typeof this.grid[data.row][data.col] !== 'undefined'
      )
        this.$set(this.grid[data.row], data.col, data.value);
    });
  };
  return options;
}

export default function FutureSolver({ weekday }) {
  const [controller] = useState(() =>
    createController((deps) => futureOptions(deps, weekday)),
  );
  useSyncExternalStore(controller.subscribe, controller.snapshot);
  useLayoutEffect(() => controller.flush());
  useEffect(() => {
    controller.start();
    return () => controller.dispose();
  }, [controller]);
  return <CrosswordView app={controller.app} />;
}
