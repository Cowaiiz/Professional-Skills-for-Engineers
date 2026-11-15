// These are synthetic observations, including whether enough of the actor is visible.
const upright = (id, x, y = 192, visible = true) => ({id, x, y, visible, pose: 'upright'});
const floor = (actor) => ({...actor, pose: 'floor'});
const walk = (id, t, delay, target, y) => upright(id, Math.min(target, 105 + Math.max(0, t - delay) * 88), y);
const fall = (actor, t) => t < 1.5 ? actor : floor(actor);

export const scenes = {
  entry: ['01 · One person enters', 3, t => [walk('A', t, 0, 310, 192)]],
  two_entries: ['02 · Two people enter', 4, t => [walk('A', t, 0, 326, 178), walk('B', t, 1, 268, 205)]],
  center_fall: ['03 · Fall in the center', 5.5, t => [fall(upright('A', 292, 201), t)]],
  door_fall: ['04 · Fall near the door', 5.5, t => [fall(upright('A', 148, 193), t)]],
  sofa_fall: ['05 · Fall beside the sofa', 5.5, t => [fall(upright('A', 498, 218), t)]],
  crowded_fall: ['06 · Two people, only B falls', 5.5, t => [upright('A', 252, 176), fall(upright('B', 378, 214), t)]],
  partial_entry: ['07 · Partial person at the frame edge', 3, () => [upright('A', -3, 193, false)]],
  partial_fall: ['08 · Fall partly outside the frame', 5.5, t => [fall(upright('A', 549, 212, false), t)]],
  quick_recovery: ['09 · Down briefly, then stands up', 5, t => {
    const actor = upright('A', 298, 206);
    return [t >= 1.5 && t < 3 ? floor(actor) : actor];
  }],
  empty: ['10 · Empty room', 2, () => []],
};
