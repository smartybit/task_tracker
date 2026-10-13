import { writeFileSync } from 'node:fs';
import { instanceConfig } from '../instance-config.ts';

writeFileSync('.instance-build.json', JSON.stringify(instanceConfig(process.env)) + '\n');
