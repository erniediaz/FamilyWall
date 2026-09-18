export type Highlight = {
  id: string; category: 'history' | 'observances' | 'quotes' | 'sports';
  text: string; detail: string; source: string; url: string; cached?: boolean;
};

function shuffle<T>(values: T[], random: () => number): T[] {
  const result = [...values];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

// Each category gets a turn. Shorter lists cycle while longer lists finish,
// so a weekend full of scores never becomes a long sports-only segment.
export function highlightOrder(items: Highlight[], random = Math.random): string[] {
  const categories = shuffle(['history', 'observances', 'quotes', 'sports'], random);
  const groups = categories.map(category => shuffle(
    [...new Map(items.filter(row => row.category === category).map(row => [row.id, row])).values()], random)
  ).filter(group => group.length);
  const count = Math.max(0, ...groups.map(group => group.length));
  return Array.from({length: count}, (_, index) => groups.map(group => group[index % group.length].id)).flat();
}

export const HIGHLIGHT_INTERVAL = 15000;
