import React, { useEffect, useLayoutEffect, useState, useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';
import { createController } from './controller';
import { createOptions as desktopOptions } from './behavior/desktop';
import { createOptions as mobileOptions } from './behavior/mobile';
import CrosswordView from './CrosswordView';
import MobileView from './MobileView';

const mobile = window.location.pathname.match(/\/mobile\/([^/]+)\/([^/]+)/);
function App() {
  const [controller] = useState(() => createController(mobile ? mobileOptions : desktopOptions, mobile ? { room: mobile[1], role: mobile[2] } : {}));
  useSyncExternalStore(controller.subscribe, controller.snapshot);
  useLayoutEffect(() => controller.flush());
  useEffect(() => {
    if (mobile) {
      document.title = 'Crossword Mobile';
      /** @type {HTMLMetaElement} */ (document.querySelector('meta[name="viewport"]')).content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
    }
    controller.start();
    return () => controller.dispose();
  }, [controller]);
  return mobile ? <MobileView app={controller.app} /> : <CrosswordView app={controller.app} />;
}
createRoot(document.getElementById('react-root')).render(<App />);
