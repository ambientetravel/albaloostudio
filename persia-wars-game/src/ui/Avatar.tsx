import { avatarAt } from './avatars';
import { UnitGlyph } from './UnitGlyph';

export function Avatar({ index, size = 56 }: { index: number; size?: number }) {
  const a = avatarAt(index);
  return (
    <span
      className="avatar"
      style={
        {
          width: size,
          height: size,
          background: a.body,
          borderColor: a.ring,
          '--glyph-body': a.ring,
          '--glyph-trim': '#ffffff',
          '--glyph-blade': '#ffffff',
        } as React.CSSProperties
      }
    >
      <UnitGlyph kind={a.silhouette} size={size * 0.66} />
    </span>
  );
}
