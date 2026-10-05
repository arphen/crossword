// territory.js — publish the ranks of the items showing in the four corners of
// the screen, so the ground's light is exactly the hue of what is on screen.
// Call once per page; it re-publishes (rAF-throttled) whenever a lane scrolls.
// Each item must carry its rank as an inline custom property: style="--rank:0.43".

function edgeRanks(lane) {
  const box = lane.getBoundingClientRect();
  const visible = [...lane.querySelectorAll(':scope > li')].filter((li) => {
    const r = li.getBoundingClientRect();
    return r.bottom > box.top && r.top < box.bottom;
  });
  if (!visible.length) return null;
  const rank = (li) => parseFloat(li.style.getPropertyValue('--rank')) || 0;
  return { top: rank(visible[0]), bottom: rank(visible[visible.length - 1]) };
}

export function publishTerritory(ground, laneA, laneB) {
  let queued = false;
  const publish = () => {
    queued = false;
    const a = edgeRanks(laneA);
    const b = edgeRanks(laneB);
    if (a) { ground.style.setProperty('--ta-top', a.top); ground.style.setProperty('--ta-bottom', a.bottom); }
    if (b) { ground.style.setProperty('--tb-top', b.top); ground.style.setProperty('--tb-bottom', b.bottom); }
  };
  const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(publish); } };
  laneA.addEventListener('scroll', schedule, { passive: true });
  laneB.addEventListener('scroll', schedule, { passive: true });
  addEventListener('resize', schedule);
  schedule();
  return () => {
    laneA.removeEventListener('scroll', schedule);
    laneB.removeEventListener('scroll', schedule);
    removeEventListener('resize', schedule);
  };
}
