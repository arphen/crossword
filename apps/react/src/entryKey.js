/** The identity of one clue: its lane and number, `across-17`. Two clues can
 *  share their wording ("See 5-Across"), so the wording never names a clue.
 *  Same shape as the session journal's legacy entry ids. */
export function entryKey(entry) {
  return `${entry?.direction}-${entry?.clue_number}`;
}
