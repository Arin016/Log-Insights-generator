#!/bin/sh
# Foreground, dedicated synthetic service. Stop with Ctrl-C / terminate this process.
set -eu
cd "$(dirname "$0")/.."
ff_root=$(pwd)
ff_archive=elasticsearch-8.13.4-darwin-aarch64.tar.gz
if [ ! -x .runtime/elasticsearch-8.13.4/bin/elasticsearch ]; then
  mkdir -p .runtime
  curl -fsSL "https://artifacts.elastic.co/downloads/elasticsearch/$ff_archive" -o ".runtime/$ff_archive"
  curl -fsSL "https://artifacts.elastic.co/downloads/elasticsearch/$ff_archive.sha512" -o ".runtime/$ff_archive.sha512"
  (cd .runtime && shasum -a 512 -c "$ff_archive.sha512" && tar -xzf "$ff_archive")
fi
export ES_JAVA_OPTS='-Xms512m -Xmx512m'
exec .runtime/elasticsearch-8.13.4/bin/elasticsearch \
  -Ecluster.name=ff-insights-synthetic -Enode.name=ff-v2-local \
  -Enetwork.host=127.0.0.1 -Ehttp.port=19200 -Etransport.port=19300 \
  -Ediscovery.type=single-node -Expack.security.enabled=false -Expack.ml.enabled=false \
  -Eingest.geoip.downloader.enabled=false \
  -Ecluster.routing.allocation.disk.watermark.low=5gb \
  -Ecluster.routing.allocation.disk.watermark.high=3gb \
  -Ecluster.routing.allocation.disk.watermark.flood_stage=2gb \
  "-Epath.data=$ff_root/.runtime/es-data" "-Epath.logs=$ff_root/.runtime/es-logs"
