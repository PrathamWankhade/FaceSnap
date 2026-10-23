export interface FitTransform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

/**
 * Map a source frame onto the box it is displayed in.
 *
 * `contain` matches CSS `object-fit: contain` (letterboxed, whole frame visible),
 * `cover` matches `object-fit: cover` (frame cropped to fill).
 */
export function fitFrame(
  frameWidth: number,
  frameHeight: number,
  boxWidth: number,
  boxHeight: number,
  mode: 'contain' | 'cover' = 'contain'
): FitTransform {
  if (!frameWidth || !frameHeight || !boxWidth || !boxHeight) {
    return { scale: 0, offsetX: 0, offsetY: 0 };
  }
  const scaleX = boxWidth / frameWidth;
  const scaleY = boxHeight / frameHeight;
  const scale = mode === 'contain' ? Math.min(scaleX, scaleY) : Math.max(scaleX, scaleY);
  return {
    scale,
    offsetX: (boxWidth - frameWidth * scale) / 2,
    offsetY: (boxHeight - frameHeight * scale) / 2,
  };
}
