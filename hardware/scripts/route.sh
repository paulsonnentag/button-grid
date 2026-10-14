#!/usr/bin/env bash
# Autoroute the placed board with Freerouting, then add GND pours.
#   FREEROUTING_JAR=/path/freerouting-2.5.0-executable.jar hardware/scripts/route.sh
# Needs Java 25+ (Freerouting 2.5). Download the jar from Maven Central:
#   https://repo1.maven.org/maven2/app/freerouting/freerouting/2.5.0/
set -euo pipefail
cd "$(dirname "$0")/../.."
K=hardware/scripts/kicad.sh
JAVA="${JAVA:-java}"
JAR="${FREEROUTING_JAR:?set FREEROUTING_JAR to the freerouting executable jar}"
PASSES="${PASSES:-60}"
$K python3 hardware/gen/dsn_export.py hardware/button-grid.kicad_pcb hardware/button-grid.dsn
"$JAVA" -jar "$JAR" -de hardware/button-grid.dsn -do hardware/button-grid.ses -mp "$PASSES" \
  --gui.enabled=false --usage_and_diagnostic_data.disable_analytics=true \
  --router.optimizer.enabled=false
$K python3 hardware/gen/finish_pcb.py hardware/button-grid.kicad_pcb hardware/button-grid.ses
