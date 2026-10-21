#!/usr/bin/env bash
# Read-only diagnostics: run from your normal SSH terminal without sudo.
# This script does not start/stop containers or change permissions/configuration.
set -u

run_check() {
    printf '\n---'
    printf ' %q' "$@"
    printf ' ---\n'
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'SKIPPED: command unavailable: %s\n' "$1"
        return 0
    fi
    local result
    if command -v timeout >/dev/null 2>&1; then
        timeout 20s "$@" 2>&1
        result=$?
    else
        "$@" 2>&1
        result=$?
    fi
    printf '[exit status: %s]\n' "$result"
    return 0
}

printf 'Task tracker Docker access diagnostics\n'
printf 'Read-only; run without sudo in your normal SSH terminal.\n'
printf 'Some failed/skipped checks are expected; please share the complete output.\n'
printf 'Working directory: %s\n' "$PWD"
printf 'DOCKER_HOST=%s\n' "${DOCKER_HOST:-<unset>}"
printf 'DOCKER_CONTEXT=%s\n' "${DOCKER_CONTEXT:-<unset>}"

run_check date -u '+%Y-%m-%dT%H:%M:%SZ'
run_check id
run_check uname -srmo
run_check stat -Lc '%A %a %U:%G %u:%g %n' /var/run/docker.sock
run_check readlink -f /var/run/docker.sock
run_check namei -l /var/run/docker.sock
run_check getfacl -p /var/run/docker.sock

# Namespace mappings help distinguish the host view from a sandbox's view.
run_check cat /proc/self/uid_map /proc/self/gid_map
run_check docker context show
run_check docker context inspect --format '{{.Endpoints.docker.Host}}'
run_check docker version
run_check docker info --format '{{json .Driver}} {{json .ServerVersion}}'

# Check both system-managed and rootless Docker; either may legitimately fail.
run_check systemctl is-active docker.service docker.socket
run_check systemctl --user is-active docker.service

printf '\nDiagnostics complete. No configuration or container state was changed.\n'
