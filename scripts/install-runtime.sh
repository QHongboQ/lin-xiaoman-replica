#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/AstrBot/data" >&2
  exit 2
fi

target="$(realpath -m "$1")"
mkdir -p "$target/plugins" "$target/config"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

copy_plugin() {
  local source="$1"
  local name
  name="$(basename "$source")"
  if [[ -e "$target/plugins/$name" ]]; then
    echo "Keeping existing plugin: $name"
    return
  fi
  cp -a "$source" "$target/plugins/$name"
  echo "Installed plugin source: $name"
}

copy_plugin "$repo_root/plugins/astrbot_plugin_xiaoman_personal_interface"
for source in "$repo_root"/plugins/bundled/*; do
  [[ -d "$source" ]] || continue
  copy_plugin "$source"
done

for source in "$repo_root"/configs/runtime/*.example.json; do
  [[ -f "$source" ]] || continue
  name="$(basename "$source" .example.json).json"
  if [[ "$name" == "astrbot_cmd_config.json" ]]; then
    destination="$target/cmd_config.json"
  else
    destination="$target/config/$name"
  fi
  if [[ -e "$destination" ]]; then
    echo "Keeping existing config: $name"
    continue
  fi
  cp "$source" "$destination"
  echo "Installed config template: $name"
done

echo "Done. Configure credentials, provider IDs, admin accounts, and chat targets in AstrBot before enabling plugins."
