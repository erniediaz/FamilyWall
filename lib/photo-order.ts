// Preserve the current slideshow order across polling; shuffle newly added photos.
export function photoOrder(incoming: string[], previous: string[] = [], random = Math.random): string[] {
  const available = new Set(incoming);
  const kept = previous.filter(photo => available.has(photo));
  const known = new Set(kept);
  const added = [...available].filter(photo => !known.has(photo));
  for (let i = added.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [added[i], added[j]] = [added[j], added[i]];
  }
  return [...kept, ...added];
}
