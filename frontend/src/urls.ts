import { buildApiUrl } from "../instance-config";

declare const __INSTANCE_ID__: string;
export const appBasePath = import.meta.env.BASE_URL;
export const instanceId = __INSTANCE_ID__;
export const apiUrl = (endpoint: string) => buildApiUrl(appBasePath, endpoint);
