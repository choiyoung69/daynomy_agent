#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export XDG_CONFIG_HOME="$TASK_ROOT/.local/flutter-config"
export PUB_CACHE="$TASK_ROOT/.local/flutter-pub-cache"
export GRADLE_USER_HOME="$TASK_ROOT/.local/flutter-gradle"
export ANDROID_USER_HOME="$TASK_ROOT/.local/flutter-android-user"
export ANALYZER_STATE_LOCATION_OVERRIDE="$TASK_ROOT/.local/flutter-dart-server"
if [[ -d "$TASK_ROOT/.local/flutter-android-sdk" ]]; then
  export ANDROID_HOME="$TASK_ROOT/.local/flutter-android-sdk"
  export ANDROID_SDK_ROOT="$ANDROID_HOME"
fi
export FLUTTER_SUPPRESS_ANALYTICS=true
export DASH__SUPPRESS_ANALYTICS=true
export CI=true
exec "$TASK_ROOT/.local/flutter-sdk/flutter/bin/flutter" "$@"
