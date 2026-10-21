export interface TimeRow {
  id: string; session: string; kind: 'task' | 'break'; task: string | null;
  task_label: string; task_readable: boolean; started_at: string; ended_at: string | null; duration_seconds: number;
}
export interface TimeSession {
  id: string; state: 'active' | 'unfinished' | 'closed'; rows: TimeRow[];
  ended_at: string | null; continues_before: boolean; continues_after: boolean;
}
export interface Day {
  date: string; revision: number; time_zone: string; work_seconds: number; unfinished: boolean; sessions: TimeSession[];
}
export interface SheetContext {
  today: string; time_zone: string; revision: number;
  open_sessions: { id: string; state: string; date: string; tail: TimeRow }[];
}
export interface PickerTask { id: string; title: string; project: string; status: string }
export interface PickerStatus { id: string; name: string; final: boolean }

// datetime-local fields represent the shared working zone, independent of the browser zone.
export function localStamp(value: string, zone: string): string {
  const parts = new Intl.DateTimeFormat('sv-SE', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(value));
  const part = (key: string) => parts.find(p => p.type === key)?.value;
  const fraction = value.match(/\.\d+/)?.[0].slice(0, 4) ?? '';
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}:${part('second')}${fraction}`;
}
export function instant(value: string, zone: string): string | null {
  if (!value) return null;
  const wall = Date.parse(`${value}Z`);
  if (!Number.isFinite(wall)) return null;
  let result = wall;
  for (let i = 0; i < 3; i++) {
    const rendered = Date.parse(`${localStamp(new Date(result).toISOString(), zone)}Z`);
    result += wall - rendered;
  }
  return new Date(result).toISOString();
}
export function clock(value: string | null, zone: string): string {
  if (!value) return 'Unfinished';
  return localStamp(value, zone).slice(11, 16);
}
export function hours(seconds: number): string {
  return `${Number((seconds / 3600).toFixed(4))} h`;
}
export function nextDate(day: string): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) + 86400000).toISOString().slice(0, 10);
}
