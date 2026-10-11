import { useState } from 'react';
import { type User } from './api';
import { Tasks } from './Tasks';
import { Timesheet } from './Timesheet';

export function WorkArea({ user, version, onError }: { user: User; version: number; onError: (error: unknown) => void }) {
  const [request, setRequest] = useState<{ id: string; nonce: number } | null>(null);
  const [opened, setOpened] = useState<{ id: string; nonce: number } | null>(null);
  const [changes, setChanges] = useState(0);
  return <div className="work-area">
    <Tasks user={user} version={version} onError={onError} onRecord={id => setRequest({ id, nonce: Date.now() })} openRequest={opened} onChanged={() => setChanges(value => value + 1)} />
    <Timesheet user={user} version={version + changes} request={request} onError={onError} openTask={id => setOpened({ id, nonce: Date.now() })} />
  </div>;
}
